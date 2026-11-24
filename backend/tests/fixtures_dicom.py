"""Synthetic DICOM generators, reusable by any test module.

    from fixtures_dicom import make_dx_dicom, make_ecg_dicom
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

DX_SOP = "1.2.840.10008.5.1.4.1.1.1.1"
ECG_12_SOP = "1.2.840.10008.5.1.4.1.1.9.1.1"
LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]


def _base(path, sop_class, modality, study_uid, series_uid, sop_uid=None) -> FileDataset:
    sop_uid = sop_uid or generate_uid()
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = sop_class
    meta.MediaStorageSOPInstanceUID = sop_uid
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = sop_class
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid or generate_uid()
    ds.SeriesInstanceUID = series_uid or generate_uid()
    ds.Modality = modality
    ds.PatientName = "Doe^Jane"
    ds.PatientID = "SECRET-123"
    ds.PatientBirthDate = "19800101"
    ds.PatientAge = "045Y"
    ds.PatientSex = "F"
    return ds


def _chest_phantom(h: int, w: int, view: str) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.full((h, w), 2000.0, np.float32)
    cx, cy = w / 2, h / 2
    if view in ("LL", "RL"):
        img += 800 * np.exp(-(((xx - cx) / (0.3 * w)) ** 2 + ((yy - cy) / (0.4 * h)) ** 2))
    else:
        for sx in (-0.2, 0.2):  # lungs (dark)
            img -= 1200 * np.exp(-(((xx - cx - sx * w) / (0.13 * w)) ** 2 + ((yy - cy) / (0.3 * h)) ** 2))
        img += 1500 * np.exp(-(((xx - cx + 0.05 * w) / (0.1 * w)) ** 2 + ((yy - cy - 0.1 * h) / (0.12 * h)) ** 2))
    return np.clip(img, 0, 4095)


def make_dx_dicom(path, view: str = "PA", monochrome1: bool = False, study_uid=None,
                  series_uid=None, size: tuple[int, int] = (128, 128), body_part: str = "CHEST",
                  modality: str = "DX", pixel_spacing=(0.2, 0.2), imager_spacing_only=False,
                  with_window: bool = True, rescale: tuple[float, float] | None = None,
                  uid_seed: str | None = None) -> Path:
    """Write a tiny digital-radiography DICOM (12-bit stored in 16). Returns path."""
    h, w = size
    ds = _base(path, DX_SOP, modality, study_uid, series_uid)
    if uid_seed:
        ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID = generate_uid(entropy_srcs=[uid_seed])
    ds.ViewPosition = view
    ds.BodyPartExamined = body_part
    ds.SeriesDescription = f"{body_part} {view}"
    ds.PhotometricInterpretation = "MONOCHROME1" if monochrome1 else "MONOCHROME2"
    ds.SamplesPerPixel = 1
    ds.Rows, ds.Columns = h, w
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 12, 11, 0
    if imager_spacing_only:
        ds.ImagerPixelSpacing = list(pixel_spacing)
    else:
        ds.PixelSpacing = list(pixel_spacing)
    if with_window:
        ds.WindowCenter, ds.WindowWidth = 2000, 4000
    if rescale:
        ds.RescaleSlope, ds.RescaleIntercept = rescale
    ds.PixelData = _chest_phantom(h, w, view).astype("<u2").tobytes()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(str(path), enforce_file_format=True)
    return Path(path)


def synth_ecg(fs: int = 500, seconds: float = 10, bpm: float = 60) -> np.ndarray:
    """(12, n) synthetic ECG in microvolts: P, QRS, T gaussians per beat, per-lead gain."""
    n = int(fs * seconds)
    t = np.arange(n) / fs
    rr = 60.0 / bpm
    gains = np.array([0.8, 1.2, 0.5, -1.0, 0.3, 0.8, 0.4, 0.9, 1.4, 1.3, 1.1, 0.9])
    base = np.zeros(n)
    for b in np.arange(0.4, seconds, rr):
        base += 150 * np.exp(-((t - (b - 0.16)) / 0.025) ** 2)       # P
        base += -120 * np.exp(-((t - (b - 0.02)) / 0.008) ** 2)      # Q
        base += 1000 * np.exp(-((t - b) / 0.010) ** 2)               # R
        base += -200 * np.exp(-((t - (b + 0.025)) / 0.010) ** 2)     # S
        base += 300 * np.exp(-((t - (b + 0.25)) / 0.05) ** 2)        # T
    return np.outer(gains, base)


def make_ecg_dicom(path, fs: int = 500, seconds: float = 10, bpm: float = 60,
                   study_uid=None, series_uid=None) -> Path:
    """12-lead ECG waveform DICOM (WaveformSequence, int16, 1 uV/LSB)."""
    ds = _base(path, ECG_12_SOP, "ECG", study_uid, series_uid)
    data = np.round(synth_ecg(fs, seconds, bpm)).astype("<i2")  # (12, n)
    item = pydicom.Dataset()
    item.WaveformOriginality = "ORIGINAL"
    item.NumberOfWaveformChannels = 12
    item.NumberOfWaveformSamples = data.shape[1]
    item.SamplingFrequency = float(fs)
    chans = []
    for name in LEADS:
        c = pydicom.Dataset()
        src = pydicom.Dataset()
        src.CodeValue, src.CodingSchemeDesignator, src.CodeMeaning = f"lead-{name}", "MDC", f"Lead {name}"
        c.ChannelSourceSequence = Sequence([src])
        c.ChannelLabel = name
        c.ChannelSensitivity = 1.0
        unit = pydicom.Dataset()
        unit.CodeValue, unit.CodingSchemeDesignator, unit.CodeMeaning = "uV", "UCUM", "microvolt"
        c.ChannelSensitivityUnitsSequence = Sequence([unit])
        c.ChannelSensitivityCorrectionFactor = 1.0
        c.ChannelBaseline = 0.0
        c.WaveformBitsStored = 16
        chans.append(c)
    item.ChannelDefinitionSequence = Sequence(chans)
    item.WaveformBitsAllocated = 16
    item.WaveformSampleInterpretation = "SS"
    item.WaveformData = data.T.copy().tobytes()  # interleaved: sample-major
    ds.WaveformSequence = Sequence([item])
    ds.ContentDate, ds.ContentTime = "20240101", "120000"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(str(path), enforce_file_format=True)
    return Path(path)
