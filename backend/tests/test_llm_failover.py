"""Retry exponencial curto e failover Anthropic -> OpenRouter (clientes stubados, sem rede)."""
import json
from contextlib import contextmanager
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app import llm
from app.llm import client as C
from tests.test_llm import GOOD, _ecg, _png
from tests.test_llm_openrouter import OK_BODY

REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _api_err(status, headers=None):
    resp = httpx.Response(status, request=REQ, headers=headers or {})
    cls = {429: anthropic.RateLimitError, 401: anthropic.AuthenticationError, 400: anthropic.BadRequestError}.get(
        status, anthropic.InternalServerError if status >= 500 else anthropic.APIStatusError)
    return cls("x", response=resp, body=None)


class ScriptedAnthropic:
    """Cada chamada a stream() consome um item: exceção (levantada) ou texto."""

    def __init__(self, script):
        self.script = list(script)
        self.n = 0
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    @contextmanager
    def _stream(self, **kw):
        self.n += 1
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        msg = SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5", stop_details=None,
                              content=[SimpleNamespace(type="text", text=item)], usage=None)
        yield SimpleNamespace(get_final_message=lambda: msg)


@pytest.fixture
def env(monkeypatch):
    sleeps = []
    monkeypatch.setattr(C, "_sleep", sleeps.append)
    monkeypatch.setattr(C, "_jitter", lambda: 0.0)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    return sleeps


def _or_mock(monkeypatch, handler):
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append(json)
        return handler(len(calls))

    monkeypatch.setattr(httpx, "post", post)
    return calls


def _ok(text):
    return httpx.Response(200, json=OK_BODY(text))


def _call(client):
    return C.run_resilient(client, [{"type": "text", "text": "s"}], [{"role": "user", "content": "q"}], 100)


def test_retry_then_success_same_provider(env):
    fake = ScriptedAnthropic([_api_err(429), "ok"])
    text, _, prov = _call(fake)
    assert (text, prov, fake.n) == ("ok", "anthropic", 2)
    assert env == [1.0]


def test_backoff_exponential_and_capped(monkeypatch):
    monkeypatch.setattr(C, "_jitter", lambda: 0.0)
    assert [C.backoff_delay(i) for i in range(4)] == [1.0, 2.0, 4.0, 4.0]
    monkeypatch.setattr(C, "_jitter", lambda: 0.5)
    assert C.backoff_delay(0) == 1.5 and C.backoff_delay(2) == 4.0


def test_jitter_default_within_bounds():
    for _ in range(50):
        assert 1.0 <= C.backoff_delay(0) <= 1.5


def test_retry_after_is_respected(env):
    fake = ScriptedAnthropic([_api_err(429, {"retry-after": "3"}), "ok"])
    _call(fake)
    assert env == [3.0]


def test_retry_after_too_long_goes_straight_to_failover(env, monkeypatch):
    fake = ScriptedAnthropic([_api_err(429, {"retry-after": "120"})])
    calls = _or_mock(monkeypatch, lambda n: _ok("via or"))
    text, _, prov = _call(fake)
    assert (text, prov, fake.n, len(calls), env) == ("via or", "openrouter", 1, 1, [])


def test_failover_after_two_attempts_on_5xx(env, monkeypatch):
    fake = ScriptedAnthropic([_api_err(503), _api_err(500)])
    calls = _or_mock(monkeypatch, lambda n: _ok("via or"))
    text, final, prov = _call(fake)
    assert (text, prov, fake.n, len(calls)) == ("via or", "openrouter", 2, 1)
    assert final.model == "anthropic/claude-sonnet-5.5"


def test_failover_on_timeout_and_connection(env, monkeypatch):
    fake = ScriptedAnthropic([anthropic.APITimeoutError(request=REQ), anthropic.APIConnectionError(request=REQ)])
    _or_mock(monkeypatch, lambda n: _ok("via or"))
    assert _call(fake)[2] == "openrouter"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_no_retry_no_failover_on_4xx(env, monkeypatch, status):
    fake = ScriptedAnthropic([_api_err(status)])
    calls = _or_mock(monkeypatch, lambda n: _ok("x"))
    with pytest.raises(anthropic.APIStatusError):
        _call(fake)
    assert fake.n == 1 and calls == [] and env == []


def test_openrouter_retries_429_then_succeeds(env, monkeypatch):
    seq = [httpx.Response(429, json={}, headers={"retry-after": "2"}), _ok("done")]
    calls = _or_mock(monkeypatch, lambda n: seq[n - 1])
    text, _, prov = _call(C.OpenRouterClient("k"))
    assert (text, prov, len(calls), env) == ("done", "openrouter", 2, [2.0])


def test_openrouter_402_not_retried(env, monkeypatch):
    calls = _or_mock(monkeypatch, lambda n: httpx.Response(402, json={}))
    with pytest.raises(C.LLMProviderError):
        _call(C.OpenRouterClient("k"))
    assert len(calls) == 1 and env == []


def test_openrouter_timeout_retried_twice_then_raises(env, monkeypatch):
    def boom(url, **kw):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(C.LLMProviderError):
        _call(C.OpenRouterClient("k"))
    assert env == [1.0]


def test_both_providers_fail_raises_last(env, monkeypatch):
    fake = ScriptedAnthropic([_api_err(500), _api_err(500)])
    calls = _or_mock(monkeypatch, lambda n: httpx.Response(503, json={}))
    with pytest.raises(C.LLMProviderError):
        _call(fake)
    assert fake.n == 2 and len(calls) == 2


def test_no_failover_without_openrouter_key(env, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    fake = ScriptedAnthropic([_api_err(500), _api_err(500)])
    with pytest.raises(anthropic.APIStatusError):
        _call(fake)
    assert fake.n == 2


def test_refusal_not_retried(env):
    fake = ScriptedAnthropic(["x"])
    fake.beta.messages.stream = lambda **kw: (_ for _ in ()).throw(C.LLMRefusal("r"))
    with pytest.raises(C.LLMRefusal):
        _call(fake)


def test_pipeline_records_provider_after_failover(env, monkeypatch):
    fake = ScriptedAnthropic([_api_err(503), _api_err(503), _api_err(503), _api_err(503)])
    monkeypatch.setattr(llm._client, "make_client", lambda: fake)
    outs = ["descricao", json.dumps(GOOD)]
    _or_mock(monkeypatch, lambda n: _ok(outs[n - 1]))
    rep = llm.ecg_report(_ecg(), _png())
    assert rep.available and rep.provider == "openrouter" and rep.description == "desc final"


def test_pipeline_records_provider_anthropic(env, monkeypatch):
    fake = ScriptedAnthropic(["descricao", json.dumps(GOOD)])
    monkeypatch.setattr(llm._client, "make_client", lambda: fake)
    assert llm.ecg_report(_ecg(), _png()).provider == "anthropic"


def test_pipeline_4xx_reports_error_without_failover(env, monkeypatch):
    fake = ScriptedAnthropic([_api_err(401)])
    monkeypatch.setattr(llm._client, "make_client", lambda: fake)
    calls = _or_mock(monkeypatch, lambda n: _ok("x"))
    rep = llm.ecg_report(_ecg(), None)
    assert rep.available is False and "Credenciais" in rep.limitations[0] and calls == []


def test_make_client_disables_sdk_retries(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert C.make_client().max_retries == 0
