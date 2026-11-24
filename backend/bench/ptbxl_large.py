"""Frozen, class-enriched PTB-XL DEV sample for the R2 evaluation base ("large" set).

Only strat_fold 1-8 (dev) records are ever selected; folds 9-10 stay BURNED/test and are never listed.
The list is written to bench/lists/ptbxl_large_dev.json (versioned, self-contained: id -> strat_fold) and
referenced from bench/splits.json ("lists"). Rebuild (deterministic, seed fixed):

    MEDLENS_DATASETS=/path/to/datasets python -m bench.ptbxl_large build

Selection (codes read from ptbxl_database.csv.scp_codes, positive = likelihood >= 50 or 0, same rule as the bench gold):
  * every record of each target class, randomly capped at CAP_PER_CLASS per class (seeded)
  * all myocardial-infarction records whose infarction_stadium1 is 'Stadium I' / 'Stadium I-II' (acute STE gold)
  * NORM_N random NORM records (>= 400 required), BACKGROUND_N random records of the remaining dev pool.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import random
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
LIST_PATH = Path(__file__).with_name("lists") / "ptbxl_large_dev.json"
DEV_FOLDS = (1, 8)
SEED = 20261124
CAP_PER_CLASS = 600
NORM_N = 1500
BACKGROUND_N = 1000
ACUTE_STADIUMS = ("Stadium I", "Stadium I-II")
MI_CODES = {"IMI", "ASMI", "ILMI", "AMI", "ALMI", "INJAS", "LMI", "INJAL", "IPLMI", "IPMI", "INJIN", "INJLA", "PMI",
            "INJIL", "MI"}
TARGET_CODES = ["1AVB", "2AVB", "3AVB", "AFLT", "AFIB", "CLBBB", "ILBBB", "CRBBB", "IRBBB", "LVH", "RVH", "STACH",
                "SBRAD", "PACE", "STD_", "STE_", "LNGQT", "WPW", "LAFB", "LPFB", "LVOLT", "ISC_", "NDT", "NST_"]


def datasets_root() -> Path:
    return Path(os.environ.get("MEDLENS_DATASETS", BACKEND.parent / "data" / "datasets"))


def database_csv(root: Path | None = None) -> Path:
    root = root or datasets_root()
    for sub in ("ptbxl_full", "ptbxl"):
        p = root / sub / "ptbxl_database.csv"
        if p.exists():
            return p
    raise FileNotFoundError("ptbxl_database.csv not found under " + str(root))


def parse_codes(s: str) -> dict[str, float]:
    try:
        v = ast.literal_eval(s) if s else {}
    except (ValueError, SyntaxError):
        v = {}
    return {str(k): float(x) for k, x in v.items()} if isinstance(v, dict) else {}


def positive_codes(scp: dict[str, float]) -> set[str]:
    return {k for k, v in scp.items() if v >= 50 or v == 0}


def load_database(path: Path | None = None) -> list[dict]:
    with (path or database_csv()).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rid_of(row: dict) -> str:
    return f"ptbxl-{int(row['ecg_id']):05d}"


def is_acute_mi(row: dict, pos: set[str]) -> bool:
    return bool(pos & MI_CODES) and (row.get("infarction_stadium1") or "").strip() in ACUTE_STADIUMS


def build_sample(rows: list[dict], seed: int = SEED) -> dict[str, int]:
    """id -> strat_fold of the frozen dev sample (deterministic for a given database + seed)."""
    rng = random.Random(seed)
    dev = [r for r in rows if DEV_FOLDS[0] <= int(r["strat_fold"]) <= DEV_FOLDS[1]]
    dev.sort(key=lambda r: int(r["ecg_id"]))
    pos = {rid_of(r): positive_codes(parse_codes(r["scp_codes"])) for r in dev}
    chosen: set[str] = set()
    for code in TARGET_CODES + ["__MI__"]:
        ids = [rid_of(r) for r in dev if (code in pos[rid_of(r)] if code != "__MI__" else pos[rid_of(r)] & MI_CODES)]
        chosen.update(ids if len(ids) <= CAP_PER_CLASS else rng.sample(ids, CAP_PER_CLASS))
    chosen.update(rid_of(r) for r in dev if is_acute_mi(r, pos[rid_of(r)]))
    norm = [rid_of(r) for r in dev if "NORM" in pos[rid_of(r)] and rid_of(r) not in chosen]
    chosen.update(rng.sample(norm, min(NORM_N, len(norm))))
    rest = [rid_of(r) for r in dev if rid_of(r) not in chosen]
    chosen.update(rng.sample(rest, min(BACKGROUND_N, len(rest))))
    fold = {rid_of(r): int(r["strat_fold"]) for r in dev}
    return {i: fold[i] for i in sorted(chosen)}


def class_counts(rows: list[dict], ids: set[str]) -> dict[str, int]:
    from collections import Counter
    c: Counter = Counter()
    for r in rows:
        i = rid_of(r)
        if i in ids:
            pos = positive_codes(parse_codes(r["scp_codes"]))
            c.update(pos)
            if is_acute_mi(r, pos):
                c["MI_acute(stadium I/I-II)"] += 1
    return dict(c.most_common())


def load_list(path: Path = LIST_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def large_dev_records(root: Path | None = None) -> list[dict]:
    """Manifest-like records (id, absolute path, extra{...}) of the frozen sample, read from ptbxl_full."""
    root = root or datasets_root()
    lst = load_list()
    want = lst["ids"]
    base = root / "ptbxl_full"
    out = []
    for r in load_database(base / "ptbxl_database.csv"):
        i = rid_of(r)
        if i not in want:
            continue
        extra = {k: r.get(k, "") for k in ("scp_codes", "age", "sex", "heart_axis", "strat_fold", "device", "site",
                                            "infarction_stadium1", "baseline_drift", "static_noise", "burst_noise",
                                            "electrodes_problems", "extra_beats", "pacemaker", "patient_id", "ecg_id")}
        out.append({"id": i, "source": "ptbxl", "kind": "signal", "path": str(base / (r["filename_hr"] + ".hea")),
                    "extra": extra})
    out.sort(key=lambda r: r["id"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "show"])
    a = ap.parse_args(argv)
    if a.cmd == "show":
        lst = load_list()
        print(json.dumps({"n": len(lst["ids"]), "counts": lst["class_counts"]}, indent=1))
        return 0
    rows = load_database()
    ids = build_sample(rows)
    assert all(DEV_FOLDS[0] <= f <= DEV_FOLDS[1] for f in ids.values())
    cc = class_counts(rows, set(ids))
    assert cc.get("NORM", 0) >= 400
    LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIST_PATH.write_text(json.dumps({
        "version": 1, "seed": SEED, "folds": list(DEV_FOLDS), "cap_per_class": CAP_PER_CLASS, "norm_n": NORM_N,
        "background_n": BACKGROUND_N, "n": len(ids), "class_counts": cc,
        "note": "Frozen class-enriched PTB-XL DEV sample (strat_fold 1-8 only). Folds 9-10 are BURNED and never listed. "
                "ids maps record id -> strat_fold. Rebuild: python -m bench.ptbxl_large build.",
        "ids": ids}, indent=0), encoding="utf-8")
    print(f"wrote {LIST_PATH} n={len(ids)}")
    print(json.dumps(cc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
