"""P wave inside the T wave (fast rates), AV conduction by P:QRS ratio and dissociation, probable sinus tachycardia."""
from __future__ import annotations

import numpy as np

from app.ecg.analysis import analyze_signal
from app.ecg.analysis.rhythm import _av_core, av_analysis
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
