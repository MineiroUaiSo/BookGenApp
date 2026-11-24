"""DICOM Waveform (12-lead ECG, Waveform IOD) reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.schemas import SourceKind

from .leads import STD_LEADS, build_signal, normalize_lead, to_mv


def _channel_label(ch) -> str | None:
    cands = []
    seq = ch.get("ChannelSourceSequence")
    if seq:
        src = seq[0]
        cands += [src.get("CodeMeaning"), src.get("CodeValue")]
    cands.append(ch.get("ChannelLabel"))
    for c in cands:
        n = normalize_lead(c)
        if n:
            return n
    return None


def _unit(ch) -> str | None:
    seq = ch.get("ChannelSensitivityUnitsSequence")
    if seq:
        return seq[0].get("CodeValue") or seq[0].get("CodeMeaning")
    return None


def has_waveform(ds) -> bool:
    return "WaveformSequence" in ds and len(ds.WaveformSequence) > 0


def read_dicom_ecg(ds):
    groups = []
    for i, item in enumerate(ds.WaveformSequence):
        try:
            raw = ds.waveform_array(i)  # (samples, channels), scaled to channel units
        except Exception:
            continue
        chans = item.get("ChannelDefinitionSequence", [])
        fs = float(item.get("SamplingFrequency", 0) or 0)
        names, data = [], {}
        for j, ch in enumerate(chans):
            if j >= raw.shape[1]:
                break
            lab = _channel_label(ch)
            x = raw[:, j].astype(float)
            # waveform_array() already applied ChannelSensitivity * CorrectionFactor + ChannelBaseline,
            # so x is expressed in the units of ChannelSensitivityUnitsSequence.
            x = to_mv(x, _unit(ch) if ch.get("ChannelSensitivityUnitsSequence") else "uV")
            key = lab or (str(ch.get("ChannelLabel") or f"ch{j + 1}"))
            if key in data:  # duplicated label (e.g. rhythm copy): keep the first
                continue
            data[key] = x
        n_std = sum(1 for k in data if k in STD_LEADS)
        groups.append(dict(index=i, fs=fs, leads=data, n_std=n_std, n=raw.shape[0]))
    if not groups:
        raise ValueError("DICOM waveform sequence has no decodable multiplex group")
    best = max(groups, key=lambda g: (min(g["n_std"], 12) >= 8, g["n_std"], g["n"]))
    if best["fs"] <= 0:
        raise ValueError("DICOM waveform lacks SamplingFrequency")
    return build_signal(best["leads"], best["fs"], SourceKind.DICOM,
                        extra_cal={"waveform_group": float(best["index"])})


def load_dicom_ecg(path: Path):
    import pydicom
    ds = pydicom.dcmread(str(path), force=True)
    if has_waveform(ds):
        return read_dicom_ecg(ds)
    if "PixelData" in ds:  # ECG printout stored as image (secondary capture)
        from app.ecg.digitize import digitize_image
        arr = ds.pixel_array
        if str(ds.get("PhotometricInterpretation", "")) == "MONOCHROME1":
            arr = arr.max() - arr
        if arr.ndim == 3 and arr.shape[0] in (3, 4) and arr.shape[-1] not in (3, 4):
            arr = np.moveaxis(arr, 0, -1)
        if arr.dtype != np.uint8:
            a = arr.astype(float)
            arr = ((a - a.min()) / max(np.ptp(a), 1) * 255).astype(np.uint8)
        return digitize_image(arr)
    raise ValueError("DICOM has neither WaveformSequence nor PixelData")
