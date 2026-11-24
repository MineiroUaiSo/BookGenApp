"""Ectopic-beat exclusion before the AF irregularity test."""
from __future__ import annotations

import numpy as np

from app.ecg.analysis.ectopy import beat_correlations, ectopic_beats, rr_irregularity_excl
from app.ecg.analysis.rhythm import rr_irregularity
from app.schemas import ECGSignal, SourceKind
from app.ecg.analysis import analyze_signal
from synth_ecg import synth_signal

FS = 500


def _peaks(rr):
    return np.concatenate([[0.0], np.cumsum(rr)])


def test_ectopic_mask_flags_premature_low_correlation_beat():
    pk = _peaks([800, 800, 800, 480, 1120, 800, 800, 800])
    corr = np.ones(len(pk))
    corr[4] = 0.5
    assert ectopic_beats(pk, corr).tolist() == [False] * 4 + [True] + [False] * 4


def test_ectopic_mask_ignores_premature_beat_with_same_morphology_without_pause():
    pk = _peaks([800, 800, 800, 560, 800, 800, 800, 800])
    assert not ectopic_beats(pk, np.ones(len(pk))).any()


def test_excluding_ectopic_beats_removes_irregularity_of_regular_rhythm():
    pk = _peaks([800, 800, 480, 1120, 800, 800, 480, 1120, 800, 800])
    corr = np.ones(len(pk))
    corr[3] = corr[7] = 0.4
    mask = ectopic_beats(pk, corr)
    raw, ex = rr_irregularity(pk), rr_irregularity_excl(pk, mask)
    assert raw["cv"] > 0.15 and ex["cv"] < 0.05 and ex["n_excluded"] == 2


def test_true_af_keeps_irregularity_when_morphology_is_constant():
    rng = np.random.default_rng(3)
    pk = _peaks(rng.uniform(450, 1100, 14))
    mask = ectopic_beats(pk, np.ones(len(pk)))   # identical morphology: no beat is ectopic
    assert not mask.any()
    assert rr_irregularity_excl(pk, mask)["cv"] > 0.2 or rr_irregularity(pk)["cv"] > 0.2


def test_beat_correlation_low_for_inverted_wide_beat():
    leads, fid = synth_signal(hr=60, noise_mv=0.005, seed=1)
    amp = np.stack([leads[k] for k in leads])
    r = np.round(fid["r_peaks_s"] * FS).astype(int)
    i = r[3]
    amp[:, i - 40:i + 41] *= -1.0
    c = beat_correlations(amp, r, FS, 1)
    assert c[3] < 0.5 and np.delete(c, 3).min() > 0.95


def test_regular_rhythm_with_pvcs_is_not_af():
    leads, fid = synth_signal(hr=60, noise_mv=0.005, seed=1)
    t = np.arange(len(leads["I"])) / FS
    for rt in fid["r_peaks_s"][[3, 6]]:
        pvc = -1.2 * np.exp(-0.5 * ((t - (rt + 0.45)) / 0.045) ** 2)
        for k in leads:
            leads[k] = leads[k] + pvc
    sig = ECGSignal(fs=FS, leads={k: [float(x) for x in v] for k, v in leads.items()}, duration_s=10.0,
                    source=SourceKind.CSV)
    codes = {x.code for x in analyze_signal(sig, "t").findings}
    assert "ecg.atrial_fibrillation" not in codes
