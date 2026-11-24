"""DICOM / image rendering to 8-bit arrays."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import numpy as np
import pydicom
from PIL import Image, ImageOps

try:  # optional HEIC support
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception:  # pragma: no cover
    pass


def load_dicom(path) -> pydicom.Dataset:
    return pydicom.dcmread(str(path), force=True)


def _first(v):
    if v is None:
        return None
    try:
        if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
            v = list(v)[0]
        return float(v)
    except Exception:
        return None


def _frame(ds) -> np.ndarray:
    try:
        arr = ds.pixel_array
    except Exception as e:  # compressed syntax without a decoder, corrupt data...
        raise RuntimeError(
            f"cannot decode pixel data ({getattr(ds.file_meta, 'TransferSyntaxUID', '?')}): {e}. "
            "Install optional decoders: pip install pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg"
        ) from e
    spp = int(ds.get("SamplesPerPixel", 1) or 1)
    nframes = int(ds.get("NumberOfFrames", 1) or 1)
    if nframes > 1 or arr.ndim == 4:
        arr = arr[0]
    if spp == 1 and arr.ndim == 3:
        arr = arr[..., 0]
    return arr


def _auto_window(x: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(x, [0.5, 99.5])
    if hi <= lo:
        lo, hi = float(x.min()), float(x.max())
    if hi <= lo:
        hi = lo + 1.0
    return (lo + hi) / 2.0, hi - lo


def render_to_uint8(ds, wc: Optional[float] = None, ww: Optional[float] = None) -> np.ndarray:
    """Render a DICOM dataset to an HxW uint8 array (first frame)."""
    arr = _frame(ds)
    photometric = str(ds.get("PhotometricInterpretation", "MONOCHROME2"))
    if arr.ndim == 3:  # colour -> luminance
        if photometric.startswith("YBR"):
            try:
                from pydicom.pixels import convert_color_space
            except ImportError:  # pydicom 2.x
                from pydicom.pixel_data_handlers.util import convert_color_space
            arr = convert_color_space(arr, photometric, "RGB")
        a = arr.astype(np.float32)
        gray = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
        if gray.max() > 255:
            gray = gray / gray.max() * 255
        return np.clip(gray, 0, 255).astype(np.uint8)

    x = arr.astype(np.float32)
    slope = _first(ds.get("RescaleSlope")) or 1.0
    icpt = _first(ds.get("RescaleIntercept")) or 0.0
    x = x * slope + icpt

    c, w = wc, ww
    if c is None or w is None or w <= 0:
        c = _first(ds.get("WindowCenter"))
        w = _first(ds.get("WindowWidth"))
    if c is None or w is None or w <= 0:
        if "VOILUTSequence" in ds:
            try:
                try:
                    from pydicom.pixels import apply_voi_lut
                except ImportError:
                    from pydicom.pixel_data_handlers.util import apply_voi_lut
                y = np.asarray(apply_voi_lut(arr, ds), dtype=np.float32)
                lo, hi = float(y.min()), float(y.max())
                x = (y - lo) / max(hi - lo, 1e-6) * 255.0
                c = w = None
            except Exception:
                c, w = _auto_window(x)
        else:
            c, w = _auto_window(x)
    if c is not None:
        x = (x - (c - w / 2.0)) / w * 255.0
    out = np.clip(x, 0, 255).astype(np.uint8)
    if photometric == "MONOCHROME1":
        out = 255 - out
    return out


def pixel_spacing_mm(ds) -> tuple[float, float] | None:
    """(row_spacing, col_spacing) in mm; PixelSpacing, else ImagerPixelSpacing."""
    for tag in ("PixelSpacing", "ImagerPixelSpacing"):
        v = ds.get(tag)
        if v is not None:
            try:
                vals = [float(i) for i in v]
                if len(vals) >= 2 and vals[0] > 0 and vals[1] > 0:
                    return vals[0], vals[1]
            except Exception:
                continue
    return None


# ------------------------------------------------------------ instance level
def open_image(path: Path, gray: bool = False) -> np.ndarray:
    """Load a non-DICOM raster image (EXIF-rotated). RGB uint8, or L if gray."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if gray:
            if im.mode in ("I;16", "I;16B", "I;16L", "I"):
                a = np.asarray(im, dtype=np.float32)
                lo, hi = np.percentile(a, [0.5, 99.5])
                a = np.clip((a - lo) / max(hi - lo, 1e-6) * 255, 0, 255)
                return a.astype(np.uint8)
            return np.asarray(im.convert("L"))
        return np.asarray(im.convert("RGB"))


def render_instance(instance_id: str, wc=None, ww=None, gray: bool = True):
    """Return (array, dicom_dataset_or_None, kind) for a stored instance."""
    from app.store import store

    meta = store.instance_meta(instance_id)
    path = store.instance_path(instance_id)
    kind = meta.get("kind")
    if kind == "dicom":
        ds = load_dicom(path)
        if "PixelData" not in ds:
            raise ValueError(f"instance {instance_id} has no pixel data (waveform?)")
        return render_to_uint8(ds, wc, ww), ds, kind
    if kind == "image":
        return open_image(path, gray=gray), None, kind
    raise ValueError(f"instance {instance_id} ({kind}) is not renderable as an image")


def to_png_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()
