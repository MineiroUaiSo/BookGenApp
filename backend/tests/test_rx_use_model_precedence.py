"""Explicit use_model argument beats MEDLENS_RX_MODELS env (env only applies when argument is None)."""
from __future__ import annotations

import numpy as np

from app.rx import seg_model


def _stub_model(monkeypatch):
    calls = {"n": 0}

    def fake_psp():
        calls["n"] += 1
        return None  # model unavailable after being requested -> psp_probs returns None

    monkeypatch.setattr(seg_model, "_psp", fake_psp)
    return calls


def test_explicit_true_overrides_env_off(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")
    calls = _stub_model(monkeypatch)
    seg_model.psp_probs(np.zeros((64, 64), dtype=np.float32), use_model=True)
    assert calls["n"] == 1


def test_explicit_false_overrides_env_on(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "1")
    calls = _stub_model(monkeypatch)
    assert seg_model.psp_probs(np.zeros((64, 64), dtype=np.float32), use_model=False) is None
    assert calls["n"] == 0
    assert seg_model.pathology_scores(np.zeros((64, 64), dtype=np.float32), use_model=False) == {}


def test_none_defers_to_env(monkeypatch):
    calls = _stub_model(monkeypatch)
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")
    seg_model.psp_probs(np.zeros((8, 8), dtype=np.float32))
    assert calls["n"] == 0
    monkeypatch.setenv("MEDLENS_RX_MODELS", "1")
    seg_model.psp_probs(np.zeros((8, 8), dtype=np.float32))
    assert calls["n"] == 1
