"""Pacemaker spike detection on the RAW signal (before the 150 Hz low-pass) and paced-rhythm classification.

A pacing stimulus is a rectangular pulse of 0.5-2 ms: after a 100 Hz high-pass it is the largest
narrow event of the record, present in several leads at the same sample, and it sits at a fixed delay
before the paced chamber's depolarisation (ventricular: spike -> wide QRS; atrial: spike -> P -> narrow QRS).
Without that timing relation, an isolated narrow transient is not called a spike.
References: AHA/ACCF/HRS 2009 ECG standardization Part I (pacemaker ECG); Goldberger 10th ed.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks, sosfiltfilt, butter

HP_HZ = 100.0
STRICT = dict(k_sigma=10.0, min_mv=0.05, min_leads=3)
RELAXED = dict(k_sigma=5.0, min_mv=0.02, min_leads=3)
MAX_WIDTH_MS = 6.0
LOOKBACK_MS = 250.0
VENT_DELAY_MS = 90.0     # spike -> R peak up to this = ventricular capture (wide QRS)
MIN_QRS_PACED_MS = 100.0


def _empty() -> dict:
    return dict(idx=np.array([], int), amp=np.array([]), n_leads=np.array([], int))


def detect_spikes(x: np.ndarray, fs: float, k_sigma: float = 10.0, min_mv: float = 0.05,
                  min_leads: int = 3) -> dict:
    """x: (L, n) RAW mV. Returns dict(idx, amp, n_leads): sample index, mean z-score of the high-passed
    trace and number of leads where the narrow event exceeds its threshold. Needs fs >= 250 Hz."""
    x = np.asarray(x, float)
    if fs < 250 or x.shape[1] < int(1.0 * fs):
        return _empty()
    h = np.abs(sosfiltfilt(butter(4, min(HP_HZ, 0.4 * fs), btype="highpass", fs=fs, output="sos"), x, axis=1))
    sig = 1.4826 * np.median(h, axis=1, keepdims=True) + 1e-9
    thr = np.maximum(k_sigma * sig, min_mv)
    over = h >= thr                                   # (L, n)
    width = max(1, int(round(0.003 * fs)))            # +-3 ms tolerance between leads
    cnt = np.zeros(x.shape[1], int)
    for l in range(x.shape[0]):
        o = over[l].astype(float)
        cnt += (np.convolve(o, np.ones(2 * width + 1), mode="same") > 0).astype(int)
    z = (h / thr).sum(0)
    ok = cnt >= min(min_leads, x.shape[0])
    if not ok.any():
        return _empty()
    score = np.where(ok, z, 0.0)
    pk, _ = find_peaks(score, distance=max(1, int(0.02 * fs)))
    pk = pk[score[pk] > 0]
    keep = []
    hm = h.max(0)
    for p in pk:   # reject broad events (QRS slopes, motion): the half-maximum width must be narrow
        seg = hm[max(0, p - int(0.02 * fs)):p + int(0.02 * fs) + 1]
        if (seg >= 0.5 * hm[p]).sum() * 1000.0 / fs <= MAX_WIDTH_MS:
            keep.append(p)
    keep = np.array(keep, int)
    return dict(idx=keep, amp=score[keep] if len(keep) else np.array([]), n_leads=cnt[keep] if len(keep) else np.array([], int))


def spike_timing(spikes_idx: np.ndarray, r_idx: np.ndarray, fs: float) -> dict:
    """Relation of spikes to R peaks: for each R the nearest spike 0..LOOKBACK_MS before it.
    Returns dict(frac = beats with a spike, delays_ms = list, sd_ms, n_spikes, ratio = spikes/beats)."""
    s = np.asarray(spikes_idx, float) * 1000.0 / fs
    r = np.asarray(r_idx, float) * 1000.0 / fs
    delays = []
    for rt in r:
        c = s[(s <= rt + 10.0) & (s >= rt - LOOKBACK_MS)]
        if len(c):
            delays.append(float(rt - c[-1]))
    nb = max(1, len(r))
    return dict(frac=len(delays) / nb, delays_ms=delays, n_spikes=int(len(s)), ratio=len(s) / nb,
                sd_ms=float(np.std(delays)) if len(delays) >= 2 else float("inf"))


def is_paced_timing(t: dict, frac_min: float = 0.6, sd_max: float = 12.0, ratio_max: float = 3.0) -> bool:
    """Spikes are real pacing only if most beats are preceded by one at a stable delay and there are not
    many more spikes than beats (artifact bursts)."""
    return bool(t["n_spikes"] >= 2 and len(t["delays_ms"]) >= 2 and t["frac"] >= frac_min
                and t["sd_ms"] <= sd_max and t["ratio"] <= ratio_max)


def classify_pacing(t: dict, qrs_ms: float | None, spikes_idx: np.ndarray, r_idx: np.ndarray, fs: float) -> str | None:
    """'ventricular' | 'atrial' | 'dual' | None (call only when is_paced_timing)."""
    s = np.asarray(spikes_idx, float) * 1000.0 / fs
    r = np.asarray(r_idx, float) * 1000.0 / fs
    near_v = near_a = 0
    for rt in r:
        c = rt - s[(s <= rt + 10.0) & (s >= rt - LOOKBACK_MS)]
        if (c <= VENT_DELAY_MS).any():
            near_v += 1
        if ((c > 110.0) & (c <= LOOKBACK_MS)).any():
            near_a += 1
    nb = max(1, len(r))
    v, a = near_v / nb >= 0.6, near_a / nb >= 0.6
    wide = qrs_ms is not None and qrs_ms >= MIN_QRS_PACED_MS
    if v and a:
        return "dual"
    if v and wide:
        return "ventricular"
    if a and not wide:
        return "atrial"
    return None   # narrow QRS right after the spike: not a paced ventricle


def blank_spikes(x: np.ndarray, idx: np.ndarray, fs: float, half_ms: float = 3.0) -> np.ndarray:
    """Linear interpolation across each spike so that the low-pass/delineation do not see a fake QRS onset."""
    y = np.array(x, float, copy=True)
    h = max(1, int(round(half_ms * fs / 1000)))
    n = y.shape[1]
    for p in idx:
        a, b = max(0, int(p) - h), min(n - 1, int(p) + h)
        if b - a < 2:
            continue
        for l in range(y.shape[0]):
            y[l, a:b + 1] = np.linspace(y[l, a], y[l, b], b - a + 1)
    return y
