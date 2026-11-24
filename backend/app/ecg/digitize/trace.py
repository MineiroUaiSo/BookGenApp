"""Layout detection and column-wise trace extraction (dynamic-programming continuity tracking)."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from scipy.signal import find_peaks

LAYOUT_LEADS = {
    "3x4+1": [["I", "II", "III"], ["aVR", "aVL", "aVF"], ["V1", "V2", "V3"], ["V4", "V5", "V6"]],  # columns
    "3x4": [["I", "II", "III"], ["aVR", "aVL", "aVF"], ["V1", "V2", "V3"], ["V4", "V5", "V6"]],
    "6x2": [["I", "II", "III", "aVR", "aVL", "aVF"], ["V1", "V2", "V3", "V4", "V5", "V6"]],
    "12x1": [["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]],
}
STRIP_NAMES = ["II", "V1", "V5", "I", "III", "aVF", "V2", "V3", "V4", "V6", "aVL", "aVR"]
ROWS_TO_LAYOUT = {3: "3x4", 4: "3x4+1", 6: "6x2", 12: "12x1"}


def clean_ink(ink: np.ndarray, ppm_x: float, ppm_y: float) -> np.ndarray:
    """Remove page border, specks and small text-like blobs."""
    ink = ink.copy()
    bx, by = int(1.5 * ppm_x), int(1.5 * ppm_y)
    ink[:by] = False
    ink[-by:] = False
    ink[:, :bx] = False
    ink[:, -bx:] = False
    lab, n = ndi.label(ink, structure=np.ones((3, 3)))
    if n == 0:
        return ink
    objs = ndi.find_objects(lab)
    keep = np.zeros(n + 1, bool)
    for i, sl in enumerate(objs, 1):
        hh = (sl[0].stop - sl[0].start) / ppm_y
        ww = (sl[1].stop - sl[1].start) / ppm_x
        if ww < 4.5 and hh < 7.0 and not (hh > 9 and ww < 2.5):  # text glyph / speck
            continue
        keep[i] = True
    return keep[lab]


def remove_grid_lines(ink: np.ndarray, ppm_x: float, ppm_y: float) -> np.ndarray:
    """Dark printed grid lines (bold 5 mm lines in grey scans) survive the ink threshold. A grid line is a
    thin full-height (or full-width) streak; the trace covers only a few rows per column. Columns/rows whose ink
    coverage is far above the local median are cleared where the run is thin (<= 4 px)."""
    ink = ink.copy()
    frac = ink.mean(0)
    med = ndi.median_filter(frac, size=int(max(9, 6 * ppm_x)), mode="nearest")
    bad = (frac > 0.5) & (frac > med + 0.35)
    lab, k = ndi.label(bad)
    runs = [np.nonzero(lab == i)[0] for i in range(1, k + 1)]
    runs = [r for r in runs if len(r) <= 4]
    if len(runs) >= 3:  # a grid, not a QRS: several thin full-height streaks
        for r in runs:
            ink[:, r] = False
    return ink


def detect_rows(ink: np.ndarray, xa: int, xb: int, ppm_y: float):
    prof = ink[:, xa:xb].sum(1).astype(np.float64)
    sm = ndi.gaussian_filter1d(prof, 2.5 * ppm_y)
    pk, _ = find_peaks(sm, distance=int(11 * ppm_y), height=0.25 * sm.max())
    # refine each baseline with a narrow window on the raw profile
    fine = ndi.gaussian_filter1d(prof, 0.6 * ppm_y)
    rows = []
    for p in pk:
        lo, hi = max(0, int(p - 3 * ppm_y)), int(p + 3 * ppm_y)
        rows.append(lo + int(np.argmax(fine[lo:hi])))
    return rows


def find_pulse(ink: np.ndarray, y_base: float, xs_left: int, ppm_x: float, ppm_y: float, band: float):
    """Detect calibration pulse near the left end of one row.
    Returns dict(height_mm, width_mm, x_end) or None."""
    y0, y1 = int(max(0, y_base - band)), int(min(ink.shape[0], y_base + band))
    x0, x1 = xs_left, xs_left + int(14 * ppm_x)
    sub = ink[y0:y1, x0:x1]
    if sub.size == 0 or not sub.any():
        return None
    top = np.where(sub.any(0), sub.argmax(0), -1).astype(np.float64)  # first ink row per column
    bot = np.where(sub.any(0), sub.shape[0] - 1 - sub[::-1].argmax(0), -1).astype(np.float64)
    ok = top >= 0
    yref = y_base - y0
    cand = ok & ((yref - top) > 2.0 * ppm_y) & ((bot - top) < 1.2 * ppm_y)  # thin horizontal line above baseline
    # largest run of cand columns with near-constant top
    best = None
    i = 0
    n = len(cand)
    while i < n:
        if not cand[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and cand[j + 1] and abs(top[j + 1] - top[i]) <= 0.35 * ppm_y:
            j += 1
        if best is None or (j - i) > (best[1] - best[0]):
            best = (i, j)
        i = j + 1
    if best is None:
        return None
    i, j = best
    wmm = (j - i + 1) / ppm_x
    if wmm < 2.5:
        return None
    thick = float(np.median((bot - top + 1)[i:j + 1]))
    y_plat = float(np.median(top[i:j + 1]) + thick / 2)
    foot = np.arange(0, max(0, i - int(thick) - 2))
    foot = foot[ok[foot]] if len(foot) else foot
    if len(foot) >= 3:
        y_f = float(np.median((top[foot] + bot[foot]) / 2))
    else:  # no foot visible: baseline right after the falling edge
        aft = np.arange(j + int(0.4 * ppm_x) + 2, min(n, j + int(1.6 * ppm_x) + 2))
        aft = aft[ok[aft]] if len(aft) else aft
        if len(aft) == 0:
            return None
        y_f = float(np.median((top[aft] + bot[aft]) / 2))
    hmm = (y_f - y_plat) / ppm_y
    # falling edge centre = plateau end + half thickness; rising stroke start
    return dict(height_mm=hmm, width_mm=wmm + thick / ppm_x, x_end=x0 + j + thick / 2.0,
                x_start=x0 + i, thick=thick)


def extract_row(ink: np.ndarray, xa: int, xb: int, y_base: float, half_band: int, ppm_y: float):
    """DP column tracking. Returns arrays (len xb-xa): centre y (NaN missing), top, bottom, valid mask."""
    y0 = int(max(0, y_base - half_band))
    y1 = int(min(ink.shape[0], y_base + half_band))
    B = ink[y0:y1, xa:xb]
    h, w = B.shape
    pad = np.zeros((h + 2, w), np.int8)
    pad[1:-1] = B
    d = np.diff(pad, axis=0)
    cs, rs = np.nonzero((d == 1).T)
    ce, re_ = np.nonzero((d == -1).T)
    # runs per column
    starts = [[] for _ in range(w)]
    ends = [[] for _ in range(w)]
    for c, r in zip(cs, rs):
        starts[c].append(r)
    for c, r in zip(ce, re_):
        ends[c].append(r - 1)
    yb = y_base - y0
    pm = ppm_y
    # DP
    cols = [c for c in range(w) if starts[c]]
    if not cols:
        nan = np.full(w, np.nan)
        return nan, nan.copy(), nan.copy(), np.zeros(w, bool)
    cand = []
    for c in cols:
        t = np.array(starts[c], float)
        b = np.array(ends[c], float)
        cand.append((t, b, (t + b) / 2))
    prev_cost = None
    back = []
    prev_c = None
    for k, c in enumerate(cols):
        t, b, ctr = cand[k]
        node = 0.02 * np.abs(ctr - yb) / pm
        if prev_cost is None:
            cost = node
            bp = np.zeros(len(t), int)
        else:
            pt, pb, pc = cand[k - 1]
            g = c - prev_c
            gap = np.maximum(0, np.maximum(t[None, :] - pb[:, None], pt[:, None] - b[None, :])) / pm  # mm
            trans = gap / (1 + 0.5 * (g - 1)) + 0.02 * np.abs(ctr[None, :] - pc[:, None]) / pm
            tot = prev_cost[:, None] + trans
            bp = np.argmin(tot, 0)
            cost = tot[bp, np.arange(len(t))] + node
        back.append(bp)
        prev_cost = cost
        prev_c = c
    idx = int(np.argmin(prev_cost))
    sel = [0] * len(cols)
    for k in range(len(cols) - 1, -1, -1):
        sel[k] = idx
        idx = back[k][idx]
    cen = np.full(w, np.nan)
    top = np.full(w, np.nan)
    bot = np.full(w, np.nan)
    valid = np.zeros(w, bool)
    prev_i = None
    for k, c in enumerate(cols):
        t, b, ctr = cand[k]
        j = sel[k]
        cen[c], top[c], bot[c] = ctr[j], t[j], b[j]
        valid[c] = True
        if prev_i is not None:
            pt, pb, pc = cand[k - 1]
            jj = sel[k - 1]
            gap = max(0.0, max(t[j] - pb[jj], pt[jj] - b[j])) / pm
            if gap > 3.0:  # discontinuity -> not confident
                valid[c] = False
        if (b[j] - t[j]) > 0.9 * half_band:
            valid[c] = False
        prev_i = j
    return cen + y0, top + y0, bot + y0, valid


def refine_extrema(cen, top, bot, thick):
    """At local maxima/minima use the run's extreme edge instead of its centre (sharp R/S tips)."""
    y = cen.copy()
    n = len(y)
    idx = np.nonzero(~np.isnan(cen))[0]
    if len(idx) < 3:
        return y
    c = cen[idx]
    for q in range(1, len(idx) - 1):
        i = idx[q]
        run = bot[i] - top[i] + 1
        if run <= 1.5 * thick:
            continue
        if c[q] <= c[q - 1] and c[q] <= c[q + 1]:  # screen-up peak
            y[i] = top[i] + thick / 2
        elif c[q] >= c[q - 1] and c[q] >= c[q + 1]:
            y[i] = bot[i] - thick / 2
    return y


def classify_triplet(rows: list[np.ndarray]):
    """Identify what three simultaneously recorded rows are, from physics alone (no lead labels needed):
    I,II,III obey II = I + III (Einthoven); aVR,aVL,aVF sum to zero (Goldberger); anything else is a chest triplet.
    Scores are the residual of the correct relation divided by that of the sign/row-permuted wrong ones
    (<< 1 means the relation holds). Returns (einthoven_ratio, goldberger_ratio, median R/S ratio)."""
    r = [np.asarray(x, float) for x in rows]
    r = [x - ndi.median_filter(x, size=max(3, int(0.7 * 500) | 1), mode="nearest") for x in r]  # baseline wander out
    n = min(len(x) for x in r)
    a, b, c = (x[:n] for x in r)
    nz = lambda v: float(np.linalg.norm(v)) + 1e-9
    ein = nz(b - a - c) / min(nz(a - b - c), nz(c - a - b), nz(a + b + c), nz(b - a + c))
    gold = nz(a + b + c) / min(nz(a + b - c), nz(a - b + c), nz(-a + b + c))
    rs = []
    for x in (a, b, c):
        hi, lo = float(np.percentile(x, 99.5)), float(np.percentile(x, 0.5))
        rs.append(hi / max(abs(lo), 1e-6))
    return float(ein), float(gold), float(np.median(rs))


def assign_triplets(cols_rows: list[list[np.ndarray]]):
    """cols_rows[c] = three row signals of column c. Returns a lead-name triplet per column; columns without clear
    evidence keep the standard order (I-III, aVR-aVF, V1-V3, V4-V6)."""
    LIMB, AVR = ["I", "II", "III"], ["aVR", "aVL", "aVF"]
    std = [LIMB, AVR, ["V1", "V2", "V3"], ["V4", "V5", "V6"]]
    kinds = []
    for rows in cols_rows:
        einth, gold, rs = classify_triplet(rows)
        if einth < 0.45 and einth <= gold:
            kinds.append("limb")
        elif gold < 0.45:
            kinds.append("avr")
        elif min(einth, gold) > 0.75:
            kinds.append(("chest", rs))
        else:
            kinds.append(None)
    out = []
    n_chest = sum(1 for k in kinds if isinstance(k, tuple))
    seen_chest = 0
    for c, k in enumerate(kinds):
        if k == "limb":
            out.append(LIMB)
        elif k == "avr":
            out.append(AVR)
        elif k is None:
            out.append(std[min(c, 3)])
        else:
            if n_chest == 1:
                out.append(["V4", "V5", "V6"] if k[1] > 1.2 and c > 0 else ["V1", "V2", "V3"])
            else:
                out.append(["V1", "V2", "V3"] if seen_chest == 0 else ["V4", "V5", "V6"])
            seen_chest += 1
    return out

