"""Pacemaker spike detector + paced-rhythm findings on synthetic 12-lead signals."""
from __future__ import annotations

import numpy as np
import pytest

from app.ecg.analysis import analyze_signal
from app.ecg.analysis.pacing import (blank_spikes, classify_pacing, detect_spikes, is_paced_timing,
                                     spike_timing)
from app.schemas import ECGSignal, SourceKind
from synth_ecg import synth_signal

FS = 500


def add_spikes(leads, times_s, fs=FS, amp=2.0, width_ms=2.0, sign=1.0):
    out = {k: v.copy() for k, v in leads.items()}
    w = max(1, int(round(width_ms * fs / 1000)))
    for t in times_s:
        i = int(round(t * fs))
        for j, k in enumerate(out):
            out[k][i:i + w] += sign * amp * (1.0 if j % 2 == 0 else 0.6)
    return out


def paced_ventricular(hr=70, seed=1, noise=0.01, delay_s=0.0):
    leads, fid = synth_signal(hr=hr, qrs_ms=160, noise_mv=noise, wander_mv=0.1, seed=seed)
    return add_spikes(leads, fid["qrs_on_s"] - 0.004 - delay_s), fid


def run(leads, fs=FS, seconds=10.0):
    sig = ECGSignal(fs=fs, leads={k: [float(x) for x in v] for k, v in leads.items()}, duration_s=seconds,
                    source=SourceKind.CSV)
    return analyze_signal(sig, "t")


def codes(a):
    return {f.code for f in a.findings}


def test_detects_spikes_near_each_qrs():
    leads, fid = paced_ventricular()
    X = np.stack([leads[k] for k in leads])
    s = detect_spikes(X, FS)
    assert len(s["idx"]) == len(fid["qrs_on_s"])
    exp = np.round((fid["qrs_on_s"] - 0.004) * FS)
    assert np.all(np.min(np.abs(s["idx"][:, None] - exp[None, :]), axis=1) <= 2)


def test_no_spikes_in_unpaced_signal():
    leads, _ = synth_signal(hr=70, qrs_ms=90, noise_mv=0.01, wander_mv=0.1, seed=2)
    X = np.stack([leads[k] for k in leads])
    assert len(detect_spikes(X, FS)["idx"]) == 0


def test_wide_qrs_without_spike_is_not_spike():
    leads, _ = synth_signal(hr=70, qrs_ms=160, noise_mv=0.02, seed=3)
    X = np.stack([leads[k] for k in leads])
    assert len(detect_spikes(X, FS)["idx"]) == 0


def test_single_lead_transient_is_rejected():
    leads, fid = synth_signal(hr=70, noise_mv=0.01, seed=4)
    leads["V2"] = leads["V2"].copy()
    leads["V2"][1000] += 3.0
    X = np.stack([leads[k] for k in leads])
    assert len(detect_spikes(X, FS)["idx"]) == 0


def test_timing_and_classification_ventricular():
    leads, fid = paced_ventricular()
    X = np.stack([leads[k] for k in leads])
    s = detect_spikes(X, FS)
    r = np.round(fid["r_peaks_s"] * FS).astype(int)
    t = spike_timing(s["idx"], r, FS)
    assert is_paced_timing(t)
    assert classify_pacing(t, 160.0, s["idx"], r, FS) == "ventricular"
    assert classify_pacing(t, 90.0, s["idx"], r, FS) is None


def test_atrial_pacing_classified_atrial():
    leads, fid = synth_signal(hr=70, qrs_ms=90, pr_ms=180, noise_mv=0.01, seed=5)
    lp = add_spikes(leads, fid["p_on_s"] - 0.01)
    X = np.stack([lp[k] for k in lp])
    s = detect_spikes(X, FS)
    r = np.round(fid["r_peaks_s"] * FS).astype(int)
    t = spike_timing(s["idx"], r, FS)
    assert is_paced_timing(t)
    assert classify_pacing(t, 90.0, s["idx"], r, FS) == "atrial"


def test_random_artifact_spikes_not_paced():
    leads, fid = synth_signal(hr=70, noise_mv=0.01, seed=6)
    rng = np.random.default_rng(0)
    lp = add_spikes(leads, rng.uniform(0.3, 9.5, 5))
    X = np.stack([lp[k] for k in lp])
    s = detect_spikes(X, FS)
    r = np.round(fid["r_peaks_s"] * FS).astype(int)
    assert not is_paced_timing(spike_timing(s["idx"], r, FS))


def test_blank_spikes_removes_peak():
    leads, fid = paced_ventricular()
    X = np.stack([leads[k] for k in leads])
    s = detect_spikes(X, FS)
    Y = blank_spikes(X, s["idx"], FS)
    assert len(detect_spikes(Y, FS)["idx"]) == 0
    assert np.abs(Y).max() < np.abs(X).max()


def test_paced_ventricular_end_to_end_suppresses_ischemia_and_bbb():
    leads, fid = paced_ventricular()
    leads = {k: v + (0.2 if k in ("V2", "V3") else 0.0) * 0 for k, v in leads.items()}
    a = run(leads)
    c = codes(a)
    assert "ecg.paced_rhythm" in c
    f = [x for x in a.findings if x.code == "ecg.paced_rhythm"][0]
    assert "sugestivo" in f.label.lower()
    assert not any(x.startswith(("ecg.st_elevation_", "ecg.st_depression_", "ecg.pathologic_q_",
                                 "ecg.lbbb", "ecg.rbbb", "ecg.irbbb", "ecg.ilbbb", "ecg.t_inversion_")) for x in c)
    assert "ecg.sinus_rhythm" not in c and "ecg.within_normal_limits" not in c


def test_unpaced_signal_has_no_paced_finding():
    leads, _ = synth_signal(hr=70, qrs_ms=90, noise_mv=0.01, wander_mv=0.1, seed=2)
    assert "ecg.paced_rhythm" not in codes(run(leads))
