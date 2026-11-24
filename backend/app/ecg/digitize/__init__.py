"""ECG photo/scan -> ECGSignal digitizer."""
from __future__ import annotations

import numpy as np

from app.schemas import ECGSignal, SourceKind

from . import geometry, grid, layout as layout_mod, trace

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
                   gain_mm_mv: float | None = None, return_debug: bool = False, strict_layout: bool = False):
    """Digitize a 12-lead ECG paper photo/scan. See module docs; leads of a 3x4(+1) page are 2.5 s long,
    except `II` which is the 10 s rhythm strip when present. Per-lead start offsets are reported in
    calibration["offset_s.<lead>"]."""
    warnings: list[str] = []
    rgb0 = geometry.to_rgb_uint8(img)
    rgb = geometry.limit_size(rgb0)
    proc_scale = rgb.shape[1] / rgb0.shape[1]
    rgb, ginfo = geometry.rectify(rgb)
    norm = grid.normalise(rgb)
    ink0 = grid.trace_mask(norm)
    gr = grid.detect_grid(norm, ink0)
    lag = grid.rr_lag_px(ink0)
    grid_conf = float(gr["confidence"]) if gr["px_per_mm_x"] else 0.0
    if gr["px_per_mm_x"]:
        ppx, ppy = gr["px_per_mm_x"], gr["px_per_mm_y"]
        mm_x, px_of_mm_x = gr["map_x"]
        mm_y, _ = gr["map_y"]
        if lag is not None and not grid.plausible_scale(ppx, lag):  # wrong harmonic of the grid (1 mm vs 5 mm ...): pick by heart rate
            for f in (5.0, 0.2, 2.0, 0.5, 4.0, 0.25):
                if grid.plausible_scale(ppx * f, lag):
                    ppx = ppy = ppx * f
                    mm_x = mm_y = np.poly1d([1.0 / ppx, 0.0])
                    px_of_mm_x = np.poly1d([ppx, 0.0])
                    grid_conf *= 0.8
                    warnings.append(f"grid pitch rescaled x{f:g} to give a plausible heart rate")
                    break
            else:
                grid_conf *= 0.7
                warnings.append("grid pitch gives an implausible heart rate")
    else:  # no grid at all: scale from the beat period (assume 75 bpm) or from a 250 mm wide page
        if lag:
            ppx = ppy = lag / (0.8 * 25.0)
        else:
            ppx = ppy = rgb.shape[1] / 250.0
        if not (1.0 < ppx < 80):
            raise ValueError("could not detect the ECG grid (px/mm)")
        mm_x = mm_y = np.poly1d([1.0 / ppx, 0.0])
        px_of_mm_x = np.poly1d([ppx, 0.0])
        grid_conf = 0.1
        warnings.append("no grid found; scale assumed from beat period / page width")
    gr["confidence"] = grid_conf
    ink = trace.remove_grid_lines(ink0, ppx, ppy)
    ink = trace.clean_ink(ink, ppx, ppy)

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
    pitch = float(np.median(np.diff(rows))) if n_rows > 1 else 30 * ppy
    half_band = int(0.75 * pitch) if n_rows > 1 else int(min(0.6 * ink.shape[0], 40 * ppy))

    # calibration pulse per row (left end; else right end of the page) -> gain, speed, data origin / end
    def pulses_at(inkm, x0):
        out = []
        for r in rows:
            p = trace.find_pulse(inkm, r, x0, ppx, ppy, band=min(0.9 * pitch, 25 * ppy))
            if p:
                out.append(p)
        return out

    pulses = pulses_at(ink, xs_left)
    x_end_data = x_right
    pulse_side = "left" if pulses else None
    if not pulses:
        inkf = ink[:, ::-1]
        pf = pulses_at(inkf, ink.shape[1] - 1 - x_right)
        if pf:
            pulses = pf
            pulse_side = "right"
            x_end_data = int(ink.shape[1] - 1 - np.median([p["x_end"] for p in pf]))
    gain = gain_mm_mv
    speed = paper_speed_mm_s
    xs = None
    if pulses:
        hmm = float(np.median([p["height_mm"] for p in pulses]))
        wmm = float(np.median([p["width_mm"] for p in pulses]))
        if pulse_side == "left":
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
        xs = float(xs_left)
    skip_cols = int(np.ceil(float(np.median([p["thick"] for p in pulses])) / 2)) + 2 if pulses and pulse_side == "left" else 1
    xs_mm = float(mm_x(xs))
    cps = ppx * speed  # columns per second
    meas = (x_end_data - xs) / cps
    wide = meas >= 7.0
    layout_given = layout != "auto"
    plan = None
    if not layout_given:  # K1: layout confirmed by the printed lead labels (grid + rhythm strips, column-cropped traces)
        plan = layout_mod.detect_layout(ink0, ink, rows, ppx, ppy, xs + skip_cols, x_end_data)
        if plan.ok:
            warnings.append(f"layout {plan.name} confirmado por {plan.n_labels} rótulos de derivação")
            gain = gain_mm_mv or plan.gain_mm_mv or gain
            speed = paper_speed_mm_s or plan.speed_mm_s or speed
            cps = ppx * speed
        else:
            warnings.append("layout não confirmado por rótulos: " + plan.reason)
            if strict_layout:
                raise ValueError("layout desconhecido: " + plan.reason)
    if layout == "auto":
        if n_rows <= 2:
            layout = "strips"
        elif n_rows in (3, 4, 5):
            layout = "3x4+1" if n_rows >= 4 else "3x4"
        elif n_rows == 6 or 7 <= n_rows <= 9:
            layout = "6x2"
        else:
            layout = "12x1"
    has_rhythm = layout == "3x4+1"
    if layout == "strips":
        lay = [trace.STRIP_NAMES[:n_rows]]
        total_s, n_cols = meas, 1
    else:
        lay = trace.LAYOUT_LEADS[layout]
        n_cols = len(lay)
        seg_nom = 10.0 / n_cols
        if n_cols == 1:
            total_s = meas
        elif wide and abs(meas - 10.0) < 2.5:
            # columns are equal parts of the printed trace: place the boundaries on the measured span (a nominal
            # 2.5 s grid drifts by 100+ ms on scaled/cropped prints and corrupts RR across column borders)
            total_s = meas if abs(meas - 10.0) > 0.15 else 10.0
        else:  # cropped / narrower page: keep the nominal segment length, drop columns that do not fit
            n_fit = max(1, min(n_cols, int(round(meas / seg_nom))))
            lay = lay[:n_fit]
            n_cols = n_fit
            total_s = seg_nom * n_fit
            warnings.append(f"trace length {meas:.1f}s differs from 10 s; {n_fit} column(s) assumed")
    expect_rows = len(lay[0]) + (1 if has_rhythm else 0)
    if n_rows != expect_rows and layout != "strips":
        warnings.append(f"detected {n_rows} rows, layout {layout} expects {expect_rows}")
    seg_s = total_s / n_cols
    bounds_t = [c * seg_s for c in range(n_cols + 1)]

    leads: dict[str, list[float]] = {}
    quality: dict[str, float] = {}
    calib_extra: dict[str, float] = {}
    dbg = {"rows": rows, "ink": ink, "rgb": rgb, "traces": {}}

    if plan is not None and plan.ok:
        leads, quality, offs = layout_mod.extract_slices(plan, ink, ppx, ppy, mm_y, mm_x, px_of_mm_x, xs_mm, speed, gain, OUT_FS)
        calib_extra = {f"offset_s.{k}": v for k, v in offs.items()}
        sig = ECGSignal(
            fs=OUT_FS, leads=leads, duration_s=max((len(v) for v in leads.values()), default=0) / OUT_FS,
            source=SourceKind.IMAGE, quality=quality,
            calibration={"paper_speed_mm_s": float(speed), "gain_mm_mv": float(gain),
                         "px_per_mm": float(0.5 * (ppx + ppy) / proc_scale),
                         "px_per_mm_x": float(ppx / proc_scale), "px_per_mm_y": float(ppy / proc_scale),
                         "grid_confidence": float(gr["confidence"]), "skew_deg": float(ginfo["skew_deg"]),
                         "layout_confirmed": 1.0, "rhythm_strips": float(len(plan.rhythm)), **calib_extra})
        if return_debug:
            dbg.update(layout=plan.name, warnings=warnings, plan=plan)
            return sig, dbg
        return sig

    row_cache = {}
    for ri, ry in enumerate(rows):
        xa = int(round(xs)) + skip_cols
        xb = min(int(round(xs + total_s * cps)), ink.shape[1])
        cen, top, bot, valid = trace.extract_row(ink, xa, xb, ry, half_band, ppy)
        thick = float(np.nanmedian(bot - top + 1)) if np.isfinite(bot - top).any() else 3.0
        cen = trace.refine_extrema(cen, top, bot, thick)
        row_cache[ri] = (xa, cen, valid)
        dbg["traces"][ri] = (xa, cen)

    def lead_from(ri, t0, t1):
        xa, cen, valid = row_cache[ri]
        n_out = int(round((t1 - t0) * OUT_FS))
        if n_out < 10:
            return None, 0.0
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

    if layout in ("3x4", "3x4+1") and n_rows >= 3:
        cr = [[lead_from(r, bounds_t[c], bounds_t[c + 1]) for r in range(3)] for c in range(n_cols)]
        okc = [c for c in range(n_cols) if all(x[0] is not None for x in cr[c])]
        std_ok = wide  # a full 10 s page is overwhelmingly the standard 3x4 order; only cropped pages are re-identified
        if okc and not layout_given and not std_ok:
            trip = trace.assign_triplets([[cr[c][r][0] for r in range(3)] for c in okc])
            new = [list(l) for l in lay]
            for c, t in zip(okc, trip):
                new[c] = t
            if new != [list(l) for l in lay]:
                warnings.append("lead groups identified from signal physics: " + " | ".join("/".join(n) for n in new))
            lay = new
    for c, names in enumerate(lay):
        for r, name in enumerate(names):
            if r >= n_rows:
                continue
            sig, q = lead_from(r, bounds_t[c], bounds_t[c + 1])
            if sig is None:
                continue
            leads[name] = sig.tolist()
            quality[name] = round(q, 3)
            calib_extra[f"offset_s.{name}"] = bounds_t[c]
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
                     "px_per_mm": float(0.5 * (ppx + ppy) / proc_scale),
                     "px_per_mm_x": float(ppx / proc_scale), "px_per_mm_y": float(ppy / proc_scale), "grid_confidence": float(gr["confidence"]),
                     "skew_deg": float(ginfo["skew_deg"]), **calib_extra})
    if return_debug:
        dbg.update(layout=layout, warnings=warnings)
        return sig, dbg
    return sig
