"""Local usage log (JSONL) WITHOUT PHI.

Only whitelisted, typed fields are ever written: commit hash, app version, per-stage latency, quality flags,
emitted finding codes, AI provider, agree/disagree feedback. Never names, ids, birth dates, pixels, free report
text or DICOM UIDs. Study ids are replaced by a per-installation random-salted hash so events can be correlated
without exposing the id. Log path: <MEDLENS_DATA>/logs/usage.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from . import config

APP_VERSION = "0.1.0"
_CODE_RE = re.compile(r"^[a-z0-9_.\-]{1,80}$")
_LOCK = threading.Lock()
_COMMIT: str | None = None

# field -> validator. Anything not listed here is dropped; anything failing validation is dropped.
_NUM = (int, float)


def _codes(v: Any) -> bool:
    return isinstance(v, list) and len(v) <= 200 and all(isinstance(x, str) and _CODE_RE.match(x) for x in v)


def _latency(v: Any) -> bool:
    return isinstance(v, dict) and len(v) <= 12 and all(
        isinstance(k, str) and _CODE_RE.match(k) and isinstance(x, _NUM) and not isinstance(x, bool) for k, x in v.items())


def _flags(v: Any) -> bool:
    return _codes(v)


_FIELDS = {
    "kind": lambda v: v in ("ecg", "rx"),
    "latency_ms": _latency,
    "quality_flags": _flags,
    "codes": _codes,
    "ai_provider": lambda v: v is None or (isinstance(v, str) and _CODE_RE.match(v) is not None),
    "ai_requested": lambda v: isinstance(v, bool),
    "code": lambda v: isinstance(v, str) and _CODE_RE.match(v) is not None,
    "verdict": lambda v: v in ("agree", "disagree"),
    "n_findings": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "out_of_scope": lambda v: isinstance(v, bool),
}
ALLOWED_FIELDS = frozenset(_FIELDS) | {"ts", "event", "commit", "version", "study_hash"}


def log_path() -> Path:
    return config.data_dir() / "logs" / "usage.jsonl"


def _salt() -> str:
    p = config.data_dir() / "logs" / ".salt"
    if p.exists():
        return p.read_text().strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    s = secrets.token_hex(16)
    p.write_text(s)
    return s


def study_hash(study_id: str) -> str:
    return hashlib.sha256((_salt() + study_id).encode()).hexdigest()[:16]


def commit_hash() -> str:
    global _COMMIT
    if _COMMIT is None:
        try:
            out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=3,
                                 cwd=Path(__file__).resolve().parent)
            _COMMIT = out.stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            _COMMIT = "unknown"
    return _COMMIT


def sanitize(fields: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in fields.items():
        if k in ("codes", "quality_flags") and isinstance(v, list):
            v = [x for x in v if isinstance(x, str) and _CODE_RE.match(x)][:200]   # drop invalid items, keep valid
        if k in _FIELDS and _FIELDS[k](v):
            out[k] = v
    return out


def log_event(event: str, study_id: str | None = None, **fields: Any) -> dict[str, Any]:
    """Append one sanitized event. Never raises (logging must not break an analysis)."""
    rec: dict[str, Any] = {"ts": round(time.time(), 3), "event": event if _CODE_RE.match(event) else "invalid",
                           "commit": commit_hash(), "version": APP_VERSION, **sanitize(fields)}
    try:
        if study_id:
            rec["study_hash"] = study_hash(study_id)
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec
