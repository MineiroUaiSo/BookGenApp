"""Deterministic measurements and image-quality estimates for frontal chest films."""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import gaussian
from scipy.signal import find_peaks

from ..schemas import RXMeasurement


class Conv:
    """work-pixel -> physical conversion (mm if spacing known, else full-res px)."""

    def __init__(self, scale: tuple[float, float], spacing: Optional[tuple[float, float]]):
        self.sy, self.sx = scale
        self.has_mm = spacing is not None
        self.ky = self.sy * (spacing[0] if spacing else 1.0)
        self.kx = self.sx * (spacing[1] if spacing else 1.0)
        self.unit = "mm" if self.has_mm else "px"

    def seg(self, x0, y0, x1, y1):
        return [round(float(x0 * self.sx), 1), round(float(y0 * self.sy), 1),
                round(float(x1 * self.sx), 1), round(float(y1 * self.sy), 1)]


def _bbox(m):
    ys, xs = np.nonzero(m)
    return ys.min(), ys.max(), xs.min(), xs.max()


def _bottom(m):
    return np.where(m.any(axis=0), m.shape[0] - 1 - m[::-1].argmax(axis=0), -1)


def costophrenic_angle(mask: np.ndarray, lateral_sign: int):
    """lateral_sign: -1 if lateral side is image-left, +1 if image-right.
    Returns (angle_deg, corner(x,y)) or None."""
    ys, xs = np.nonzero(mask)
    if len(ys) < 200:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    Hl, Wl = y1 - y0 + 1, x1 - x0 + 1
    bot = _bottom(mask)
    cols = np.arange(mask.shape[1])
    if lateral_sign < 0:
        lat = (cols >= x0) & (cols <= x0 + 0.30 * Wl)
    else:
        lat = (cols <= x1) & (cols >= x1 - 0.30 * Wl)
    lat &= bot >= 0
    if not lat.any():
        return None
    cand = np.nonzero(lat)[0]
    best = bot[cand].max()
    tied = cand[bot[cand] >= best - 1]
    cx = int(tied.min() if lateral_sign < 0 else tied.max())      # most lateral of the lowest
    cy = int(bot[cx])
    # lateral wall points
    rows = np.arange(int(max(y0, cy - 0.22 * Hl)), int(max(y0, cy - 0.05 * Hl)) + 1)
    pts = []
    for y in rows:
        r = np.nonzero(mask[y])[0]
        if len(r):
            pts.append((r.min() if lateral_sign < 0 else r.max(), y))
    # diaphragm points medial to corner
    dpts = []
    for off in np.linspace(0.05, 0.25, 12) * Wl:
        c = int(round(cx - lateral_sign * off))
        if 0 <= c < mask.shape[1] and bot[c] >= 0:
            dpts.append((c, bot[c]))
    if len(pts) < 4 or len(dpts) < 4:
        return None
    pts, dpts = np.array(pts, float), np.array(dpts, float)
    a = np.polyfit(pts[:, 1], pts[:, 0], 1)[0]          # x = a*y + b
    u = np.array([-a, -1.0])                             # up the wall
    u /= np.linalg.norm(u)
    c_ = np.polyfit(dpts[:, 0], dpts[:, 1], 1)[0]        # y = c*x + d
    med = -lateral_sign
    v = np.array([med * 1.0, med * c_])
    v /= np.linalg.norm(v)
    ang = float(np.degrees(np.arccos(np.clip(u @ v, -1, 1))))
    return ang, (cx, cy)


def hemidiaphragm_apex(mask: np.ndarray, lateral_sign: int) -> Optional[tuple[float, float]]:
    """(x, y) of the dome apex ~ highest point of the lower lung contour over the lateral 40% of the lung
    (the medial part is distorted by the heart / mediastinum)."""
    bot = _bottom(mask)
    valid = np.nonzero(bot >= 0)[0]
    if len(valid) < 20:
        return None
    n = len(valid)
    cols = valid[:int(0.4 * n)] if lateral_sign < 0 else valid[n - int(0.4 * n):]
    cols = cols[int(0.1 * len(cols)):] if lateral_sign < 0 else cols[:len(cols) - int(0.1 * len(cols))]
    y = bot[cols]
    i = int(np.argsort(y)[max(0, int(0.1 * len(y)) - 1)])
    return float(cols[i]), float(y[i])


def measure_frontal(masks: dict[str, np.ndarray], conv: Conv, view: str):
    """Returns (measurements, extras dict)."""
    ms: list[RXMeasurement] = []
    ex: dict = {}
    R, L = masks.get("right_lung"), masks.get("left_lung")
    if R is None or L is None or not R.any() or not L.any():
        return ms, ex
    union = R | L
    uy0, uy1, ux0, ux1 = _bbox(union)
    Hl, Wt = uy1 - uy0 + 1, ux1 - ux0 + 1
    ex.update(thorax_x=(ux0, ux1), thorax_y=(uy0, uy1))
    thoracic_mm = Wt * conv.kx
    ms.append(RXMeasurement(key="thoracic_width", label="Largura torácica interna (campos pulmonares)",
                            value=round(float(thoracic_mm), 1), unit=conv.unit))

    # --- CTR
    heart = masks.get("heart")
    if heart is not None and heart.any():
        hy0, hy1, hx0, hx1 = _bbox(heart)
        hw = hx1 - hx0 + 1
        ctr = hw / Wt
        rowmid = int((hy0 + hy1) / 2)
        ms.append(RXMeasurement(
            key="cardiothoracic_ratio", label="Índice cardiotorácico", value=round(float(ctr), 3), unit="",
            normal_range="< 0,50 (PA); AP magnifica a silhueta",
            drawing=[conv.seg(hx0, rowmid, hx1, rowmid), conv.seg(ux0, uy1 - 0.1 * Hl, ux1, uy1 - 0.1 * Hl)]))
        ms.append(RXMeasurement(key="heart_width", label="Largura máxima da silhueta cardíaca",
                                value=round(float(hw * conv.kx), 1), unit=conv.unit))
        ex["ctr"] = ctr
        # --- spine/midline fallbacks for later
    # --- midline
    spine_x = None
    if "_spine_x" in masks:
        spine_x = float(masks["_spine_x"][0])
    elif masks.get("spine") is not None and masks["spine"].any():
        spine_x = float(np.nonzero(masks["spine"])[1].mean())
    else:
        spine_x = (ux0 + ux1) / 2
    ex["midline_x"] = spine_x

    # --- tracheal deviation
    tr = masks.get("trachea")
    if tr is not None and tr.any():
        ty, tx = np.nonzero(tr)
        # restrict to upper part to reduce bronchial influence
        sel = ty <= np.percentile(ty, 80)
        tcx = float(tx[sel].mean())
        tcy = float(ty[sel].mean())
        dev = (tcx - spine_x)                       # + => toward image right (patient left)
        ms.append(RXMeasurement(
            key="tracheal_deviation", label="Desvio traqueal em relação à linha média da coluna",
            value=round(float(dev * conv.kx), 1), unit=conv.unit,
            normal_range="≈ 0 (leve desvio à direita do paciente é fisiológico)",
            drawing=[conv.seg(spine_x, tcy, tcx, tcy)]))
        ms.append(RXMeasurement(key="tracheal_deviation_pct", label="Desvio traqueal (% da largura torácica)",
                                value=round(float(100 * dev / Wt), 1), unit="%"))
        ex["trachea_dev_pct"] = 100 * dev / Wt

    # --- costophrenic angles & hemidiaphragms (R is image-left if centroid smaller)
    cr = float(np.nonzero(R)[1].mean())
    cl = float(np.nonzero(L)[1].mean())
    img_left_is_right = cr < cl
    for key, m, name in (("right", R, "direito"), ("left", L, "esquerdo")):
        is_img_left = (key == "right") == img_left_is_right
        res = costophrenic_angle(m, -1 if is_img_left else +1)
        if res is not None:
            ang, (cx, cy) = res
            ms.append(RXMeasurement(
                key=f"costophrenic_angle_{key}", label=f"Ângulo costofrênico {name} (estimativa)",
                value=round(ang, 0), unit="°", normal_range="agudo (< ~90°); ≥ ~90° sugere embotamento",
                drawing=[conv.seg(cx, cy - 0.12 * Hl, cx, cy)]))
            ex[f"cp_{key}"] = ang
    apr = hemidiaphragm_apex(R, -1 if img_left_is_right else +1)
    apl = hemidiaphragm_apex(L, +1 if img_left_is_right else -1)
    if apr and apl:
        dy = apl[1] - apr[1]            # + => right dome higher (normal: right ≥ left)
        ms.append(RXMeasurement(
            key="hemidiaphragm_height_difference", label="Diferença de altura das cúpulas (D − E, + = direita mais alta)",
            value=round(float(dy * conv.ky), 1), unit=conv.unit, normal_range="direita até ~25 mm acima da esquerda",
            drawing=[conv.seg(apr[0] - 0.08 * Wt, apr[1], apr[0] + 0.08 * Wt, apr[1]),
                     conv.seg(apl[0] - 0.08 * Wt, apl[1], apl[0] + 0.08 * Wt, apl[1])]))
        pct = 100.0 * dy / Hl
        ms.append(RXMeasurement(key="hemidiaphragm_height_difference_pct",
                                label="Diferença de altura das cúpulas (% da altura pulmonar)", value=round(pct, 1), unit="%"))
        ex["dome_diff_pct"] = pct
        ex["dome_diff_mm"] = dy * conv.ky if conv.has_mm else None

    # --- mediastinal width at aortic-knob level (gap between lungs)
    if img_left_is_right:
        Li, Ri = R, L
    else:
        Li, Ri = L, R
    ycenter = int(uy0 + 0.20 * Hl)
    best = None
    for y in range(max(uy0, ycenter - int(0.03 * Hl)), ycenter + int(0.03 * Hl) + 1):
        a = np.nonzero(Li[y])[0]
        b = np.nonzero(Ri[y])[0]
        if len(a) and len(b) and b.min() > a.max():
            w = b.min() - a.max()
            if best is None or w > best[0]:
                best = (w, a.max(), b.min(), y)
    if best is not None:
        w, xa, xb, y = best
        ms.append(RXMeasurement(
            key="mediastinal_width", label="Largura do mediastino (nível do botão aórtico)",
            value=round(float(w * conv.kx), 1), unit=conv.unit, normal_range="< ~80 mm (PA)",
            drawing=[conv.seg(xa, y, xb, y)]))
        ms.append(RXMeasurement(key="mediastinal_width_ratio", label="Largura do mediastino (% da largura torácica)",
                                value=round(100.0 * w / Wt, 1), unit="%", normal_range="< ~30 %"))
        ex["med_ratio"] = 100.0 * w / Wt

    # --- lung area ratio L/R
    if R.sum() > 0:
        ratio = float(L.sum() / R.sum())
        ms.append(RXMeasurement(key="lung_area_ratio_L_R", label="Razão de área pulmonar E/D", value=round(ratio, 2),
                                unit="", normal_range="≈ 0,7–1,1 (coração reduz o pulmão esquerdo)"))
        ex["area_ratio"] = ratio
    return ms, ex


# ------------------------------------------------------------------ quality
def quality_frontal(s: np.ndarray, masks: dict[str, np.ndarray], ex: dict) -> dict[str, str]:
    q: dict[str, str] = {}
    if "thorax_x" not in ex:
        return q
    ux0, ux1 = ex["thorax_x"]
    uy0, uy1 = ex["thorax_y"]
    Wt, Hl = ux1 - ux0 + 1, uy1 - uy0 + 1
    mid = ex.get("midline_x", (ux0 + ux1) / 2)

    # rotation
    def medial_end(m):
        ys, xs = np.nonzero(m)
        i = np.argmin(np.abs(xs - mid))
        return xs[i]
    rc, lc = masks.get("right_clavicle"), masks.get("left_clavicle")
    if rc is not None and lc is not None and rc.any() and lc.any():
        dr, dl = abs(mid - medial_end(rc)), abs(medial_end(lc) - mid)
        idx = (dr - dl) / max(dr + dl, 1)
        tot = "clavículas"
    else:
        centre = (ux0 + ux1) / 2
        idx = (mid - centre) / (0.25 * Wt)
        tot = "coluna × campos pulmonares"
    ex["rotation_index"] = float(idx)
    if abs(idx) < 0.25:
        q["rotação"] = f"adequada (simétrica; critério: {tot})"
    else:
        side = "direita" if idx > 0 else "esquerda"
        q["rotação"] = f"possível rotação (assimetria {abs(idx):.2f}; critério: {tot}; {side}) — interpretar tamanho cardíaco/mediastino com cautela"

    # inspiration: count posterior-rib-like peaks above the right dome
    R, L = masks.get("right_lung"), masks.get("left_lung")
    union = R | L
    cr = float(np.nonzero(R)[1].mean())
    cl = float(np.nonzero(L)[1].mean())
    lat = R if cr < cl else L
    ys, xs = np.nonzero(lat)
    x0, x1 = xs.min(), xs.max()
    band = (slice(uy0, uy1 + 1), slice(int(x0 + 0.15 * (x1 - x0)), int(x0 + 0.60 * (x1 - x0))))
    colmask = lat[band]
    vals = np.where(colmask, s[band], np.nan)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        p = np.nanmean(vals, axis=1)
    n_ribs = None
    if np.isfinite(p).sum() > 0.5 * len(p):
        p = np.where(np.isfinite(p), p, np.nanmean(p))
        p = p - gaussian(p, sigma=max(6, 0.12 * len(p)))
        p = gaussian(p, sigma=max(1.0, 0.008 * len(p)))
        pk, _ = find_peaks(p, distance=max(4, int(0.045 * Hl)), prominence=0.004)
        n_ribs = int(len(pk))
    ratio = Hl / Wt
    if n_ribs is not None and 4 <= n_ribs <= 14:
        if n_ribs >= 9:
            q["inspiração"] = f"adequada (≈{n_ribs} arcos costais posteriores estimados; altura/largura pulmonar {ratio:.2f})"
        else:
            q["inspiração"] = f"possivelmente insuficiente (≈{n_ribs} arcos posteriores estimados; <9); altura/largura pulmonar {ratio:.2f}"
    else:
        q["inspiração"] = f"indeterminada (contagem de arcos não confiável); altura/largura pulmonar {ratio:.2f}"
    ex["n_ribs"] = n_ribs

    # penetration: spine contrast behind the heart vs adjacent heart region
    heart, spine = masks.get("heart"), masks.get("spine")
    lung_mean = float(s[union].mean())
    if heart is not None and spine is not None and heart.any() and spine.any():
        sp_in = spine & ndi.binary_dilation(heart, iterations=2)
        hr_adj = heart & ~ndi.binary_dilation(spine, iterations=int(0.03 * Wt))
        if sp_in.sum() > 30 and hr_adj.sum() > 30:
            c = float(s[sp_in].mean() - s[hr_adj].mean())
            ex["spine_contrast"] = c
            if lung_mean < 0.10:
                q["penetração"] = "possivelmente excessiva (campos pulmonares muito escuros)"
            elif c > 0.012:
                q["penetração"] = f"adequada (coluna discernível atrás do coração; contraste {c:.2f})"
            else:
                q["penetração"] = f"possivelmente insuficiente (coluna pouco visível atrás do coração; contraste {c:.2f})"
    if "penetração" not in q:
        q["penetração"] = "indeterminada"
    return q
