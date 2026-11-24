"""ECG photo/scan -> ECGSignal digitizer."""
from __future__ import annotations

import numpy as np

from app.schemas import ECGSignal, SourceKind

from . import geometry, grid, trace

OUT_FS = 500.0


def _interp_nan(y):
    n = np.isnan(y)
    if n.all():
        return np.zeros_like(y), 0.0
    if n.any():
        x = np.arange(len(y))
        y = np.interp(x, x[~n], y[~n])
    return y, 1.0


def _unused(y_cols: np.ndarray, cols_per_s: float, n_out: int) -> np.ndarray:
    if cols_per_s > OUT_FS * 1.2:
        from scipy.ndimage import gaussian_filter1d
        y_cols = gaussian_filter1d(y_cols, 0.5 * cols_per_s / OUT_FS)
    t = np.arange(n_out) / OUT_FS
    return np.interp(t * cols_per_s, np.arange(len(y_cols)), y_cols)


def digitize_image(img: np.ndarray, layout: str = "auto", paper_speed_mm_s: float | None = None,
                   gain_mm_mv: float | None = None, return_debug: bool = False):
    """Digitize a 12-lead ECG paper photo/scan. See module docs; leads of a 3x4(+1) page are 2.5 s long,
    except `II` which is the 10 s rhythm strip when present. Per-lead start offsets are reported in
    calibration["offset_s.<lead>"]."""
    warnings: list[str] = []
    rgb = geometry.limit_size(geometry.to_rgb_uint8(img))
    rgb, ginfo = geometry.rectify(rgb)
    norm = grid.normalise(rgb)
    ink0 = grid.trace_mask(norm)
    gr = grid.detect_grid(norm, ink0)
    if not gr["px_per_mm_x"]:
        raise ValueError("could not detect the ECG grid (px/mm)")
    ppx, ppy = gr["px_per_mm_x"], gr["px_per_mm_y"]
    mm_x, px_of_mm_x = gr["map_x"]
    mm_y, _ = gr["map_y"]
    ink = trace.clean_ink(ink0, ppx, ppy)

    cols_ink = ink.sum(0)
    nz = np.nonzero(cols_ink > 0)[0]
    if len(nz) == 0:
        raise ValueError("no ECG trace found")
    xs_left, x_right = int(nz[0]), int(nz[-1])
    row_xa = xs_left + int(10 * ppx)
    rows = trace.detect_rows(ink, row_xa, x_right, ppy)
    n_rows = len(rows)
    if n_rows == 0:
        raise ValueError("no trace rows found")
    if layout == "auto":
        layout = trace.ROWS_TO_LAYOUT.get(n_rows) or trace.ROWS_TO_LAYOUT[
            min(trace.ROWS_TO_LAYOUT, key=lambda k: abs(k - n_rows))]
    lay = trace.LAYOUT_LEADS[layout]
    has_rhythm = layout == "3x4+1"
    expect_rows = len(lay[0]) + (1 if has_rhythm else 0)
    if n_rows != expect_rows:
        warnings.append(f"detected {n_rows} rows, layout {layout} expects {expect_rows}")
    pitch = float(np.median(np.diff(rows))) if n_rows > 1 else 30 * ppy
    half_band = int(0.75 * pitch)

    # calibration pulse per row -> gain, speed, data origin
    pulses = []
    for r in rows:
        p = trace.find_pulse(ink, r, xs_left, ppx, ppy, band=min(0.9 * pitch, 25 * ppy))
        if p:
            pulses.append(p)
    gain = gain_mm_mv
    speed = paper_speed_mm_s
    xs = None
    if pulses:
        hmm = float(np.median([p["height_mm"] for p in pulses]))
        wmm = float(np.median([p["width_mm"] for p in pulses]))
        xs = float(np.median([p["x_end"] for p in pulses]))
        if gain is None:
            snapped = min((5.0, 10.0, 20.0), key=lambda g: abs(g - hmm))
            gain = snapped if abs(snapped - hmm) / snapped < 0.2 else 10.0
            if gain == 10.0 and abs(hmm - 10) / 10 >= 0.2:
                warnings.append(f"calibration pulse height {hmm:.1f} mm implausible; assuming 10 mm/mV")
        if speed is None:
            if abs(wmm - 5) / 5 < 0.3:
                speed = 25.0
            elif abs(wmm - 10) / 10 < 0.3:
                speed = 50.0
    else:
        warnings.append("calibration pulse not found; using defaults")
    gain = gain or 10.0
    speed = speed or 25.0
    if xs is None:
        xs = xs_left + 9 * ppx
    xs_mm = float(mm_x(xs))
    cps = ppx * speed  # columns per second
    total_s = 10.0
    meas = (x_right - xs) / cps
    if meas < 0.9 * total_s or meas > 1.08 * total_s:
        snap = min((2.5, 5.0, 10.0), key=lambda v: abs(v - meas))
        total_s = snap if abs(snap - meas) / snap < 0.1 else max(2.5, round(meas * 2) / 2)
        warnings.append(f"trace length {meas:.1f}s differs from 10 s")
    n_cols = len(lay)
    seg_s = total_s / n_cols

    leads: dict[str, list[float]] = {}
    quality: dict[str, float] = {}
    calib_extra: dict[str, float] = {}
    dbg = {"rows": rows, "ink": ink, "rgb": rgb, "traces": {}}

    def process(row_y, t0_s, t1_s):
        xa = int(round(xs + t0_s * cps))
        xb = min(int(round(xs + t1_s * cps)), ink.shape[1])
        return xa, xb

    row_cache = {}
    for ri, ry in enumerate(rows):
        xa = int(round(xs))
        xb = min(int(round(xs + total_s * cps)), ink.shape[1])
        cen, top, bot, valid = trace.extract_row(ink, xa, xb, ry, half_band, ppy)
        thick = float(np.nanmedian(bot - top + 1)) if np.isfinite(bot - top).any() else 3.0
        cen = trace.refine_extrema(cen, top, bot, thick)
        row_cache[ri] = (xa, cen, valid)
        dbg["traces"][ri] = (xa, cen)

    def lead_from(ri, t0, t1):
        xa, cen, valid = row_cache[ri]
        n_out = int(round((t1 - t0) * OUT_FS))
        t = t0 + np.arange(n_out) / OUT_FS
        px = px_of_mm_x(xs_mm + t * speed) - xa  # local column coordinate of every output sample
        a, b = int(np.floor(px.min())), int(np.ceil(px.max())) + 1
        a, b = max(a, 0), min(b, len(cen))
        if b <= a:
            return None, 0.0
        q = float(valid[a:b].mean())
        seg, ok = _interp_nan(cen[a:b].copy())
        if not ok:
            return None, 0.0
        ymm = mm_y(seg + 0.0)  # px -> mm on the paper (vertical)
        base = float(np.median(ymm))
        mv = -(ymm - base) / gain
        if cps > OUT_FS * 1.2:
            from scipy.ndimage import gaussian_filter1d
            mv = gaussian_filter1d(mv, 0.5 * cps / OUT_FS)
        return np.interp(px - a, np.arange(len(mv)), mv), q

    for c, names in enumerate(lay):
        for r, name in enumerate(names):
            if r >= n_rows:
                continue
            sig, q = lead_from(r, c * seg_s, (c + 1) * seg_s)
            if sig is None:
                continue
            leads[name] = sig.tolist()
            quality[name] = round(q, 3)
            calib_extra[f"offset_s.{name}"] = c * seg_s
    if has_rhythm and n_rows > len(lay[0]):
        sig, q = lead_from(len(lay[0]), 0.0, total_s)
        if sig is not None:
            leads["II"] = sig.tolist()
            quality["II"] = round(q, 3)
            calib_extra["offset_s.II"] = 0.0
    sig = ECGSignal(
        fs=OUT_FS, leads=leads, duration_s=max((len(v) for v in leads.values()), default=0) / OUT_FS,
        source=SourceKind.IMAGE, quality=quality,
        calibration={"paper_speed_mm_s": float(speed), "gain_mm_mv": float(gain),
                     "px_per_mm": float(0.5 * (ppx + ppy)), "px_per_mm_x": float(ppx),
                     "px_per_mm_y": float(ppy), "grid_confidence": float(gr["confidence"]),
                     "skew_deg": float(ginfo["skew_deg"]), **calib_extra})
    if return_debug:
        dbg.update(layout=layout, warnings=warnings)
        return sig, dbg
    return sig
