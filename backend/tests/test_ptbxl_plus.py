"""PTB-XL+ 12SL measurement comparison (bench/ptbxl_plus.py): units, pairing, bias/MAE."""
from __future__ import annotations

import numpy as np

from bench import ptbxl_plus as pp


def _res(i, gm, stj):
    return {"id": f"ptbxl-{i:05d}", "ok": True, "data": {"gm": gm, "stj_mv": stj}}


def test_paired_converts_st_mv_to_uv_and_skips_missing():
    ref = {1: {"PR_Int_Global": 160.0, "QRS_Dur_Global": 90.0, "QT_Int_Global": 400.0, "QT_IntBazett_Global": 430.0,
               "HR__Global": 70.0, "ST_Amp_II": 0.10, "ST_Amp_V2": float("nan")},
           2: {"PR_Int_Global": float("nan"), "QRS_Dur_Global": 100.0, "QT_Int_Global": 380.0, "QT_IntBazett_Global": 420.0,
               "HR__Global": 60.0, "ST_Amp_II": 0.0}}
    res = [_res(1, {"pr_ms": 170.0, "qrs_ms": 96.0, "qt_ms": 410.0, "qtc_bazett_ms": 440.0, "heart_rate_bpm": 72.0},
                {"II": 0.12, "V2": 0.5}),
           _res(2, {"pr_ms": 150.0, "qrs_ms": 90.0, "qt_ms": 380.0, "qtc_bazett_ms": 420.0, "heart_rate_bpm": 60.0}, {"II": -0.05}),
           _res(3, {"pr_ms": 100.0}, {})]     # no reference row -> ignored
    pr = pp.paired(res, ref)
    assert list(pr["PR"][0]) == [170.0] and list(pr["PR"][1]) == [160.0]       # record 2: 12SL PR missing
    assert list(pr["QRS"][0]) == [96.0, 90.0] and list(pr["QRS"][1]) == [90.0, 100.0]
    assert np.allclose(pr["ST-J II"][0], [120.0, -50.0]) and np.allclose(pr["ST-J II"][1], [100.0, 0.0])
    assert "ST-J V2" not in pr    # 12SL value NaN


def test_error_stats_bias_mae_and_section_runs():
    ours = np.array([100.0, 110.0, 120.0, 130.0])
    ref = np.array([100.0, 100.0, 100.0, 100.0])
    s = pp.error_stats(ours, ref)
    assert s["n"] == 4 and s["bias"][0] == 15.0 and s["mae"][0] == 15.0
    assert s["bias"][1] <= 15.0 <= s["bias"][2]
    assert pp.error_stats(ours, ref)["bias"] == s["bias"]      # deterministic
    res = [_res(i, {"qrs_ms": 90.0 + i}, {}) for i in range(1, 6)]
    ref5 = {i: {"QRS_Dur_Global": 90.0} for i in range(1, 6)}
    body, stats = pp.section(res, ref5)
    assert "QRS" in body and abs(stats["QRS"]["bias"][0] - 3.0) < 1e-9 and "viés" in body


def test_load_12sl_reads_bom_and_blanks(tmp_path):
    p = tmp_path / "f.csv"
    p.write_text("ecg_id,PR_Int_Global,QRS_Dur_Global,QT_Int_Global,QT_IntBazett_Global,HR__Global,ST_Amp_I\n"
                 "7,,94.0,394,430,71,0.015\n", encoding="utf-8-sig")
    d = pp.load_12sl(p)
    assert d[7]["QRS_Dur_Global"] == 94.0 and np.isnan(d[7]["PR_Int_Global"]) and d[7]["ST_Amp_I"] == 0.015
    assert np.isnan(d[7]["ST_Amp_V6"])
