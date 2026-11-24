"""Optional deep models (torchxrayvision). Everything is lazy and fails soft."""
from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np
from skimage.measure import label
from skimage.transform import resize

log = logging.getLogger(__name__)

# ChestX-Det PSPNet targets (verified against torchxrayvision 1.5.7)
PSP_TARGETS = ['Left Clavicle', 'Right Clavicle', 'Left Scapula', 'Right Scapula', 'Left Lung',
               'Right Lung', 'Left Hilus Pulmonis', 'Right Hilus Pulmonis', 'Heart', 'Aorta',
               'Facies Diaphragmatica', 'Mediastinum', 'Weasand', 'Spine']
PSP_KEYS = {
    'Left Clavicle': 'left_clavicle', 'Right Clavicle': 'right_clavicle',
    'Left Scapula': 'left_scapula', 'Right Scapula': 'right_scapula',
    'Left Lung': 'left_lung', 'Right Lung': 'right_lung',
    'Left Hilus Pulmonis': 'left_hilum', 'Right Hilus Pulmonis': 'right_hilum',
    'Heart': 'heart', 'Aorta': 'aorta', 'Facies Diaphragmatica': 'diaphragm',
    'Mediastinum': 'mediastinum', 'Weasand': 'trachea', 'Spine': 'spine',
}

_state: dict = {}


def models_enabled() -> bool:
    return os.environ.get("MEDLENS_RX_MODELS", "1").lower() not in ("0", "off", "false", "no")


def _xrv():
    try:
        import torch  # noqa: F401
        import torchxrayvision as xrv
        return xrv
    except Exception as e:  # pragma: no cover - depends on env
        log.info("torchxrayvision unavailable: %s", e)
        return None


def _get(name: str, factory):
    if name in _state:
        return _state[name]
    try:
        _state[name] = factory()
    except Exception as e:  # network/weights/torch problems
        log.warning("RX model %s unavailable: %s", name, e)
        _state[name] = None
    return _state[name]


def _psp():
    def f():
        xrv = _xrv()
        if xrv is None:
            return None
        m = xrv.baseline_models.chestx_det.PSPNet()
        m.eval()
        return m
    return _get("psp", f)


def _dense():
    def f():
        xrv = _xrv()
        if xrv is None:
            return None
        m = xrv.models.DenseNet(weights="densenet121-res224-all")
        m.eval()
        return m
    return _get("dense", f)


def _largest(mask: np.ndarray) -> np.ndarray:
    lab = label(mask)
    if lab.max() <= 1:
        return mask
    counts = np.bincount(lab.ravel())
    counts[0] = 0
    return lab == counts.argmax()


def segment_chest_model(work: np.ndarray) -> Optional[dict[str, np.ndarray]]:
    """work: float 0..1 image at working res. Returns masks at working res, or None."""
    if not models_enabled():
        return None
    model = _psp()
    if model is None:
        return None
    try:
        import torch
        xrv = _xrv()
        img = resize(work, (512, 512), anti_aliasing=True, order=1).astype(np.float32)
        x = xrv.datasets.normalize((img * 255).astype(np.float32), 255)
        t = torch.from_numpy(x)[None, None].float()
        with torch.no_grad():
            out = model(t)[0].numpy()
        prob = 1.0 / (1.0 + np.exp(-out))
        masks: dict[str, np.ndarray] = {}
        h, w = work.shape
        for i, name in enumerate(PSP_TARGETS):
            m = prob[i] > 0.5
            if m.sum() == 0:
                continue
            if name != 'Facies Diaphragmatica':
                m = _largest(m)
            m = resize(m.astype(np.uint8), (h, w), order=0, preserve_range=True, anti_aliasing=False) > 0
            masks[PSP_KEYS[name]] = m
    except Exception as e:  # pragma: no cover
        log.warning("PSPNet inference failed: %s", e)
        return None
    area = work.shape[0] * work.shape[1]
    ok = (masks.get("left_lung") is not None and masks.get("right_lung") is not None
          and masks["left_lung"].sum() > 0.015 * area and masks["right_lung"].sum() > 0.015 * area
          and masks.get("heart") is not None and masks["heart"].sum() > 0.01 * area)
    return masks if ok else None


def pathology_scores(work: np.ndarray) -> dict[str, float]:
    if not models_enabled():
        return {}
    model = _dense()
    if model is None:
        return {}
    try:
        import torch
        xrv = _xrv()
        img = resize(work, (224, 224), anti_aliasing=True, order=1).astype(np.float32)
        x = xrv.datasets.normalize((img * 255).astype(np.float32), 255)
        t = torch.from_numpy(x)[None, None].float()
        with torch.no_grad():
            out = model(t)[0].numpy()
        return {p: round(float(v), 4) for p, v in zip(model.pathologies, out) if p}
    except Exception as e:  # pragma: no cover
        log.warning("DenseNet inference failed: %s", e)
        return {}
