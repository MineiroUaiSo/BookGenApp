from bench import rule_ppv


def _rec(codes, scp, stadium=""):
    return {"ok": True, "data": {"findings": [{"code": c} for c in codes], "scp": scp}}


def test_compute_ppv_counts_true_positives_with_wilson_interval():
    res = {"a": _rec(["ecg.atrial_fibrillation"], {"AFIB": 100.0}),
           "b": _rec(["ecg.atrial_fibrillation"], {"NORM": 100.0}),
           "c": _rec(["ecg.atrial_fibrillation", "ecg.irregular_rhythm"], {"AFIB": 100.0}),
           "d": _rec(["ecg.sinus_rhythm"], {"SR": 100.0})}

    out = rule_ppv.compute(res, {})

    af = out["ecg.atrial_fibrillation"]
    assert (af["n"], af["tp"]) == (3, 2) and af["ppv"] == round(2 / 3, 3)
    assert af["ic_inf"] < af["ppv"] < af["ic_sup"] and af["fonte"] == "PTB-XL dev"
    assert out["ecg.sinus_rhythm"]["ppv"] == 1.0
    assert "ecg.irregular_rhythm" not in out        # no gold class mapped: "não medido"


def test_gold_for_prefixes():
    assert rule_ppv.gold_for("ecg.st_elevation_anterior") == "STE_acute"
    assert rule_ppv.gold_for("ecg.av_block_2_mobitz1") == "AV2"
    assert rule_ppv.gold_for("ecg.unknown_thing") is None


def test_shipped_rule_ppv_file_is_dev_only_and_consistent():
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "app" / "knowledge" / "rule_ppv.json"
    if not p.exists():
        return
    j = json.loads(p.read_text())
    for code, v in j["codes"].items():
        assert v["fonte"] == "PTB-XL dev" and 0 <= v["ic_inf"] <= v["ppv"] <= v["ic_sup"] <= 1 and v["n"] >= 1
