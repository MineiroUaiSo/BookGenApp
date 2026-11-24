import importlib.util

from fastapi import APIRouter

router = APIRouter()

_OPTIONAL = {
    "neurokit2": "neurokit2", "wfdb": "wfdb", "cv2": "opencv", "torch": "torch",
    "torchvision": "torchvision", "torchxrayvision": "torchxrayvision",
    "trimesh": "trimesh", "anthropic": "anthropic", "pylibjpeg": "pylibjpeg",
    "pillow_heif": "pillow_heif",
}


def _has(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


@router.get("/health")
def health():
    ai = False
    try:
        from app.llm import ai_available

        ai = bool(ai_available())
    except Exception:
        ai = False
    return {
        "status": "ok",
        "ai_available": ai,
        "models": {label: _has(mod) for mod, label in _OPTIONAL.items()},
    }
