"""Printed-header reader (K2): PR / QRS / QT-QTc / P-R-T axes / vent. rate printed by the ECG machine.

Deterministic digit template matching only (no OCR engine, no model): glyphs found in the top-left text block are
matched against rendered serif digit templates. Used as a cross-check of the digitised signal, never as a measurement
source for findings. Returns None when nothing legible is found.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

from .layout import _font

UPSCALE = 4
LINE_PITCH_MM = 3.3       # GE 12SL header line pitch
MIN_DIGIT_SCORE = 0.72
DIGITS = "0123456789/"


@dataclass(frozen=True)
class PrintedValues:
    pr_ms: float | None = None
    qrs_ms: float | None = None
    qt_ms: float | None = None
    qtc_ms: float | None = None
    p_axis: float | None = None
    r_axis: float | None = None
    t_axis: float | None = None
    vent_rate: float | None = None
    sex: str | None = None            # "M"/"F" when the printed word is legible, else None
    lines: tuple = field(default=(), repr=False)

    def as_calibration(self) -> dict[str, float]:
        d = {"printed.pr_ms": self.pr_ms, "printed.qrs_ms": self.qrs_ms, "printed.qt_ms": self.qt_ms,
             "printed.qtc_ms": self.qtc_ms, "printed.p_axis": self.p_axis, "printed.r_axis": self.r_axis,
             "printed.t_axis": self.t_axis, "printed.vent_rate": self.vent_rate}
        return {k: float(v) for k, v in d.items() if v is not None}

    def text(self) -> str:
        parts = []
        if self.vent_rate is not None:
            parts.append(f"FC {self.vent_rate:.0f} bpm")
        if self.pr_ms is not None:
            parts.append(f"PR {self.pr_ms:.0f} ms")
        if self.qrs_ms is not None:
            parts.append(f"QRS {self.qrs_ms:.0f} ms")
        if self.qt_ms is not None:
            parts.append(f"QT/QTc {self.qt_ms:.0f}/{self.qtc_ms:.0f} ms" if self.qtc_ms is not None else f"QT {self.qt_ms:.0f} ms")
        if None not in (self.p_axis, self.r_axis, self.t_axis):
            parts.append(f"eixos P/R/T {self.p_axis:.0f}/{self.r_axis:.0f}/{self.t_axis:.0f}°")
        return "; ".join(parts)


@functools.lru_cache(maxsize=64)
def _sized_templates(h: int) -> dict:
    """Digit templates rendered at pixel height h (antialiased, thresholded) -> {char: bool array}."""
    from PIL import Image, ImageDraw
    out = {}
    for size in (h / 0.66, h / 0.70):
        font = _font(max(6, int(round(size))))
        for ch in DIGITS:
            im = Image.new("L", (80, 80), 0)
            ImageDraw.Draw(im).text((10, 10), ch, font=font, fill=255)
            a = np.asarray(im) > 100
            ys, xs = np.nonzero(a)
            crop = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            if abs(crop.shape[0] - h) <= 2:
                out.setdefault(ch, []).append(crop)
    return out


def _dice(a: np.ndarray, b: np.ndarray) -> float:
    """Best Dice overlap of two bool masks over +-1 px shifts, both lightly dilated."""
    H, W = max(a.shape[0], b.shape[0]) + 4, max(a.shape[1], b.shape[1]) + 4
    def pad(m, dy, dx):
        z = np.zeros((H, W), bool)
        y0, x0 = (H - m.shape[0]) // 2 + dy, (W - m.shape[1]) // 2 + dx
        z[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m
        return z
    best = 0.0
    pa = ndi.binary_dilation(pad(a, 0, 0))
    for dy in (-2, 0, 2):
        for dx in (-2, 0, 2):
            pb = ndi.binary_dilation(pad(b, dy, dx))
            best = max(best, 2.0 * (pa & pb).sum() / max(pa.sum() + pb.sum(), 1))
    return best


def classify_blob(mask: np.ndarray) -> tuple[str | None, float]:
    """One glyph, or two touching glyphs (e.g. '8/') split at the ink valley of a wide blob."""
    ch, s = classify_glyph(mask)
    if ch is not None:
        return ch, s
    h, w = mask.shape
    if w < 0.55 * h:
        return None, s
    prof = mask.sum(0).astype(float)
    lo, hi = int(0.3 * w), max(int(0.7 * w), int(0.3 * w) + 1)
    cut = lo + int(np.argmin(prof[lo:hi]))
    (a, sa), (b, sb) = classify_glyph(mask[:, :cut]), classify_glyph(mask[:, cut:])
    if a is not None and b is not None:
        return a + b, min(sa, sb)
    return None, s


def classify_glyph(mask: np.ndarray) -> tuple[str | None, float]:
    h, w = mask.shape
    if h < 12 or w < 2:
        return None, 0.0
    best, best_s = None, 0.0
    for ch, crops in _sized_templates(h).items():
        for t in crops:
            if abs(t.shape[1] - w) > 8 + 0.3 * w:
                continue
            s = _dice(mask, t)
            if s > best_s:
                best, best_s = ch, s
    return (best, best_s) if best_s >= MIN_DIGIT_SCORE else (None, best_s)


def _binary_header(norm: np.ndarray, y_max: int, x_max: int) -> np.ndarray:
    """Upsampled (x UPSCALE, bicubic) dark-pixel mask of the header area: digit shapes are smooth enough to compare."""
    import cv2
    from skimage.filters import threshold_otsu
    dark = 1.0 - norm[:y_max, :x_max].min(axis=2)
    up = cv2.resize(dark.astype(np.float32), None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)
    thr = max(float(threshold_otsu(up)), 0.35)
    return up > thr


def _glyphs(binary: np.ndarray, ppx: float, ppy: float) -> list[dict]:
    """Digit-sized connected components of the upsampled header mask (pixel units of the upsampled mask)."""
    sub = ndi.binary_closing(binary, structure=np.ones((2 * UPSCALE + 1, 1)))  # printed grid lines cut glyphs
    lab, _ = ndi.label(sub, structure=np.ones((3, 3)))
    out = []
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        h, w = (sl[0].stop - sl[0].start) / (ppy * UPSCALE), (sl[1].stop - sl[1].start) / (ppx * UPSCALE)
        if 1.4 <= h <= 3.6 and w <= 4.5 and sl[0].start > UPSCALE:  # glyphs cut by the page edge are unreadable
            out.append(dict(x0=sl[1].start, x1=sl[1].stop, y0=sl[0].start, y1=sl[0].stop, mask=lab[sl] == i))
    return out


def _numeric_words(glyphs: list[dict], ppx: float, ppy: float) -> list[dict]:
    """Group glyphs of one text line into words and keep the fully numeric ones."""
    lines: list[list[dict]] = []
    for g in sorted(glyphs, key=lambda g: g["y1"]):  # baseline = bottom edge
        for ln in lines:
            if abs(ln[0]["y1"] - g["y1"]) <= 0.5 * ppy * UPSCALE:
                ln.append(g)
                break
        else:
            lines.append([g])
    words = []
    for li, ln in enumerate(sorted(lines, key=lambda l: l[0]["y1"])):
        ln.sort(key=lambda g: g["x0"])
        cur: list[dict] = []
        for g in ln + [None]:
            if g is not None and cur and g["x0"] - cur[-1]["x1"] <= 1.2 * ppx * UPSCALE:
                cur.append(g)
                continue
            if cur:
                cls = [classify_blob(c["mask"]) for c in cur]
                if all(c[0] is not None for c in cls):
                    words.append(dict(line=li, y1=cur[0]["y1"], x0=cur[0]["x0"], text="".join(c[0] for c in cls),
                                      score=float(np.mean([c[1] for c in cls]))))
            cur = [g] if g is not None else []
    return words


def _num(s: str) -> float | None:
    try:
        v = float(s)
    except ValueError:
        return None
    return v


def read_header(norm: np.ndarray, ppx: float, ppy: float) -> PrintedValues | None:
    """Printed intervals/axes of the top-left header block (GE MUSE/12SL-like order: [vent. rate], PR, QRS, QT/QTc,
    P-R-T axes). The line identity comes from the digit pattern and line order; None when nothing legible."""
    y_max = int(min(norm.shape[0] * 0.2, 22 * ppy))
    x_max = int(norm.shape[1] * 0.6)
    words = _numeric_words(_glyphs(_binary_header(norm, y_max, x_max), ppx, ppy), ppx, ppy)
    by_line: dict[int, list[dict]] = {}
    for w in words:
        by_line.setdefault(w["line"], []).append(w)
    rows, row_y = [], []
    for li in sorted(by_line):
        ws = sorted(by_line[li], key=lambda w: w["x0"])
        rows.append([w["text"] for w in ws])
        row_y.append(float(np.mean([w["y1"] for w in ws])))
    # the numeric block is the right-aligned cluster of the header: keep the last consecutive lines
    qt = [r for r in rows if len(r) == 1 and r[0].count("/") == 1]
    axes = [r for r in rows if len(r) == 3 and all("/" not in t for t in r)]
    if not (qt or axes):
        return None
    # the machine prints [vent. rate,] PR, QRS, QT/QTc, axes on a fixed line pitch: identify single-number lines by
    # their distance (in lines) from the QT/axes anchor, so a line clipped by the page edge cannot shift the others
    ys = {tuple(r): y for r, y in zip(rows, row_y)}
    pitch = LINE_PITCH_MM * ppy * UPSCALE
    anchor = ys[tuple(qt[0])] if qt else ys[tuple(axes[0])] - pitch
    vr = pr = qrs = None
    for r in rows:
        if len(r) != 1 or "/" in r[0]:
            continue
        k = int(round((anchor - ys[tuple(r)]) / pitch))   # lines above the QT line
        if k == 1:
            qrs = _num(r[0])
        elif k == 2:
            pr = _num(r[0])
        elif k == 3:
            vr = _num(r[0])
    qt_v = qtc_v = None
    if qt:
        a, b = qt[0][0].split("/")
        qt_v, qtc_v = _num(a), _num(b)
    pa = ra = ta = None
    if axes:
        pa, ra, ta = (_num(t) for t in axes[0])
    pv = PrintedValues(pr_ms=pr, qrs_ms=qrs, qt_ms=qt_v, qtc_ms=qtc_v, p_axis=pa, r_axis=ra, t_axis=ta,
                       vent_rate=vr, lines=tuple(tuple(r) for r in rows))
    # sanity: physiologic ranges, else drop the value (a misread digit must never become a "reference")
    ok = lambda v, lo, hi: v if v is not None and lo <= v <= hi else None
    return PrintedValues(pr_ms=ok(pv.pr_ms, 60, 400), qrs_ms=ok(pv.qrs_ms, 50, 300), qt_ms=ok(pv.qt_ms, 200, 700),
                         qtc_ms=ok(pv.qtc_ms, 250, 700), p_axis=ok(pv.p_axis, -180, 180), r_axis=ok(pv.r_axis, -180, 180),
                         t_axis=ok(pv.t_axis, -180, 180), vent_rate=ok(pv.vent_rate, 20, 300), lines=pv.lines)
