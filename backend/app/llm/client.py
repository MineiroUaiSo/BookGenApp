"""Cliente Anthropic: credenciais, chamadas em streaming com saída estruturada."""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Optional

log = logging.getLogger("medlens.llm")

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS_DESCRIBE = 32000
MAX_TOKENS_ANALYZE = 48000


def model_name() -> str:
    return os.environ.get("MEDLENS_MODEL") or DEFAULT_MODEL


def effort() -> str:
    return os.environ.get("MEDLENS_EFFORT") or "high"


def credentials_present() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def ai_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return credentials_present()


def make_client():
    import anthropic

    return anthropic.Anthropic()


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

    Lança LLMRefusal / LLMTruncated; erros da API propagam como anthropic.APIError."""
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


def parse_json(text: str) -> dict:
    return json.loads(text)
