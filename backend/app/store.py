"""Disk store: studies (JSON), original instance files, artifacts.

Layout under root ($MEDLENS_DATA, default ./data)::

    studies/<study_id>/study.json
    studies/<study_id>/instances/<instance_id>/meta.json + original file(s)
    studies/<study_id>/artifacts/<name>

instance_id is ``<study_id>-<hash>`` so the owning study is derivable from it.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Optional

from app import config
from app.schemas import StudyInfo

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(name: str, default: str = "file") -> str:
    base = Path(name.replace("\\", "/")).name
    base = _SAFE.sub("_", base).strip("._") or default
    return base[:120]


class Store:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else config.data_dir()
        self._lock = threading.RLock()

    # ---- paths
    def _study_dir(self, study_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", study_id):
            raise KeyError(study_id)
        return self.root / "studies" / study_id

    @staticmethod
    def study_of(instance_id: str) -> str:
        return instance_id.rsplit("-", 1)[0]

    def _inst_dir(self, instance_id: str) -> Path:
        return self._study_dir(self.study_of(instance_id)) / "instances" / instance_id

    # ---- studies
    def save_study(self, study: StudyInfo) -> None:
        with self._lock:
            d = self._study_dir(study.study_id)
            d.mkdir(parents=True, exist_ok=True)
            tmp = d / "study.json.tmp"
            tmp.write_text(study.model_dump_json(indent=1), encoding="utf-8")
            tmp.replace(d / "study.json")

    def get_study(self, study_id: str) -> Optional[StudyInfo]:
        try:
            f = self._study_dir(study_id) / "study.json"
        except KeyError:
            return None
        if not f.exists():
            return None
        return StudyInfo.model_validate_json(f.read_text(encoding="utf-8"))

    def list_studies(self) -> list[StudyInfo]:
        base = self.root / "studies"
        if not base.exists():
            return []
        out = []
        for d in base.iterdir():
            s = self.get_study(d.name)
            if s:
                out.append(s)
        out.sort(key=lambda s: s.created_at, reverse=True)
        return out

    # ---- instances
    def save_instance(self, instance_id: str, filename: str, data: bytes, meta: dict) -> Path:
        with self._lock:
            d = self._inst_dir(instance_id)
            d.mkdir(parents=True, exist_ok=True)
            fn = safe_name(filename)
            (d / fn).write_bytes(data)
            meta = dict(meta, file=fn)
            (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            return d / fn

    def add_instance_file(self, instance_id: str, filename: str, data: bytes) -> Path:
        d = self._inst_dir(instance_id)
        p = d / safe_name(filename)
        p.write_bytes(data)
        return p

    def instance_meta(self, instance_id: str) -> dict:
        try:
            f = self._inst_dir(instance_id) / "meta.json"
        except KeyError:
            raise KeyError(instance_id)
        if not f.exists():
            raise KeyError(instance_id)
        return json.loads(f.read_text(encoding="utf-8"))

    def instance_path(self, instance_id: str) -> Path:
        meta = self.instance_meta(instance_id)
        return self._inst_dir(instance_id) / meta["file"]

    # ---- artifacts
    def put_artifact(self, study_id: str, name: str, data: bytes) -> Path:
        with self._lock:
            d = self._study_dir(study_id) / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            p = d / safe_name(name)
            p.write_bytes(data)
            return p

    def get_artifact(self, study_id: str, name: str) -> Path | None:
        try:
            p = self._study_dir(study_id) / "artifacts" / safe_name(name)
        except KeyError:
            return None
        return p if p.exists() else None


store = Store()
