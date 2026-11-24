"""ECG ingestion: dispatch by file type to DICOM / aECG XML / CSV / WFDB / image digitizer."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.schemas import ECGSignal

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
CSV_EXT = {".csv", ".tsv", ".txt"}
WFDB_EXT = {".hea", ".dat"}


def _sniff(path: Path) -> str:
    ext = path.suffix.lower()
    if not path.exists():
        if Path(str(path) + ".hea").exists():
            return "wfdb"
        raise FileNotFoundError(path)
    with open(path, "rb") as f:
        head = f.read(512)
    if len(head) >= 132 and head[128:132] == b"DICM":
        return "dicom"
    if head[:4] in (b"\x89PNG", ) or head[:3] == b"\xff\xd8\xff" or head[:2] == b"BM" or head[:4] in (
            b"II*\x00", b"MM\x00*") or (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
        return "image"
    stripped = head.lstrip(b"\xef\xbb\xbf \r\n\t")
    if stripped.startswith(b"<"):
        return "xml"
    if ext in WFDB_EXT:
        return "wfdb"
    if ext in IMAGE_EXT:
        return "image"
    if ext in (".xml",):
        return "xml"
    if ext in CSV_EXT:
        return "csv"
    if ext in (".dcm", ".dicom", ""):
        return "dicom"  # headerless / extensionless DICOM
    return "csv"


def load_image_array(path: Path) -> np.ndarray:
    from PIL import Image, ImageOps
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    return np.asarray(im.convert("RGB"))


def load_ecg(path, layout: str = "auto") -> ECGSignal:
    """Load any supported ECG file into an ECGSignal (leads in mV, fs in Hz)."""
    p = Path(path)
    kind = _sniff(p)
    if kind == "dicom":
        from .dicom_ecg import load_dicom_ecg
        return load_dicom_ecg(p)
    if kind == "xml":
        from .aecg_xml import load_aecg
        return load_aecg(p)
    if kind == "wfdb":
        from .wfdb_ecg import load_wfdb
        return load_wfdb(p)
    if kind == "image":
        from app.ecg.digitize import digitize_image
        return digitize_image(load_image_array(p), layout=layout)
    from .csv_ecg import load_csv
    return load_csv(p)


__all__ = ["load_ecg", "load_image_array"]
