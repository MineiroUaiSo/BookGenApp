"""find_lung_pair memoises per image (positive and negative results) and stays within its attempt budget."""
from __future__ import annotations

import numpy as np

from app.rx import seg_heuristic as H


def test_negative_result_is_memoised(monkeypatch):
    H._lung_cache.clear()
    calls = {"n": 0}
    real = H.dark_components

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(H, "dark_components", counting)
    flat = np.full((512, 512), 0.5, dtype=np.float32)
    assert H.find_lung_pair(flat) is None
    first = calls["n"]
    assert first <= H.LUNG_MAX_TRIES
    assert H.find_lung_pair(flat) is None
    assert calls["n"] == first  # second call served from cache


def test_cache_is_bounded():
    H._lung_cache.clear()
    for i in range(H._LUNG_CACHE_SIZE + 5):
        H.find_lung_pair(np.full((64, 64), i / 100.0, dtype=np.float32) + np.eye(64, dtype=np.float32) * 0.01 * i)
    assert len(H._lung_cache) <= H._LUNG_CACHE_SIZE
