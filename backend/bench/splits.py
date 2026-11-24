"""Frozen dataset splits (see bench/splits.json). Pure stdlib; usable from tests and benchmarks.

split_of(source, record_id, fold=None) -> "dev" | "test"
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

SPLITS_PATH = Path(__file__).with_name("splits.json")


@lru_cache(maxsize=1)
def load_splits() -> dict:
    return json.loads(SPLITS_PATH.read_text(encoding="utf-8"))


def hash_bucket(key: str) -> int:
    """Stable 0-99 bucket of a patient key (md5, platform independent)."""
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) % 100


def _numeric_suffix(rid: str) -> int:
    m = re.search(r"(\d+)$", rid)
    if not m:
        raise ValueError(f"no numeric suffix in id {rid!r}")
    return int(m.group(1))


def split_of(source: str, rid: str, fold: Optional[int] = None) -> str:
    """Split of one record. PTB-XL needs its strat_fold (manifest extra.strat_fold or ptbxl_database.csv)."""
    cfg = load_splits()["sources"][source]
    method = cfg["method"]
    if method == "id_range":
        n = _numeric_suffix(rid)
        if cfg["dev"][0] <= n <= cfg["dev"][1]:
            return "dev"
        if cfg["test"][0] <= n <= cfg["test"][1]:
            return "test"
        raise ValueError(f"{rid!r} outside the frozen {source} ranges")
    if method == "strat_fold":
        if fold is None:
            raise ValueError(f"{source}: strat_fold required to place {rid!r}")
        return "dev" if cfg["dev"][0] <= int(fold) <= cfg["dev"][1] else "test"
    if method in ("external_test",):
        return "test"
    if method == "dev_only":
        return "dev"
    if method == "patient_hash":
        m = re.match(cfg["patient_key_regex"], rid)
        key = m.group(1) if m else rid
        return "dev" if hash_bucket(key) < cfg["dev_pct"] else "test"
    raise ValueError(f"unknown split method {method!r}")


def source_of_id(rid: str) -> Optional[str]:
    """Source whose id_regex fully matches rid (None if unknown)."""
    for src, cfg in load_splits()["sources"].items():
        if re.fullmatch(cfg["id_regex"], rid):
            return src
    return None


def find_ids(text: str) -> list[tuple[str, str]]:
    """All (source, id) tokens of known sources found inside text."""
    out, seen = [], set()
    for src, cfg in load_splits()["sources"].items():
        for m in re.finditer(r"(?<![\w.-])(?:" + cfg["id_regex"] + r")(?![\w])", text):
            key = (src, m.group(0))
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def test_ids_in(text: str, fold_lookup: Optional[dict[str, int]] = None) -> list[tuple[str, str]]:
    """Ids found in text that belong to a TEST split. PTB-XL ids are resolved via fold_lookup
    (id -> strat_fold); an unresolvable PTB-XL id is reported as test (fail closed)."""
    bad = []
    for src, rid in find_ids(text):
        fold = None
        if src == "ptbxl":
            fold = (fold_lookup or {}).get(rid)
            if fold is None:
                bad.append((src, rid))
                continue
        if split_of(src, rid, fold) == "test":
            bad.append((src, rid))
    return bad


def ptbxl_fold_lookup(manifest_paths: Iterable[Path]) -> dict[str, int]:
    """id -> strat_fold from ptbxl manifest.jsonl files (those that exist)."""
    out: dict[str, int] = {}
    for p in manifest_paths:
        if not Path(p).exists():
            continue
        for line in Path(p).open(encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            fo = (r.get("extra") or {}).get("strat_fold")
            if fo not in (None, ""):
                out[r["id"]] = int(float(fo))
    return out
