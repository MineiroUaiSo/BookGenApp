"""Isotonic calibration (bench) + 'indeterminado' zone (app) with synthetic data, no models."""
import json

import numpy as np
import pytest

from app.rx import calibration as CAL
from app.rx import findings as F
from bench import calibrate_rx as C

CURVE = {"Effusion": {"x": [0.0, 0.2, 0.3, 0.6, 1.0], "y": [0.0, 0.05, 0.1, 0.5, 1.0],
                      "raw_low": 0.2, "raw_high": 0.6, "p_low": 0.05, "p_high": 0.5}}


@pytest.fixture
def calib(monkeypatch):
    monkeypatch.setattr(CAL, "_CALIB", dict(CURVE))
    monkeypatch.setattr(F, "_TUNING", {"default": 0.65, "thresholds": {}})


def test_pav_monotone_and_matches_sklearn():
    rng = np.random.default_rng(1)
    s = rng.random(300).round(2)
    y = (rng.random(300) < s).astype(float)
    xs, ys = C.pav(s, y)
    assert all(b >= a for a, b in zip(ys, ys[1:])) and all(b >= a for a, b in zip(xs, xs[1:]))
    try:
        from sklearn.isotonic import IsotonicRegression
    except ImportError:
        return
    ir = IsotonicRegression(out_of_bounds="clip").fit(s, y)
    grid = np.linspace(0, 1, 101)
    assert np.allclose(C.apply_curve(xs, ys, grid), ir.predict(grid), atol=1e-9)


def test_patient_folds_keep_patients_together_and_are_seeded():
    g = np.array([f"P{i % 40}" for i in range(200)])
    f1, f2 = C.patient_folds(g, 5, 0), C.patient_folds(g, 5, 0)
    assert (f1 == f2).all() and (C.patient_folds(g, 5, 1) != f1).any()
    for p in np.unique(g):
        assert len(set(f1[g == p])) == 1


def test_cv_calibration_reduces_ece_on_miscalibrated_scores():
    rng = np.random.default_rng(0)
    s = rng.random(1500)
    y = rng.random(1500) < s ** 3          # true prob far below the score
    g = np.array([f"P{i}" for i in range(1500)])
    m = C.cv_metrics(y, s, g, n_boot=50)
    assert m["ece"]["cal"] < m["ece"]["raw"] and m["ece"]["cal"] < 0.06
    assert m["brier"]["cal"] < m["brier"]["raw"]
    assert 0 <= m["ece"]["cal_ci"][0] < m["ece"]["cal_ci"][1]


def test_calibrate_skips_without_positives_and_hides_ids():
    rows = [{"ok": True, "mode": "model", "id": f"CXR{i}_IM-1", "gt_labels": ["effusion"] if i < 40 else [],
             "gt_raw": [] if i < 40 else ["rx.normal"],
             "images": [{"scores": {"Effusion": 0.7 if i < 40 else 0.1 + (i % 7) / 50}}], "findings": []}
            for i in range(120)]
    doc, summ = C.calibrate(rows, n_boot=20)
    assert "Effusion" in doc["pathologies"] and "skipped" in summ["Pneumothorax"]
    assert "CXR" not in json.dumps(doc)


def test_curve_monotone_and_probability(calib):
    ps = [CAL.calibrated_probability("Effusion", s) for s in np.linspace(0, 1, 50)]
    assert all(b >= a - 1e-12 for a, b in zip(ps, ps[1:]))
    assert CAL.calibrated_probability("Effusion", 0.45) == pytest.approx(0.3)
    assert CAL.calibrated_probability("Edema", 0.5) is None


@pytest.mark.parametrize("score,z", [(0.1, "nao_sugerido"), (0.4, "indeterminado"), (0.7, "sugestivo")])
def test_zones(calib, score, z):
    assert CAL.zone("Effusion", score) == z


def test_shipped_calibration_file_is_valid_and_monotone():
    data = json.loads(C.DEFAULT_OUT.read_text(encoding="utf-8"))
    assert "Pneumothorax" not in data["pathologies"]
    for e in data["pathologies"].values():
        assert all(b >= a for a, b in zip(e["y"], e["y"][1:])) and e["raw_low"] <= e["raw_high"]


def _img(scores):
    from test_rx_phantoms import pa_phantom
    from app.rx import analyze_image
    a = analyze_image(pa_phantom()[0], "x", None)
    a.model_scores = scores
    return a


def test_indeterminate_zone_emits_non_affirming_finding(calib):
    fs = {f.code: f for f in F._frontal_findings(_img({"Effusion": 0.4}), "")}
    assert "rx.model.effusion" not in fs
    f = fs["rx.model_indeterminate.effusion"]
    assert "Indeterminado" in f.label and "23%" in f.label and f.confidence <= 0.3


def test_suggestive_shows_calibrated_probability_and_not_suggested_is_silent(calib):
    fs = {f.code: f for f in F._frontal_findings(_img({"Effusion": 0.8}), "")}
    assert "Sugestivo" in fs["rx.model.effusion"].label and "%" in fs["rx.model.effusion"].label
    codes = {f.code for f in F._frontal_findings(_img({"Effusion": 0.1}), "")}
    assert not any(c.startswith("rx.model") for c in codes)


def test_pneumothorax_never_confirmed_and_carries_insufficient_evidence_note(calib):
    fs = {f.code: f for f in F._frontal_findings(_img({"Pneumothorax": 0.9}), "")}
    f = fs["rx.model.pneumothorax"]
    assert "Sugestivo" in f.label and any("evidência insuficiente" in e for e in f.evidence)
    assert not any(c.startswith("rx.model") for c in
                   {f.code for f in F._frontal_findings(_img({"Pneumothorax": 0.2}), "")})   # never 'afastado' either


def test_fallback_without_calibration_file_is_legacy(monkeypatch):
    monkeypatch.setattr(CAL, "_CALIB", {})
    monkeypatch.setattr(F, "_TUNING", {"default": 0.65, "thresholds": {"Effusion": 0.3}})
    img = _img({"Effusion": 0.35, "Edema": 0.35})
    codes = {f.code for f in F._frontal_findings(img, "")}
    assert "rx.model.effusion" in codes and "rx.model.edema" not in codes and not any("indeterminate" in c for c in codes)
    assert CAL.calibrate_scores({"Effusion": 0.5}) == ({}, {})


def test_analyze_image_exposes_calibrated_probability(calib):
    from test_rx_phantoms import pa_phantom
    from app.rx import analyze_image
    probs, zones = CAL.calibrate_scores({"Effusion": 0.4, "Edema": 0.9})
    assert probs == {"Effusion": 0.233} and zones == {"Effusion": "indeterminado"}
    assert analyze_image(pa_phantom()[0], "x", None).model_probs is not None
