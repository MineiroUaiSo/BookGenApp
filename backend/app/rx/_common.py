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
    im.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def encode_png_b64(img_u8: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(img_u8).save(buf, format="PNG")
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
