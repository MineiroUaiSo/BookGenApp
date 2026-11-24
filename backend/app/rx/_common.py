"""Shared helpers: palette, mask encoding, polygons, Structure builder."""
from __future__ import annotations

import base64
import io
from typing import Optional

import numpy as np
from PIL import Image
from skimage import measure
from skimage.transform import resize

from ..schemas import Structure

# key -> (pt-BR label, category, color)
PALETTE: dict[str, tuple[str, str, str]] = {
    "right_lung": ("pulmão direito", "lung", "#3b82f6"),
    "left_lung": ("pulmão esquerdo", "lung", "#06b6d4"),
    "lung_field": ("campos pulmonares (sobrepostos)", "lung", "#60a5fa"),
    "right_hilum": ("hilo pulmonar direito", "lung", "#1d4ed8"),
    "left_hilum": ("hilo pulmonar esquerdo", "lung", "#0e7490"),
    "heart": ("coração (silhueta cardíaca)", "heart_vessels", "#ef4444"),
    "aorta": ("aorta", "heart_vessels", "#f97316"),
    "mediastinum": ("mediastino", "mediastinum", "#a855f7"),
    "trachea": ("traqueia", "airway", "#22c55e"),
    "spine": ("coluna vertebral", "bone", "#eab308"),
    "right_clavicle": ("clavícula direita", "bone", "#fb7185"),
    "left_clavicle": ("clavícula esquerda", "bone", "#f472b6"),
    "right_scapula": ("escápula direita", "bone", "#a3e635"),
    "left_scapula": ("escápula esquerda", "bone", "#65a30d"),
    "ribs": ("arcos costais (aproximado)", "bone", "#d6d3d1"),
    "sternum": ("esterno", "bone", "#e7e5e4"),
    "diaphragm": ("diafragma", "diaphragm", "#14b8a6"),
    "right_diaphragm": ("hemidiafragma direito", "diaphragm", "#14b8a6"),
    "left_diaphragm": ("hemidiafragma esquerdo", "diaphragm", "#2dd4bf"),
    "bowel_gas": ("alças intestinais (gás)", "abdomen", "#fb923c"),
    "pelvis_bones": ("ossos da pelve", "bone", "#e7e5e4"),
    "bones": ("estruturas ósseas (limiar)", "bone", "#d4d4d8"),
}


def upsample_mask(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    h, w = mask.shape
    H, W = shape
    if (h, w) == (H, W):
        return mask.astype(bool)
    ri = np.minimum((np.arange(H) * h / H).astype(int), h - 1)
    ci = np.minimum((np.arange(W) * w / W).astype(int), w - 1)
    return mask[np.ix_(ri, ci)].astype(bool)


def encode_mask(mask_full: np.ndarray) -> str:
    im = Image.fromarray((mask_full.astype(np.uint8)) * 255, mode="L")
    buf = io.BytesIO()
    im.save(buf, format="PNG", compress_level=3)   # optimize=True cost ~25 ms/mask for ~no size gain
    return base64.b64encode(buf.getvalue()).decode("ascii")


def encode_png_b64(img_u8: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(img_u8).save(buf, format="PNG", compress_level=3)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def mask_polygon(mask: np.ndarray, sx: float, sy: float, max_pts: int = 160) -> list[list[float]]:
    padded = np.pad(mask.astype(float), 1)
    cs = measure.find_contours(padded, 0.5)
    if not cs:
        return []
    c = max(cs, key=len) - 1.0
    tol = 0.8
    pts = c
    while True:
        pts = measure.approximate_polygon(c, tol)
        if len(pts) <= max_pts or tol > 50:
            break
        tol *= 1.5
    return [[round(float((x + 0.5) * sx), 1), round(float((y + 0.5) * sy), 1)] for y, x in pts]


def build_structure(key: str, mask_work: np.ndarray, full_shape: tuple[int, int],
                    scale: tuple[float, float], spacing: Optional[tuple[float, float]],
                    conf: float, origin: str, label: Optional[str] = None) -> Optional[Structure]:
    """mask_work: bool mask at working resolution; scale=(sy, sx) work->full."""
    mask_work = np.asarray(mask_work, bool)
    if mask_work.sum() < 12:
        return None
    sy, sx = scale
    lab, cat, color = PALETTE.get(key, (key, "other", "#9ca3af"))
    full = upsample_mask(mask_work, full_shape)
    ys, xs = np.nonzero(mask_work)
    area_px = float(mask_work.sum()) * sx * sy
    area_mm2 = round(area_px * spacing[0] * spacing[1], 1) if spacing else None
    return Structure(
        key=key, label=label or lab, category=cat, color=color,  # type: ignore[arg-type]
        mask_png_b64=encode_mask(full),
        polygon=mask_polygon(mask_work, sx, sy),
        bbox=[round(float(xs.min() * sx), 1), round(float(ys.min() * sy), 1),
              round(float((xs.max() + 1) * sx), 1), round(float((ys.max() + 1) * sy), 1)],
        area_mm2=area_mm2, confidence=round(float(conf), 2), origin=origin,  # type: ignore[arg-type]
    )


def to_work(img_u8: np.ndarray, max_side: int = 512):
    """Downscale to working resolution. Returns (float image 0..1, (sy, sx))."""
    H, W = img_u8.shape
    f = max(H, W) / max_side
    if f <= 1.0:
        return img_u8.astype(np.float32) / 255.0, (1.0, 1.0)
    h, w = int(round(H / f)), int(round(W / f))
    g = resize(img_u8.astype(np.float32) / 255.0, (h, w), anti_aliasing=True, order=1)
    return g.astype(np.float32), (H / h, W / w)


def autocrop(img_u8: np.ndarray, min_trim: float = 0.06):
    """Trim flat borders (letterbox/zero padding/black frames). Returns (cropped, (y0, x0)).
    Only trims when a dimension loses at least `min_trim` of its length; never below 40% of the side."""
    a = img_u8.astype(np.int16)
    H, W = a.shape
    if H < 32 or W < 32:
        return img_u8, (0, 0)
    # a row/column is 'flat' if it carries (almost) no signal: constant padding, text-free frame
    rflat = (a.max(axis=1) - a.min(axis=1)) <= 3
    cflat = (a.max(axis=0) - a.min(axis=0)) <= 3

    def span(flat):
        n = len(flat)
        idx = np.nonzero(~flat)[0]
        if len(idx) == 0:
            return 0, n
        return int(idx[0]), int(idx[-1]) + 1

    y0, y1 = span(rflat)
    x0, x1 = span(cflat)
    # re-evaluate columns inside the row span (a padded band can hide behind a bright label)
    sub = a[y0:y1]
    x0b, x1b = span((sub.max(axis=0) - sub.min(axis=0)) <= 3)
    x0, x1 = max(x0, x0b), min(x1, x1b)
    if (y1 - y0) < 0.4 * H or (x1 - x0) < 0.4 * W or x1 <= x0 or y1 <= y0:
        return img_u8, (0, 0)
    if (H - (y1 - y0)) < min_trim * H and (W - (x1 - x0)) < min_trim * W:
        return img_u8, (0, 0)
    return img_u8[y0:y1, x0:x1], (y0, x0)


def polarity_margin(img_u8: np.ndarray) -> float:
    """median(outer ring) - median(centre) on the autocropped image, in 0..1. Radiographs normally have a darker
    ring (air/soft tissue) than centre (spine/mediastinum/bone): margin <= ~0 normal, clearly > 0 suggests an
    inverted (MONOCHROME1-like) PNG/JPG. Overlaps slightly at the low end (2/53 normal JSRT/Montgomery > 0.05),
    so callers arbitrate small margins with the chest model."""
    c, _ = autocrop(img_u8)
    f = c[::4, ::4].astype(np.float32) / 255.0
    H, W = f.shape
    if H < 16 or W < 16:
        return 0.0
    ring = np.concatenate([f[:max(1, int(.06 * H))].ravel(), f[:, :max(1, int(.06 * W))].ravel(),
                           f[:, -max(1, int(.06 * W)):].ravel()])
    centre = f[int(.1 * H):int(.9 * H), int(.1 * W):int(.9 * W)]
    return float(np.median(ring)) - float(np.median(centre))


def normalize_polarity(img_u8: np.ndarray, thr: float = 0.12) -> tuple[np.ndarray, bool]:
    """Model-free polarity fix: invert only when the margin is clearly positive (> thr)."""
    if polarity_margin(img_u8) > thr:
        return (255 - img_u8).astype(np.uint8), True
    return img_u8, False
