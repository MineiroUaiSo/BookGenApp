"""Classical (no-ML) segmentation fallbacks. All inputs are float 0..1 at working res.

Orientation convention for frontal chest: standard display, patient's RIGHT on image LEFT.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy import ndimage as ndi
from skimage.feature import hessian_matrix
from skimage.filters import gaussian, sato, threshold_multiotsu, threshold_otsu
from skimage.measure import label, regionprops
from skimage.morphology import closing as _closing, convex_hull_image, disk, opening as _opening


def bopen(m: np.ndarray, se) -> np.ndarray:
    return _opening(m.astype(np.uint8), se).astype(bool)


def bclose(m: np.ndarray, se) -> np.ndarray:
    return _closing(m.astype(np.uint8), se).astype(bool)


def rm_small(m: np.ndarray, n: int) -> np.ndarray:
    lab = label(m)
    if lab.max() == 0:
        return m
    counts = np.bincount(lab.ravel())
    keep = counts >= n
    keep[0] = False
    return keep[lab]


def smooth(g: np.ndarray) -> np.ndarray:
    return gaussian(g, sigma=max(1.0, max(g.shape) / 256.0))


def _largest(mask: np.ndarray) -> np.ndarray:
    lab = label(mask)
    if lab.max() == 0:
        return mask
    counts = np.bincount(lab.ravel())
    counts[0] = 0
    return lab == counts.argmax()


def _clean(mask: np.ndarray, r: int) -> np.ndarray:
    m = bclose(mask, disk(r))
    m = ndi.binary_fill_holes(m)
    return bopen(m, disk(max(1, r // 2)))


def dark_components(s: np.ndarray, min_area_frac: float = 0.015):
    """Dark, non-border-connected, central components. Returns (list of regionprops, lab, threshold)."""
    H, W = s.shape
    y0, y1, x0, x1 = int(.05 * H), int(.95 * H), int(.08 * W), int(.92 * W)
    crop = s[y0:y1, x0:x1]
    if crop.std() < 1e-4:
        return [], None, 0.0
    t = threshold_otsu(crop)
    dark = s < t
    r = max(1, int(round(0.006 * max(H, W))))
    dark = bopen(dark, disk(r))
    lab = label(dark)
    cands = []
    for rp in regionprops(lab):
        if rp.area < min_area_frac * H * W:
            continue
        minr, minc, maxr, maxc = rp.bbox
        touches = int(minr == 0) + int(minc == 0) + int(maxr == H) + int(maxc == W)
        if touches >= 2:
            continue
        cy, cx = rp.centroid
        if not (0.10 * W < cx < 0.90 * W and 0.08 * H < cy < 0.92 * H):
            continue
        cands.append(rp)
    cands.sort(key=lambda r_: -r_.area)
    return cands, lab, float(t)


def find_lung_pair(s: np.ndarray) -> Optional[dict]:
    """Return {'img_left': mask, 'img_right': mask, 't': thr} or None."""
    H, W = s.shape
    cands, lab, t = dark_components(s)
    if not cands:
        return None
    r = max(2, int(round(0.01 * max(H, W))))
    first = cands[0]
    second = None
    for c in cands[1:]:
        if abs(c.centroid[1] - first.centroid[1]) >= 0.15 * W and c.area >= 0.25 * first.area:
            second = c
            break
    if second is not None:
        a, b = (first, second) if first.centroid[1] < second.centroid[1] else (second, first)
        ml, mr = _clean(lab == a.label, r), _clean(lab == b.label, r)
        return {"img_left": ml, "img_right": mr, "t": t}
    # merged lungs? split at column valley
    minr, minc, maxr, maxc = first.bbox
    if (maxc - minc) >= 0.40 * W:
        m = lab == first.label
        prof = m.sum(axis=0).astype(float)
        lo, hi = minc + int(0.35 * (maxc - minc)), minc + int(0.65 * (maxc - minc))
        v = lo + int(np.argmin(prof[lo:hi]))
        # a real mediastinal gap is a deep valley between two lobes; a single blob (lateral view) is not
        if prof[v] > 0.5 * min(prof[minc:v].max(), prof[v:maxc].max()):
            return None
        ml, mr = m.copy(), m.copy()
        ml[:, v:] = False
        mr[:, :v] = False
        if ml.sum() > 0.01 * H * W and mr.sum() > 0.01 * H * W:
            return {"img_left": _clean(ml, r), "img_right": _clean(mr, r), "t": t}
    return None


def find_single_dark(s: np.ndarray) -> Optional[dict]:
    cands, lab, t = dark_components(s, 0.05)
    if not cands:
        return None
    r = max(2, int(round(0.01 * max(s.shape))))
    return {"mask": _clean(lab == cands[0].label, r), "t": t}


# ------------------------------------------------------------------ frontal chest
def _row_extent(mask: np.ndarray):
    """per-row (min x, max x), NaN where empty"""
    H, W = mask.shape
    any_ = mask.any(axis=1)
    xmin = np.where(any_, mask.argmax(axis=1), np.nan)
    xmax = np.where(any_, W - 1 - mask[:, ::-1].argmax(axis=1), np.nan)
    return xmin, xmax


def _smooth_nan(a: np.ndarray, k: int = 5) -> np.ndarray:
    out = a.copy()
    for i in range(len(a)):
        w = a[max(0, i - k):i + k + 1]
        w = w[~np.isnan(w)]
        out[i] = np.median(w) if len(w) else np.nan
    return out


def segment_chest_frontal(s: np.ndarray, lungs: Optional[dict] = None) -> Optional[dict[str, np.ndarray]]:
    """Heuristic frontal chest segmentation. Keys follow patient side (right = image left)."""
    H, W = s.shape
    lungs = lungs or find_lung_pair(s)
    if lungs is None:
        return None
    R, L = lungs["img_left"], lungs["img_right"]       # patient right / left
    union = R | L
    ys, xs = np.nonzero(union)
    y0, y1, xL, xR = ys.min(), ys.max(), xs.min(), xs.max()
    Hl, Wt = y1 - y0 + 1, xR - xL + 1
    out: dict[str, np.ndarray] = {"right_lung": R, "left_lung": L}

    # --- gap between lungs, per row
    _, r_max = _row_extent(R)
    l_min, _ = _row_extent(L)
    gap_lo, gap_hi = _smooth_nan(r_max), _smooth_nan(l_min)
    width = gap_hi - gap_lo
    valid = ~np.isnan(width) & (width > 0)
    yy = np.arange(H)
    gap = np.zeros((H, W), bool)
    for y in np.nonzero(valid)[0]:
        gap[y, int(gap_lo[y]) + 1:int(gap_hi[y])] = True
    gap &= ~union
    centers = (gap_lo + gap_hi) / 2
    upper = valid & (yy >= y0 + 0.08 * Hl) & (yy <= y0 + 0.30 * Hl)
    if upper.any():
        mid0 = float(np.nanmedian(centers[upper]))
    else:
        mid0 = float(np.nanmedian(centers[valid])) if valid.any() else (xL + xR) / 2

    # --- heart rows: where the gap widens versus the upper mediastinum
    up = valid & (yy >= y0 + 0.08 * Hl) & (yy <= y0 + 0.30 * Hl)
    base = float(np.nanmedian(width[up])) if up.any() else float(np.nanmedian(width[valid]) if valid.any() else 0.1 * Wt)
    heart_top = None
    for y in range(int(y0 + 0.30 * Hl), int(y1)):
        if valid[y] and width[y] > 1.25 * max(base, 2):
            heart_top = y
            break
    if heart_top is None:
        heart_top = int(y0 + 0.55 * Hl)
    heart = gap.copy()
    heart[:heart_top] = False
    heart[int(y0 + 0.88 * Hl):] = False       # below this the gap includes cardiophrenic/subdiaphragmatic spaces
    heart = bopen(heart, disk(max(1, int(0.004 * W))))
    heart = _largest(heart) if heart.any() else heart
    med = gap.copy()
    med[heart_top:] = False
    med[: max(0, int(y0 - 0.04 * Hl))] = False
    if heart.any():
        out["heart"] = heart
    if med.any():
        out["mediastinum"] = med

    # --- spine: bright midline column (profile taken above the heart, where the heart does not bias it)
    bw = int(0.12 * Wt)
    bl, br = max(0, int(mid0) - bw), min(W, int(mid0) + bw)
    pr0 = int(y0 + 0.05 * Hl)
    pr1 = heart_top - 1 if heart_top - pr0 > 0.12 * Hl else int(y0 + 0.30 * Hl)
    prof = gaussian(s[pr0:max(pr1, pr0 + 3), bl:br].mean(axis=0), 1.5)
    pk = int(np.argmax(prof))
    floor = np.percentile(prof, 10)
    half = floor + 0.5 * (prof[pk] - floor)
    above = np.nonzero(prof > half)[0]
    a, b = int(above.min()), int(above.max())
    if prof[pk] - floor < 0.015 or (b - a) > 0.18 * Wt:
        pk = int(mid0) - bl
        a, b = pk - int(0.03 * Wt), pk + int(0.03 * Wt)
    spine = np.zeros((H, W), bool)
    sy0, sy1 = max(0, int(y0 - 0.08 * Hl)), min(H, int(y1 + 0.04 * Hl))
    spine[sy0:sy1, bl + a:bl + b + 1] = True
    spine &= ~union
    out["spine"] = spine
    spine_x = (bl + (a + b) / 2.0)

    # --- trachea: dark vertical tube in the upper midline
    ty0, ty1 = max(0, int(y0 - 0.10 * Hl)), int(y0 + 0.35 * Hl)
    tw = int(0.12 * Wt)
    region = np.zeros((H, W), bool)
    region[ty0:ty1, max(0, int(mid0) - tw):int(mid0) + tw + 1] = True
    region &= ~union
    if region.sum() > 50:
        v = s[region]
        lo, md = np.percentile(v, 5), np.median(v)
        if md - lo > 0.02:
            cand = region & (s < lo + 0.35 * (md - lo))
            cand = bopen(cand, disk(1))
            lab = label(cand)
            best, bh = None, 0
            for rp in regionprops(lab):
                h_ = rp.bbox[2] - rp.bbox[0]
                w_ = rp.bbox[3] - rp.bbox[1]
                if h_ > bh and h_ >= 1.5 * w_ and w_ <= 0.09 * Wt and rp.area > 30:
                    best, bh = rp.label, h_
            if best is not None:
                out["trachea"] = bclose(lab == best, disk(1))
    out["_spine_x"] = np.array([spine_x])
    out["_mid0"] = np.array([mid0])

    # --- aorta (aortic knob zone, patient left of midline) -- coarse
    knob = med.copy()
    knob[:, : int(mid0 + 0.02 * Wt)] = False
    knob[: int(y0 + 0.06 * Hl)] = False
    knob[int(y0 + 0.30 * Hl):] = False
    if knob.sum() > 40:
        out["aorta"] = knob

    # --- diaphragm: bottom contours of each lung
    for key, m, name in (("right_diaphragm", R, "R"), ("left_diaphragm", L, "L")):
        cols = m.any(axis=0)
        bot = np.where(cols, H - 1 - m[::-1].argmax(axis=0), -1)
        band = np.zeros((H, W), bool)
        t = max(2, int(0.012 * H))
        for c in np.nonzero(cols)[0]:
            band[max(0, bot[c] - t):min(H, bot[c] + t), c] = True
        out[key] = band

    # --- clavicles: bright oblique ridges in upper fifth
    cy0, cy1 = max(0, int(y0 - 0.08 * Hl)), int(y0 + 0.38 * Hl)
    sig = (max(1.5, 0.008 * W), max(2.5, 0.014 * W))
    resp = sato(s, sigmas=sig, black_ridges=False)
    hrr, hrc, hcc = hessian_matrix(s, sigma=sig[1], order="rc", use_gaussian_derivatives=False)
    horiz = np.abs(0.5 * np.arctan2(2 * hrc, hrr - hcc)) > np.deg2rad(40)   # ridge direction near-horizontal
    rb = max(3, int(0.012 * W))
    border = ndi.binary_dilation(union, iterations=2 * rb) & ~ndi.binary_erosion(union, iterations=rb)
    for key, sl in (("right_clavicle", (0, int(mid0))), ("left_clavicle", (int(mid0), W))):
        reg = np.zeros((H, W), bool)
        reg[cy0:cy1, sl[0]:sl[1]] = True
        reg[:, max(0, int(spine_x - 0.04 * Wt)):int(spine_x + 0.04 * Wt)] = False
        reg &= ~border
        if reg.sum() < 100:
            continue
        thr = np.percentile(resp[reg], 93)
        cand = bopen(reg & (resp > thr) & horiz, disk(1))
        lab = label(cand)
        best, bscore = None, 0
        for rp in regionprops(lab):
            w_ = rp.bbox[3] - rp.bbox[1]
            h_ = rp.bbox[2] - rp.bbox[0]
            if w_ >= 0.18 * Wt and w_ >= 1.5 * h_ and w_ > bscore:
                best, bscore = rp.label, w_
        if best is not None:
            out[key] = bclose(lab == best, disk(2))

    # --- ribs: ridge response inside lung fields
    rr = sato(s, sigmas=(max(1.0, 0.005 * W), max(1.5, 0.008 * W)), black_ridges=False)
    lungs_in = bopen(union, disk(max(2, int(0.01 * W)))) & ~ndi.binary_dilation(
        out.get("trachea", np.zeros_like(union)), iterations=2)
    # erode to avoid lung borders
    lungs_in = ndi.binary_erosion(lungs_in, iterations=max(2, int(0.01 * W)))
    if lungs_in.sum() > 200:
        thr = np.percentile(rr[lungs_in], 88)
        ribs = bopen(lungs_in & (rr > thr), disk(1))
        ribs = rm_small(ribs, max(20, int(0.0004 * H * W)))
        if ribs.sum() > 50:
            out["ribs"] = ribs
    return out


# ------------------------------------------------------------------ lateral chest
def segment_chest_lateral(s: np.ndarray, posterior: Optional[str] = None,
                          lung_hint: Optional[np.ndarray] = None) -> Optional[dict[str, np.ndarray]]:
    """posterior in {'left','right'} (image side of the spine) if known from DICOM tags.
    lung_hint: lung-field mask from the PSPNet pass (more reliable than the Otsu blob) at the same resolution."""
    H, W = s.shape
    if lung_hint is not None and lung_hint.shape == s.shape and lung_hint.sum() > 0.04 * H * W:
        r_ = max(2, int(round(0.01 * max(H, W))))
        found = {"mask": _clean(lung_hint, r_), "t": float(threshold_otsu(s[int(.05 * H):int(.95 * H), int(.08 * W):int(.92 * W)]))}
    else:
        found = find_single_dark(s)
    if found is None:
        return None
    lung, t = found["mask"], found["t"]
    ys, xs = np.nonzero(lung)
    r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
    Hl, Wl = r1 - r0 + 1, c1 - c0 + 1
    if posterior not in ("left", "right"):
        sw = max(2, int(0.10 * W))
        lstrip = s[r0:r1 + 1, max(0, c0 - sw):c0]
        rstrip = s[r0:r1 + 1, c1 + 1:min(W, c1 + 1 + sw)]
        lm = lstrip.mean() if lstrip.size else 0.0
        rm = rstrip.mean() if rstrip.size else 0.0
        posterior = "left" if lm > rm else "right"
    post_sign = -1 if posterior == "left" else 1       # direction towards posterior
    out: dict[str, np.ndarray] = {"lung_field": lung}
    out["_posterior"] = np.array([0 if posterior == "left" else 1])

    # heart: hull minus lung, lower part, anterior side
    hull = convex_hull_image(lung)
    diff = hull & ~lung
    diff[: int(r0 + 0.35 * Hl)] = False
    xs_idx = np.arange(W)
    ant_frac = (c1 - xs_idx) / max(Wl, 1) if posterior == "left" else (xs_idx - c0) / max(Wl, 1)
    diff[:, ~((ant_frac >= -0.05) & (ant_frac <= 0.65))] = False
    diff = bopen(diff, disk(max(1, int(0.006 * W))))
    if diff.any():
        h = _largest(diff)
        if h.sum() > 0.003 * H * W:
            out["heart"] = h

    # diaphragm domes
    cols = lung.any(axis=0)
    bot = np.where(cols, H - 1 - lung[::-1].argmax(axis=0), -1)
    band = np.zeros((H, W), bool)
    tt = max(2, int(0.012 * H))
    for c in np.nonzero(cols)[0]:
        band[max(0, bot[c] - tt):min(H, bot[c] + tt), c] = True
    out["diaphragm"] = band

    # spine: posterior strip
    sp = np.zeros((H, W), bool)
    sw = int(0.14 * W)
    if post_sign > 0:
        a, b = max(0, c1 - int(0.02 * Wl)), min(W, c1 + sw)
    else:
        a, b = max(0, c0 - sw), min(W, c0 + int(0.02 * Wl))
    sp[max(0, int(r0 - 0.05 * Hl)):min(H, int(r1 + 0.04 * Hl)), a:b] = True
    sp &= ~lung
    sp &= s > t
    sp = bopen(sp, disk(2))
    if sp.any():
        out["spine"] = _largest(sp)

    # sternum: anterior strip
    st = np.zeros((H, W), bool)
    sw2 = int(0.07 * W)
    if post_sign > 0:   # anterior at left
        a, b = max(0, c0 - sw2), c0 + int(0.01 * Wl)
    else:
        a, b = c1 - int(0.01 * Wl), min(W, c1 + sw2)
    st[int(r0):int(r0 + 0.80 * Hl), a:b] = True
    st &= ~lung
    st &= s > t
    st = bopen(st, disk(1))
    if st.sum() > 40:
        out["sternum"] = _largest(st)

    # trachea: dark tube above/within the upper-central lung field, separated by opening
    opened = bopen(lung, disk(max(3, int(0.04 * W))))
    reg = np.zeros((H, W), bool)
    reg[max(0, int(r0 - 0.20 * Hl)):int(r0 + 0.40 * Hl), int(c0 + 0.20 * Wl):int(c0 + 0.80 * Wl)] = True
    cand = reg & (s < t) & ~opened
    cand = bopen(cand, disk(1))
    lab = label(cand)
    best, bh = None, 0
    for rp in regionprops(lab):
        h_ = rp.bbox[2] - rp.bbox[0]
        w_ = rp.bbox[3] - rp.bbox[1]
        if h_ >= 2 * w_ and h_ > bh and rp.area > 40:
            best, bh = rp.label, h_
    if best is not None:
        out["trachea"] = lab == best
    return out


# ------------------------------------------------------------------ abdomen & generic
def _central_ridge_mask(s: np.ndarray, bright: np.ndarray, y0: int, y1: int, cx: float, halfw: float):
    H, W = s.shape
    bl, br = max(0, int(cx - halfw)), min(W, int(cx + halfw))
    if br - bl < 6 or y1 <= y0:
        return None
    prof = gaussian(s[y0:y1, bl:br].mean(axis=0), 1.5)
    pk = int(np.argmax(prof))
    floor = np.percentile(prof, 10)
    half = floor + 0.5 * (prof[pk] - floor)
    a = pk
    while a > 0 and prof[a - 1] > half:
        a -= 1
    b = pk
    while b < len(prof) - 1 and prof[b + 1] > half:
        b += 1
    if prof[pk] - floor < 0.015:
        return None
    m = np.zeros((H, W), bool)
    m[y0:y1, bl + a:bl + b + 1] = True
    return m


def segment_abdomen(s: np.ndarray) -> dict[str, np.ndarray]:
    H, W = s.shape
    out: dict[str, np.ndarray] = {}
    try:
        tl, th = threshold_multiotsu(s, classes=3)
    except Exception:
        return out
    r = max(2, int(0.01 * max(H, W)))
    body = bclose(s > tl, disk(r))
    body = ndi.binary_fill_holes(_largest(body))
    gas = body & (s <= tl)
    gas = bopen(gas, disk(max(1, r // 2)))
    gas = rm_small(gas, max(30, int(0.001 * H * W)))
    if gas.any():
        out["bowel_gas"] = gas
    bright = s > th
    ys, xs = np.nonzero(body)
    if len(ys) == 0:
        return out
    by0, by1 = ys.min(), ys.max()
    cx = (xs.min() + xs.max()) / 2
    sp = _central_ridge_mask(s, bright, int(by0), int(by0 + 0.80 * (by1 - by0)), cx, 0.15 * W)
    if sp is not None:
        out["spine"] = sp & body
    pel = bright.copy()
    pel[: int(by0 + 0.62 * (by1 - by0))] = False
    pel = bopen(pel, disk(2))
    pel = rm_small(pel, max(40, int(0.002 * H * W)))
    if pel.any():
        out["pelvis_bones"] = pel
    return out


def segment_bones(s: np.ndarray) -> dict[str, np.ndarray]:
    try:
        th = threshold_multiotsu(s, classes=3)[1]
    except Exception:
        return {}
    H, W = s.shape
    b = bopen(s > th, disk(2))
    b = rm_small(b, max(40, int(0.002 * H * W)))
    return {"bones": b} if b.any() else {}


def classify_region_heuristic(s: np.ndarray) -> tuple[str, str]:
    """Returns (kind, detail): kind in chest_frontal, chest_lateral, abdomen, extremity, other."""
    H, W = s.shape
    pair = find_lung_pair(s)
    if pair is not None and (pair["img_left"].sum() + pair["img_right"].sum()) >= 0.08 * H * W:
        return "chest_frontal", "par de campos pulmonares escuros"
    single = find_single_dark(s)
    if single is not None and single["mask"].sum() >= 0.12 * H * W:
        return "chest_lateral", "campo pulmonar único amplo"
    # background (air) fraction connected to border
    try:
        t0 = threshold_multiotsu(s, classes=3)[0]
    except Exception:
        t0 = 0.0
    dark = s < t0
    lab = label(dark)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    border_frac = float(np.isin(lab, list(border)).mean()) if border else 0.0
    if border_frac > 0.30:
        return "extremity", "grande área de ar/fundo"
    if 0.6 <= H / W <= 1.7:
        return "abdomen", "corpo preenche o campo"
    return "other", "indeterminado"
