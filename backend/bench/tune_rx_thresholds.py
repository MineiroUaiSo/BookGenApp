"""Tune per-pathology TorchXRayVision thresholds on DEV (IU X-ray cache) for a fixed specificity; evaluate on VinDr-CXR test.

    python -m bench.tune_rx_thresholds [--spec 0.90] [--out bench/tuning/rx_thresholds.json] [--dry-run]
    python -m bench.tune_rx_thresholds --source vindr --vindr-labels image_labels_test.csv --vindr-images DIR

Dev = IU X-ray (cache from `python -m bench.rx_bench --source iu --models on`). CAVEAT: TorchXRayVision 'all' weights were
trained on OpenI (= IU) among others, so IU scores are optimistic (leakage); thresholds tuned here may be too high for
unseen data. Thresholds are only ever fitted on IU; the primary TEST is VinDr-CXR test consensus labels (requires
credentialed PhysioNet download: PENDING). Never use NIH/CheXpert/MIMIC/PadChest/IU as test. Scores are frontal-only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from bench.rx_bench import auc_ci, wilson  # noqa: E402

DEFAULT_OUT = HERE / "tuning" / "rx_thresholds.json"
DEFAULT_THR = 0.65
MIN_POS = 10          # fewer positives -> keep default
MIN_AUC_LO = 0.55     # AUC lower CI bound must clear this, else threshold is not trusted
COSTO_SENS_MIN = 0.30

# TorchXRayVision pathology -> IU study-level target (rx_bench.text_labels names)
PATHO_TARGET = {"Atelectasis": "atelectasis", "Consolidation": "consolidation", "Pneumonia": "consolidation",
                "Effusion": "effusion", "Pneumothorax": "pneumothorax", "Cardiomegaly": "cardiomegaly"}
# VinDr-CXR consensus label column -> TorchXRayVision pathology
VINDR_MAP = {"Cardiomegaly": "Cardiomegaly", "Pleural effusion": "Effusion", "Pneumothorax": "Pneumothorax",
             "Consolidation": "Consolidation", "Atelectasis": "Atelectasis", "Nodule/Mass": "Nodule",
             "Pleural thickening": "Pleural_Thickening", "Lung Opacity": "Lung Opacity", "Emphysema": "Emphysema",
             "Fracture": "Fracture", "Infiltration": "Infiltration", "Pneumonia": "Pneumonia"}


def threshold_for_specificity(y, s, spec: float = 0.90) -> Optional[float]:
    """Smallest score t (3 decimals, rounded up) such that 'score >= t' has specificity >= spec on negatives."""
    y = np.asarray(y, bool)
    s = np.asarray(s, float)
    neg = np.sort(s[~y])
    if not len(neg):
        return None
    allowed_fp = int(math.floor((1 - spec) * len(neg) + 1e-9))
    # t must exceed the (allowed_fp+1)-th largest negative score
    if allowed_fp >= len(neg):
        return 0.0
    kth = neg[len(neg) - 1 - allowed_fp]
    return min(1.0, math.floor(kth * 1000 + 1e-9) / 1000 + 0.001)


def ece(y, s, bins: int = 10) -> float:
    """Expected calibration error of raw scores read as probabilities (equal-width bins)."""
    y = np.asarray(y, float)
    s = np.clip(np.asarray(s, float), 0, 1)
    idx = np.minimum((s * bins).astype(int), bins - 1)
    tot = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            tot += m.sum() / len(s) * abs(y[m].mean() - s[m].mean())
    return float(tot)


def ppv_at(sens: float, spec: float, prev: float) -> float:
    den = sens * prev + (1 - spec) * (1 - prev)
    return float(sens * prev / den) if den > 0 else float("nan")


def evaluate(y, s, thr: float, prevalence: Optional[float] = None, n_boot: int = 500) -> dict:
    y = np.asarray(y, bool)
    s = np.asarray(s, float)
    pred = s >= thr
    tp, fn = int((y & pred).sum()), int((y & ~pred).sum())
    tn, fp = int((~y & ~pred).sum()), int((~y & pred).sum())
    a, lo, hi = auc_ci(y, s, n_boot=n_boot)
    sens = tp / (tp + fn) if tp + fn else float("nan")
    spec = tn / (tn + fp) if tn + fp else float("nan")
    prev = float(y.mean()) if prevalence is None else prevalence
    return {"n": int(len(y)), "pos": int(y.sum()), "threshold": thr, "auc": a, "auc_lo": lo, "auc_hi": hi,
            "sens": sens, "sens_ci": list(wilson(tp, tp + fn)), "spec": spec, "spec_ci": list(wilson(tn, tn + fp)),
            "ppv_at_prevalence": ppv_at(sens, spec, prev), "prevalence": prev, "ece": ece(y, s)}


def _study_scores(rows: list[dict], patho: str) -> list[Optional[float]]:
    out = []
    for r in rows:
        v = [i["scores"][patho] for i in r["images"] if "error" not in i and i.get("scores") and patho in i["scores"]]
        out.append(max(v) if v else None)
    return out


def iu_samples(rows: list[dict], patho: str) -> tuple[list[bool], list[float]]:
    """Study-level (max over frontal images) score vs IU label; negatives = studies tagged rx.normal."""
    tgt = PATHO_TARGET[patho]
    rs = [r for r in rows if r.get("ok") and r["mode"] == "model" and r.get("gt_labels") is not None
          and (tgt in r["gt_labels"] or "rx.normal" in r.get("gt_raw", []))]
    sc = _study_scores(rs, patho)
    ys, ss = [], []
    for r, v in zip(rs, sc):
        if v is not None:
            ys.append(tgt in r["gt_labels"])
            ss.append(float(v))
    return ys, ss


def costophrenic_validation(rows: list[dict]) -> dict:
    """Sensitivity/specificity of the geometric costophrenic-angle rule vs the IU effusion label."""
    rs = [r for r in rows if r.get("ok") and r["mode"] == "model" and r.get("gt_labels") is not None and r["images"]
          and ("effusion" in r["gt_labels"] or "rx.normal" in r.get("gt_raw", []))]
    y = [("effusion" in r["gt_labels"]) for r in rs]
    p = [any(f["code"].startswith("rx.costophrenic_blunting") for f in r["findings"]) for r in rs]
    tp = sum(a and b for a, b in zip(y, p)); npos = sum(y)
    tn = sum((not a) and (not b) for a, b in zip(y, p)); nneg = len(y) - npos
    sens = tp / npos if npos else float("nan")
    return {"n": len(y), "pos": npos, "sens": sens, "sens_ci": list(wilson(tp, npos)),
            "spec": tn / nneg if nneg else float("nan"), "demoted": bool(npos >= MIN_POS and sens < COSTO_SENS_MIN)}


def tune(rows: list[dict], spec: float = 0.90) -> dict:
    thresholds, metrics = {}, {}
    for patho in PATHO_TARGET:
        y, s = iu_samples(rows, patho)
        if sum(y) < MIN_POS or sum(y) == len(y):
            metrics[patho] = {"skipped": f"positivos insuficientes (n={len(y)}, pos={sum(y)})", "threshold": DEFAULT_THR}
            continue
        thr = threshold_for_specificity(y, s, spec)
        m = evaluate(y, s, thr)
        if not (m["auc_lo"] >= MIN_AUC_LO):
            m["skipped"] = f"AUC IC95% inferior {m['auc_lo']:.2f} < {MIN_AUC_LO}: limiar não confiável, mantido o padrão"
            m["threshold"] = DEFAULT_THR
        else:
            thresholds[patho] = thr
        metrics[patho] = m
    return {"version": 1, "status": "tuned-dev-iu" if thresholds else "untuned", "default": DEFAULT_THR,
            "specificity_target": spec,
            "dev_source": "iu_xray (DEV; vazamento: TorchXRayVision 'all' foi treinado em OpenI=IU). Teste primário: VinDr-CXR test (PENDENTE, credencial PhysioNet).",
            "thresholds": thresholds, "metrics": metrics, "costophrenic_rule": costophrenic_validation(rows)}


def read_vindr_labels(path: Path) -> dict[str, dict[str, bool]]:
    """VinDr-CXR test consensus CSV (image_id + one 0/1 column per finding) -> {image_id: {patho: bool}}."""
    out: dict[str, dict[str, bool]] = {}
    with Path(path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            iid = row.get("image_id") or row.get("image_name")
            if not iid:
                continue
            out[iid] = {p: str(row.get(col, "0")).strip() in ("1", "1.0", "True", "true")
                        for col, p in VINDR_MAP.items() if col in row}
    return out


def evaluate_vindr(labels: dict[str, dict[str, bool]], scores: dict[str, dict[str, float]], thresholds: dict[str, float]) -> dict:
    """Frozen thresholds (no fitting) vs consensus labels."""
    res = {}
    for patho in sorted({p for d in labels.values() for p in d}):
        ids = [i for i in labels if i in scores and patho in scores[i] and patho in labels[i]]
        y = [labels[i][patho] for i in ids]
        if sum(y) < 5 or sum(y) == len(y):
            continue
        res[patho] = evaluate(y, [scores[i][patho] for i in ids], thresholds.get(patho, DEFAULT_THR))
    return res


def _score_vindr_images(labels, image_dir: Path, limit: Optional[int]) -> dict[str, dict[str, float]]:
    import types
    from app.rx import analyze_image
    from bench.rx_bench import load_gray
    out = {}
    for n, iid in enumerate(sorted(labels)):
        if limit and n >= limit:
            break
        for ext in (".png", ".jpg", ".jpeg"):
            p = image_dir / f"{iid}{ext}"
            if p.exists():
                a = analyze_image(load_gray(p), iid, types.SimpleNamespace(BodyPartExamined="CHEST", ViewPosition="PA"), use_model=True)
                out[iid] = a.model_scores
                break
    return out


def _fmt(m: dict) -> str:
    if "auc" not in m:
        return m.get("skipped", "-")
    return (f"n={m['n']} pos={m['pos']} thr={m['threshold']:.3f} AUC={m['auc']:.3f} [{m['auc_lo']:.3f},{m['auc_hi']:.3f}] "
            f"sens={m['sens']:.2f} spec={m['spec']:.2f} PPV@prev({m['prevalence']:.2f})={m['ppv_at_prevalence']:.2f} ECE={m['ece']:.3f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench.tune_rx_thresholds")
    ap.add_argument("--source", choices=["iu", "vindr"], default="iu")
    ap.add_argument("--spec", type=float, default=0.90)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--vindr-labels", type=Path)
    ap.add_argument("--vindr-images", type=Path)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    if a.source == "iu":
        from bench.rx_bench import load_cache
        res = tune(list(load_cache("iu").values()), a.spec)
        for k, m in res["metrics"].items():
            print(f"{k}: {_fmt(m)}")
        print("costofrênico:", json.dumps(res["costophrenic_rule"]))
        if not a.dry_run:
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
            print("escrito", a.out)
        return 0
    if not (a.vindr_labels and a.vindr_images and a.vindr_labels.exists() and a.vindr_images.exists()):
        print("VinDr-CXR test não disponível (credencial PhysioNet). Passe --vindr-labels CSV e --vindr-images DIR.")
        return 2
    labels = read_vindr_labels(a.vindr_labels)
    thr = json.loads(a.out.read_text(encoding="utf-8")).get("thresholds", {}) if a.out.exists() else {}
    res = evaluate_vindr(labels, _score_vindr_images(labels, a.vindr_images, a.limit), thr)
    for k, m in res.items():
        print(f"VinDr {k}: {_fmt(m)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
