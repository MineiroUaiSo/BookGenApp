"""Runtime configuration (env driven)."""
from __future__ import annotations

import os
from pathlib import Path

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "MEDLENS_CORS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

FRONTEND_DIST = Path(
    os.environ.get(
        "MEDLENS_FRONTEND_DIST",
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
    )
)

# Safety limits for archive expansion
MAX_ZIP_FILES = int(os.environ.get("MEDLENS_MAX_ZIP_FILES", "20000"))
MAX_ZIP_BYTES = int(os.environ.get("MEDLENS_MAX_ZIP_BYTES", str(4 * 1024**3)))


def data_dir() -> Path:
    return Path(os.environ.get("MEDLENS_DATA", "./data")).expanduser()
