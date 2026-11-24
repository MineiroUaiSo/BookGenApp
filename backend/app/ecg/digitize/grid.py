"""Grid / trace separation and grid-pitch (px per mm) estimation."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from scipy.signal import find_peaks

from .geometry import _otsu


def normalise(rgb: np.ndarray) -> np.ndarray:
    """Per-channel division by an estimated paper background -> float32 0..~1.2."""
    f = rgb.astype(np.float32)
    out = np.empty_like(f)
    h, w = f.shape[:2]
    for c in range(3):
        ch = f[..., c]
        small = ch[::4, ::4]
        bg = ndi.gaussian_filter(ndi.maximum_filter(small, size=9), 3)
        bg = ndi.zoom(bg, 4, order=1)
        bg = np.pad(bg, ((0, max(0, h - bg.shape[0])), (0, max(0, w - bg.shape[1]))), mode="edge")[:h, :w]
        out[..., c] = ch / np.maximum(bg, 1.0)
    return out


def _masked_median(v: np.ndarray, axis: int, lim: float = 0.62) -> np.ndarray:
    """Median along `axis` ignoring pixels darker than `lim` (trace/text); NaN-filled gaps are interpolated."""
    m = np.where(v < lim, np.nan, v)
    with np.errstate(all="ignore"):
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("ignore")
            med = np.nanmedian(m, axis=axis)
    n = len(med)
    ok = np.isfinite(med)
    if ok.sum() < 3:
        return np.ones(n, np.float32)
    return np.interp(np.arange(n), np.nonzero(ok)[0], med[ok]).astype(np.float32)


def flatten(norm: np.ndarray) -> np.ndarray:
    """V (max over channels, 0..1 paper) with the printed grid divided out: the grid is a (near) separable
    product of a per-column and a per-row factor. Dark vertical lines then vanish while the trace stays dark."""
    v = norm.max(2).astype(np.float32)
    cm = _masked_median(v, 0)
    rm = _masked_median(v, 1)
    base = float(np.median(v))
    cmn = np.clip(cm / base, 0.6, 1.3)
    rmn = np.clip(rm / base, 0.6, 1.3)
    return np.clip(v / (cmn[None, :] * rmn[:, None]), 0, 1.3)


def trace_mask(norm: np.ndarray) -> np.ndarray:
    """Dark ink (trace/text) after grid flattening. Red/pink/orange grid keeps high V."""
    v = flatten(norm)
    thr = float(np.clip(_otsu(v[::2, ::2].ravel()), 0.5, 0.85))
    core = v < thr
    # QRS strokes are thin and anti-aliased: bridge short vertical breaks and take the fainter fringe that touches ink
    loose = v < min(thr + 0.08, 0.92)
    bridged = ndi.binary_closing(core, structure=np.ones((5, 1), bool))
    fringe = ndi.binary_dilation(bridged, structure=np.ones((3, 3), bool)) & loose
    return bridged | fringe


def grid_profiles(norm: np.ndarray, ink: np.ndarray):
    g = np.clip(1 - norm[..., 1], 0, 0.6)
    ink_d = ndi.binary_dilation(ink, iterations=3)
    g = np.where(ink_d, 0, g)
    valid = (~ink_d).astype(np.float32)
    # row profile: mean over valid columns
    py = g.sum(1) / np.maximum(valid.sum(1), 1)
    px = g.sum(0) / np.maximum(valid.sum(0), 1)
    return py, px


def _autocorr(x: np.ndarray) -> np.ndarray:
    n = len(x)
    f = np.fft.rfft(x, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    return ac / max(ac[0], 1e-12)


def estimate_pitch(profile: np.ndarray, min_pitch: float = 3.0):
    """Return (pitch_px of the 1 mm small square, confidence 0..1) from a 1-D grid profile."""
    x = profile.astype(np.float64)
    x = x - ndi.gaussian_filter1d(x, 40, mode="nearest")
    # drop the borders (rim artefacts)
    m = max(5, int(0.02 * len(x)))
    x[:m] = 0
    x[-m:] = 0
    ac = _autocorr(x)
    maxlag = len(x) // 2
    pk, props = find_peaks(ac[:maxlag], height=0.03)
    pk = [p for p in pk if p >= min_pitch]
    if not pk:
        return None, 0.0, None, None
    hs = {p: ac[p] for p in pk}
    hmax = max(hs.values())
    L = next(p for p in pk if hs[p] >= 0.4 * hmax)
    # N = number of pitches across the profile: 1 mm pitch -> N >~ 100 (a page is >100 mm), 5 mm pitch -> N <~ 65.
    bold = len(x) / L < 80
    # refine: regression on detected line positions (5 mm bold lines if the small ones are faint)
    unit = 5.0 if bold else 1.0
    p0 = float(L)
    sm = ndi.gaussian_filter1d(x, max(0.6, p0 / 12))
    pos, _ = find_peaks(sm, distance=max(2, int(0.6 * p0)), prominence=0.15 * np.std(sm) + 1e-9)
    pitch = p0
    mm_of_px = np.poly1d([unit / p0, 0.0])
    px_of_mm = np.poly1d([p0 / unit, 0.0])
    conf = float(min(1.0, ac[L] / 0.5))
    if len(pos) >= 10:
        pos = pos.astype(np.float64)
        idx = np.round((pos - pos[0]) / pitch)
        for _ in range(5):
            A = np.stack([idx, np.ones_like(idx)], 1)
            coef, *_ = np.linalg.lstsq(A, pos, rcond=None)
            res = pos - A @ coef
            keep = np.abs(res) < 0.2 * coef[0]
            if keep.sum() < 8:
                break
            pos, idx = pos[keep], idx[keep]
            coef, *_ = np.linalg.lstsq(np.stack([idx, np.ones_like(idx)], 1), pos, rcond=None)
            pitch = float(coef[0])
            idx = np.round((pos - coef[1]) / pitch)
        if len(pos) >= 8:
            deg = 2 if len(pos) >= 15 else 1
            mm = idx * unit
            mm_of_px = np.poly1d(np.polyfit(pos, mm, deg))
            px_of_mm = np.poly1d(np.polyfit(mm, pos, deg))
            # mean pitch over the span (robust to the quadratic term)
            span = pos.max() - pos.min()
            pitch = span / ((mm.max() - mm.min()) / unit)
    else:
        conf *= 0.5
    mean_ppm = pitch / unit
    return mean_ppm, conf, mm_of_px, px_of_mm


def rr_lag_px(ink: np.ndarray):
    """Dominant beat period (px) from the column-wise ink extent (works for multi-row pages); None if weak."""
    c = ink.sum(0).astype(np.float64)
    if c.sum() < 50:
        return None
    c = c - ndi.gaussian_filter1d(c, max(6, len(c) // 40))
    ac = _autocorr(c)
    n = len(ac) // 2
    pk, _ = find_peaks(ac[:n], height=0.08)
    pk = [p for p in pk if p >= 6]
    return float(pk[0]) if pk else None


def plausible_scale(ppm: float, lag_px, speed: float = 25.0, lo: float = 0.25, hi: float = 2.6):
    if lag_px is None:
        return None
    rr = lag_px / (ppm * speed)
    return lo <= rr <= hi


def detect_grid(norm: np.ndarray, ink: np.ndarray):
    """Return dict(px_per_mm_x/y, confidence, map_x/map_y (numpy poly1d pairs)).
    Square grid assumption: a y estimate that disagrees with x (trace rows pollute the y profile) is replaced."""
    py, px = grid_profiles(norm, ink)
    ph, ch, mh, ih = estimate_pitch(py)
    pw, cw, mw, iw = estimate_pitch(px)
    res = {"px_per_mm_y": ph, "px_per_mm_x": pw, "confidence": min(ch, cw)}
    if ph and pw:
        ratio = ph / pw
        if 0.87 < ratio < 1.15:
            res.update(map_x=(mw, iw), map_y=(mh, ih))
        else:  # inconsistent -> trust the axis with the higher confidence (x on ties), mirror to the other
            if ch > cw + 0.15:
                v, m, i, c = ph, mh, ih, ch
            else:
                v, m, i, c = pw, mw, iw, cw
            res.update(px_per_mm_x=v, px_per_mm_y=v, map_x=(m, i), map_y=(m, i), confidence=c * 0.6)
    elif ph or pw:
        v, m, i = (ph, mh, ih) if ph else (pw, mw, iw)
        res.update(px_per_mm_x=v, px_per_mm_y=v, map_x=(m, i), map_y=(m, i), confidence=res["confidence"] * 0.5)
    return res
