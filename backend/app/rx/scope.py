"""Out-of-scope gate for RX images: abstain from thoracic findings when the image is not an adult chest film.

Deterministic and local (no extra model weights): relies on the region/view decided by app.rx.view
(DICOM tags + PSPNet anatomical plausibility) plus pixel-statistics sanity checks for blank images and
document / line-art images (ECG paper, screenshots).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..schemas import BodyRegion

BLANK_STD_MAX = 12.0          # 8-bit std below this = blank / uniform image
LINEART_TOP_MIN = 0.55        # share of pixels within +-4 grey levels of the dominant tone
LINEART_ENTROPY_MAX = 5.5     # bits; radiographs sit at >= 6.3 (JSRT/IU/PAX-Ray dev sample)
MIN_SIDE_PX = 64

REGION_PT = {
    BodyRegion.ABDOMEN: "abdome", BodyRegion.PELVIS: "pelve", BodyRegion.SPINE: "coluna",
    BodyRegion.SKULL: "crânio", BodyRegion.EXTREMITY: "extremidade", BodyRegion.OTHER: "região indeterminada",
}


def pixel_stats(img: np.ndarray) -> dict[str, float]:
    a = np.asarray(img, dtype=np.uint8)
    h = np.bincount(a.ravel(), minlength=256) / max(a.size, 1)
    top = float(np.convolve(h, np.ones(9), "same").max())
    nz = h[h > 0]
    return {"std": float(a.std()), "top": top, "entropy": float(-(nz * np.log2(nz)).sum())}


def check_scope(img: np.ndarray, region: BodyRegion, kind: str) -> tuple[bool, Optional[str]]:
    """-> (out_of_scope, reason). reason is pt-BR and goes to the user."""
    if min(img.shape[:2]) < MIN_SIDE_PX:
        return True, "imagem pequena demais para análise radiográfica"
    st = pixel_stats(img)
    if st["std"] < BLANK_STD_MAX:
        return True, "imagem praticamente uniforme (em branco), não é uma radiografia"
    if st["top"] > LINEART_TOP_MIN and st["entropy"] < LINEART_ENTROPY_MAX:
        return True, "imagem com aparência de documento/traçado (fundo uniforme dominante), não é uma radiografia"
    if region != BodyRegion.CHEST:
        nome = REGION_PT.get(region, region.value)
        return True, (f"não é radiografia de tórax ({nome}): achados torácicos não gerados; "
                      "medidas heurísticas de baixa confiança")
    return False, None
