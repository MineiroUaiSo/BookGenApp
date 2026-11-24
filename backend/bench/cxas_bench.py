"""CXAS vs current pipeline (PSPNet 'model' mode / heuristic) on the local PAX-Ray++ test subset (rx_masks_other).

    python -m bench.cxas_bench --stage cxas|model|heur [--limit N] [--tag T]      # writes data/bench/cxas/<tag>_<stage>.jsonl
    python -m bench.cxas_bench --stage report --tag T                              # Dice per structure/view, bootstrap CI95
    python -m bench.cxas_bench --stage latency --tag T [--limit N]                 # p50/p95 per image, one method at a time

GT = CT-projected pseudo-labels (synthetic radiographs, NOT radiologist ground truth). Dataset licence CC BY-NC 4.0:
non-commercial evaluation only. Nothing here is versioned (data/ is gitignored).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from bench.rx_bench import _analyze, _fake_ds, decode_struct_mask, dice_iou, load_gray, load_mask, view_class

DATASETS = Path(os.environ.get("MEDLENS_DATASETS", "data/datasets"))
BENCH = Path(os.environ.get("MEDLENS_BENCH", "data/bench"))
SRC = "rx_masks_other"
CXAS_PY = os.environ.get("MEDLENS_CXAS_PYTHON", "/Users/macbook/medlens-venvs/cxas/bin/python")
RUNNER = Path(__file__).resolve().parents[1] / "app" / "rx" / "cxas_runner.py"
KEYS = ["heart", "left_lung", "right_lung", "lungs", "spine", "aorta", "left_clavicle", "right_clavicle", "ribs_left",
        "ribs_right", "left_hemidiaphragm", "right_hemidiaphragm", "sternum", "trachea", "cardiomediastinum",
        "left_scapula", "right_scapula"]
GROUPS = {"clavicles": ["left_clavicle", "right_clavicle"], "ribs": ["ribs_left", "ribs_right"],
          "hemidiaphragms": ["left_hemidiaphragm", "right_hemidiaphragm"], "lungs": ["left_lung", "right_lung"]}
TARGETS = {"heart": 0.80, "spine": 0.75}


def load_rows(limit: int | None) -> list[dict]:
    root = DATASETS / SRC
    rows = [json.loads(line) for line in open(root / "manifest.jsonl")]
    rows.sort(key=lambda r: r["id"])
    if limit:  # deterministic, view-balanced: alternate PA / LATERAL
        pa = [r for r in rows if r["view"] != "LATERAL"][: (limit + 1) // 2]
        la = [r for r in rows if r["view"] == "LATERAL"][: limit // 2]
        rows = pa + la
    return rows


def gt_for(row: dict, shape) -> dict[str, np.ndarray]:
    root = DATASETS / SRC
    g = {k: load_mask(root / p, shape) for k, p in row["extra"]["masks"].items() if k in KEYS}
    if "left_lung" in g and "right_lung" in g:
        g["lungs"] = g["left_lung"] | g["right_lung"]
    return g


def score(pred: dict, gts: dict, supported: set | None) -> dict:
    out = {}
    for k, g in gts.items():
        p = pred.get(k)
        if p is None:
            out[k] = None if (supported is not None and k not in supported) else 0.0
        else:
            out[k] = dice_iou(p, g)[0]
    return out


def run_cxas(rows: list[dict], out_path: Path, chunk: int = 40) -> None:
    root = DATASETS / SRC
    with open(out_path, "w") as fh:
        for i in range(0, len(rows), chunk):
            for vc in ("frontal", "lateral"):
                grp = [r for r in rows[i:i + chunk] if (view_class(r["view"]) or "frontal") == vc]
                if not grp:
                    continue
                with tempfile.TemporaryDirectory() as td:
                    cmd = [CXAS_PY, "-I", str(RUNNER), "--out", td, "--view", vc] + [str(root / r["path"]) for r in grp]
                    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
                    res = json.loads(p.stdout.strip().splitlines()[-1])
                    if not res.get("ok"):
                        raise RuntimeError(res.get("error"))
                    for r, rr in zip(grp, res["results"]):
                        shape = tuple(rr["shape"])
                        gts = gt_for(r, shape)
                        pred = {k: load_mask(Path(pth), shape) for k, pth in rr["masks"].items()}
                        if "left_lung" in pred and "right_lung" in pred:
                            pred["lungs"] = pred["left_lung"] | pred["right_lung"]
                        sc = score(pred, gts, None)
                        # patient-side swap diagnostics for lateral-agnostic sides
                        fh.write(json.dumps({"id": r["id"], "view": vc, "t": rr["t"], "dice": sc,
                                             "dev": res["device"]}) + "\n")
                        fh.flush()
            print(f"cxas {min(i + chunk, len(rows))}/{len(rows)}", flush=True)


def run_base(rows: list[dict], mode: str, out_path: Path) -> None:
    root = DATASETS / SRC
    from app.rx.analyze import supported_structures
    with open(out_path, "w") as fh:
        for n, r in enumerate(rows):
            vc = view_class(r["view"]) or "frontal"
            img = load_gray(root / r["path"], 1024)
            shape = img.shape
            gts = gt_for(r, shape)
            a, dt = _analyze(img, r["id"], mode, _fake_ds("LATERAL" if vc == "lateral" else "PA"))
            pred = {}
            for st in a.structures:
                m = decode_struct_mask(st, shape)
                if m is not None:
                    pred[st.key] = m
            if "left_lung" in pred or "right_lung" in pred:
                pred["lungs"] = pred.get("left_lung", np.zeros(shape, bool)) | pred.get("right_lung", np.zeros(shape, bool))
            elif "lung_field" in pred:
                pred["lungs"] = pred["lung_field"]
            sup = supported_structures(mode, vc) | {"lungs"}
            fh.write(json.dumps({"id": r["id"], "view": vc, "t": round(dt, 4), "dice": score(pred, gts, sup)}) + "\n")
            fh.flush()
            if n % 50 == 0:
                print(f"{mode} {n}/{len(rows)}", flush=True)


def boot_ci(x: np.ndarray, n: int = 5000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), (n, len(x)))
    m = x[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(line) for line in open(p)] if p.exists() else []


def report(tag: str) -> str:
    d = BENCH / "cxas"
    methods = {"CXAS": "cxas", "PSPNet(model)": "model", "heuristic": "heur"}
    data = {m: load_jsonl(d / f"{tag}_{s}.jsonl") for m, s in methods.items()}
    lines = []
    for vc in ("frontal", "lateral"):
        lines.append(f"\n### {vc.upper() if vc == 'lateral' else 'PA (frontal)'}  (mean Dice [CI95 bootstrap], n)\n")
        lines.append("| estrutura | " + " | ".join(methods) + " |")
        lines.append("|---|" + "---|" * len(methods))
        for k in KEYS + list(GROUPS):
            cells = []
            for m in methods:
                rs = [r for r in data[m] if r["view"] == vc]
                if k in GROUPS:
                    vals = []
                    for r in rs:
                        ds = [r["dice"].get(q) for q in GROUPS[k]]
                        ds = [x for x in ds if x is not None]
                        if ds and len(ds) == sum(q in r["dice"] for q in GROUPS[k]):
                            vals.append(float(np.mean(ds)))
                else:
                    vals = [r["dice"][k] for r in rs if r["dice"].get(k) is not None]
                if len(vals) < 5:
                    cells.append("n/a" if not vals else f"({len(vals)})")
                    continue
                a = np.array(vals)
                lo, hi = boot_ci(a)
                cells.append(f"{a.mean():.3f} [{lo:.3f},{hi:.3f}] n={len(a)}")
            if k in GROUPS and k == "lungs":
                continue
            lines.append(f"| {k} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def latency(tag: str, limit: int) -> None:
    rows = load_rows(limit)
    out = {}
    for mode in ("cxas", "model", "heur"):
        p = BENCH / "cxas" / f"{tag}_lat_{mode}.jsonl"
        (run_cxas if mode == "cxas" else (lambda rs, o: run_base(rs, mode, o)))(rows, p)
        ts = [r["t"] for r in load_jsonl(p)][2:] if mode != "cxas" else [r["t"] for r in load_jsonl(p)]
        out[mode] = {"n": len(ts), "p50": float(np.percentile(ts, 50)), "p95": float(np.percentile(ts, 95))}
    print(json.dumps(out, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["cxas", "model", "heur", "report", "latency"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="v1")
    a = ap.parse_args()
    (BENCH / "cxas").mkdir(parents=True, exist_ok=True)
    if a.stage == "report":
        print(report(a.tag))
        return 0
    if a.stage == "latency":
        latency(a.tag, a.limit or 40)
        return 0
    rows = load_rows(a.limit)
    p = BENCH / "cxas" / f"{a.tag}_{a.stage}.jsonl"
    t0 = time.time()
    run_cxas(rows, p) if a.stage == "cxas" else run_base(rows, a.stage, p)
    print(f"done {a.stage} {len(rows)} in {time.time() - t0:.0f}s -> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
