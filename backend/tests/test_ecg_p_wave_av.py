"""P wave inside the T wave (fast rates), AV conduction by P:QRS ratio and dissociation, probable sinus tachycardia."""
from __future__ import annotations

import numpy as np

from app.ecg.analysis import analyze_signal
from app.ecg.analysis.rhythm import _av3_from_grid, _av_core, atrial_grid, av_analysis
from app.schemas import ECGSignal, SourceKind
from synth_ecg import synth_signal

FS = 500


def _signal(leads):
    return ECGSignal(fs=FS, leads={k: [float(x) for x in v] for k, v in leads.items()}, duration_s=10.0,
                     source=SourceKind.CSV)


def test_analysis_tachycardia_p_inside_t_wave_reports_sinus_tachycardia_not_irregular_rhythm():
    leads, _ = synth_signal(hr=130, qt_ms=330, pr_ms=140, seconds=10.0, seed=1)

    an = analyze_signal(_signal(leads), "synth-stach")

    codes = {f.code for f in an.findings}
    assert "ecg.sinus_tachycardia" in codes
    assert "ecg.irregular_rhythm" not in codes
    assert "ecg.atrial_fibrillation" not in codes


def test_av_core_two_to_one_block_flags_av2_with_blocked_p_waves():
    q = np.arange(500.0, 9500.0, 1600.0)       # QRS every 1.6 s
    p = np.arange(340.0, 9500.0, 800.0)        # P every 0.8 s, PR 160 ms on the conducted ones: 2:1 block

    res = _av_core(p, q, FS)

    assert res["type"] == "av2_21"
    assert res["n_drops"] >= 3


def test_av_core_atrioventricular_dissociation_flags_av3_with_escape_rhythm():
    q = np.arange(400.0, 9600.0, 1700.0)       # regular escape ~35 bpm
    p = np.arange(150.0, 9600.0, 850.0 * 0.8)  # atrial rate ~88 bpm, unrelated to the QRS

    res = _av_core(p, q, FS)

    assert res["type"] == "av3"
    assert res["vent_rate"] < 0.7 * res["atrial_rate"]


def test_av_analysis_uses_alternative_p_series_when_primary_has_no_block_pattern():
    q = np.arange(400.0, 9600.0, 1700.0)
    p_alt = np.arange(150.0, 9600.0, 680.0)

    res = av_analysis(np.array([]), q, FS, p_alt=p_alt)

    assert res["type"] == "av3"
    assert res.get("alt") is True


def test_av_core_normal_one_to_one_conduction_has_no_block():
    q = np.arange(500.0, 9500.0, 900.0)
    p = q - 160.0

    res = _av_core(p, q, FS)

    assert res["type"] is None

def test_av3_from_grid_dissociated_p_at_75_and_qrs_at_40_flags_complete_block():
    q = np.arange(400.0, 9600.0, 1500.0)       # escape ~40 bpm, regular
    g = np.arange(100.0, 9600.0, 800.0)        # atrial ~75 bpm, unrelated phase (ratio 1.9 is not an integer lock)

    res = _av3_from_grid(g, q, {})

    assert res is not None and res["type"] == "av3"
    assert res["vent_rate"] < 0.85 * res["atrial_rate"]


def test_av3_from_grid_normal_sinus_conduction_is_not_block():
    q = np.arange(500.0, 9500.0, 900.0)
    g = q - 160.0                               # fixed PR: QRS phase locked to the grid

    assert _av3_from_grid(g, q, {}) is None


def test_av3_from_grid_harmonic_grid_at_half_rr_is_not_block():
    q = np.arange(500.0, 9500.0, 800.0)
    g = np.arange(150.0, 9500.0, 400.0)         # grid at half the RR (T-wave/subharmonic artefact), ratio 2.0

    assert _av3_from_grid(g, q, {}) is None


def test_atrial_grid_recovers_independent_atrial_period_from_synthetic_leads():
    rng = np.random.default_rng(3)
    n = 10 * FS
    t = np.arange(n) / FS
    q_ms = np.arange(400.0, 9600.0, 1500.0)
    leads = {}
    for ln, sign in (("II", 1.0), ("aVF", 1.0), ("V1", -0.6)):
        x = 0.01 * rng.standard_normal(n)
        for pt in np.arange(150.0, 9800.0, 800.0):                 # P waves every 800 ms
            x += sign * 0.12 * np.exp(-0.5 * ((t - pt / 1000.0) / 0.025) ** 2)
        for qt in q_ms:                                            # narrow QRS every 1500 ms
            x += 1.0 * np.exp(-0.5 * ((t - qt / 1000.0) / 0.012) ** 2)
        leads[ln] = x
    beats = [{"qrs_on": int(qt * FS / 1000) - 10, "qrs_off": int(qt * FS / 1000) + 10, "t_off": int(qt * FS / 1000) + 90}
             for qt in q_ms]

    grid, info = atrial_grid(leads, FS, beats)

    assert grid is not None
    assert abs(info["period_ms"] - 800.0) < 30.0
