"""Region/view robustness: border trimming, polarity, model-feature classifier, heuristic honesty."""
from __future__ import annotations

import numpy as np
import pytest

from app.rx import analyze_image, view as V
from app.rx._common import autocrop, normalize_polarity
from app.schemas import BodyRegion, RXView

from test_rx_phantoms import pa_phantom


@pytest.fixture(autouse=True)
def _no_models(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")


def test_autocrop_trims_black_padding():
    img, _ = pa_phantom()
    img = img.copy()
    img = img[::2, ::2]
    pad = np.zeros((img.shape[0] * 2, img.shape[1] * 2), np.uint8)
    pad[:img.shape[0], 40:40 + img.shape[1]] = img
    crop, (y0, x0) = autocrop(pad)
    assert crop.shape[0] <= img.shape[0] + 2 and crop.shape[1] <= img.shape[1] + 2 and y0 == 0 and x0 >= 30


def test_autocrop_keeps_unpadded():
    img, _ = pa_phantom()
    assert autocrop(img)[1] == (0, 0)


def test_polarity_inversion_detected():
    rng = np.random.default_rng(0)
    base = np.full((200, 160), 60, np.uint8)       # dark ring (air), brighter centre (body)
    base[30:170, 30:130] = 150
    base = np.clip(base + rng.integers(-5, 5, base.shape), 0, 255).astype(np.uint8)
    out, inv = normalize_polarity(base)
    assert not inv
    out, inv = normalize_polarity(255 - base)
    assert inv and out.mean() < 130


def test_padded_phantom_still_chest():
    img, _ = pa_phantom()
    pad = np.zeros((img.shape[0] + 300, img.shape[1] + 200), np.uint8)
    pad[:img.shape[0], 100:100 + img.shape[1]] = img
    a = analyze_image(pad, "p", None)
    assert a.region == BodyRegion.CHEST and a.view == RXView.PA
    assert (a.height, a.width) == pad.shape


def test_heuristic_flags_low_confidence():
    img, _ = pa_phantom()
    a = analyze_image(img, "h", None)
    assert "BAIXA CONFIABILIDADE" in a.quality["confiabilidade"]
    assert all(s.confidence <= 0.3 for s in a.structures)


def _feat(**kw):
    f = dict(left=0.15, right=0.15, heart=0.06, lungs=0.30, spine=0.1, maxprob=1.0, heart_cy=0.6, heart_cx=.5,
             lung_cx_gap=.3)
    f.update(kw)
    return f


def test_classify_from_features():
    assert V.classify_from_features(_feat())[0] == "chest_frontal"
    assert V.classify_from_features(_feat(heart=0.0, spine=0.0, lungs=0.12))[0] == "chest_lateral"
    assert V.classify_from_features(_feat(heart=0.0, spine=0.05, lungs=0.12))[0] == "nochest"   # abdomen-like
    assert V.classify_from_features(_feat(heart=0.0, lungs=0.0, left=0, right=0, maxprob=0.3))[0] == "nochest"
    assert not V._upright(_feat(heart_cy=0.1))


def test_heart_side_check():
    from app.rx.analyze import _heart_side_check
    z = np.zeros((100, 100), bool)
    rl, ll, ht = z.copy(), z.copy(), z.copy()
    rl[20:80, 10:40] = True      # patient right = image left
    ll[20:80, 60:90] = True
    ht[50:80, 52:72] = True      # towards image right: normal
    assert _heart_side_check({"right_lung": rl, "left_lung": ll, "heart": ht}) is None
    ht2 = z.copy(); ht2[50:80, 28:48] = True
    assert "espelhada" in _heart_side_check({"right_lung": rl, "left_lung": ll, "heart": ht2})
