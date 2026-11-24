"""Ectopic-beat exclusion before the AF irregularity test.

A premature ventricular/atrial complex makes a regular rhythm look irregular. In true AF the QRS morphology
is the same for all beats (conducted through the normal pathway) while a PVC has a different morphology and
arrives early. A beat is ectopic when it is premature (RR before < 0.8 of the local median) AND its
waveform correlates poorly with the median beat (PVC), or when it is very premature with a compensatory pause.
Intervals touching an ectopic beat are dropped before CV/RMSSD/turning-point statistics.
"""
from __future__ import annotations

import numpy as np

PREMATURE = 0.80
CORR_MAX = 0.90
WIN_MS = 120.0


def beat_correlations(amp: np.ndarray, peaks: np.ndarray, fs: float, ref: int) -> np.ndarray:
    """Pearson correlation of each beat window (+-WIN_MS around R, all leads concatenated) with the median beat."""
    w = int(WIN_MS * fs / 1000)
    n = amp.shape[1]
    segs, ok = [], []
    for p in peaks:
        if p - w < 0 or p + w >= n:
            segs.append(None)
            continue
        segs.append(amp[:, p - w:p + w + 1].ravel())
        ok.append(len(segs) - 1)
    if len(ok) < 3:
        return np.ones(len(peaks))
    med = np.median(np.stack([segs[i] for i in ok]), axis=0)
    out = np.ones(len(peaks))
    for i in ok:
        s = segs[i]
        if s.std() < 1e-9 or med.std() < 1e-9:
            continue
        out[i] = float(np.corrcoef(s, med)[0, 1])
    return out


def ectopic_beats(peaks_ms, corr: np.ndarray) -> np.ndarray:
    """Boolean mask per beat. Premature + different morphology, or premature + compensatory pause."""
    pk = np.asarray(peaks_ms, float)
    mask = np.zeros(len(pk), bool)
    if len(pk) < 5:
        return mask
    rr = np.diff(pk)
    med = float(np.median(rr))
    for i in range(1, len(pk)):
        pre = rr[i - 1]
        if pre >= PREMATURE * med:
            continue
        post = rr[i] if i < len(rr) else None
        if corr[i] < CORR_MAX:
            mask[i] = True
        elif post is not None and pre < 0.7 * med and pre + post >= 1.8 * med:   # compensatory pause
            mask[i] = True
    return mask


def rr_irregularity_excl(peaks_ms, mask: np.ndarray) -> dict:
    """Same descriptors as rhythm.rr_irregularity but computed only on RR intervals between non-ectopic beats
    (intervals touching an ectopic beat are removed; successive differences only inside contiguous runs)."""
    pk = np.asarray(peaks_ms, float)
    rr = np.diff(pk)
    keep = ~(mask[:-1] | mask[1:])
    if keep.sum() < 3:
        return dict(cv=0.0, rmssd=0.0, tpr=0.0, dfrac=0.0, n_excluded=int(mask.sum()))
    m = float(rr[keep].mean())
    d, tp = [], []
    for i in range(1, len(rr)):
        if keep[i] and keep[i - 1]:
            d.append(rr[i] - rr[i - 1])
    for i in range(1, len(rr) - 1):
        if keep[i - 1] and keep[i] and keep[i + 1]:
            tp.append((rr[i] - rr[i - 1]) * (rr[i] - rr[i + 1]) > 0)
    d = np.array(d)
    return dict(cv=float(rr[keep].std() / m),
                rmssd=float(np.sqrt(np.mean(d ** 2)) / m) if len(d) else 0.0,
                tpr=float(np.mean(tp)) if tp else 0.0,
                dfrac=float(np.mean(np.abs(d) > 0.10 * m)) if len(d) else 0.0,
                n_excluded=int(mask.sum()))
