"""Threshold tuning + per-pathology thresholds in findings (synthetic data, no models)."""
import json

import numpy as np
import pytest

from app.rx import findings as F
from bench import tune_rx_thresholds as T


def _rows(n_pos=40, n_neg=60, seed=0, patho="Effusion"):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_pos):
        rows.append({"ok": True, "mode": "model", "gt_labels": ["effusion"], "gt_raw": [], "findings": [],
                     "images": [{"scores": {patho: float(np.clip(rng.normal(0.6, 0.15), 0, 1))}}]})
    for i in range(n_neg):
        rows.append({"ok": True, "mode": "model", "gt_labels": [], "gt_raw": ["rx.normal"], "findings": [],
                     "images": [{"scores": {patho: float(np.clip(rng.normal(0.2, 0.1), 0, 1))}}]})
    return rows


def test_threshold_for_specificity_exact():
    y = [False] * 10 + [True] * 3
    s = [i / 100 for i in range(10)] + [0.5, 0.6, 0.7]
    t = T.threshold_for_specificity(y, s, 0.9)
    pred = np.asarray(s) >= t
    assert (~np.asarray(y) & pred).sum() <= 1          # spec >= 0.9
    assert t <= 0.5                                     # positives above still flagged


def test_tune_keeps_default_without_positives_and_fits_dev():
    rows = _rows()
    res = T.tune(rows, 0.9)
    assert "Effusion" in res["thresholds"] and 0.2 < res["thresholds"]["Effusion"] < 0.6
    m = res["metrics"]["Effusion"]
    assert m["spec"] >= 0.9 and m["auc"] > 0.9 and m["auc_lo"] <= m["auc"] <= m["auc_hi"]
    assert "skipped" in res["metrics"]["Pneumothorax"]


def test_ece_ppv():
    assert T.ece([1, 0], [1.0, 0.0]) == pytest.approx(0.0)
    assert T.ppv_at(0.9, 0.9, 0.5) == pytest.approx(0.9)
    assert T.ppv_at(0.5, 0.9, 0.01) < 0.1


def test_costophrenic_validation_demotes_low_sens():
    rows = _rows()
    for r in rows[:2]:
        r["findings"] = [{"code": "rx.costophrenic_blunting_left"}]
    v = T.costophrenic_validation(rows)
    assert v["pos"] == 40 and v["sens"] == pytest.approx(2 / 40) and v["demoted"] is True


def test_vindr_labels_and_frozen_eval(tmp_path):
    p = tmp_path / "labels.csv"
    p.write_text("image_id,Cardiomegaly,Pleural effusion\n" + "\n".join(f"a{i},{int(i % 2 == 0)},0" for i in range(20)) + "\n")
    lab = T.read_vindr_labels(p)
    assert lab["a0"] == {"Cardiomegaly": True, "Effusion": False}
    sc = {k: {"Cardiomegaly": 0.9 if v["Cardiomegaly"] else 0.1} for k, v in lab.items()}
    res = T.evaluate_vindr(lab, sc, {"Cardiomegaly": 0.5})
    assert res["Cardiomegaly"]["sens"] == 1.0 and res["Cardiomegaly"]["spec"] == 1.0
    assert "Effusion" not in res


def _img(scores):
    from test_rx_phantoms import pa_phantom
    from app.rx import analyze_image
    a = analyze_image(pa_phantom()[0], "x", None)
    a.model_scores = scores
    return a


def test_findings_use_per_pathology_threshold(monkeypatch):
    monkeypatch.setattr(F, "_TUNING", {"default": 0.65, "thresholds": {"Effusion": 0.3}})
    codes = {f.code for f in F._frontal_findings(_img({"Effusion": 0.35, "Edema": 0.35}), "")}
    assert "rx.model.effusion" in codes and "rx.model.edema" not in codes


def test_findings_default_when_file_missing(monkeypatch):
    monkeypatch.setattr(F, "_TUNING", {})
    assert F.model_threshold("Effusion") == F.MODEL_THRESHOLD
    assert not F.costophrenic_demoted()


def _with_angle(angle):
    from test_rx_phantoms import pa_phantom
    from app.rx import analyze_image
    a = analyze_image(pa_phantom()[0], "x", None)
    from app.schemas import RXMeasurement
    m = RXMeasurement(key="costophrenic_angle_left", label="ângulo costofrênico E", value=angle, unit="°")
    a.measurements = [x for x in a.measurements if x.key != "costophrenic_angle_left"] + [m]
    return a


def test_costophrenic_rule_demoted_lowers_confidence(monkeypatch):
    a = _with_angle(120.0)
    monkeypatch.setattr(F, "_TUNING", {"costophrenic_rule": {"demoted": False}})
    base = [f for f in F._frontal_findings(a, "") if f.code == "rx.costophrenic_blunting_left"][0]
    monkeypatch.setattr(F, "_TUNING", {"costophrenic_rule": {"demoted": True}})
    low = [f for f in F._frontal_findings(a, "") if f.code == "rx.costophrenic_blunting_left"][0]
    assert low.confidence <= 0.15 < base.confidence and any("baixa sensibilidade" in e for e in low.evidence)
