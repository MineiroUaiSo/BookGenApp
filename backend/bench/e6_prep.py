"""E6 shadow (bench only): export the PTB-XL DEV (large set, folds 1-8) signals resampled to 400 Hz as npy shards.

Runs in the MedLens backend venv. The classifier itself runs in a separate venv (bench/e6_infer.py).
Output (MEDLENS_BENCH/e6/): sig_XXXX.npy float32 (n, 4000, 12) in mV, lead order DI DII DIII aVR aVL aVF V1..V6, and ids_XXXX.json.
Usage (from backend/): python -m bench.e6_prep [--limit N] [--workers K]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from bench import ecg_bench, ptbxl_large  # noqa: E402

LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
FS_OUT = 400
N_OUT = 4000
SHARD = 500
OUT = Path(os.environ.get("MEDLENS_BENCH", BACKEND.parent / "data" / "bench")) / "e6"


def load_resampled(rec: dict) -> np.ndarray | None:
    from app.ecg.ingest import load_ecg
    sig = load_ecg(ecg_bench.resolve("ptbxl", rec["path"]))
    if not all(l in sig.leads for l in LEADS):
        return None
    fs = int(round(sig.fs))
    x = np.stack([np.asarray(sig.leads[l], dtype=np.float64) for l in LEADS], axis=1)
    g = np.gcd(fs, FS_OUT)
    y = resample_poly(x, FS_OUT // g, fs // g, axis=0)
    out = np.zeros((N_OUT, 12), dtype=np.float32)
    n = min(N_OUT, len(y))
    out[:n] = y[:n]
    return out


def _work(rec: dict):
    try:
        return rec["id"], load_resampled(rec)
    except Exception:  # noqa: BLE001 - bench: record failures are counted, not fatal
        return rec["id"], None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    ecg_bench.SET = "large"   # fold map of the frozen large DEV list
    recs = ptbxl_large.large_dev_records(ecg_bench.DATA_ROOT)
    folds = ecg_bench.ptbxl_fold_map()
    recs = [r for r in recs if ecg_bench.in_split(r["id"], "dev", folds)]   # safety: DEV folds 1-8 only
    if a.limit:
        recs = recs[: a.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    pool = mp.get_context("fork").Pool(a.workers)
    failed = []
    try:
        for s in range(0, len(recs), SHARD):
            chunk = recs[s: s + SHARD]
            res = pool.map(_work, chunk, chunksize=4)
            ids = [i for i, x in res if x is not None]
            failed += [i for i, x in res if x is None]
            np.save(OUT / f"sig_{s // SHARD:04d}.npy", np.stack([x for _, x in res if x is not None]))
            (OUT / f"ids_{s // SHARD:04d}.json").write_text(json.dumps(ids))
            print(f"shard {s // SHARD} ok={len(ids)} failed_total={len(failed)}", flush=True)
    finally:
        pool.terminate()
    (OUT / "failed.json").write_text(json.dumps(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
