"""CODE-test external test set (Ribeiro et al., Nat Commun 2020; Zenodo 3765780, CC BY 4.0): PREPARED, NOT RUN.

827 patients, 12 leads, 400 Hz, 4096 samples (zero-padded on both sides), gold standard labels
1dAVb, RBBB, LBBB, SB, AF, ST (cardiologists 1+2, third specialist decides disagreements).

This is the FINAL external test: it may be run ONCE, at the very end of the whole work, never to tune anything.
Protection (enforced in code, see guard_run):
  * needs the explicit flag  --i-know-this-is-the-final-external-test
  * writes data/bench/ecg/code_test.RUN before analysing and refuses to run again while that marker exists

    python -m bench.ecg_bench --source code_test --i-know-this-is-the-final-external-test --workers 3   # ONCE, final

Data layout (datasets/code_test/data/): ecg_tracings.hdf5 (dataset 'tracings' (827, 4096, 12), lead order
DI, DII, DIII, AVL, AVF, AVR, V1..V6), annotations/gold_standard.csv (+ dnn.csv, cardiologist*.csv ...), attributes.csv (age,sex).
Loading: h5py when installed, else tracings_float32.npy next to it (python -m bench.code_test convert, needs h5py, run once with any
interpreter that has h5py; the server venv has none and must not get new packages).
Unit: the README says "scale 1e-4 V" but the numbers are empirically millivolts (lead II 99.5th percentile |x| per record has
median 1.44, P10 0.71, P90 2.95: R waves of ~1-3 mV); UNIT_TO_MV = 1.0 documents/pins that choice (smoke-tested in tests/test_code_test.py).
"""
from __future__ import annotations

import csv
import json
import multiprocessing as mp
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.environ.get("MEDLENS_DATASETS", BACKEND.parent / "data" / "datasets"))
FINAL_FLAG = "--i-know-this-is-the-final-external-test"
FS = 400.0
N_SAMPLES = 4096
UNIT_TO_MV = 1.0   # values are already mV (see module docstring)
# dataset lead order -> our lead names
DATASET_LEADS = ["I", "II", "III", "aVL", "aVF", "aVR", "V1", "V2", "V3", "V4", "V5", "V6"]
LABELS = ["1dAVb", "RBBB", "LBBB", "SB", "AF", "ST"]
# label -> key of bench.ecg_bench.PRED (our finding predicate); the dataset does not separate complete/incomplete RBBB or LBBB
LABEL_TO_PRED = {"1dAVb": "AV1", "RBBB": "RBBB_any", "LBBB": "LBBB_any", "SB": "SBRAD", "AF": "AF", "ST": "STACH"}


def root(data_root: Optional[Path] = None) -> Path:
    return (data_root or DATA_ROOT) / "code_test" / "data"


def out_root() -> Path:
    return Path(os.environ.get("MEDLENS_BENCH", BACKEND.parent / "data" / "bench")) / "ecg"


def marker_path(out: Optional[Path] = None) -> Path:
    return (out or out_root()) / "code_test.RUN"


def rid(i: int) -> str:
    return f"codetest-{i:04d}"


def load_tracings(data_root: Optional[Path] = None) -> np.ndarray:
    """(827, 4096, 12) float array in file units (see UNIT_TO_MV). Memory-mapped when the npy cache is used."""
    r = root(data_root)
    h5 = r / "ecg_tracings.hdf5"
    try:
        import h5py  # type: ignore
        with h5py.File(h5, "r") as f:
            return np.array(f["tracings"])
    except ImportError:
        npy = r / "tracings_float32.npy"
        if not npy.exists():
            raise RuntimeError("h5py is not installed and tracings_float32.npy is missing: run  python -m bench.code_test convert "
                               "with an interpreter that has h5py") from None
        return np.load(npy, mmap_mode="r")


def load_labels(name: str = "gold_standard", data_root: Optional[Path] = None) -> np.ndarray:
    """(827, 6) int array, columns = LABELS."""
    with (root(data_root) / "annotations" / f"{name}.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return np.array([[int(r[k]) for k in LABELS] for r in rows], dtype=int)


def load_attributes(data_root: Optional[Path] = None) -> list[dict]:
    with (root(data_root) / "attributes.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def trim_padding(x: np.ndarray) -> np.ndarray:
    """x (4096, 12): drop the all-zero padding added on both sides (first/last row with any non-zero sample)."""
    nz = np.flatnonzero(np.any(np.asarray(x) != 0, axis=1))
    if not len(nz):
        return np.asarray(x)
    return np.asarray(x)[nz[0]: nz[-1] + 1]


def to_signal(x: np.ndarray):
    """One tracing (4096, 12) -> app.schemas.ECGSignal (fs 400 Hz, mV, padding removed)."""
    from app.schemas import ECGSignal, SourceKind
    y = trim_padding(x).astype(float) * UNIT_TO_MV
    leads = {name: [float(v) for v in y[:, k]] for k, name in enumerate(DATASET_LEADS)}
    return ECGSignal(fs=FS, leads=leads, duration_s=round(len(y) / FS, 3), source=SourceKind.CSV)


# ----------------------------------------------------------------------------------------------------------------- guard
class FinalTestGuardError(RuntimeError):
    pass


def guard_run(i_know: bool, out: Optional[Path] = None, head: str = "") -> Path:
    """Refuse unless the flag is given and no marker exists; then create the marker (before any analysis). Returns marker path."""
    if not i_know:
        raise FinalTestGuardError(f"CODE-test is the final external test: pass {FINAL_FLAG} to run it (once).")
    m = marker_path(out)
    if m.exists():
        raise FinalTestGuardError(f"{m} exists: the CODE-test was already run. It must never be run twice "
                                  f"(delete the marker only with explicit owner approval).")
    m.parent.mkdir(parents=True, exist_ok=True)
    with m.open("x", encoding="utf-8") as f:   # 'x': atomic, fails if it appears concurrently
        f.write(json.dumps({"started": datetime.now(timezone.utc).isoformat(), "head": head}) + "\n")
    return m


# ----------------------------------------------------------------------------------------------------------------- run
def _task(i: int) -> dict:
    from app.ecg.analysis import analyze_signal
    x = load_tracings()[i]
    attrs = load_attributes()[i]
    t0 = time.time()
    try:
        age = float(attrs["age"])
    except (KeyError, ValueError):
        age = None
    an = analyze_signal(to_signal(x), rid(i), age=age, sex=attrs.get("sex") or None)
    return {"id": rid(i), "ok": True, "codes": sorted({f.code for f in an.findings}),
            "hr": an.global_measurements.heart_rate_bpm, "t_s": round(time.time() - t0, 3)}


def _safe_task(i: int) -> dict:
    try:
        return _task(i)
    except Exception as e:  # noqa: BLE001 - every record must give a line
        return {"id": rid(i), "ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def run_final(i_know: bool, workers: int = 3, out: Optional[Path] = None, head: str = "") -> int:
    """THE one-shot run (guarded). Writes <out>/code_test.jsonl and the metrics table to stdout."""
    guard_run(i_know, out, head)
    out = out or out_root()
    n = len(load_labels())
    cache = out / "code_test.jsonl"
    with cache.open("w", encoding="utf-8") as f, mp.get_context("fork").Pool(workers) as pool:
        for res in pool.imap_unordered(_safe_task, range(n), chunksize=1):
            f.write(json.dumps(res) + "\n")
    print(evaluate_file(cache))
    return 0


def evaluate(results: list[dict], gold: np.ndarray) -> str:
    """Metrics table (sens/spec/PPV/acc with bootstrap IC95%) per label from result lines; pure, used after the final run."""
    from bench import ecg_bench as eb
    from bench.report import bootstrap_binary_arrays, fmt_ci, table
    by = {r["id"]: r for r in results if r.get("ok")}
    rows = []
    for k, label in enumerate(LABELS):
        idx = [i for i in range(len(gold)) if rid(i) in by]
        g = [bool(gold[i, k]) for i in idx]
        p = [bool(eb.PRED[LABEL_TO_PRED[label]](set(by[rid(i)]["codes"]))) for i in idx]
        b = bootstrap_binary_arrays(g, p)
        tp, fp, fn, tn = b["counts"]
        rows.append([label, LABEL_TO_PRED[label], len(idx), tp + fn, tp, fp, fmt_ci(*b["sens"]), fmt_ci(*b["spec"]),
                     fmt_ci(*b["ppv"]), fmt_ci(*b["acc"])])
    return table(rows, ["rótulo", "nossa regra", "N", "N pos", "TP", "FP", "Sens [IC95%]", "Espec [IC95%]", "VPP [IC95%]", "Acc [IC95%]"])


def evaluate_file(cache: Path) -> str:
    res = [json.loads(line) for line in cache.open(encoding="utf-8") if line.strip()]
    return evaluate(res, load_labels())


def convert() -> int:
    """One-off: HDF5 -> tracings_float32.npy (needs h5py)."""
    import h5py  # type: ignore
    r = root()
    with h5py.File(r / "ecg_tracings.hdf5", "r") as f:
        np.save(r / "tracings_float32.npy", np.array(f["tracings"]).astype(np.float32))
    print("wrote", r / "tracings_float32.npy")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["convert"]:
        sys.exit(convert())
    print(__doc__)
