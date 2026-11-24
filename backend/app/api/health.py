"""GET /health: real import/load checks per component (ok | ausente | erro: <motivo>), cached per process."""
from __future__ import annotations

import importlib
import threading
from typing import Callable

from fastapi import APIRouter

router = APIRouter()

_OPTIONAL = {
    "neurokit2": "neurokit2", "wfdb": "wfdb", "cv2": "opencv", "torch": "torch",
    "torchvision": "torchvision", "torchxrayvision": "torchxrayvision",
    "trimesh": "trimesh", "anthropic": "anthropic", "pylibjpeg": "pylibjpeg",
    "pillow_heif": "pillow_heif",
}
_ANALYZERS = {"app.ecg": "analisador_ecg", "app.rx": "analisador_rx"}
RX_MODEL_LABEL = "modelo_rx"
RX_MODEL_TIMEOUT_S = 10.0
_MAX_REASON = 120

_lock = threading.Lock()
_cache: dict[str, str] = {}


def _short(e: BaseException) -> str:
    msg = (str(e).splitlines() or [""])[0].strip()
    return f"erro: {type(e).__name__}: {msg}"[:_MAX_REASON]


def _check_import(mod: str) -> str:
    try:
        importlib.import_module(mod)
        return "ok"
    except ModuleNotFoundError as e:
        # the module itself missing -> ausente; a broken transitive import -> erro
        root = mod.split(".")[0]
        return "ausente" if (e.name or "").split(".")[0] == root else _short(e)
    except Exception as e:  # broken install, ABI mismatch, ...
        return _short(e)


def _load_rx_model() -> str:
    try:
        from app.rx import seg_model
    except Exception as e:
        return _short(e)
    if not seg_model.models_enabled():
        return "ausente"
    if _check_import("torchxrayvision") != "ok" or _check_import("torch") != "ok":
        return "ausente"
    try:
        return "ok" if seg_model._psp() is not None else "erro: pesos do modelo não carregaram"
    except Exception as e:
        return _short(e)


def _run_with_timeout(fn: Callable[[], str], timeout_s: float) -> str | None:
    """Run fn in a daemon thread; None if it did not finish in time (it keeps loading in the background)."""
    box: list[str] = []
    t = threading.Thread(target=lambda: box.append(fn()), daemon=True)
    t.start()
    t.join(timeout_s)
    return box[0] if box else None


def reset_cache() -> None:
    with _lock:
        _cache.clear()


def component_status() -> dict[str, str]:
    with _lock:
        if _cache:
            return dict(_cache)
        out = {label: _check_import(mod) for mod, label in _OPTIONAL.items()}
        out.update({label: _check_import(mod) for mod, label in _ANALYZERS.items()})
        rx = _run_with_timeout(_load_rx_model, RX_MODEL_TIMEOUT_S)
        if rx is None:
            return {**out, RX_MODEL_LABEL: "erro: carregamento excedeu 10 s"}  # not cached: retry next call
        out[RX_MODEL_LABEL] = rx
        _cache.update(out)
        return dict(out)


@router.get("/health")
def health():
    ai = False
    try:
        from app.llm import ai_available

        ai = bool(ai_available())
    except Exception:
        ai = False
    models = component_status()
    degraded = sorted(k for k, v in models.items() if v != "ok")
    return {"status": "ok", "ai_available": ai, "models": models, "degraded": degraded}
