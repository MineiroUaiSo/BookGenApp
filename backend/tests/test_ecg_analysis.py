"""ECG analysis tests on synthetic signals with known fiducials."""
from __future__ import annotations

import numpy as np
import pytest

from app.ecg.analysis import analyze_signal
from app.schemas import ECGSignal, SourceKind

try:
    from .test_ecg_analysis_gen import PREC, make_ecg, sinus
except ImportError:  # tests dir is on sys.path (conftest)
    from test_ecg_analysis_gen import PREC, make_ecg, sinus
from synth_ecg import synth_signal

FS = 500


def run(leads, seconds=10.0, fs=FS):
    sig = ECGSignal(fs=fs, leads={k: [float(x) for x in v] for k, v in leads.items()},
                    duration_s=seconds, source=SourceKind.CSV)
    return analyze_signal(sig, "t")


def codes(a):
    return {f.code for f in a.findings}


def ang_err(a, b):
    return abs((a - b + 180) % 360 - 180)


# ---------------------------------------------------------------- measurement accuracy
@pytest.mark.parametrize("hr,qt", [(50, 420), (70, 400), (100, 340), (130, 290)])
def test_intervals_and_hr(hr, qt):
    leads, fid = synth_signal(hr=hr, qt_ms=qt, pr_ms=150, noise_mv=0.01, wander_mv=0.2, seed=1)
    a = run(leads)
    g = a.global_measurements
    assert abs(g.heart_rate_bpm - hr) <= 2
    assert abs(g.pr_ms - 150) <= 20, g.pr_ms
    assert abs(g.qrs_ms - 90) <= 15, g.qrs_ms     # Gaussian QRS: nominal border at ~2.5-3 sigma
    assert abs(g.qt_ms - qt) <= 20, g.qt_ms
    # P borders of the Gaussian synthetic are fuzzy; the robust isoelectric reference (needed for
    # digitised photos) reads ~80-90 ms here. PR, the clinically decisive interval, stays within 15 ms.
    assert abs(g.p_duration_ms - 100) <= 25, g.p_duration_ms
    assert g.rhythm and "sinusal" in g.rhythm.lower()
    # Bazett consistency
    assert abs(g.qtc_bazett_ms - g.qt_ms / np.sqrt(60 / hr)) < 2
    assert g.qtc_hodges_ms is not None and g.qtc_framingham_ms is not None


def test_r_peaks_and_wave_contract():
    leads, fid = synth_signal(hr=75, noise_mv=0.01, seed=2)
    a = run(leads)
    truth = fid["r_peaks_s"] * 1000
    assert len(a.r_peaks_ms) == len(truth)
    assert np.max(np.abs(np.array(a.r_peaks_ms) - truth)) <= 10
    # waves: absolute ms, 0-based beat index, P/QRS/T on lead II for an inner beat
    w2 = [w for w in a.waves if w.lead == "II" and w.beat_index == 3]
    kinds = {w.kind.value for w in w2}
    assert {"P", "QRS", "T", "R"} <= kinds
    p = next(w for w in w2 if w.kind.value == "P")
    assert abs(p.onset_ms - fid["p_on_s"][3] * 1000) <= 25
    assert abs(p.peak_ms - (fid["p_on_s"][3] + 0.05) * 1000) <= 15
    assert min(w.beat_index for w in a.waves) >= 0
    r3 = next(w for w in w2 if w.kind.value == "R")
    assert abs(r3.peak_ms - a.r_peaks_ms[3]) <= 6
    # median beat starts exactly 300 ms before R
    r_idx = a.median_beat_r_index
    assert r_idx == int(round(0.3 * FS))
    m = np.array(a.median_beats["II"])
    assert abs(int(np.argmax(m)) - r_idx) <= 3
    assert len(m) >= r_idx + int(0.4 * FS)


@pytest.mark.parametrize("axis", [-50, 0, 45, 100])
def test_qrs_axis(axis):
    L, r = sinus(70, axis_deg=axis, noise=0.005)
    a = run(L)
    assert ang_err(a.global_measurements.qrs_axis_deg, axis) <= 15
    if axis < -30:
        assert "ecg.left_axis_deviation" in codes(a)
    if axis > 90:
        assert "ecg.right_axis_deviation" in codes(a)


def test_normal_has_no_abnormal_findings():
    leads, _ = synth_signal(hr=72, noise_mv=0.01, wander_mv=0.15, seed=3)
    a = run(leads)
    bad = [f.code for f in a.findings if f.severity != "normal"]
    assert not bad, bad
    assert a.global_measurements.sokolow_lyon_mv < 3.5
    assert a.global_measurements.precordial_transition in ("V3", "V4")
    assert abs(a.global_measurements.p_axis_deg - 50) <= 25
    for m in a.lead_measurements:
        assert m.lead
    v1 = next(m for m in a.lead_measurements if m.lead == "V1")
    assert v1.morphology in ("rS", "rs", "RS")
    assert v1.s_amplitude_mv < -0.8


def test_robust_to_mains_and_wander():
    L, _ = sinus(80, noise=0.01, wander=0.3, mains=0.05)
    a = run(L)
    assert abs(a.global_measurements.heart_rate_bpm - 80) <= 2
    assert any("rede" in w for w in a.warnings)
    assert abs(a.global_measurements.qt_ms - 400) <= 25


# ---------------------------------------------------------------- abnormalities
def test_av_block_1():
    leads, _ = synth_signal(hr=65, pr_ms=260, noise_mv=0.01, seed=4)
    a = run(leads)
    assert abs(a.global_measurements.pr_ms - 260) <= 20
    assert "ecg.av_block_1" in codes(a)


def test_short_pr_not_bav1():
    leads, _ = synth_signal(hr=65, pr_ms=100, noise_mv=0.005, seed=4)
    a = run(leads)
    assert "ecg.av_block_1" not in codes(a)
    assert codes(a) & {"ecg.short_pr", "ecg.preexcitation"}


def _brd_prec():
    prec = dict(PREC)
    prec["V1"] = [(-30, 8, 0.25), (0, 10, -0.9), (35, 11, 1.0)]
    prec["V6"] = [(-20, 8, -0.1), (0, 10, 1.0), (40, 13, -0.5)]
    return prec


def test_rbbb():
    L, _ = sinus(75, qrs_scale=1.35, prec=_brd_prec(), axis_deg=30, noise=0.005)
    a = run(L)
    g = a.global_measurements
    assert 125 <= g.qrs_ms <= 175, g.qrs_ms
    assert "ecg.rbbb" in codes(a)
    assert "ecg.lbbb" not in codes(a)
    v1 = next(m for m in a.lead_measurements if m.lead == "V1")
    assert "R'" in v1.morphology


def test_lbbb():
    prec = dict(PREC)
    prec["V1"] = [(10, 14, -1.2)]
    prec["V2"] = [(10, 14, -1.6)]
    prec["V5"] = [(0, 14, 1.4), (30, 14, 0.9)]
    prec["V6"] = [(0, 14, 1.2), (30, 14, 0.8)]
    L, _ = sinus(70, qrs_scale=1.35, prec=prec, axis_deg=10, noise=0.005)
    a = run(L)
    assert a.global_measurements.qrs_ms >= 120
    assert "ecg.lbbb" in codes(a)


def test_inferior_st_elevation():
    L, _ = sinus(70, st={"II": 0.25, "III": 0.25, "aVF": 0.25}, noise=0.005)
    a = run(L)
    f = [f for f in a.findings if f.code == "ecg.st_elevation_inferior"]
    assert f and f[0].severity == "critical" and f[0].origin == "rules"
    assert {r.id for r in f[0].references} & {"udmi4_2018"}
    stj = {m.lead: m.st_j_mv for m in a.lead_measurements}
    assert abs(stj["II"] - 0.25) <= 0.06
    assert abs(stj["V2"]) < 0.05
    assert not any(c.startswith("ecg.st_elevation") and "inferior" not in c for c in codes(a))


def test_st_depression_anterior():
    L, _ = sinus(70, st={"V3": -0.15, "V4": -0.15, "V5": -0.15}, noise=0.005)
    a = run(L)
    assert any(c.startswith("ecg.st_depression") for c in codes(a))


def test_atrial_fibrillation():
    rng = np.random.default_rng(1)
    r = np.cumsum(rng.uniform(0.4, 1.1, 30)) + 0.3
    r = r[r < 9.4]
    L = make_ecg(r, [], fwave=0.01, noise=0.01)
    a = run(L)
    g = a.global_measurements
    assert g.rhythm == "Fibrilação atrial"
    assert "ecg.atrial_fibrillation" in codes(a)
    assert g.rr_sd_ms > 100
    assert g.pr_ms is None


def test_complete_av_block():
    p = np.arange(0.2, 19.5, 0.8)
    r = np.arange(0.9, 19.2, 1.5)
    a = run(make_ecg(r, p, seconds=20, qrs_scale=1.5, noise=0.005), 20)
    assert "ecg.av_block_3" in codes(a)
    assert abs(a.global_measurements.heart_rate_bpm - 40) <= 2


def test_mobitz_1_and_2():
    P = np.arange(0.3, 19.6, 0.8)
    prs = [0.2, 0.28, 0.36, None]
    r = [p + prs[i % 4] + 0.035 for i, p in enumerate(P) if prs[i % 4]]
    a = run(make_ecg(r, P, seconds=20, noise=0.005), 20)
    assert "ecg.av_block_2_mobitz1" in codes(a)
    r2 = [p + 0.22 + 0.035 for i, p in enumerate(P) if i % 4 != 3]
    a2 = run(make_ecg(r2, P, seconds=20, noise=0.005), 20)
    assert "ecg.av_block_2_mobitz2" in codes(a2)


def test_brady_tachy_qt():
    a = run(synth_signal(hr=42, noise_mv=0.005, seed=5)[0])
    assert "ecg.sinus_bradycardia" in codes(a)
    assert a.global_measurements.rhythm == "Bradicardia sinusal"
    a = run(synth_signal(hr=125, qt_ms=300, pr_ms=140, noise_mv=0.005, seed=5)[0])
    assert "ecg.sinus_tachycardia" in codes(a)
    a = run(synth_signal(hr=65, qt_ms=520, noise_mv=0.005, seed=5)[0])
    assert "ecg.long_qt" in codes(a)


def test_lvh_and_low_voltage():
    prec = dict(PREC)
    prec["V1"] = [(0, 9, 0.1), (22, 10, -2.0)]
    prec["V5"] = [(-20, 8, -0.1), (0, 10, 2.6), (22, 10, -0.2)]
    L, _ = sinus(70, prec=prec, noise=0.005)
    a = run(L)
    assert a.global_measurements.sokolow_lyon_mv > 3.5
    assert "ecg.lvh" in codes(a)
    L, _ = sinus(70, mag=0.25, t_mag=0.08, p_mag=0.04, noise=0.002,
                 prec={k: [(d, s, x * 0.15) for d, s, x in v] for k, v in PREC.items()})
    a = run(L)
    assert "ecg.low_voltage" in codes(a)


def test_pathologic_q_inferior():
    # deep wide Q waves in II/III/aVF: build via negative-first template using axis -> use direct limb override
    L, r = sinus(70, noise=0.003)
    t = np.arange(len(L["II"])) / FS
    for lead in ("II", "III", "aVF"):
        for rt in r:
            L[lead] = L[lead] - 0.5 * np.exp(-0.5 * ((t - (rt - 0.03)) / 0.012) ** 2) - 0.0
            L[lead] = L[lead] - 0.0
    a = run(L)
    assert any(c.startswith("ecg.pathologic_q") for c in codes(a))


def test_degenerate_inputs_do_not_crash():
    a = run({"II": [0.0] * 5000})
    assert a.warnings
    a = run({"I": list(np.random.default_rng(0).normal(0, 0.01, 5000)),
             "II": list(np.random.default_rng(1).normal(0, 0.01, 5000))})
    assert a.global_measurements is not None


def test_limb_leads_derived_from_I_II():
    leads, _ = synth_signal(hr=70, noise_mv=0.005)
    sub = {k: leads[k] for k in ("I", "II", "V1", "V2", "V3", "V4", "V5", "V6")}
    a = run(sub)
    assert any("calculadas" in w for w in a.warnings)
    assert abs(a.global_measurements.qrs_axis_deg - 47) <= 15


def test_preexcitation_delta_wave():
    r = np.arange(0.45, 9.4, 60 / 70)
    L = make_ecg(r, r - 0.19, pd_ms=70, noise=0.005)
    t = np.arange(len(L["II"])) / FS
    gain = {"I": 0.5, "II": 1, "III": 0.5, "aVR": -0.9, "aVL": 0, "aVF": 0.8}
    for l in L:
        for rt in r:
            L[l] = L[l] + 0.35 * gain.get(l, 0.5) * np.exp(-0.5 * ((t - (rt - 0.045)) / 0.014) ** 2)
    a = run(L)
    assert a.global_measurements.pr_ms < 120
    assert a.global_measurements.qrs_ms >= 110
    assert "ecg.preexcitation" in codes(a)
