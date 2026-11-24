"""Imagens auxiliares enviadas ao modelo: plot do ECG em grade e overlay de segmentação do RX."""
from __future__ import annotations

import base64
import io
from typing import Optional

from ..schemas import ECGAnalysis, RXImageAnalysis

_LAYOUT = [["I", "aVR", "V1", "V4"], ["II", "aVL", "V2", "V5"], ["III", "aVF", "V3", "V6"]]
MAX_SIDE = 1568


def render_ecg_plot(analysis: ECGAnalysis) -> Optional[bytes]:
    """Renderiza as 12 derivações em grade de ECG (25 mm/s, 10 mm/mV), layout 3x4 + ritmo (DII)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:  # pragma: no cover
        return None
    sig = analysis.signal
    fs = sig.fs
    if not sig.leads or not fs:
        return None
    seg_s = min(2.5, sig.duration_s / 4) if sig.duration_s else 2.5
    total_s = 4 * seg_s
    mm_per_s, mm_per_mv = 25.0, 10.0
    width_mm = total_s * mm_per_s
    row_h_mm = 30.0  # 3 mV por faixa
    n_rows = 4
    fig_w = width_mm / 25.4 * 0.75
    fig_h = (n_rows * row_h_mm) / 25.4 * 0.75 + 0.3
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=130)
    ax.set_xlim(0, width_mm)
    ax.set_ylim(-n_rows * row_h_mm + row_h_mm * 0.5, row_h_mm * 0.5)
    for x in np.arange(0, width_mm + 1, 1):
        ax.axvline(x, color="#f4b6b6", lw=0.25 if x % 5 else 0.6)
    for y in np.arange(ax.get_ylim()[0], ax.get_ylim()[1] + 1, 1):
        ax.axhline(y, color="#f4b6b6", lw=0.25 if int(round(y)) % 5 else 0.6)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)

    def draw(lead: str, row: int, t0: float, t1: float, x0_mm: float):
        data = sig.leads.get(lead)
        if not data:
            return
        i0, i1 = int(t0 * fs), min(len(data), int(t1 * fs))
        if i1 <= i0:
            return
        y = np.asarray(data[i0:i1], dtype=float) * mm_per_mv - row * row_h_mm
        x = x0_mm + (np.arange(i1 - i0) / fs) * mm_per_s
        ax.plot(x, y, color="black", lw=0.7)
        ax.text(x0_mm + 1, -row * row_h_mm + row_h_mm * 0.38, lead, fontsize=7, fontweight="bold")

    for col in range(4):
        t0 = col * seg_s
        for row in range(3):
            draw(_LAYOUT[row][col], row, t0, t0 + seg_s, col * seg_s * mm_per_s)
    rhythm = "II" if "II" in sig.leads else next(iter(sig.leads))
    draw(rhythm, 3, 0.0, min(total_s, sig.duration_s or total_s), 0.0)
    ax.text(width_mm - 1, row_h_mm * 0.42, "25 mm/s  10 mm/mV  (1 mm = 40 ms = 0,1 mV)",
            ha="right", fontsize=6, color="#555")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return buf.getvalue()


def _fit(img):
    w, h = img.size
    s = MAX_SIDE / max(w, h)
    if s < 1:
        img = img.resize((int(w * s), int(h * s)))
    return img


def _to_png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def rx_image_png(img: RXImageAnalysis) -> bytes:
    from PIL import Image

    raw = base64.b64decode(img.image_png_b64.split(",")[-1])
    return _to_png(_fit(Image.open(io.BytesIO(raw)).convert("RGB")))


def rx_overlay_png(img: RXImageAnalysis) -> Optional[bytes]:
    """Imagem com máscaras coloridas e legenda das estruturas segmentadas; None se não há máscaras."""
    from PIL import Image, ImageDraw

    structs = [s for s in img.structures if s.mask_png_b64 or s.polygon]
    if not structs:
        return None
    base = Image.open(io.BytesIO(base64.b64decode(img.image_png_b64.split(",")[-1]))).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    drawer = ImageDraw.Draw(overlay)
    for s in structs:
        rgb = tuple(int(s.color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if s.color.startswith("#") and len(s.color) >= 7 else (255, 0, 0)
        if s.mask_png_b64:
            try:
                m = Image.open(io.BytesIO(base64.b64decode(s.mask_png_b64.split(",")[-1]))).convert("L").resize(base.size)
                m = m.point(lambda v: 90 if v > 127 else 0)
                overlay.paste(Image.new("RGBA", base.size, rgb + (255,)), (0, 0), m)
            except Exception:
                pass
        if s.polygon and len(s.polygon) > 2:
            drawer.line([tuple(p) for p in s.polygon] + [tuple(s.polygon[0])], fill=rgb + (255,), width=2)
    comp = Image.alpha_composite(base, overlay).convert("RGB")
    d = ImageDraw.Draw(comp)
    y = 6
    for s in structs[:30]:
        rgb = tuple(int(s.color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if s.color.startswith("#") and len(s.color) >= 7 else (255, 0, 0)
        d.rectangle([6, y, 18, y + 10], fill=rgb, outline=(255, 255, 255))
        d.text((22, y), s.label, fill=(255, 255, 0))
        y += 14
    return _to_png(_fit(comp))
