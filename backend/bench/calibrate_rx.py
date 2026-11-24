"""Calibração isotônica por patologia dos escores do TorchXRayVision no IU DEV (validação cruzada por PACIENTE).

    python -m bench.calibrate_rx [--folds 5] [--seed 0] [--spec 0.90] [--sens 0.95] [--n-boot 500]
                                 [--out bench/tuning/rx_calibration.json] [--dry-run]

Usa o cache do IU (python -m bench.rx_bench --source iu --models on). CAVEATS: (1) IU está no treino dos pesos 'all' do
TorchXRayVision -> resultados otimistas; (2) negativos = estudos rx.normal, logo a prevalência da amostra é inflada e a
probabilidade calibrada vale para essa amostra; (3) sem rótulo IU de edema/nódulo -> sem curva (nódulo: ver bench.rx_bench
--source jsrt-nodule); (4) pneumotórax tem 3 positivos -> sem curva. Nada de teste (VinDr/BRAX: pendente de credencial).
Escreve só pontos da curva + resumo de métricas; nenhum id de imagem/paciente.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from bench.rx_bench import auc_ci  # noqa: E402
from bench.tune_rx_thresholds import MIN_AUC_LO, MIN_POS, PATHO_TARGET, _study_scores, threshold_for_specificity  # noqa: E402

DEFAULT_OUT = HERE / "tuning" / "rx_calibration.json"
ECE_TARGET = 0.05


def pav(x, y) -> tuple[list[float], list[float]]:
    """Isotonic (non-decreasing) regression by pool-adjacent-violators. Returns curve points (x, y), np.interp-ready.

    Equal x are pooled first; each flat block contributes its left and right x (like sklearn's X/y_thresholds_)."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    order = np.argsort(x, kind="mergesort")
    x, y = x[order], y[order]
    ux, inv = np.unique(x, return_inverse=True)
    w = np.bincount(inv).astype(float)
    m = np.bincount(inv, weights=y) / w
    # blocks: [mean, weight, x_left, x_right]
    blocks: list[list[float]] = []
    for xi, mi, wi in zip(ux, m, w):
        blocks.append([mi, wi, xi, xi])
        while len(blocks) > 1 and blocks[-2][0] >= blocks[-1][0]:
            b = blocks.pop()
            a = blocks[-1]
            tw = a[1] + b[1]
            a[0], a[1], a[3] = (a[0] * a[1] + b[0] * b[1]) / tw, tw, b[3]
    xs: list[float] = []
    ys: list[float] = []
    for mean, _, xl, xr in blocks:
        xs.append(float(xl)); ys.append(float(mean))
        if xr != xl:
            xs.append(float(xr)); ys.append(float(mean))
    return xs, ys


def apply_curve(xs, ys, s) -> np.ndarray:
    return np.interp(np.asarray(s, float), xs, ys)


def ece10(y, p, bins: int = 10) -> float:
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), 0, 1)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    tot = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            tot += m.sum() / len(p) * abs(y[m].mean() - p[m].mean())
    return float(tot)


def brier(y, p) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def patient_of(study_id: str) -> str:
    """IU ids look like CXR3925_IM-1999: the part before '_' is the patient."""
    return str(study_id).split("_")[0]


def patient_folds(groups, k: int = 5, seed: int = 0) -> np.ndarray:
    """Fold index per sample; all samples of a patient share a fold (seeded shuffle of patients)."""
    groups = np.asarray(groups)
    pats = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(pats)
    fold_of = {p: i % k for i, p in enumerate(pats)}
    return np.array([fold_of[g] for g in groups])


def cv_predict(y, s, groups, k: int = 5, seed: int = 0) -> np.ndarray:
    """Out-of-fold calibrated probabilities (curve fitted on the other folds)."""
    y = np.asarray(y, float)
    s = np.asarray(s, float)
    folds = patient_folds(groups, k, seed)
    out = np.empty(len(y))
    for f in range(k):
        te, tr = folds == f, folds != f
        if not te.any():
            continue
        if y[tr].sum() == 0 or y[tr].sum() == tr.sum():
            out[te] = s[te]
            continue
        xs, ys = pav(s[tr], y[tr])
        out[te] = apply_curve(xs, ys, s[te])
    return out


def _boot_ci(fn, groups, n_boot: int, seed: int) -> tuple[float, float]:
    """95% percentile bootstrap resampling PATIENTS; fn(idx) -> statistic."""
    groups = np.asarray(groups)
    pats = np.unique(groups)
    members = {p: np.flatnonzero(groups == p) for p in pats}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        pick = rng.choice(pats, size=len(pats), replace=True)
        idx = np.concatenate([members[p] for p in pick])
        v = fn(idx)
        if not math.isnan(v):
            vals.append(v)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def cv_metrics(y, s, groups, k: int = 5, seed: int = 0, n_boot: int = 500) -> dict:
    y = np.asarray(y, float)
    s = np.asarray(s, float)
    p = cv_predict(y, s, groups, k, seed)
    out = {}
    for name, fn in (("ece", ece10), ("brier", brier)):
        raw, cal = fn(y, s), fn(y, p)
        out[name] = {
            "raw": raw, "raw_ci": list(_boot_ci(lambda i: fn(y[i], s[i]), groups, n_boot, seed + 1)),
            "cal": cal, "cal_ci": list(_boot_ci(lambda i: fn(y[i], p[i]), groups, n_boot, seed + 1)),
        }
    return out


def samples(rows: list[dict], patho: str) -> tuple[list[bool], list[float], list[str]]:
    """Study-level (max over images) score vs IU label; negatives = rx.normal studies; plus patient id per study."""
    tgt = PATHO_TARGET[patho]
    rs = [r for r in rows if r.get("ok") and r["mode"] == "model" and r.get("gt_labels") is not None
          and (tgt in r["gt_labels"] or "rx.normal" in r.get("gt_raw", []))]
    ys, ss, gs = [], [], []
    for r, v in zip(rs, _study_scores(rs, patho)):
        if v is not None:
            ys.append(tgt in r["gt_labels"]); ss.append(float(v)); gs.append(patient_of(r["id"]))
    return ys, ss, gs


def raw_low_for_sensitivity(y, s, sens: float = 0.95) -> float:
    """Largest raw score t (3 decimals, rounded down) with sensitivity('score >= t') >= sens on dev positives."""
    pos = np.sort(np.asarray(s, float)[np.asarray(y, bool)])
    k = int(math.floor((1 - sens) * len(pos) + 1e-9))
    return math.floor(pos[k] * 1000 + 1e-9) / 1000


def calibrate(rows: list[dict], k: int = 5, seed: int = 0, spec: float = 0.90, sens: float = 0.95,
              n_boot: int = 500) -> dict:
    curves, summary = {}, {}
    for patho in PATHO_TARGET:
        y, s, g = samples(rows, patho)
        npos = int(sum(y))
        info: dict = {"n": len(y), "pos": npos, "patients": len(set(g))}
        if npos < MIN_POS or npos == len(y):
            info["skipped"] = f"positivos insuficientes (n={len(y)}, pos={npos}); sem curva, escore cru mantido"
            summary[patho] = info
            continue
        a, lo, hi = auc_ci(y, s, n_boot=n_boot)
        info["auc"], info["auc_ci"] = a, [lo, hi]
        if not lo >= MIN_AUC_LO:
            info["skipped"] = f"AUC IC95% inferior {lo:.2f} < {MIN_AUC_LO}: sem curva"
            summary[patho] = info
            continue
        info["cv"] = cv_metrics(y, s, g, k, seed, n_boot)
        xs, ys = pav(s, np.asarray(y, float))
        raw_high = threshold_for_specificity(y, s, spec)
        raw_low = min(raw_low_for_sensitivity(y, s, sens), raw_high)
        info["raw_low"], info["raw_high"] = raw_low, raw_high
        info["p_low"] = float(apply_curve(xs, ys, raw_low))
        info["p_high"] = float(apply_curve(xs, ys, raw_high))
        info["ece_meets_target"] = bool(info["cv"]["ece"]["cal"] <= ECE_TARGET)
        summary[patho] = info
        curves[patho] = {"x": [round(v, 4) for v in xs], "y": [round(v, 4) for v in ys]}
    pathologies = {}
    for patho, c in curves.items():
        i = summary[patho]
        pathologies[patho] = {**c, "raw_low": i["raw_low"], "raw_high": i["raw_high"],
                              "p_low": round(i["p_low"], 4), "p_high": round(i["p_high"], 4),
                              "n": i["n"], "pos": i["pos"], "cv_ece_raw": round(i["cv"]["ece"]["raw"], 4),
                              "cv_ece_cal": round(i["cv"]["ece"]["cal"], 4)}
    return {"version": 1, "method": "isotonic (PAV), interpolação linear entre pontos, clip fora do intervalo",
            "dev_source": "iu_xray DEV (vazamento: TorchXRayVision 'all' treinou em OpenI=IU; negativos = só rx.normal; "
                          "prevalência inflada). Teste externo: pendente (credencial).",
            "cv": f"{k} folds por paciente, semente {seed}", "spec_high": spec, "sens_low": sens,
            "pathologies": pathologies}, summary


def _f(v) -> str:
    return "-" if v is None else f"{v:.3f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench.calibrate_rx")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--spec", type=float, default=0.90)
    ap.add_argument("--sens", type=float, default=0.95)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--summary-json", type=Path, default=None, help="métricas completas (para o log); não versionar ids")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from bench.rx_bench import load_cache
    doc, summary = calibrate(list(load_cache("iu").values()), a.folds, a.seed, a.spec, a.sens, a.n_boot)
    for patho, i in summary.items():
        if "skipped" in i:
            print(f"{patho}: n={i['n']} pos={i['pos']} SKIP {i['skipped']}")
            continue
        e, b = i["cv"]["ece"], i["cv"]["brier"]
        print(f"{patho}: n={i['n']} pos={i['pos']} pac={i['patients']} AUC={i['auc']:.3f} "
              f"ECE {e['raw']:.3f}[{e['raw_ci'][0]:.3f},{e['raw_ci'][1]:.3f}] -> {e['cal']:.3f}[{e['cal_ci'][0]:.3f},{e['cal_ci'][1]:.3f}] | "
              f"Brier {b['raw']:.3f}[{b['raw_ci'][0]:.3f},{b['raw_ci'][1]:.3f}] -> {b['cal']:.3f}[{b['cal_ci'][0]:.3f},{b['cal_ci'][1]:.3f}] | "
              f"raw L/U={_f(i['raw_low'])}/{_f(i['raw_high'])} p L/U={_f(i['p_low'])}/{_f(i['p_high'])} meta ECE<=0.05={i['ece_meets_target']}")
    if a.summary_json:
        a.summary_json.write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    if not a.dry_run:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("escrito", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
