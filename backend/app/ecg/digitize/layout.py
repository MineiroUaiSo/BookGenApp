"""Automatic ECG page layout detection (K1): lead rows x columns + rhythm strips, from printed lead labels.

The page is described by a frozen `Layout` (lead grid, rhythm strips, column borders in pixels, lead slices).
Labels (I, II, III, aVR, aVL, aVF, V1-V6) are found as small glyph groups next to the trace baselines and matched against
rendered serif templates (own font fallback chain, no OCR dependency). A layout is accepted only when the recognised
labels agree with one of the known page layouts; otherwise `Layout.ok` is False and the caller must abstain or use
its legacy heuristics. Calibration pulses (rectangles at the left of each row) give gain and paper speed.
"""
from __future__ import annotations

import functools
import os
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

LEAD_NAMES = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
GRID_3x4 = [["I", "II", "III"], ["aVR", "aVL", "aVF"], ["V1", "V2", "V3"], ["V4", "V5", "V6"]]  # columns
GRID_6x2 = [["I", "II", "III", "aVR", "aVL", "aVF"], ["V1", "V2", "V3", "V4", "V5", "V6"]]
GRID_12x1 = [LEAD_NAMES[:]]
# name -> (columns of leads, rhythm strip leads); the order of rhythm strips is the printed order top-down
KNOWN_LAYOUTS = {
    "3x4+3": (GRID_3x4, ["V1", "II", "V5"]),
    "3x4+2": (GRID_3x4, ["II", "V5"]),
    "3x4+1": (GRID_3x4, ["II"]),
    "3x4": (GRID_3x4, []),
    "6x2+1": (GRID_6x2, ["II"]),
    "6x2": (GRID_6x2, []),
    "12x1": (GRID_12x1, []),
}
STRONG_LABEL = 0.55     # minimum template score for a recognised label
MIN_LABELS = 4          # recognised labels needed to confirm a layout
MIN_AGREEMENT = 0.75    # fraction of recognised labels that must agree with the layout
BASELINE_PULL = 0.06  # DP node cost per mm of distance from the row baseline (keeps tracking off neighbour rows)
UP_PITCH, DOWN_PITCH = 2.0, 1.0   # vertical search window of a lead, in row pitches (tall R waves reach 1.5 rows)


@dataclass(frozen=True)
class LeadSlice:
    name: str
    row: int                   # index of the baseline in Layout.row_y
    x0: int
    x1: int
    y0: int
    y1: int
    rhythm: bool = False


@dataclass(frozen=True)
class Layout:
    ok: bool
    name: str = ""
    reason: str = ""
    columns: tuple = ()        # ((x0, x1), ...) of the lead grid
    names: tuple = ()          # names[col][row]
    rhythm: tuple = ()         # rhythm strip lead names
    row_y: tuple = ()
    slices: tuple = ()
    n_labels: int = 0
    agreement: float = 0.0
    gain_mm_mv: float | None = None
    speed_mm_s: float | None = None
    pulse_x_end: float | None = None
    labels: tuple = field(default=(), repr=False)


# --------------------------------------------------------------------------------------------- label templates
def _font(size: int):
    from PIL import ImageFont
    cands = []
    try:
        import matplotlib
        cands.append(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "STIXGeneral.ttf"))
        cands.append(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSerif.ttf"))
    except Exception:  # noqa: BLE001 - matplotlib is optional
        pass
    cands += ["/System/Library/Fonts/Supplemental/Times New Roman.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
    for c in cands:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


@functools.lru_cache(maxsize=1)
def _templates() -> dict:
    from PIL import Image, ImageDraw
    font = _font(90)
    out = {}
    for n in LEAD_NAMES:
        im = Image.new("L", (500, 160), 0)
        ImageDraw.Draw(im).text((20, 20), n, font=font, fill=255)
        a = np.asarray(im) > 128
        ys, xs = np.nonzero(a)
        out[n] = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return out


_CMP = (48, 26)  # (w, h) of the comparison raster


def _raster(a: np.ndarray) -> np.ndarray:
    import cv2
    r = cv2.resize(a.astype(np.float32), _CMP, interpolation=cv2.INTER_AREA)
    r = cv2.GaussianBlur(r, (0, 0), 0.6)
    r = r - r.mean()
    return r / (np.linalg.norm(r) + 1e-9)


@functools.lru_cache(maxsize=1)
def _template_rasters() -> dict:
    return {n: (_raster(t), t.shape[1] / t.shape[0]) for n, t in _templates().items()}


def match_label(word: np.ndarray) -> tuple[str | None, float]:
    """Best lead name for a binary word crop and its score (None when nothing plausible)."""
    h, w = word.shape
    if h < 4 or w < 2:
        return None, 0.0
    r, ratio = _raster(word), w / h
    best, best_s = None, -1.0
    for n, (tr, tratio) in _template_rasters().items():
        s = float((r * tr).sum()) - 0.6 * abs(np.log(ratio / tratio))
        if s > best_s:
            best, best_s = n, s
    return (best, best_s) if best_s >= STRONG_LABEL else (None, best_s)


# --------------------------------------------------------------------------------------------- words
def find_words(ink0: np.ndarray, ink: np.ndarray, ppx: float, ppy: float) -> list[dict]:
    """Small text-like glyph groups (pixels dropped by clean_ink) as dicts(x0, y0, x1, y1, mask)."""
    txt = ink0 & ~ink
    bx, by = int(1.5 * ppx), int(1.5 * ppy)
    txt[:by], txt[-by:], txt[:, :bx], txt[:, -bx:] = False, False, False, False
    lab, n = ndi.label(txt, structure=np.ones((3, 3)))
    glyphs = []
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        h, w = (sl[0].stop - sl[0].start) / ppy, (sl[1].stop - sl[1].start) / ppx
        if 0.9 <= h <= 4.2 and w <= 4.0:
            glyphs.append([sl[1].start, sl[0].start, sl[1].stop, sl[0].stop, i])
    glyphs.sort()
    words: list[list] = []
    for g in glyphs:
        for wd in words:
            ov = min(g[3], wd[3]) - max(g[1], wd[1])
            if ov >= 0.5 * min(g[3] - g[1], wd[3] - wd[1]) and 0 <= g[0] - wd[2] <= 1.1 * ppx:
                wd[0], wd[1], wd[2], wd[3] = min(wd[0], g[0]), min(wd[1], g[1]), max(wd[2], g[2]), max(wd[3], g[3])
                wd[4].append(g[4])
                break
        else:
            words.append([g[0], g[1], g[2], g[3], [g[4]]])
    out = []
    for x0, y0, x1, y1, ids in words:
        h, w = (y1 - y0) / ppy, (x1 - x0) / ppx
        if not (1.3 <= h <= 4.2 and 0.6 <= w <= 9.0):
            continue
        out.append(dict(x0=x0, y0=y0, x1=x1, y1=y1, mask=np.isin(lab[y0:y1, x0:x1], ids)))
    return out


def label_words(ink0, ink, rows, ppx, ppy, x_min: float) -> list[dict]:
    """Recognised lead labels: dicts(name, score, x0, x1, y0, y1, row). A label sits just below the left end of its
    own baseline (up to ~9 mm below, 1 mm above)."""
    out = []
    for w in find_words(ink0, ink, ppx, ppy):
        if w["x0"] < x_min - 2 * ppx:
            continue
        cy = 0.5 * (w["y0"] + w["y1"])
        ri = [i for i, y in enumerate(rows) if y - 1.5 * ppy <= cy <= y + 9.0 * ppy]
        if not ri:
            continue
        name, s = match_label(w["mask"])
        if name:
            out.append(dict(name=name, score=s, x0=w["x0"], x1=w["x1"], y0=w["y0"], y1=w["y1"], row=ri[-1]))
    return out


# --------------------------------------------------------------------------------------------- layout choice
def _score_layout(labels: list[dict], rows: list[float], cols, rhythm, x_min: float) -> tuple[float, int, list]:
    """Agreement of the recognised labels with one layout hypothesis -> (agreement, n_labels, column_x0 per column)."""
    n_lead_rows = len(cols[0])
    if len(rows) != n_lead_rows + len(rhythm):
        return 0.0, 0, []
    ok = bad = 0
    col_x = [[] for _ in cols]
    for lb in labels:
        r = lb["row"]
        if r < n_lead_rows:  # lead row: label belongs to whichever column has this name in this row
            hit = [c for c, names in enumerate(cols) if names[r] == lb["name"]]
            if hit:
                ok += 1
                col_x[hit[0]].append(lb["x0"])
            else:
                bad += 1
        else:
            if lb["name"] == rhythm[r - n_lead_rows]:
                ok += 1
            else:
                bad += 1
    n = ok + bad
    return (ok / n if n else 0.0), n, [float(np.median(c)) if c else None for c in col_x]


def _pulses(ink0, rows, ppx, ppy, band) -> list[dict]:
    """Calibration pulses on the left page border: rectangle of ~5 mm x 10 mm below/above each baseline."""
    out = []
    for y_b in rows:
        y0, y1 = int(max(0, y_b - band)), int(min(ink0.shape[0], y_b + 0.3 * band))
        sub = ink0[y0:y1, : int(14 * ppx)]
        if not sub.any():
            continue
        has = sub.any(0)
        top = np.where(has, sub.argmax(0), -1)
        thin = np.array([top[i] >= 0 and (sub[top[i]:top[i] + int(1.3 * ppy) + 1, i].sum() >= 1) for i in range(len(top))])
        yref = y_b - y0
        cand = (top >= 0) & ((yref - top) > 3.0 * ppy)
        best, i = None, 0
        while i < len(cand):
            if not cand[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(cand) and cand[j + 1] and abs(top[j + 1] - top[i]) <= 1:
                j += 1
            if best is None or j - i > best[1] - best[0]:
                best = (i, j)
            i = j + 1
        if best is None or not thin[best[0]]:
            continue
        i, j = best
        wmm = (j - i + 1) / ppx
        if wmm < 2.5 or wmm > 12:
            continue
        # falling edge: first columns after the plateau; its lowest ink is the pulse foot
        edge = [c for c in range(j + 1, min(len(top), j + 4)) if has[c]]
        if not edge:
            continue
        foot = np.median([y0 + (sub.shape[0] - 1 - sub[::-1, c].argmax()) for c in edge])
        plat = y0 + float(np.median(top[i:j + 1]))
        out.append(dict(height_mm=(foot - plat) / ppy, width_mm=wmm, x_end=float(j), row_y=float(y_b)))
    return out


def snap_calibration(pulses: list[dict]) -> tuple[float | None, float | None]:
    if len(pulses) < 2:
        return None, None
    h = float(np.median([p["height_mm"] for p in pulses]))
    w = float(np.median([p["width_mm"] for p in pulses]))
    gain = min((5.0, 10.0, 20.0), key=lambda g: abs(g - h))
    gain = gain if abs(gain - h) / gain < 0.2 else None
    speed = 25.0 if abs(w - 5) / 5 < 0.3 else (50.0 if abs(w - 10) / 10 < 0.3 else None)
    return gain, speed


def detect_layout(ink0: np.ndarray, ink: np.ndarray, rows: list[float], ppx: float, ppy: float,
                  x_start: float, x_end: float) -> Layout:
    """Confirm the page layout from lead labels. `rows` are the trace baselines found by trace.detect_rows;
    x_start/x_end the data span in px (after the calibration pulse)."""
    n_rows = len(rows)
    if n_rows < 1:
        return Layout(False, reason="sem linhas de traçado")
    pitch = float(np.median(np.diff(rows))) if n_rows > 1 else 30 * ppy
    pul = _pulses(ink0, rows, ppx, ppy, band=min(0.95 * pitch, 26 * ppy))
    gain, speed = snap_calibration(pul)
    labels = label_words(ink0, ink, rows, ppx, ppy, x_min=x_start - 4 * ppx)
    best = None
    for name, (cols, rhythm) in KNOWN_LAYOUTS.items():
        agr, n, cx = _score_layout(labels, rows, cols, rhythm, x_start)
        if n >= MIN_LABELS and agr >= MIN_AGREEMENT and (best is None or (agr, n) > (best[1], best[2])):
            best = (name, agr, n, cx, cols, rhythm)
    px_end = float(np.median([p["x_end"] for p in pul])) if pul else None
    if best is None:
        return Layout(False, reason=f"rótulos das derivações não confirmam um layout conhecido ({len(labels)} reconhecidos, {n_rows} linhas)",
                      row_y=tuple(rows), n_labels=len(labels), gain_mm_mv=gain, speed_mm_s=speed, pulse_x_end=px_end,
                      labels=tuple(labels))
    name, agr, n, cx, cols, rhythm = best
    # column borders: label left edges; missing ones fall back to equal division of the data span
    nc = len(cols)
    starts = [float(x_start)]
    for c in range(1, nc):
        starts.append(cx[c] - 1.0 if cx[c] is not None else x_start + c * (x_end - x_start) / nc)
    starts.append(float(x_end))
    if any(b <= a + 5 * ppx for a, b in zip(starts, starts[1:])):
        return Layout(False, reason="colunas inconsistentes", row_y=tuple(rows), n_labels=len(labels),
                      gain_mm_mv=gain, speed_mm_s=speed, labels=tuple(labels))
    columns = tuple((int(round(a)), int(round(b - 2 if c < nc - 1 else b))) for c, (a, b) in enumerate(zip(starts, starts[1:])))
    H = int(max(r for r in rows) + 2 * pitch) + 1
    sl = []
    for r, y in enumerate(rows):
        y0, y1 = int(max(0, y - UP_PITCH * pitch)), int(min(H, y + DOWN_PITCH * pitch))
        if r < len(cols[0]):
            for c, (a, b) in enumerate(columns):
                sl.append(LeadSlice(cols[c][r], r, a, b, y0, y1))
        else:
            sl.append(LeadSlice(rhythm[r - len(cols[0])], r, int(x_start), int(x_end), y0, y1, True))
    return Layout(True, name=name, columns=columns, names=tuple(tuple(c) for c in cols), rhythm=tuple(rhythm),
                  row_y=tuple(rows), slices=tuple(sl), n_labels=n, agreement=agr, gain_mm_mv=gain, speed_mm_s=speed,
                  pulse_x_end=px_end, labels=tuple(labels))


# --------------------------------------------------------------------------------------------- slice extraction
def _stroke_path(cen: np.ndarray, top: np.ndarray, bot: np.ndarray, thick: float) -> np.ndarray:
    """One y per column. Columns holding a long vertical stroke (steep QRS flank, merged up/down strokes of an R wave)
    take the end of the run farthest from the previous sample, so a spike is a clean up-down pair instead of the
    run centre (which produced a fake double peak and widened the QRS)."""
    y = cen.copy()
    prev = None
    for i in range(len(y)):
        if np.isnan(y[i]):
            continue
        if prev is not None and (bot[i] - top[i] + 1) > 2.5 * thick + 1:
            y[i] = top[i] + thick / 2 if abs(top[i] - prev) > abs(bot[i] - prev) else bot[i] - thick / 2
        prev = y[i]
    return y


def extract_slices(lay: Layout, ink: np.ndarray, ppx: float, ppy: float, mm_y, mm_x, px_of_mm_x, xs_mm: float, speed: float,
                   gain: float, out_fs: float) -> tuple[dict, dict, dict]:
    """Digitize every slice of a confirmed layout independently (column-restricted, vertical window of its own row).
    A trace can never cross into the neighbouring column: its pixels are cropped at the column borders. Rhythm strips
    (full width) replace the short segment of the same lead, being the longer record. Returns (leads, quality, offset_s)."""
    from scipy.ndimage import gaussian_filter1d
    from . import trace
    leads: dict[str, list[float]] = {}
    quality: dict[str, float] = {}
    offsets: dict[str, float] = {}
    for sl in sorted(lay.slices, key=lambda s: s.rhythm):  # rhythm strips last: they override
        if sl.x1 - sl.x0 < 10:
            continue
        y_b = lay.row_y[sl.row]
        cen, top, bot, valid = trace.extract_row(ink, sl.x0, sl.x1, y_b, 0, ppy, y_lo=sl.y0, y_hi=sl.y1, node_w=BASELINE_PULL)
        if not np.isfinite(cen).any():
            continue
        thick = float(np.nanmedian(bot - top + 1)) if np.isfinite(bot - top).any() else 3.0
        cen = _stroke_path(cen, top, bot, thick)
        n = len(cen)
        idx = np.arange(n)
        ok = ~np.isnan(cen)
        if ok.sum() < 0.3 * n:
            continue
        seg = np.interp(idx, idx[ok], cen[ok])
        t0 = float(mm_x(sl.x0) - xs_mm) / speed
        t1 = float(mm_x(sl.x1) - xs_mm) / speed
        n_out = int(round((t1 - t0) * out_fs))
        if n_out < 10:
            continue
        ymm = mm_y(seg + 0.0)
        mv = -(ymm - float(np.median(ymm))) / gain
        cps = float(px_of_mm_x(xs_mm + 1.0 * speed) - px_of_mm_x(xs_mm))
        if cps > out_fs * 1.2:
            mv = gaussian_filter1d(mv, 0.5 * cps / out_fs)
        px = px_of_mm_x(xs_mm + (t0 + np.arange(n_out) / out_fs) * speed) - sl.x0
        leads[sl.name] = np.interp(px, idx, mv).tolist()
        quality[sl.name] = round(float(valid.mean()), 3)
        offsets[sl.name] = max(t0, 0.0)
    return leads, quality, offsets
