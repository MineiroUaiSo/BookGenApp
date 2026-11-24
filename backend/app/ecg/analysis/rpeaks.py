"""R-peak detection by multi-lead consensus (Pan-Tompkins-like, no external deps)."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks, sosfiltfilt, butter


def detect_r_peaks(amp: np.ndarray, fs: float):
    """amp: (L, n). Returns (peaks int array, ref_lead index)."""
    n = amp.shape[1]
    hi = min(20.0, 0.4 * fs)
    sos = butter(2, [5.0, hi], btype="bandpass", fs=fs, output="sos")
    bp = sosfiltfilt(sos, amp, axis=1)
    d = np.gradient(bp, axis=1) * fs
    e = (d ** 2).sum(0)
    mwi = uniform_filter1d(e, max(3, int(0.10 * fs)))
    cand, _ = find_peaks(mwi, distance=max(1, int(0.2 * fs)))
    if len(cand) == 0:
        return np.array([], int), 0
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
    return np.array(clean, int), ref_lead
