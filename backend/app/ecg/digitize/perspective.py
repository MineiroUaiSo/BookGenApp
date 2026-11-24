"""Perspective rectification from the printed grid itself (no paper contour needed).

When the sheet fills the frame there is no quad to warp, so a keystone (perspective) distortion and a small
rotation/shear remain. Here the 4 parameters (rotation, shear, 2 projective terms) are fitted so that the two
families of grid lines become straight, parallel and axis aligned: i.e. the vanishing points of the grid go to
infinity. The objective is the sharpness (variance) of the row / column projections of the high-passed grid
darkness map, evaluated on a down-scaled copy. The result is rejected (caller keeps the old behaviour) when the
fit is at a bound, barely improves on the identity, or is numerically unstable.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import minimize

try:  # opencv is optional
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

WORK_MAX = 900
CROP = 0.1
ROT_MAX_DEG = 8.0
SHEAR_MAX = 0.08
PROJ_MAX = 0.16  # projective terms are per normalised unit (image max side = 1)
MIN_GAIN = 1.08  # fitted score must beat the identity by this ratio


def homography(p, w: int, h: int) -> np.ndarray:
    """Pixel homography for params p = (rot_deg, shear, a, b), about the image centre."""
    rot, sh, a, b = p
    s0 = float(max(w, h))
    t = np.deg2rad(rot)
    R = np.array([[np.cos(t), -np.sin(t), 0], [np.sin(t), np.cos(t), 0], [0, 0, 1]])
    P = np.array([[1, sh, 0], [0, 1, 0], [a, b, 1.0]])
    T = np.array([[1 / s0, 0, -w / 2 / s0], [0, 1 / s0, -h / 2 / s0], [0, 0, 1.0]])
    return np.linalg.inv(T) @ R @ P @ T


def _score_map(d: np.ndarray, H: np.ndarray) -> float:
    h, w = d.shape
    r = cv2.warpPerspective(d, H, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    m = np.ones_like(d)
    rm = cv2.warpPerspective(m, H, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    y0, y1, x0, x1 = int(h * CROP), int(h * (1 - CROP)), int(w * CROP), int(w * (1 - CROP))
    r, rm = r[y0:y1, x0:x1], rm[y0:y1, x0:x1]
    if rm.mean() < 0.97:  # the crop must stay inside the warped image
        return -1.0
    return float(r.sum(0).var() + r.sum(1).var())


def _prep(rgb: np.ndarray) -> tuple[np.ndarray, float]:
    from .geometry import grid_darkness
    d = grid_darkness(rgb)
    sc = WORK_MAX / max(d.shape)
    if sc < 1:
        d = cv2.resize(d, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
    else:
        sc = 1.0
    d = d - ndi.gaussian_filter(d, 25)
    return np.ascontiguousarray(d.astype(np.float32)), sc


def fit_grid_homography(rgb: np.ndarray):
    """Return (H_fullres 3x3 | None, info). info: score gain, params, reason when rejected."""
    info: dict = {"ok": False}
    if cv2 is None:
        info["reason"] = "no-cv2"
        return None, info
    d, sc = _prep(rgb)
    h, w = d.shape
    ident = _score_map(d, np.eye(3))
    if ident <= 0:
        info["reason"] = "flat"
        return None, info
    # coarse search on rotation (cheap), then local refinement of all 4 parameters
    best, best_s = np.zeros(4), ident
    for rot in np.arange(-ROT_MAX_DEG, ROT_MAX_DEG + 1e-6, 1.0):
        s = _score_map(d, homography((rot, 0, 0, 0), w, h))
        if s > best_s:
            best, best_s = np.array([rot, 0, 0, 0.0]), s
    steps = np.array([0.7, 0.01, 0.02, 0.02])
    cur = best.copy()
    for _ in range(3):  # coordinate refinement with shrinking steps
        for _it in range(6):
            improved = False
            for k in range(4):
                for sgn in (1, -1):
                    cand = cur.copy()
                    cand[k] += sgn * steps[k]
                    s = _score_map(d, homography(cand, w, h))
                    if s > best_s * 1.0005:
                        cur, best_s, improved = cand, s, True
            if not improved:
                break
        steps = steps / 2.5
    res = minimize(lambda q: -_score_map(d, homography(q, w, h)), cur, method="Nelder-Mead",
                   options={"xatol": 1e-4, "fatol": 1e-6, "maxfev": 160,
                            "initial_simplex": np.vstack([cur] + [cur + np.eye(4)[k] * steps[k] * 2 for k in range(4)])})
    if -res.fun > best_s:
        cur, best_s = res.x, -res.fun
    gain = best_s / ident
    info.update(params=[float(v) for v in cur], gain=float(gain), score=float(best_s), ident=float(ident))
    rot, sh, a, b = cur
    if abs(rot) > ROT_MAX_DEG - 0.2 or abs(sh) > SHEAR_MAX or abs(a) > PROJ_MAX or abs(b) > PROJ_MAX:
        info["reason"] = "at-bound"
        return None, info
    if gain < MIN_GAIN:
        info["reason"] = "low-gain"
        return None, info
    H = homography(cur, w, h)  # in work pixels
    S = np.diag([sc, sc, 1.0])  # full-res -> work
    Hfull = np.linalg.inv(S) @ H @ S
    info["ok"] = True
    return Hfull, info


def apply_homography(rgb: np.ndarray, H: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    return cv2.warpPerspective(rgb, H, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)



GRID_CV_ABSTAIN = 0.09  # calibrated on PTB-XL dev renders (R2): ~2.5% of images lie above it


def _spacing_cv(profile: np.ndarray) -> float | None:
    """CV of the spacing between consecutive printed grid lines along one axis (None when too few lines)."""
    from scipy.signal import find_peaks
    from .grid import _autocorr
    x = profile.astype(np.float64)
    x = x - ndi.gaussian_filter1d(x, 40, mode="nearest")
    m = max(5, int(0.02 * len(x)))
    x[:m] = 0
    x[-m:] = 0
    ac = _autocorr(x)
    pk, _ = find_peaks(ac[: len(x) // 2], height=0.03)
    pk = [q for q in pk if q >= 3]
    if not pk:
        return None
    hs = {q: ac[q] for q in pk}
    hmax = max(hs.values())
    pitch = next(q for q in pk if hs[q] >= 0.4 * hmax)
    sm = ndi.gaussian_filter1d(x, max(0.6, pitch / 12))
    pos, _ = find_peaks(sm, distance=max(2, int(0.6 * pitch)), prominence=0.15 * np.std(sm) + 1e-9)
    if len(pos) < 8:
        return None
    d = np.diff(pos).astype(np.float64)
    return float(d.std() / d.mean())


def grid_spacing_cv(px: np.ndarray, py: np.ndarray) -> float | None:
    """Worst (max) spacing CV over the two grid axes; None if either axis cannot be measured."""
    cv = [_spacing_cv(px), _spacing_cv(py)]
    return None if any(v is None for v in cv) else float(max(cv))
