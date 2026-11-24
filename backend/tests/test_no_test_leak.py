"""CI guard: no TEST-split record id may appear in versioned tuning files (bench/tuning/*.json).

Splits are frozen in bench/splits.json. PTB-XL ids need their strat_fold: resolved from the local manifest when
present; an unresolvable PTB-XL id is treated as a leak (fail closed).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench import splits

BACKEND = Path(__file__).resolve().parents[1]
TUNING_DIR = BACKEND / "bench" / "tuning"


def _datasets_root() -> Path:
    import os
    return Path(os.environ.get("MEDLENS_DATASETS", BACKEND.parent / "data" / "datasets"))


def check_tuning_dir(directory: Path, fold_lookup: dict[str, int] | None = None) -> list[str]:
    """Return human-readable leak descriptions for every *.json under directory."""
    problems = []
    for p in sorted(directory.glob("**/*.json")):
        for src, rid in splits.test_ids_in(p.read_text(encoding="utf-8"), fold_lookup):
            problems.append(f"{p.name}: test id {rid} ({src})")
    return problems


def test_tuning_files_have_no_test_ids():
    lookup = splits.ptbxl_fold_lookup([_datasets_root() / "ptbxl" / "manifest.jsonl"])
    assert check_tuning_dir(TUNING_DIR, lookup) == []


def test_ptbxl_large_dev_list_is_dev_only():
    """The frozen enriched dev list (bench/lists/ptbxl_large_dev.json) must never contain a fold 9-10 (test/BURNED) id."""
    from bench import ptbxl_large
    cfg = splits.load_splits()["lists"]["ptbxl_large_dev"]
    lst = ptbxl_large.load_list(Path(splits.SPLITS_PATH).parent / cfg["file"])
    folds = {k: int(v) for k, v in lst["ids"].items()}
    assert len(folds) == lst["n"] >= 5000
    assert all(splits.split_of("ptbxl", rid, fo) == "dev" for rid, fo in folds.items())
    assert max(folds.values()) <= 8 and cfg["folds"] == [1, 8]
    assert lst["class_counts"]["NORM"] >= 400
    # same check through the leak scanner (ids found in the list text, resolved with the list's own folds)
    text = json.dumps(sorted(folds))
    assert splits.test_ids_in(text, folds) == []
    # and a test-fold id appended to the list text must be caught
    assert splits.test_ids_in(text + ' "ptbxl-99999"', {**folds, "ptbxl-99999": 9}) == [("ptbxl", "ptbxl-99999")]


def test_ptbxl_large_dev_list_matches_database_folds():
    """When the PTB-XL database csv is present: every listed id has strat_fold 1-8 there too (list not tampered)."""
    from bench import ptbxl_large
    try:
        rows = ptbxl_large.load_database(ptbxl_large.database_csv(_datasets_root()))
    except FileNotFoundError:
        pytest.skip("ptbxl_database.csv not available")
    lst = ptbxl_large.load_list()
    fold = {ptbxl_large.rid_of(r): int(r["strat_fold"]) for r in rows}
    assert all(fold[i] == f and 1 <= f <= 8 for i, f in lst["ids"].items())


def test_frozen_splits_shape():
    s = splits.load_splits()["sources"]
    assert s["ludb"]["dev"] == [1, 160] and s["ludb"]["test"] == [161, 200]
    assert s["ptbxl"]["dev"] == [1, 8] and s["ptbxl"]["test"] == [9, 10]
    assert s["qtdb"]["method"] == "external_test" and s["code_test"]["method"] == "external_test"
    assert s["iu_xray"]["method"] == "dev_only"
    assert [splits.split_of("ludb", f"ludb-{i}") for i in (1, 160, 161, 200)] == ["dev", "dev", "test", "test"]
    assert splits.split_of("ptbxl", "ptbxl-00001", fold=8) == "dev"
    assert splits.split_of("ptbxl", "ptbxl-00001", fold=9) == "test"
    assert splits.split_of("qtdb", "qtdb-sel100") == "test"
    assert splits.split_of("iu_xray", "CXR1_IM-0001-1001") == "dev"


def test_patient_hash_split_is_stable_and_patient_level():
    # both images of a Montgomery patient land in the same split; deterministic across runs
    for pid in ("0001", "0002", "0123"):
        a = splits.split_of("montgomery", f"MCUCXR_{pid}_0")
        b = splits.split_of("montgomery", f"MCUCXR_{pid}_1")
        assert a == b
    assert splits.hash_bucket("MCUCXR_0001") == splits.hash_bucket("MCUCXR_0001")
    got = {splits.split_of("jsrt_masks", f"JPCLN{i:03d}") for i in range(1, 100)}
    assert got == {"dev", "test"}


# --- the check itself must detect leaks (synthetic) -----------------------------------------------
def _write(tmp_path: Path, name: str, obj) -> None:
    (tmp_path / name).write_text(json.dumps(obj), encoding="utf-8")


def test_detects_ludb_test_id(tmp_path):
    _write(tmp_path, "t.json", {"thr": {"qrs": 0.4}, "tuned_on": ["ludb-12", "ludb-170"]})
    probs = check_tuning_dir(tmp_path)
    assert len(probs) == 1 and "ludb-170" in probs[0]


def test_dev_only_ids_pass(tmp_path):
    _write(tmp_path, "t.json", {"tuned_on": ["ludb-1", "ludb-160"], "note": "ptbxl-00042 fold 3"})
    assert check_tuning_dir(tmp_path, {"ptbxl-00042": 3}) == []


def test_detects_ptbxl_test_fold_and_unresolvable(tmp_path):
    _write(tmp_path, "t.json", {"ids": ["ptbxl-00042", "ptbxl-00077"]})
    probs = check_tuning_dir(tmp_path, {"ptbxl-00042": 3, "ptbxl-00077": 10})
    assert len(probs) == 1 and "ptbxl-00077" in probs[0]
    # no fold info -> fail closed
    assert len(check_tuning_dir(tmp_path, {})) == 2


def test_detects_external_test_and_hashed_test_ids(tmp_path):
    test_jsrt = next(f"JPCLN{i:03d}" for i in range(1, 248) if splits.split_of("jsrt_masks", f"JPCLN{i:03d}") == "test")
    dev_jsrt = next(f"JPCLN{i:03d}" for i in range(1, 248) if splits.split_of("jsrt_masks", f"JPCLN{i:03d}") == "dev")
    _write(tmp_path, "a.json", {"x": ["qtdb-sel100", test_jsrt, dev_jsrt]})
    probs = check_tuning_dir(tmp_path)
    assert any("qtdb-sel100" in p for p in probs) and any(test_jsrt in p for p in probs)
    assert not any(dev_jsrt in p for p in probs)


def test_detects_id_used_as_json_key(tmp_path):
    _write(tmp_path, "k.json", {"per_record": {"ludb-199": 1.0}})
    assert len(check_tuning_dir(tmp_path)) == 1
