"""Measurement ground truth from PTB-XL+ (12SL features, GE Marquette 12SL algorithm; Strodthoff et al. 2023).

Compares OUR measurements (cached by bench.ecg_bench on PTB-XL records) with the 12SL measurements:
PR, QRS duration, QT, QTc (Bazett), heart rate and ST at the J point per lead.

Units (checked against features/feature_description.csv, columns consistent_units_12sl): PR/QRS/QT/QTc in ms, HR in bpm,
ST_Amp_<lead> (= 12SL STJ, ST amplitude at the J point) in mV -> converted to microvolts (x1000) here.
Bias = mean(ours - 12SL); MAE = mean(|ours - 12SL|); CIs by bootstrap over records (bench.report, 2000 resamples).
12SL is a reference *algorithm*, not a human gold standard: differences are method disagreement, not pure error.
"""
from __future__ import annotations

import csv
import math
import os
from pathlib import Path
from typing import Optional

import numpy as np

from bench.report import bootstrap_mean_ci, fmt, fmt_ci, table

LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
# (label, unit, column in 12sl_features.csv, our gm key)
GLOBAL_MEASURES = [
    ("PR", "ms", "PR_Int_Global", "pr_ms"),
    ("QRS", "ms", "QRS_Dur_Global", "qrs_ms"),
    ("QT", "ms", "QT_Int_Global", "qt_ms"),
    ("QTc (Bazett)", "ms", "QT_IntBazett_Global", "qtc_bazett_ms"),
    ("FC", "bpm", "HR__Global", "heart_rate_bpm"),
]
MV_TO_UV = 1000.0   # 12SL ST_Amp_X is in mV; ours st_j_mv is in mV; both reported in microvolts


def features_path(root: Optional[Path] = None) -> Path:
    root = root or Path(os.environ.get("MEDLENS_DATASETS", Path(__file__).resolve().parents[2] / "data" / "datasets"))
    return root / "ptbxl_plus" / "features" / "12sl_features.csv"


def _f(x) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load_12sl(path: Optional[Path] = None) -> dict[int, dict[str, float]]:
    """ecg_id -> {column: value} for the columns used here (empty/NaN -> nan)."""
    cols = [c for _, _, c, _ in GLOBAL_MEASURES] + [f"ST_Amp_{ld}" for ld in LEADS]
    out: dict[int, dict[str, float]] = {}
    with (path or features_path()).open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            out[int(float(r["ecg_id"]))] = {c: _f(r.get(c)) for c in cols}
    return out


def ecg_id_of(rid: str) -> int:
    return int(rid.rsplit("-", 1)[-1])


def paired(results: list[dict], ref: dict[int, dict[str, float]]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """label -> (ours, 12sl) arrays over records where both exist. results = ok records of the ptbxl cache
    ({"id", "data": {"gm": {...}, "stj_mv": {lead: mV}}})."""
    acc: dict[str, tuple[list, list]] = {}
    for r in results:
        d = r["data"]
        rf = ref.get(ecg_id_of(r["id"]))
        if rf is None:
            continue
        for label, _, col, key in GLOBAL_MEASURES:
            o, x = _f((d.get("gm") or {}).get(key)), rf.get(col, float("nan"))
            if not (math.isnan(o) or math.isnan(x)):
                acc.setdefault(label, ([], []))[0].append(o)
                acc[label][1].append(x)
        stj = d.get("stj_mv") or {}
        for ld in LEADS:
            o, x = _f(stj.get(ld)), rf.get(f"ST_Amp_{ld}", float("nan"))
            if not (math.isnan(o) or math.isnan(x)):
                acc.setdefault(f"ST-J {ld}", ([], []))[0].append(o * MV_TO_UV)
                acc[f"ST-J {ld}"][1].append(x * MV_TO_UV)
    return {k: (np.asarray(a, float), np.asarray(b, float)) for k, (a, b) in acc.items()}


def error_stats(ours: np.ndarray, ref: np.ndarray) -> dict:
    """N, bias and MAE (with bootstrap CIs), mean 12SL value and Pearson r."""
    diff = ours - ref
    r = float(np.corrcoef(ours, ref)[0, 1]) if len(ours) > 2 and np.std(ours) > 0 and np.std(ref) > 0 else float("nan")
    return {"n": len(diff), "bias": bootstrap_mean_ci(diff), "mae": bootstrap_mean_ci(np.abs(diff)),
            "ref_mean": float(ref.mean()), "r": r}


def section(results: list[dict], ref: dict[int, dict[str, float]], n_total: Optional[int] = None) -> tuple[str, dict]:
    """(markdown body of "Medidas vs 12SL (PTB-XL+)", {label: stats}) ."""
    pr = paired(results, ref)
    n_total = n_total if n_total is not None else len(results)
    stats = {lab: error_stats(*v) for lab, v in pr.items()}
    rows = []
    for lab, u, _, _ in GLOBAL_MEASURES:
        if lab in stats:
            s = stats[lab]
            rows.append([lab, u, f"{s['n']} / {n_total}", fmt(s["ref_mean"], 1), fmt_ci(*s["bias"], nd=1, percent=False),
                         fmt_ci(*s["mae"], nd=1, percent=False), fmt(s["r"], 2)])
    t1 = table(rows, ["Medida", "Unid.", "N pareado / N dev", "média 12SL", "viés (nosso − 12SL) [IC95%]",
                      "MAE [IC95%]", "r de Pearson"])
    srows = []
    for ld in LEADS:
        s = stats.get(f"ST-J {ld}")
        if s:
            srows.append([ld, s["n"], fmt(s["ref_mean"], 0), fmt_ci(*s["bias"], nd=0, percent=False),
                          fmt_ci(*s["mae"], nd=0, percent=False), fmt(s["r"], 2)])
    t2 = table(srows, ["Derivação", "N pareado", "média 12SL (µV)", "viés (nosso − 12SL) µV [IC95%]", "MAE µV [IC95%]", "r"])
    body = ("Referência: algoritmo GE Marquette 12SL (PTB-XL+ 1.0.1, features/12sl_features.csv); **não é padrão-ouro humano**. "
            "Unidades: ms (PR, QRS, QT, QTc Bazett), bpm (FC), µV (ST no ponto J; 12SL STJ e nosso st_j_mv estão em mV e foram ×1000). "
            "Viés = média(nosso − 12SL); MAE = média |nosso − 12SL|; IC95% bootstrap por registro (2000 reamostras, semente fixa). "
            "Pares apenas onde ambos têm valor (PR ausente em FA/sem onda P). ECGdeli não é usado (medianas muito diferentes de 12SL e "
            "do PTB-XL, ex. QRS 160 ms vs 94 ms: critério de bordas distinto).\n\n" + t1 +
            "\n\n**ST no ponto J por derivação (µV)**\n\n" + t2)
    return body, stats
