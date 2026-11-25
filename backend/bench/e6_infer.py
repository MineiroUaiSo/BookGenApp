"""E6 shadow, inference step. Runs in the SEPARATE venv (/Users/macbook/medlens-venvs/e6: tensorflow/keras).

Reads the shards written by bench/e6_prep.py (400 Hz, 4000 samples, mV), zero-pads to 4096 and runs the
Ribeiro et al. 2020 model (Nat Commun 11:1760; Zenodo 3765717, CC BY 4.0). Output classes, in model order:
1dAVb, RBBB, LBBB, SB, AF, ST. Writes probs_<scale>.npz (ids, probs) in MEDLENS_BENCH/e6/.
Bench only: nothing here is imported by app/.

Usage: /Users/macbook/medlens-venvs/e6/bin/python bench/e6_infer.py --scale 10 [--limit-shards N]
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

CLASSES = ["1dAVb", "RBBB", "LBBB", "SB", "AF", "ST"]
BACKEND = Path(__file__).resolve().parents[1]
BENCH = Path(os.environ.get("MEDLENS_BENCH", BACKEND.parent / "data" / "bench")) / "e6"
MODEL = Path(os.environ.get("MEDLENS_E6_MODEL", BACKEND.parent / "data" / "models" / "ribeiro" / "model" / "model.hdf5"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=10.0, help="multiplier mV -> model unit (1e-4 V = 10 x mV)")
    ap.add_argument("--limit-shards", type=int, default=None)
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    import keras
    model = keras.models.load_model(str(MODEL), compile=False)
    ids, probs = [], []
    shards = sorted(BENCH.glob("sig_*.npy"))[: a.limit_shards]
    for p in shards:
        x = np.load(p).astype("float32") * a.scale
        pad = np.zeros((len(x), 4096, 12), dtype="float32")
        pad[:, : x.shape[1]] = x
        probs.append(model.predict(pad, batch_size=32, verbose=0))
        ids += json.loads((BENCH / p.name.replace("sig_", "ids_").replace(".npy", ".json")).read_text())
        print(p.name, flush=True)
    tag = a.tag or f"s{a.scale:g}"
    np.savez(BENCH / f"probs_{tag}.npz", ids=np.array(ids), probs=np.concatenate(probs), classes=np.array(CLASSES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
