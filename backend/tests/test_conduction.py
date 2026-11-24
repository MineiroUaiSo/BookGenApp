"""Conduction timeline tests (times relative to the P-wave onset of the representative beat)."""
from __future__ import annotations

import numpy as np

from app.ecg.analysis import analyze_signal
from app.ecg.conduction import conduction_timeline
from app.schemas import ECGSignal, GlobalMeasurements, SourceKind, Wave, WaveKind

try:
    from .test_ecg_analysis_gen import PREC, make_ecg, sinus
except ImportError:
    from test_ecg_analysis_gen import PREC, make_ecg, sinus
from synth_ecg import synth_signal


def run(leads, seconds=10.0):
    sig = ECGSignal(fs=500, leads={k: [float(x) for x in v] for k, v in leads.items()}, duration_s=seconds,
                    source=SourceKind.CSV)
    return analyze_signal(sig, "t")


def by(a):
    return {p.structure: p for p in a.conduction}


def test_normal_timeline_order_and_values():
    leads, _ = synth_signal(hr=70, pr_ms=160, noise_mv=0.005, seed=1)
    a = run(leads)
    p = by(a)
    assert list(p) == ["SA", "atria", "AV_node", "His", "LBB", "RBB", "purkinje", "ventricles_depol",
                       "ventricles_repol"]
    assert -30 <= p["SA"].start_ms < 0 and p["SA"].end_ms == 0
    assert p["atria"].start_ms == 0 and 70 <= p["atria"].end_ms <= 115
    gm = a.global_measurements
    assert abs(p["ventricles_depol"].start_ms - gm.pr_ms) <= 1
    assert abs(p["ventricles_depol"].end_ms - p["ventricles_depol"].start_ms - gm.qrs_ms) <= 1
    assert abs(p["ventricles_repol"].end_ms - gm.qt_ms - gm.pr_ms) <= 1
    # contiguity of the chain atria -> AV -> His -> QRS
    assert p["AV_node"].start_ms == p["atria"].end_ms
    assert p["His"].start_ms == p["AV_node"].end_ms and p["His"].end_ms == p["ventricles_depol"].start_ms
    assert p["ventricles_repol"].start_ms == p["ventricles_depol"].end_ms
    assert 30 <= p["His"].end_ms - p["His"].start_ms <= 55
    assert not any(ph.abnormal for ph in a.conduction)
    assert all(ph.ecg_correlate and ph.note for ph in a.conduction)


def test_av_block_1_prolonged_av_node():
    leads, _ = synth_signal(hr=65, pr_ms=280, noise_mv=0.005, seed=1)
    p = by(run(leads))
    assert p["AV_node"].abnormal
    assert p["AV_node"].end_ms - p["AV_node"].start_ms > 110
    assert "1º grau" in p["AV_node"].note


def test_rbbb_delays_right_branch():
    prec = dict(PREC)
    prec["V1"] = [(-30, 8, 0.25), (0, 10, -0.9), (35, 11, 1.0)]
    prec["V6"] = [(-20, 8, -0.1), (0, 10, 1.0), (40, 13, -0.5)]
    L, _ = sinus(75, qrs_scale=1.35, prec=prec, axis_deg=30, noise=0.005)
    p = by(run(L))
    assert p["RBB"].abnormal and not p["LBB"].abnormal
    assert p["RBB"].end_ms == p["ventricles_depol"].end_ms
    assert p["LBB"].end_ms - p["LBB"].start_ms <= 40
    assert "direito" in p["RBB"].note


def test_atrial_fibrillation_timeline():
    rng = np.random.default_rng(1)
    r = np.cumsum(rng.uniform(0.4, 1.1, 30)) + 0.3
    r = r[r < 9.4]
    a = run(make_ecg(r, [], fwave=0.01, noise=0.01))
    p = by(a)
    assert p["atria"].abnormal and "caótica" in p["atria"].note
    assert p["atria"].ecg_correlate == "ausente"
    assert p["SA"].abnormal
    # relative to R-200 ms when no P wave: QRS starts ~200 ms after the origin minus its R lead
    assert 120 <= p["ventricles_depol"].start_ms <= 200


def test_direct_call_with_explicit_waves():
    gm = GlobalMeasurements(pr_ms=160, qrs_ms=90, qt_ms=400, p_duration_ms=100, rhythm="Ritmo sinusal regular")
    waves = [Wave(kind=WaveKind.P, lead="II", beat_index=2, onset_ms=1000, offset_ms=1100, peak_ms=1050, amplitude_mv=0.15),
             Wave(kind=WaveKind.QRS, lead="II", beat_index=2, onset_ms=1160, offset_ms=1250, peak_ms=1190, amplitude_mv=1.4),
             Wave(kind=WaveKind.T, lead="II", beat_index=2, onset_ms=1350, offset_ms=1560, peak_ms=1450, amplitude_mv=0.3)]
    ph = {x.structure: x for x in conduction_timeline(gm, waves)}
    assert ph["atria"].start_ms == 0 and ph["atria"].end_ms == 100
    assert ph["ventricles_depol"].start_ms == 160 and ph["ventricles_depol"].end_ms == 250
    assert ph["ventricles_repol"].end_ms == 560
    assert conduction_timeline(GlobalMeasurements(), []) == []


def test_conduction_only_from_gm_when_no_waves():
    gm = GlobalMeasurements(pr_ms=150, qrs_ms=90, qt_ms=380, p_duration_ms=90)
    ph = conduction_timeline(gm, [])
    assert [x.structure for x in ph][0] == "SA" and len(ph) == 9
