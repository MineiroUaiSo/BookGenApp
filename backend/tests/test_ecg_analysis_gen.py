"""Gaussian-model 12-lead ECG generator with independent P and QRS event times (for analysis tests).

Fiducials are nominal: a Gaussian wave has no hard edge, so nominal borders are at about +-2.5-3 sigma.
"""
from __future__ import annotations

import numpy as np

LIMB_ANG = {"I": 0, "II": 60, "III": 120, "aVR": -150, "aVL": -30, "aVF": 90}
PREC = {  # (dt_ms from R, sd_ms, amp_mV) lists
    "V1": [(0, 9, 0.20), (22, 10, -1.00)],
    "V2": [(0, 9, 0.50), (22, 10, -1.40)],
    "V3": [(0, 9, 0.90), (22, 10, -1.00)],
    "V4": [(-20, 8, -0.05), (0, 10, 1.50), (22, 10, -0.50)],
    "V5": [(-20, 8, -0.10), (0, 10, 1.40), (22, 10, -0.20)],
    "V6": [(-20, 8, -0.10), (0, 10, 1.10), (22, 10, -0.10)],
}
PREC_T = {"V1": -0.1, "V2": 0.4, "V3": 0.45, "V4": 0.45, "V5": 0.35, "V6": 0.30}


def _g(t, mu, sd):
    return np.exp(-0.5 * ((t - mu) / sd) ** 2)


def make_ecg(r_times, p_times=(), fs=500, seconds=10.0, qrs_scale=1.0, axis_deg=45.0, mag=1.4,
             p_mag=0.15, t_mag=0.35, qt_ms=400, pd_ms=100, prec=None, st=None, noise=0.0, wander=0.0,
             mains=0.0, seed=0, t_axis=45.0, fwave=0.0, t_scale_prec=1.0):
    """r_times / p_times in seconds (R peak and P onset). Returns dict lead -> ndarray (mV)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * fs)
    t = np.arange(n) / fs
    prec = prec or PREC
    st = st or {}
    out = {l: np.zeros(n) for l in ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]}
    s = qrs_scale
    for rt in r_times:
        tend = rt - 0.035 * s + qt_ms / 1e3
        tc = tend - 0.085
        qoff = rt + 0.055 * s
        for l, ang in LIMB_ANG.items():
            proj = np.cos(np.radians(axis_deg - ang))
            out[l] += mag * proj * _g(t, rt, 0.012 * s)
            tp = np.cos(np.radians(t_axis - ang))
            out[l] += t_mag * tp * _g(t, tc, 0.04)
        for l, comps in prec.items():
            for dt, sd, a in comps:
                out[l] += a * _g(t, rt + dt / 1e3 * s, sd / 1e3 * s)
            out[l] += PREC_T[l] * t_scale_prec * _g(t, tc, 0.04)
        for l, v in st.items():
            out[l] += v * (1 / (1 + np.exp(np.clip(-(t - qoff) / 0.008, -50, 50)))) * (1 / (1 + np.exp(np.clip((t - (tc + 0.03)) / 0.02, -50, 50))))
    for pt in p_times:
        pd = pd_ms / 1e3
        for l, ang in LIMB_ANG.items():
            out[l] += p_mag * np.cos(np.radians(60 - ang)) * _g(t, pt + pd / 2, pd / 6)
        for l in prec:
            out[l] += 0.05 * _g(t, pt + pd / 2, pd / 6)
    for l in out:
        if fwave:
            out[l] += fwave * np.sin(2 * np.pi * 6.3 * t + rng.uniform(0, 6)) + fwave * 0.6 * np.sin(2 * np.pi * 8.1 * t)
        if wander:
            out[l] += wander * np.sin(2 * np.pi * 0.25 * t + rng.uniform(0, 6))
        if mains:
            out[l] += mains * np.sin(2 * np.pi * 50 * t)
        if noise:
            out[l] += rng.normal(0, noise, n)
    return out


def sinus(hr=70, pr=0.16, seconds=10.0, first=0.45, **kw):
    rr = 60.0 / hr
    r = np.arange(first, seconds - 0.6, rr)
    return make_ecg(r, r - pr - 0.035 * kw.get("qrs_scale", 1.0), seconds=seconds, **kw), r
