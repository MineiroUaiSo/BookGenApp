"""PTB-XL gold rules of bench/ecg_bench.py (STE_ vs STE_acute)."""
from __future__ import annotations

from bench.ecg_bench import CLASS_DESC, PRED, gold_classes


def test_gold_ste_acute_requires_mi_and_early_stadium():
    assert "STE_acute" in gold_classes({"IMI": 100.0}, "Stadium I")
    assert "STE_acute" in gold_classes({"ASMI": 50.0, "NORM": 0.0}, "Stadium I-II")
    assert "STE_acute" not in gold_classes({"IMI": 100.0}, "Stadium III")
    assert "STE_acute" not in gold_classes({"IMI": 100.0}, "unknown")
    assert "STE_acute" not in gold_classes({"IMI": 100.0}, None)
    assert "STE_acute" not in gold_classes({"NORM": 100.0}, "Stadium I")   # stadium without MI code
    assert "STE_acute" not in gold_classes({"IMI": 10.0}, "Stadium I")     # likelihood < 50 is not positive


def test_gold_keeps_old_ste_statement_gold_unchanged():
    g = gold_classes({"STE_": 100.0, "IMI": 100.0}, "Stadium III")
    assert "STE" in g and "STE_acute" not in g and "MI_any" in g
    assert "STE" not in gold_classes({"IMI": 100.0}, "Stadium I")


def test_ste_acute_predicted_like_ste():
    codes = {"ecg.st_elevation_inferior"}
    assert PRED["STE"](codes) and PRED["STE_acute"](codes)
    assert not PRED["STE_acute"]({"ecg.sinus_rhythm"})
    assert "STE_acute" in CLASS_DESC
