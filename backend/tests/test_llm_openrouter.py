"""Fallback OpenRouter da IA do laudo (httpx mockado, sem rede)."""
import json

import httpx
import pytest

from app import llm
from app.llm import client as C
from tests.test_llm import GOOD, _ecg, _png

OK_BODY = lambda text, reason="stop": {"model": "anthropic/claude-sonnet-5.5", "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                                       "choices": [{"finish_reason": reason, "message": {"content": text}}]}


@pytest.fixture
def or_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("MEDLENS_OR_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")


def _mock(monkeypatch, handler):
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        return handler(len(calls), json)

    monkeypatch.setattr(httpx, "post", post)
    return calls


def _resp(status, body):
    return httpx.Response(status, json=body)


def test_openrouter_available_only_with_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert llm.ai_available() is False
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert llm.ai_available() is True and C.provider() == "openrouter"


def test_anthropic_has_priority(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    assert C.provider() == "anthropic"


def test_openrouter_model_default_and_env(or_env, monkeypatch):
    assert C.model_name() == "anthropic/claude-sonnet-5.5"
    monkeypatch.setenv("MEDLENS_OR_MODEL", "anthropic/claude-sonnet-4.6")
    assert llm.model_name() == "anthropic/claude-sonnet-4.6"


def test_openrouter_ecg_report_two_stage(or_env, monkeypatch):
    outs = ["descrição etapa 1", json.dumps(GOOD)]
    calls = _mock(monkeypatch, lambda n, p: _resp(200, OK_BODY(outs[n - 1])))
    rep = llm.ecg_report(_ecg(), _png())
    assert rep.available and rep.description == "desc final"
    assert rep.model == "anthropic/claude-sonnet-5.5"
    assert [c["url"] for c in calls] == ["https://openrouter.ai/api/v1/chat/completions"] * 2
    assert calls[0]["headers"]["Authorization"] == "Bearer or-test-key"
    p1, p2 = calls[0]["json"], calls[1]["json"]
    assert "response_format" not in p1
    assert p2["response_format"]["type"] == "json_schema" and p2["response_format"]["json_schema"]["strict"] is True
    assert p1["messages"][0]["role"] == "system"
    parts = p1["messages"][1]["content"]
    imgs = [x for x in parts if x["type"] == "image_url"]
    assert len(imgs) == 1 and imgs[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "descrição etapa 1" in json.dumps(p2["messages"], ensure_ascii=False)


@pytest.mark.parametrize("status,needle", [(402, "créditos"), (429, "limite"), (401, "credenciais"), (500, "500")])
def test_openrouter_http_errors_are_friendly(or_env, monkeypatch, status, needle):
    _mock(monkeypatch, lambda n, p: _resp(status, {"error": {"message": "x"}}))
    rep = llm.ecg_report(_ecg(), None)
    assert rep.available is False and needle in rep.limitations[0].lower()
    assert "or-test-key" not in json.dumps(rep.model_dump())


def test_openrouter_truncated_and_bad_json(or_env, monkeypatch):
    _mock(monkeypatch, lambda n, p: _resp(200, OK_BODY("x", "length")))
    assert "truncada" in llm.ecg_report(_ecg(), None).limitations[0]
    _mock(monkeypatch, lambda n, p: _resp(200, OK_BODY("não json")))
    assert "interpretada" in llm.ecg_report(_ecg(), None).limitations[0]


def test_openrouter_connection_error(or_env, monkeypatch):
    def boom(url, **kw):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    rep = llm.ecg_report(_ecg(), None)
    assert rep.available is False and "conexão" in rep.limitations[0]
