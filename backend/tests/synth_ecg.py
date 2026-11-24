"""Synthetic 12-lead ECG generator + ECG-paper renderer (test helper, reusable).

synth_signal(hr=70, fs=500, seconds=10, **abn) -> (leads, fiducials)
render_paper(leads, fs, px_per_mm=12, layout="3x4+1", photo_effects=False) -> np.ndarray (RGB uint8)

Own sum-of-Gaussians P-QRS-T model so that fiducials are known exactly.
Limb leads III/aVR/aVL/aVF are derived from I and II (Einthoven/Goldberger).
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

LEAD_ORDER = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]

# mV amplitudes (P, Q, R, S, T) for the independent leads
_AMP = {
    "I": (0.10, -0.05, 0.80, -0.10, 0.25),
    "II": (0.15, -0.08, 1.20, -0.20, 0.35),
    "V1": (0.06, 0.0, 0.20, -1.00, -0.10),
    "V2": (0.08, 0.0, 0.50, -1.40, 0.40),
    "V3": (0.08, 0.0, 0.90, -1.00, 0.45),
    "V4": (0.08, -0.05, 1.50, -0.50, 0.45),
    "V5": (0.08, -0.10, 1.40, -0.20, 0.35),
    "V6": (0.07, -0.10, 1.10, -0.10, 0.30),
}

LAYOUTS = {
    "3x4+1": dict(cols=[["I", "II", "III"], ["aVR", "aVL", "aVF"], ["V1", "V2", "V3"], ["V4", "V5", "V6"]],
                  rhythm="II"),
    "6x2": dict(cols=[["I", "II", "III", "aVR", "aVL", "aVF"], ["V1", "V2", "V3", "V4", "V5", "V6"]],
                rhythm=None),
    "12x1": dict(cols=[LEAD_ORDER], rhythm=None),
}


def _g(t, mu, sd):
    return np.exp(-0.5 * ((t - mu) / sd) ** 2)


def synth_signal(hr=70.0, fs=500, seconds=10.0, pr_ms=160.0, qrs_ms=90.0, qt_ms=400.0, p_ms=100.0,
                 st_shift_mv=0.0, rr_jitter=0.0, noise_mv=0.0, wander_mv=0.0, seed=0):
    """Return (leads: dict[str, np.ndarray mV], fiducials: dict)."""
    rng = np.random.default_rng(seed)
    n = int(round(seconds * fs))
    t = np.arange(n) / fs
    rr0 = 60.0 / hr
    r_times = []
    cur = 0.45
    while cur < seconds - 0.5:
        r_times.append(cur)
        cur += rr0 * (1 + rr_jitter * rng.uniform(-1, 1))
    pr, qrs, qt, pd = pr_ms / 1e3, qrs_ms / 1e3, qt_ms / 1e3, p_ms / 1e3
    s = qrs / 0.09  # QRS widening factor
    base = {k: np.zeros(n) for k in ("I", "II", "V1", "V2", "V3", "V4", "V5", "V6")}
    fid = dict(r_peaks_s=[], p_on_s=[], p_off_s=[], qrs_on_s=[], qrs_off_s=[], t_end_s=[], hr=hr,
               pr_ms=pr_ms, qrs_ms=qrs_ms, qt_ms=qt_ms, fs=fs)
    for rt in r_times:
        qon = rt - 0.035 * s
        qoff = qon + qrs
        pon = qon - pr
        tend = qon + qt
        tc, tsd = tend - 0.085, 0.04
        fid["r_peaks_s"].append(rt); fid["p_on_s"].append(pon); fid["p_off_s"].append(pon + pd)
        fid["qrs_on_s"].append(qon); fid["qrs_off_s"].append(qoff); fid["t_end_s"].append(tend)
        for k, (aP, aQ, aR, aS, aT) in _AMP.items():
            w = (aP * _g(t, pon + pd / 2, pd / 6) + aQ * _g(t, rt - 0.020 * s, 0.008 * s)
                 + aR * _g(t, rt, 0.010 * s) + aS * _g(t, rt + 0.022 * s, 0.010 * s)
                 + aT * _g(t, tc, tsd))
            if st_shift_mv:  # smooth ST plateau between QRS end and T centre
                w += st_shift_mv * (1 / (1 + np.exp(-(t - qoff) / 0.008))) * (1 / (1 + np.exp((t - (tc + 0.03)) / 0.02)))
            base[k] += w
    I, II = base["I"], base["II"]
    leads = {"I": I, "II": II, "III": II - I, "aVR": -(I + II) / 2, "aVL": I - II / 2, "aVF": II - I / 2}
    for k in ("V1", "V2", "V3", "V4", "V5", "V6"):
        leads[k] = base[k]
    for k in leads:
        if wander_mv:
            leads[k] = leads[k] + wander_mv * np.sin(2 * np.pi * 0.25 * t + rng.uniform(0, 6))
        if noise_mv:
            leads[k] = leads[k] + rng.normal(0, noise_mv, n)
    leads = {k: leads[k] for k in LEAD_ORDER}
    for k in ("r_peaks_s", "p_on_s", "p_off_s", "qrs_on_s", "qrs_off_s", "t_end_s"):
        fid[k] = np.array(fid[k])
    return leads, fid


# ------------------------------------------------------------------ rendering
def _font(px):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:  # old Pillow
        return ImageFont.load_default()


def render_paper(leads, fs, px_per_mm=12.0, layout="3x4+1", photo_effects=False, gain_mm_mv=10.0,
                 speed_mm_s=25.0, seed=0, grid_color=(240, 160, 160), return_info=False,
                 rotate_deg=3.0, perspective=0.025, jpeg_quality=55, blur=1.2, noise=4.0):
    """Draw leads (dict of equal-length 10 s arrays, mV) on pink ECG paper. Returns RGB uint8."""
    rng = np.random.default_rng(seed)
    ppm = float(px_per_mm)
    lay = LAYOUTS[layout]
    cols = lay["cols"]
    n_rows = len(cols[0]) + (1 if lay["rhythm"] else 0)
    seconds = len(next(iter(leads.values()))) / fs
    pitch_mm = {"3x4+1": 32.0, "6x2": 38.0, "12x1": 26.0}[layout] * max(1.0, gain_mm_mv / 10.0)
    x0_mm, top_mm = 7.0 + 0.2 * speed_mm_s, 20.0  # pulse = 0.2 s wide
    w_mm = x0_mm + seconds * speed_mm_s + 6.0
    h_mm = top_mm + n_rows * pitch_mm + 6.0
    W, H = int(round(w_mm * ppm)), int(round(h_mm * ppm))
    img = Image.new("RGB", (W, H), (255, 244, 240))
    d = ImageDraw.Draw(img)
    # grid
    minor = tuple(int(0.45 * c + 0.55 * 255) for c in grid_color)
    for i in range(int(w_mm) + 1):
        x = int(round(i * ppm))
        d.line([(x, 0), (x, H)], fill=grid_color if i % 5 == 0 else minor, width=2 if i % 5 == 0 else 1)
    for j in range(int(h_mm) + 1):
        y = int(round(j * ppm))
        d.line([(0, y), (W, y)], fill=grid_color if j % 5 == 0 else minor, width=2 if j % 5 == 0 else 1)
    lw = max(2, int(round(0.28 * ppm)))
    fnt = _font(max(10, int(2.6 * ppm)))
    d.text((x0_mm * ppm, 4 * ppm), "ECG 12 derivacoes  25 mm/s  10 mm/mV", fill=(30, 30, 30), font=fnt)
    mm2px = lambda v: v * ppm
    row_y = [top_mm + pitch_mm * (r + 0.5) for r in range(n_rows)]
    n_samp = len(next(iter(leads.values())))
    seg_s = seconds / len(cols)

    def draw_trace(sig, xs_mm, yb_mm):
        t = np.arange(len(sig)) / fs
        xs = (xs_mm + t * speed_mm_s) * ppm
        ys = (yb_mm - sig * gain_mm_mv) * ppm
        d.line(list(zip(xs.tolist(), ys.tolist())), fill=(15, 15, 15), width=lw, joint="curve")

    for r in range(n_rows):
        yb = row_y[r]
        # calibration pulse: baseline -> up gain mm for 5 mm (0.2 s) -> baseline; data starts at x0
        px = [(mm2px(5.0), mm2px(yb)), (mm2px(7.0), mm2px(yb)), (mm2px(7.0), mm2px(yb - gain_mm_mv)),
              (mm2px(x0_mm - 0.0 - 0.0), mm2px(yb - gain_mm_mv)), (mm2px(x0_mm), mm2px(yb))]
        px[3] = (mm2px(x0_mm), mm2px(yb - gain_mm_mv))
        d.line(px, fill=(15, 15, 15), width=lw, joint="curve")
    # leads
    for c, names in enumerate(cols):
        i0, i1 = int(round(c * seg_s * fs)), int(round((c + 1) * seg_s * fs))
        for r, name in enumerate(names):
            xs_mm = x0_mm + c * seg_s * speed_mm_s
            draw_trace(np.asarray(leads[name][i0:i1]), xs_mm, row_y[r])
            d.text((mm2px(xs_mm + 1.0), mm2px(row_y[r] - 12.5)), name, fill=(20, 20, 20), font=fnt)
            if c > 0:  # small separator tick
                d.line([(mm2px(xs_mm), mm2px(row_y[r] - 2)), (mm2px(xs_mm), mm2px(row_y[r] + 2))],
                       fill=(15, 15, 15), width=max(1, lw - 1))
    if lay["rhythm"]:
        r = n_rows - 1
        draw_trace(np.asarray(leads[lay["rhythm"]]), x0_mm, row_y[r])
        d.text((mm2px(x0_mm + 1.0), mm2px(row_y[r] - 12.5)), lay["rhythm"], fill=(20, 20, 20), font=fnt)
    arr = np.asarray(img)
    info = dict(px_per_mm=ppm, paper_speed_mm_s=speed_mm_s, gain_mm_mv=gain_mm_mv, layout=layout,
                x0_px=x0_mm * ppm, row_baseline_px=[y * ppm for y in row_y], seconds=seconds)
    if photo_effects:
        arr, pinfo = _photo(arr, rng, ppm, w_mm, rotate_deg, perspective, jpeg_quality, blur, noise)
        info.update(pinfo)
    return (arr, info) if return_info else arr


def _photo(arr, rng, ppm, w_mm, rotate_deg, perspective, jpeg_quality, blur, noise):
    import cv2
    h, w = arr.shape[:2]
    pad = int(0.08 * w)
    Wc, Hc = w + 2 * pad, h + 2 * pad
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    a = np.deg2rad(rotate_deg)
    R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    c = np.array([w / 2, h / 2])
    dst = (src - c) @ R.T + c + pad
    jit = perspective * w
    dst = dst + rng.uniform(-jit, jit, dst.shape) * np.array([1.0, 0.6])
    dst = dst.astype(np.float32)
    Hm = cv2.getPerspectiveTransform(src, dst)
    bg = np.zeros((Hc, Wc, 3), np.float32)
    bg[:] = (70, 85, 100)
    bg += cv2.GaussianBlur(rng.normal(0, 14, (Hc, Wc, 3)).astype(np.float32), (0, 0), 6)
    mask = cv2.warpPerspective(np.ones((h, w), np.float32), Hm, (Wc, Hc), flags=cv2.INTER_AREA)[..., None]
    warped = cv2.warpPerspective(arr, Hm, (Wc, Hc), flags=cv2.INTER_AREA).astype(np.float32)
    out = warped * mask + bg * (1 - mask)
    # illumination gradient + vignette
    yy, xx = np.mgrid[0:Hc, 0:Wc].astype(np.float32)
    shade = 1.0 - 0.18 * (xx / Wc) - 0.10 * (yy / Hc) + 0.04 * np.sin(xx / Wc * 3)
    out *= shade[..., None]
    if blur:
        out = cv2.GaussianBlur(out, (0, 0), blur)
    out += rng.normal(0, noise, out.shape)
    out = np.clip(out, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(out).save(buf, "JPEG", quality=jpeg_quality)
    out = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))
    top = np.linalg.norm(dst[1] - dst[0]); bot = np.linalg.norm(dst[2] - dst[3])
    eff_ppm = 0.5 * (top + bot) / w_mm
    side = 0.5 * (np.linalg.norm(dst[3] - dst[0]) + np.linalg.norm(dst[2] - dst[1])) / (h / ppm)
    return out, dict(px_per_mm=float(0.5 * (eff_ppm + side)), quad=dst.tolist(), homography=Hm.tolist())
