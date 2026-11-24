"""Optional CXAS (Chest X-ray Anatomy Segmentation, Seibold et al.; code + weights MIT, research tool) via SUBPROCESS.

OFF by default: set MEDLENS_RX_CXAS=1. CXAS lives in its own venv (MEDLENS_CXAS_PYTHON, default
~/medlens-venvs/cxas/bin/python) and is called through app/rx/cxas_runner.py (JSON on stdout + PNG masks in a temp dir).
Any problem (flag off, venv/weights missing, timeout, bad JSON) returns None -> the caller keeps the current behaviour.
It only FILLS structures the PSPNet/heuristic pipeline does not produce (sternum, ribs, aorta/spine in lateral...).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

RUNNER = Path(__file__).with_name("cxas_runner.py")
DEFAULT_PY = Path.home() / "medlens-venvs" / "cxas" / "bin" / "python"
# keys CXAS may add (only when the base pipeline did not produce them). Runner key -> MedLens structure key.
KEY_OUT = {"sternum": "sternum", "aorta": "aorta", "spine": "spine", "trachea": "trachea",
           "left_clavicle": "left_clavicle", "right_clavicle": "right_clavicle",
           "left_scapula": "left_scapula", "right_scapula": "right_scapula",
           "left_hemidiaphragm": "left_diaphragm", "right_hemidiaphragm": "right_diaphragm"}
CXAS_KEYS = set(KEY_OUT.values()) | {"ribs"}


def python_path() -> Path:
    return Path(os.environ.get("MEDLENS_CXAS_PYTHON", str(DEFAULT_PY)))


def enabled() -> bool:
    """Flag on AND venv python + runner present."""
    if os.environ.get("MEDLENS_RX_CXAS", "0").lower() not in ("1", "true", "on", "yes"):
        return False
    return python_path().exists() and RUNNER.exists()


def _timeout() -> float:
    try:
        return float(os.environ.get("MEDLENS_RX_CXAS_TIMEOUT", "180"))
    except ValueError:
        return 180.0


def _run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    """Isolated so tests can stub the subprocess."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)  # noqa: S603


def segment(img_u8: np.ndarray, view_class: str) -> Optional[dict[str, np.ndarray]]:
    """Run CXAS on a grayscale uint8 image. Returns {medlens_key: bool mask (same shape as img)} or None."""
    if not enabled():
        return None
    from PIL import Image
    try:
        with tempfile.TemporaryDirectory(prefix="medlens_cxas_") as td:
            src = Path(td) / "in.png"
            Image.fromarray(np.asarray(img_u8, np.uint8)).save(src)
            cmd = [str(python_path()), "-I", str(RUNNER), "--out", str(Path(td) / "out"), "--view",
                   "lateral" if view_class == "lateral" else "frontal", str(src)]
            proc = _run(cmd, _timeout())
            lines = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()]
            res = json.loads(lines[-1]) if lines else {}
            if not res.get("ok") or not res.get("results"):
                log.warning("CXAS failed: %s", res.get("error") or (proc.stderr or "")[-200:])
                return None
            masks = {}
            for key, p in res["results"][0]["masks"].items():
                im = Image.open(p).convert("L")
                if im.size != (img_u8.shape[1], img_u8.shape[0]):
                    im = im.resize((img_u8.shape[1], img_u8.shape[0]), Image.NEAREST)
                masks[key] = np.asarray(im) > 127
            return masks
    except Exception as e:  # timeout, missing weights, bad JSON, ...
        log.warning("CXAS unavailable: %s", e)
        return None


def fill_masks(cx: dict[str, np.ndarray], have: set[str]) -> dict[str, np.ndarray]:
    """Masks CXAS adds: only keys not already produced by the base pipeline."""
    out: dict[str, np.ndarray] = {}
    for src, dst in KEY_OUT.items():
        if dst not in have and src in cx and cx[src].any():
            out[dst] = cx[src]
    if "ribs" not in have:
        ribs = [cx[k] for k in ("ribs_left", "ribs_right") if k in cx]
        if ribs:
            out["ribs"] = np.logical_or.reduce(ribs)
    return out
