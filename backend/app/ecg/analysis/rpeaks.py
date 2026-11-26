"""R-peak detection by multi-lead consensus (Pan-Tompkins-like, no external deps)."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks, sosfiltfilt, butter


# E2 (R5): T-wave double-count guard. Applies only when the detected rate is implausibly fast.
TGUARD_HR_MIN = 150.0       # bpm: below this a doubled count is not suspected
TGUARD_MIN_PEAKS = 6
TGUARD_STRENGTH_RATIO = 0.85    # weak/strong median QRS-energy ratio that proves R-T alternation by strength
TGUARD_STRENGTH_RATIO_ASYM = 0.97   # looser ratio when the R->T offset is clearly not half a cycle (QT-like)
TGUARD_PAIR_CONSISTENCY = 0.8   # fraction of adjacent pairs where the strong parity beats the weak one
TGUARD_OFFSET_CV = 0.10         # R->weak-peak offset must be stable
TGUARD_OFFSET_ASYM = 0.10       # |offset / strong spacing - 0.5| for the looser strength ratio: true tachycardia sits at 0.5
TGUARD_OFFSET_MIN_ASYM = 0.05   # below this the peaks are symmetric: never dropped (real tachycardia, alternans)
TGUARD_OFFSET_S = (0.12, 0.50)  # plausible R->T-peak delay, seconds
TGUARD_REFRACTORY = 0.6         # x strong spacing: suppression radius for the weaker candidate


def _t_wave_guard(keep: np.ndarray, mwi: np.ndarray, fs: float):
    """Drop T waves counted as QRS. keep: candidate indices (sorted), mwi: QRS-energy curve.
    Returns (keep', unreliable). Rate <= 150 bpm or no R-T alternation: unchanged and not flagged.
    Alternation seen but not separable (equal strength, or still > 150 bpm): unchanged, unreliable=True."""
    if len(keep) < TGUARD_MIN_PEAKS or 60.0 * fs / float(np.median(np.diff(keep))) <= TGUARD_HR_MIN:
        return keep, False
    h = mwi[keep]
    med = [float(np.median(h[par::2])) for par in (0, 1)]
    strong = int(med[1] > med[0])
    ratio = med[1 - strong] / max(med[strong], 1e-12)
    idx = np.arange(len(keep))
    s_idx, w_idx = idx[idx % 2 == strong], idx[idx % 2 != strong]
    pairs = [(i, i + 1) if i % 2 == strong else (i + 1, i) for i in range(len(keep) - 1)]   # (strong, weak) members
    cons = float(np.mean([h[a] > h[b] for a, b in pairs]))
    spacing = float(np.median(np.diff(keep[s_idx]))) / fs
    prev = np.array([keep[w] - keep[w - 1] if w % 2 != strong and w > 0 and (w - 1) % 2 == strong else np.nan
                     for w in w_idx], float)
    prev = prev[~np.isnan(prev)] / fs
    if len(prev) < 3:
        return keep, False
    off = float(np.median(prev))
    cv = float(np.std(prev) / max(np.mean(prev), 1e-9))
    asym = abs(off / spacing - 0.5)
    t_like = TGUARD_OFFSET_S[0] <= off <= TGUARD_OFFSET_S[1] and cv <= TGUARD_OFFSET_CV and cons >= TGUARD_PAIR_CONSISTENCY
    if not t_like:
        return keep, False
    # symmetric peaks (offset ~ half a cycle) cannot be told from a real tachycardia / electrical alternans
    separable = asym >= TGUARD_OFFSET_MIN_ASYM and (
        ratio <= TGUARD_STRENGTH_RATIO or (asym >= TGUARD_OFFSET_ASYM and ratio <= TGUARD_STRENGTH_RATIO_ASYM))
    if not separable:
        return keep, ratio <= TGUARD_STRENGTH_RATIO or asym >= TGUARD_OFFSET_ASYM
    radius = TGUARD_REFRACTORY * spacing * fs
    order = np.argsort(-h, kind="stable")
    acc: list[int] = []
    for i in order:
        if all(abs(int(keep[i]) - a) >= radius for a in acc):
            acc.append(int(keep[i]))
    new = np.array(sorted(acc), int)
    still_fast = len(new) >= 3 and 60.0 * fs / float(np.median(np.diff(new))) > TGUARD_HR_MIN
    return new, bool(still_fast)


def detect_r_peaks(amp: np.ndarray, fs: float):
    """amp: (L, n). Returns (peaks int array, ref_lead index)."""
    peaks, ref, _ = detect_r_peaks_ex(amp, fs)
    return peaks, ref


def detect_r_peaks_ex(amp: np.ndarray, fs: float):
    """Same as detect_r_peaks plus `unreliable` (T-wave double count suspected but not resolvable)."""
    n = amp.shape[1]
    hi = min(20.0, 0.4 * fs)
    sos = butter(2, [5.0, hi], btype="bandpass", fs=fs, output="sos")
    bp = sosfiltfilt(sos, amp, axis=1)
    d = np.gradient(bp, axis=1) * fs
    e = (d ** 2).sum(0)
    mwi = uniform_filter1d(e, max(3, int(0.10 * fs)))
    cand, _ = find_peaks(mwi, distance=max(1, int(0.2 * fs)))
    if len(cand) == 0:
        return np.array([], int), 0, False
    h = mwi[cand]
    ref = float(np.percentile(h, 90))
    keep = cand[h >= 0.15 * ref]
    # fill long gaps with a lower threshold
    if len(keep) >= 3:
        rr = np.median(np.diff(keep))
        extra = []
        for a, b in zip(keep[:-1], keep[1:]):
            if b - a > 1.6 * rr:
                seg = (cand > a + 0.4 * rr) & (cand < b - 0.4 * rr) & (mwi[cand] >= 0.08 * ref)
                if seg.any():
                    extra.append(cand[seg][np.argmax(mwi[cand][seg])])
        if extra:
            keep = np.sort(np.concatenate([keep, extra]))
    keep, unreliable = _t_wave_guard(keep, mwi, fs)
    # ref lead: most positive R
    w = int(0.06 * fs)
    ref_scores = np.zeros(amp.shape[0])
    for k in keep:
        lo, hi_ = max(0, k - w), min(n, k + w + 1)
        b0, b1 = max(0, k - int(0.15 * fs)), min(n, k + int(0.15 * fs))
        ref_scores += amp[:, lo:hi_].max(1) - np.median(amp[:, b0:b1], axis=1)
    ref_lead = int(np.argmax(ref_scores))
    out = []
    for k in keep:
        lo, hi_ = max(0, k - w), min(n, k + w + 1)
        out.append(lo + int(np.argmax(amp[ref_lead, lo:hi_])))
    out = np.array(sorted(set(out)), int)
    # enforce refractory after refinement
    clean = []
    for k in out:
        if clean and k - clean[-1] < 0.2 * fs:
            if amp[ref_lead, k] > amp[ref_lead, clean[-1]]:
                clean[-1] = k
            continue
        clean.append(k)
    return np.array(clean, int), ref_lead, unreliable
