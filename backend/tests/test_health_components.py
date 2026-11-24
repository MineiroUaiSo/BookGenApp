"""/health imports modules for real: a stubbed or broken module changes its status."""
from __future__ import annotations

import sys

import pytest
from conftest import install_fake

from app.api import health as H


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    H.reset_cache()
    monkeypatch.setattr(H, "_load_rx_model", lambda: "ok")  # no real weights in these tests
    yield
    H.reset_cache()


def test_health_reports_ok_for_stubbed_module(client, monkeypatch):
    install_fake(monkeypatch, "pylibjpeg")
    h = client.get("/api/health").json()
    assert h["models"]["pylibjpeg"] == "ok"


def test_health_reports_ausente_for_missing_module(client, monkeypatch):
    monkeypatch.setitem(sys.modules, "pillow_heif", None)  # forces ModuleNotFoundError-like ImportError
    h = client.get("/api/health").json()
    assert h["models"]["pillow_heif"] == "ausente"
    assert "pillow_heif" in h["degraded"]


def test_health_reports_erro_for_broken_import(client, monkeypatch):
    monkeypatch.delitem(sys.modules, "trimesh", raising=False)
    real = H.importlib.import_module

    def fake_import(name, *a, **k):
        if name == "trimesh":
            raise ImportError("libfoo.so: undefined symbol")
        return real(name, *a, **k)

    monkeypatch.setattr(H.importlib, "import_module", fake_import)
    h = client.get("/api/health").json()
    assert h["models"]["trimesh"].startswith("erro: ImportError")
    assert "trimesh" in h["degraded"]


def test_health_rx_model_failure_is_reported(client, monkeypatch):
    monkeypatch.setattr(H, "_load_rx_model", lambda: "erro: pesos do modelo não carregaram")
    h = client.get("/api/health").json()
    assert h["models"][H.RX_MODEL_LABEL].startswith("erro")
    assert H.RX_MODEL_LABEL in h["degraded"]


def test_health_status_cached_once_per_process(client, monkeypatch):
    calls = {"n": 0}

    def counting():
        calls["n"] += 1
        return "ok"

    monkeypatch.setattr(H, "_load_rx_model", counting)
    client.get("/api/health")
    client.get("/api/health")
    assert calls["n"] == 1
