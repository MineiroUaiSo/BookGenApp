"""Filtering: baseline wander, mains notch, band limits."""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch, sosfiltfilt, welch


def _sos(fc, fs, kind, order=2):
    return butter(order, fc, btype=kind, fs=fs, output="sos")


def detect_mains(x: np.ndarray, fs: float):
    """Return 50.0 / 60.0 / None by narrow-band peak ratio of summed PSD."""
    if x.shape[1] < 2 * fs:
        return None
    best, ratio_best = None, 0.0
    nper = int(min(x.shape[1], 4 * fs))
    f, p = welch(x, fs=fs, nperseg=nper, axis=1)
    p = p.sum(0)
    for f0 in (50.0, 60.0):
        if f0 >= fs / 2 - 2:
            continue
        band = (f >= f0 - 0.6) & (f <= f0 + 0.6)
        side = ((f >= f0 - 8) & (f <= f0 - 3)) | ((f >= f0 + 3) & (f <= f0 + 8))
        side &= f < fs / 2
        if band.sum() == 0 or side.sum() == 0:
            continue
        r = p[band].max() / (np.median(p[side]) + 1e-18)
        if r > ratio_best:
            best, ratio_best = f0, r
    if best is None or ratio_best <= 12:
        return None
    # require a real sinusoid at f0 (lock-in amplitude), not just harmonics of the heart rhythm
    t = np.arange(x.shape[1]) / fs
    z = np.exp(-2j * np.pi * best * t)
    a = np.median(np.abs(2 * (x * z).mean(axis=1)))
    return best if a > 0.004 else None


def preprocess(x: np.ndarray, fs: float):
    """x: (n_leads, n) in mV. Returns (amp, dlt, info).

    amp: high-pass 0.5 Hz (zero phase), notch if mains, low-pass ~150 Hz  -> amplitudes/QRS borders
    dlt: amp additionally low-passed at 40 Hz                              -> P/T delineation
    """
    x = np.asarray(x, float)
    x = x - np.median(x, axis=1, keepdims=True)
    info = {"mains": None}
    y = sosfiltfilt(_sos(0.5, fs, "highpass"), x, axis=1)
    m = detect_mains(y, fs)
    if m:
        b, a = iirnotch(m, 35.0, fs=fs)
        y = filtfilt(b, a, y, axis=1)
        info["mains"] = m
    hi = min(150.0, 0.45 * fs)
    amp = sosfiltfilt(_sos(hi, fs, "lowpass", 4), y, axis=1) if hi < 0.5 * fs - 1 else y
    dlt = sosfiltfilt(_sos(min(40.0, 0.4 * fs), fs, "lowpass", 4), amp, axis=1)
    return amp, dlt, info


def noise_sigma(x: np.ndarray) -> np.ndarray:
    """Robust high-frequency noise estimate per lead (second difference MAD)."""
    d2 = np.diff(x, 2, axis=1)
    mad = np.median(np.abs(d2 - np.median(d2, axis=1, keepdims=True)), axis=1)
    return 1.4826 * mad / np.sqrt(6.0)
