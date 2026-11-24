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


def _device() -> str:
    """'mps' when available (Apple silicon, ~10x faster, numerically equivalent: max |dp| ~2e-6, 0 mask pixels differ);
    else 'cpu'. MEDLENS_RX_DEVICE=cpu|mps overrides. A failing MPS run falls back to CPU (see psp_probs)."""
    if "device" in _state:
        return _state["device"]
    want = os.environ.get("MEDLENS_RX_DEVICE", "auto").lower()
    dev = "cpu"
    if want in ("auto", "mps"):
        try:
            import torch
            if torch.backends.mps.is_available():
                dev = "mps"
        except Exception:  # pragma: no cover
            pass
    if os.environ.get("MEDLENS_RX_THREADS"):
        try:
            import torch
            torch.set_num_threads(max(1, int(os.environ["MEDLENS_RX_THREADS"])))
        except Exception:  # pragma: no cover
            pass
    _state["device"] = dev
    return dev


def _psp():
    def f():
        xrv = _xrv()
        if xrv is None:
            return None
        m = xrv.baseline_models.chestx_det.PSPNet()
        m.eval()
        if _device() == "mps":
            try:
                m = m.to("mps")
            except Exception as e:  # pragma: no cover
                log.warning("PSPNet MPS unavailable, CPU: %s", e)
                _state["device"] = "cpu"
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


def psp_probs(work: np.ndarray) -> Optional[np.ndarray]:
    """Sigmoid probabilities (14, 512, 512) of the ChestX-Det PSPNet for a working-res image (0..1), or None."""
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
        try:
            with torch.no_grad():
                out = model(t.to(_device()))[0].cpu().numpy()
        except Exception as e:  # pragma: no cover - MPS op/driver problem: retry once on CPU
            if _device() == "cpu":
                raise
            log.warning("PSPNet on %s failed (%s); falling back to CPU", _device(), e)
            _state["device"] = "cpu"
            model.to("cpu")
            with torch.no_grad():
                out = model(t)[0].numpy()
        return (1.0 / (1.0 + np.exp(-out))).astype(np.float32)
    except Exception as e:  # pragma: no cover
        log.warning("PSPNet inference failed: %s", e)
        return None


def masks_from_probs(prob: np.ndarray, shape: tuple[int, int], largest: bool = True) -> dict[str, np.ndarray]:
    """Threshold PSP probabilities -> masks at `shape` (keeps the largest component except diaphragm)."""
    masks: dict[str, np.ndarray] = {}
    h, w = shape
    for i, name in enumerate(PSP_TARGETS):
        m = prob[i] > 0.5
        if m.sum() == 0:
            continue
        if largest and name != 'Facies Diaphragmatica':
            m = _largest(m)
        m = resize(m.astype(np.uint8), (h, w), order=0, preserve_range=True, anti_aliasing=False) > 0
        masks[PSP_KEYS[name]] = m
    return masks


def masks_plausible(masks: dict[str, np.ndarray], shape: tuple[int, int]) -> bool:
    area = shape[0] * shape[1]
    return (masks.get("left_lung") is not None and masks.get("right_lung") is not None
            and masks["left_lung"].sum() > 0.015 * area and masks["right_lung"].sum() > 0.015 * area
            and masks.get("heart") is not None and masks["heart"].sum() > 0.01 * area)


def lung_field_from_probs(prob: np.ndarray, shape: tuple[int, int]) -> Optional[np.ndarray]:
    """Union of PSP left/right lung masks (on laterals the net splits the single lung field in two) -> mask."""
    m = (prob[PSP_TARGETS.index('Left Lung')] > 0.5) | (prob[PSP_TARGETS.index('Right Lung')] > 0.5)
    if m.sum() == 0:
        return None
    m = _largest(m)
    return resize(m.astype(np.uint8), shape, order=0, preserve_range=True, anti_aliasing=False) > 0


def segment_chest_model(work: np.ndarray, prob: Optional[np.ndarray] = None) -> Optional[dict[str, np.ndarray]]:
    """work: float 0..1 image at working res. Returns masks at working res, or None.
    `prob` lets the caller reuse a PSP pass already made for view detection."""
    if prob is None:
        prob = psp_probs(work)
    if prob is None:
        return None
    masks = masks_from_probs(prob, work.shape)
    return masks if masks_plausible(masks, work.shape) else None


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
