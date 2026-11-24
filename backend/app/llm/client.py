"""Cliente Anthropic: credenciais, chamadas em streaming com saída estruturada."""
from __future__ import annotations

import base64
import json
import logging
import os
import random
import time
from typing import Any, Callable, Optional

log = logging.getLogger("medlens.llm")

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS_DESCRIBE = 32000
MAX_TOKENS_ANALYZE = 48000


def effort() -> str:
    return os.environ.get("MEDLENS_EFFORT") or "high"


def credentials_present() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


OR_BASE_URL = "https://openrouter.ai/api/v1"
OR_DEFAULT_MODEL = "anthropic/claude-sonnet-5.5"  # id com entrada de imagem (GET /api/v1/models)
OR_TIMEOUT_S = 600.0


def or_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


def or_model() -> str:
    return os.environ.get("MEDLENS_OR_MODEL") or OR_DEFAULT_MODEL


def anthropic_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return credentials_present()


def openrouter_available() -> bool:
    if not or_key():
        return False
    try:
        import httpx  # noqa: F401
    except Exception:
        return False
    return True


def provider() -> Optional[str]:
    """'anthropic' tem prioridade; 'openrouter' é o fallback; None se nenhum."""
    if anthropic_available():
        return "anthropic"
    if openrouter_available():
        return "openrouter"
    return None


def ai_available() -> bool:
    return provider() is not None


def model_name() -> str:  # noqa: F811  (reflete o provedor ativo)
    if provider() == "openrouter":
        return or_model()
    return os.environ.get("MEDLENS_MODEL") or DEFAULT_MODEL


class LLMProviderError(Exception):
    """Erro de provedor com mensagem legível ao usuário (sem segredos).

    status: código HTTP quando há (None = timeout/conexão); retry_after: segundos pedidos pelo provedor."""

    def __init__(self, message: str = "", status: Optional[int] = None, retry_after: Optional[float] = None,
                 transient: bool = False):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        self.transient = transient   # timeout / falha de conexão


class OpenRouterClient:
    """Cliente mínimo OpenAI-compatível (chat/completions) via httpx."""

    def __init__(self, api_key: str, base_url: str = OR_BASE_URL, timeout: float = OR_TIMEOUT_S):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def post(self, payload: dict) -> dict:
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   "X-Title": "MedLens"}
        try:
            resp = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=headers,
                              timeout=self.timeout)
        except httpx.TimeoutException:
            raise LLMProviderError("Tempo esgotado ao chamar o OpenRouter.", transient=True)
        except httpx.HTTPError:
            raise LLMProviderError("Falha de conexão com o OpenRouter.", transient=True)
        if resp.status_code != 200:
            raise LLMProviderError(or_status_message(resp.status_code), status=resp.status_code,
                                   retry_after=parse_retry_after(resp.headers.get("retry-after")))
        try:
            return resp.json()
        except ValueError:
            raise LLMProviderError("Resposta inválida do OpenRouter.")


def parse_retry_after(value: Any) -> Optional[float]:
    """Retry-After em segundos (a forma data HTTP é ignorada)."""
    try:
        v = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def or_status_message(code: int) -> str:
    if code == 402:
        return "OpenRouter: créditos insuficientes ou limite da chave atingido (402). Recarregue ou aumente o limite."
    if code == 429:
        return "OpenRouter: limite de requisições atingido (429); tente novamente em instantes."
    if code in (401, 403):
        return f"OpenRouter: credenciais inválidas ou sem permissão ({code})."
    return f"Erro do OpenRouter ({code})."


def make_client():
    if provider() == "openrouter":
        return OpenRouterClient(or_key())
    import anthropic

    # max_retries=0: a política de retry/failover é nossa (run_resilient), não a do SDK.
    return anthropic.Anthropic(max_retries=0)


def image_block(png: bytes, media_type: str = "image/png") -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(png).decode()}}


def _request_kwargs(system: list[dict], messages: list[dict], max_tokens: int,
                    schema: Optional[dict]) -> dict:
    output_config: dict[str, Any] = {"effort": effort()}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    kw: dict[str, Any] = dict(
        model=model_name(),
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config=output_config,
        system=system,
        messages=messages,
    )
    if os.environ.get("MEDLENS_FALLBACKS", "1") != "0":
        # Refusal fallback server-side (Opus 5.5): reexecuta no modelo de fallback se houver recusa.
        kw["betas"] = [FALLBACK_BETA]
        kw["fallbacks"] = "default"
    return kw


class LLMRefusal(Exception):
    pass


class LLMTruncated(Exception):
    pass


def run(client, system: list[dict], messages: list[dict], max_tokens: int,
        schema: Optional[dict] = None) -> tuple[str, Any]:
    """Executa uma requisição em streaming e devolve (texto, mensagem final).

    Lança LLMRefusal / LLMTruncated; erros da API propagam como anthropic.APIError
    (ou LLMProviderError no OpenRouter)."""
    if isinstance(client, OpenRouterClient):
        return run_openrouter(client, system, messages, max_tokens, schema)
    kw = _request_kwargs(system, messages, max_tokens, schema)
    with client.beta.messages.stream(**kw) as stream:
        final = stream.get_final_message()
    if final.stop_reason == "refusal":
        det = getattr(final, "stop_details", None)
        raise LLMRefusal(getattr(det, "category", None) or "refusal")
    if final.stop_reason == "max_tokens":
        raise LLMTruncated("max_tokens")
    text = "".join(b.text for b in final.content if getattr(b, "type", None) == "text")
    u = getattr(final, "usage", None)
    if u is not None:
        log.info("llm usage in=%s out=%s cache_read=%s cache_write=%s", getattr(u, "input_tokens", None),
                 getattr(u, "output_tokens", None), getattr(u, "cache_read_input_tokens", None),
                 getattr(u, "cache_creation_input_tokens", None))
    return text, final


def _or_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    parts = []
    for b in content:
        if b.get("type") == "image":
            s = b["source"]
            parts.append({"type": "image_url",
                          "image_url": {"url": f"data:{s['media_type']};base64,{s['data']}"}})
        else:
            parts.append(dict(b))
    return parts


def openrouter_payload(system: list[dict], messages: list[dict], max_tokens: int,
                       schema: Optional[dict]) -> dict:
    msgs = [{"role": "system", "content": [dict(b) for b in system]}]
    msgs += [{"role": m["role"], "content": _or_content(m["content"])} for m in messages]
    payload: dict[str, Any] = {"model": or_model(), "max_tokens": max_tokens, "messages": msgs}
    if schema is not None:
        payload["response_format"] = {"type": "json_schema",
                                      "json_schema": {"name": "medlens_report", "strict": True, "schema": schema}}
    return payload


def run_openrouter(client: OpenRouterClient, system: list[dict], messages: list[dict], max_tokens: int,
                   schema: Optional[dict] = None) -> tuple[str, Any]:
    from types import SimpleNamespace

    data = client.post(openrouter_payload(system, messages, max_tokens, schema))
    if data.get("error"):
        code = data["error"].get("code") if isinstance(data["error"], dict) else None
        raise LLMProviderError(or_status_message(code) if isinstance(code, int) else "Erro do OpenRouter.",
                               status=code if isinstance(code, int) else None)
    choices = data.get("choices") or []
    if not choices:
        raise LLMProviderError("Resposta vazia do OpenRouter.")
    ch = choices[0]
    reason = ch.get("finish_reason")
    if reason == "content_filter":
        raise LLMRefusal("content_filter")
    if reason == "length":
        raise LLMTruncated("max_tokens")
    text = (ch.get("message") or {}).get("content") or ""
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    u = data.get("usage") or {}
    log.info("llm(openrouter) usage in=%s out=%s", u.get("prompt_tokens"), u.get("completion_tokens"))
    return text, SimpleNamespace(model=data.get("model") or or_model(), stop_reason=reason)


# ---------------------------------------------------------------- retry + failover
MAX_ATTEMPTS = 2            # por provedor
BACKOFF_MIN_S, BACKOFF_MAX_S = 1.0, 4.0
RETRY_AFTER_CAP_S = 30.0    # Retry-After maior que isto: não espera, parte para o failover
_sleep: Callable[[float], None] = time.sleep
_jitter: Callable[[], float] = lambda: random.uniform(0.0, 0.5)


def classify_error(exc: BaseException) -> tuple[bool, Optional[float]]:
    """(retentável, Retry-After em s). Retentável = 429, 5xx, timeout ou falha de conexão; 4xx != 429 não."""
    if isinstance(exc, LLMProviderError):
        status = exc.status
        return (exc.transient or status == 429 or (status is not None and status >= 500)), exc.retry_after
    try:
        import anthropic
    except ImportError:
        return False, None
    if isinstance(exc, anthropic.APIStatusError):
        status = exc.status_code
        hdrs = getattr(getattr(exc, "response", None), "headers", None) or {}
        return (status == 429 or status >= 500), parse_retry_after(hdrs.get("retry-after"))
    if isinstance(exc, (anthropic.APITimeoutError, anthropic.APIConnectionError)):
        return True, None
    return False, None


def backoff_delay(retry_index: int, retry_after: Optional[float] = None) -> Optional[float]:
    """Espera antes da próxima tentativa: 1 s, 2 s... (máx 4 s) + jitter; respeita Retry-After.
    None = Retry-After acima do teto (não vale esperar neste provedor)."""
    delay = min(BACKOFF_MAX_S, BACKOFF_MIN_S * (2 ** retry_index))
    delay = min(BACKOFF_MAX_S, delay * (1 + _jitter()))
    if retry_after is not None:
        if retry_after > RETRY_AFTER_CAP_S:
            return None
        delay = max(delay, retry_after)
    return delay


def _attempt_provider(client, system, messages, max_tokens, schema) -> tuple[str, Any]:
    last: Optional[BaseException] = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return run(client, system, messages, max_tokens, schema)
        except (LLMRefusal, LLMTruncated):
            raise
        except Exception as e:
            retryable, retry_after = classify_error(e)
            if not retryable:
                raise
            last = e
            if attempt + 1 >= MAX_ATTEMPTS:
                break
            delay = backoff_delay(attempt, retry_after)
            if delay is None:
                break
            log.warning("llm retry %s/%s in %.1fs (%s)", attempt + 1, MAX_ATTEMPTS - 1, delay, type(e).__name__)
            _sleep(delay)
    assert last is not None
    raise last


def provider_of(client) -> str:
    return "openrouter" if isinstance(client, OpenRouterClient) else "anthropic"


def run_resilient(client, system: list[dict], messages: list[dict], max_tokens: int,
                  schema: Optional[dict] = None) -> tuple[str, Any, str]:
    """run() com retry (máx 2 tentativas por provedor) e failover Anthropic -> OpenRouter.

    Só 429/5xx/timeout/conexão são retentados/failover; 4xx != 429, recusa e truncamento propagam.
    Devolve (texto, mensagem final, provedor que respondeu)."""
    chain = [client]
    if not isinstance(client, OpenRouterClient) and openrouter_available():
        chain.append(OpenRouterClient(or_key()))
    last: Optional[BaseException] = None
    for i, c in enumerate(chain):
        try:
            text, final = _attempt_provider(c, system, messages, max_tokens, schema)
            return text, final, provider_of(c)
        except (LLMRefusal, LLMTruncated):
            raise
        except Exception as e:
            if not classify_error(e)[0]:
                raise
            last = e
            if i + 1 < len(chain):
                log.warning("llm failover %s -> %s (%s)", provider_of(c), provider_of(chain[i + 1]),
                            type(e).__name__)
    assert last is not None
    raise last


def parse_json(text: str) -> dict:
    return json.loads(text)
