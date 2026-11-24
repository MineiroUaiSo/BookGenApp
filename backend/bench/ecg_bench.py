"""ECG benchmark: LUDB delineation, PTB-XL diagnosis, image digitisation (litfl, wikimedia, ...).

Usage (from backend/):
    python -m bench.ecg_bench [--source ludb|ptbxl|images|all] [--limit N] [--workers K] [--force] [--report-only]
    python -m bench.ecg_bench --source litfl --litfl-split dev|test --workers 2 --force   # page-level 70/30 LITFL split

Per-record raw results are cached as JSONL in  data/bench/ecg/<source>.jsonl  (one line per record id;
re-runs only process ids that are not cached unless --force).  The report (docs/benchmarks/ecg.md) is
always recomputed from the caches, so it can be regenerated without re-running the analysis.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import multiprocessing as mp
import os
import random
import re
import signal as _signal
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from bench.report import fmt, pct, table, wilson, write_markdown  # noqa: E402

REPO = BACKEND.parent
DATA_ROOT = Path(os.environ.get("MEDLENS_DATASETS", REPO / "data" / "datasets"))
OUT_ROOT = Path(os.environ.get("MEDLENS_BENCH", REPO / "data" / "bench")) / "ecg"
REPORT_PATH = REPO / "docs" / "benchmarks" / "ecg.md"

IMAGE_SOURCES = ["litfl", "wikimedia_ecg", "ecglibrary", "ecg_image_db"]
TASK_TIMEOUT_S = 120

# Classic CSE (Common Standards for Quantitative Electrocardiography) 2-SD tolerances in ms
# (Willems JL et al., Methods Inf Med 1990;29:263-71; as used in Martinez et al., IEEE TBME 2004;51:570-81).
CSE_TOL = {"p_on": 10.2, "p_off": 12.7, "qrs_on": 6.5, "qrs_off": 11.6, "t_off": 30.6}
LUDB_EXT = {"I": "i", "II": "ii", "III": "iii", "aVR": "avr", "aVL": "avl", "aVF": "avf",
            "V1": "v1", "V2": "v2", "V3": "v3", "V4": "v4", "V5": "v5", "V6": "v6"}
BEAT_MATCH_MS = 75.0


# ---------------------------------------------------------------------------------------------
# manifest access (tolerant: works with medlens_data.Record or raw dicts)
# ---------------------------------------------------------------------------------------------
def read_manifest(source: str) -> list[dict]:
    p = DATA_ROOT / source / "manifest.jsonl"
    out = []
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def resolve(source: str, rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else DATA_ROOT / source / p


def sample_records(recs: list[dict], limit: Optional[int], seed: int = 0) -> list[dict]:
    if not limit or limit >= len(recs):
        return recs
    r = random.Random(seed)
    idx = sorted(r.sample(range(len(recs)), limit))
    return [recs[i] for i in idx]


# ---------------------------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------------------------
class _Timeout(Exception):
    pass


def _alarm(_sig, _frm):
    raise _Timeout(f"timeout after {TASK_TIMEOUT_S}s")


def _num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _gm_dict(gm) -> dict:
    return {k: _num(getattr(gm, k)) for k in ("heart_rate_bpm", "pr_ms", "qrs_ms", "qt_ms", "qtc_bazett_ms",
                                               "qrs_axis_deg", "p_duration_ms", "sokolow_lyon_mv")} | {
        "rhythm": gm.rhythm}


def _findings(an) -> list[dict]:
    return [{"code": f.code, "sev": f.severity, "conf": round(float(f.confidence), 2)} for f in an.findings]


# ---------------------------------------------------------------------------------------------
# LUDB
# ---------------------------------------------------------------------------------------------
def ludb_gold(base: str) -> tuple[dict, float]:
    """Parse LUDB annotations -> {lead: [beat dict(ms)]} ; beat = {n:(on,pk,off), p:(on,pk,off)|None, t:...}"""
    import wfdb
    fs = float(wfdb.rdheader(base).fs)
    ms = 1000.0 / fs
    gold = {}
    for lead, ext in LUDB_EXT.items():
        try:
            ann = wfdb.rdann(base, ext)
        except Exception:
            continue
        sym, smp = list(ann.symbol), list(ann.sample)
        waves = []
        for i in range(len(sym) - 2):
            if sym[i] == "(" and i + 2 < len(sym) and sym[i + 1] in ("p", "N", "t") and sym[i + 2] == ")":
                waves.append((sym[i + 1], smp[i] * ms, smp[i + 1] * ms, smp[i + 2] * ms))
        waves.sort(key=lambda w: w[2])
        ns = [w for w in waves if w[0] == "N"]
        beats = []
        for k, n in enumerate(ns):
            prev_off = ns[k - 1][3] if k > 0 else -1e9
            next_on = ns[k + 1][1] if k + 1 < len(ns) else 1e12
            p = [w for w in waves if w[0] == "p" and prev_off <= w[1] and w[3] <= n[1] + 5]
            t = [w for w in waves if w[0] == "t" and w[1] >= n[3] - 5 and w[3] <= next_on + 5]
            beats.append({"n": n[1:], "p": p[-1][1:] if p else None, "t": t[0][1:] if t else None})
        if beats:
            gold[lead] = beats
    return gold, fs


def _pct_diff(a, b):
    return None if a is None or b is None else a - b


def ludb_task(rec: dict) -> dict:
    from app.ecg.analysis import analyze_signal
    from app.ecg.ingest import load_ecg
    p = resolve("ludb", rec["path"])
    base = str(p.with_suffix("")) if p.suffix.lower() in (".hea", ".dat") else str(p)
    gold, fs = ludb_gold(base)
    if not gold:
        raise ValueError("no LUDB annotations found")
    t0 = time.time()
    sig = load_ecg(Path(base + ".hea") if Path(base + ".hea").exists() else p)
    t1 = time.time()
    an = analyze_signal(sig, rec["id"])
    t2 = time.time()
    rpk = np.array(an.r_peaks_ms)
    wv: dict[tuple, Any] = {}
    for w in an.waves:
        wv.setdefault((w.lead, w.beat_index, w.kind.value), w)
    out: dict[str, Any] = {"leads": {}, "n_beats_ours": int(len(rpk)), "t_analyze_s": round(t2 - t1, 3),
                           "t_load_s": round(t1 - t0, 3), "warnings": len(an.warnings)}
    for lead, beats in gold.items():
        rl: dict[str, Any] = {"err": defaultdict(list), "cnt": defaultdict(int)}
        region = (beats[0]["n"][0] - 100, beats[-1]["n"][2] + 100)
        used = set()
        med_p, med_qrs, med_qt = [], [], []
        for b in beats:
            pk = b["n"][1]
            if len(rpk) == 0:
                bi = None
            else:
                j = int(np.argmin(np.abs(rpk - pk)))
                bi = j if abs(rpk[j] - pk) <= BEAT_MATCH_MS else None
            rl["cnt"]["gold_qrs"] += 1
            if b["p"]:
                rl["cnt"]["gold_p"] += 1
            if b["t"]:
                rl["cnt"]["gold_t"] += 1
            if bi is None:
                continue
            used.add(bi)
            rl["cnt"]["qrs_tp"] += 1
            q = wv.get((lead, bi, "QRS"))
            if q is not None and q.offset_ms is not None:
                rl["err"]["qrs_on"].append(q.onset_ms - b["n"][0])
                rl["err"]["qrs_off"].append(q.offset_ms - b["n"][2])
            else:
                rl["cnt"]["qrs_nowave"] += 1
            pw = wv.get((lead, bi, "P"))
            if pw is not None:
                rl["cnt"]["our_p"] += 1
                if b["p"] and pw.peak_ms is not None and b["p"][0] - 30 <= pw.peak_ms <= b["p"][2] + 30:
                    rl["cnt"]["p_tp"] += 1
                    rl["err"]["p_on"].append(pw.onset_ms - b["p"][0])
                    rl["err"]["p_off"].append(pw.offset_ms - b["p"][2])
            tw = wv.get((lead, bi, "T"))
            if tw is not None:
                rl["cnt"]["our_t"] += 1
                if b["t"] and tw.peak_ms is not None and b["t"][0] - 50 <= tw.peak_ms <= b["t"][2] + 50:
                    rl["cnt"]["t_tp"] += 1
                    rl["err"]["t_off"].append(tw.offset_ms - b["t"][2])
            if b["p"]:
                med_p.append(b["n"][0] - b["p"][0])
            med_qrs.append(b["n"][2] - b["n"][0])
            if b["t"]:
                med_qt.append(b["t"][2] - b["n"][0])
        ours_in_region = [i for i in range(len(rpk)) if region[0] <= rpk[i] <= region[1]]
        rl["cnt"]["our_beats_region"] = len(ours_in_region)
        rl["cnt"]["qrs_fp"] = len([i for i in ours_in_region if i not in used])
        out["leads"][lead] = {"err": dict(rl["err"]), "cnt": dict(rl["cnt"]),
                              "gold_pr": float(np.median(med_p)) if med_p else None,
                              "gold_qrs": float(np.median(med_qrs)) if med_qrs else None,
                              "gold_qt": float(np.median(med_qt)) if med_qt else None}
    # gold global intervals (earliest onset / latest offset across leads per beat cluster)
    ev = sorted((b["n"][1], lead, b) for lead, bs in gold.items() for b in bs)
    clusters, cur = [], []
    for e in ev:
        if cur and e[0] - cur[-1][0] > 150:
            clusters.append(cur)
            cur = []
        cur.append(e)
    if cur:
        clusters.append(cur)
    g_pr, g_qrs, g_qt, g_rr = [], [], [], []
    cl_t = []
    for c in clusters:
        if len({x[1] for x in c}) < 6:
            continue
        bs = [x[2] for x in c]
        qon = min(b["n"][0] for b in bs)
        qoff = max(b["n"][2] for b in bs)
        g_qrs.append(qoff - qon)
        cl_t.append(float(np.mean([b["n"][1] for b in bs])))
        pon = [b["p"][0] for b in bs if b["p"]]
        if pon:
            g_pr.append(qon - min(pon))
        toff = [b["t"][2] for b in bs if b["t"]]
        if toff:
            g_qt.append(max(toff) - qon)
    g_hr = 60000.0 / float(np.median(np.diff(cl_t))) if len(cl_t) >= 3 else None
    out["gold_global"] = {"pr": float(np.median(g_pr)) if g_pr else None,
                          "qrs": float(np.median(g_qrs)) if g_qrs else None,
                          "qt": float(np.median(g_qt)) if g_qt else None, "hr": g_hr}
    out["ours_global"] = _gm_dict(an.global_measurements)
    out["findings"] = _findings(an)
    out["labels"] = list(rec.get("labels") or [])
    return out


# ---------------------------------------------------------------------------------------------
# PTB-XL
# ---------------------------------------------------------------------------------------------
PRED = {
    "AF": lambda c: "ecg.atrial_fibrillation" in c,
    "AV1": lambda c: "ecg.av_block_1" in c,
    "AV2": lambda c: any(x.startswith("ecg.av_block_2") for x in c),
    "AV3": lambda c: "ecg.av_block_3" in c,
    "RBBB_complete": lambda c: "ecg.rbbb" in c,
    "RBBB_incomplete": lambda c: "ecg.irbbb" in c,
    "RBBB_any": lambda c: "ecg.rbbb" in c or "ecg.irbbb" in c,
    "LBBB_complete": lambda c: "ecg.lbbb" in c,
    "LBBB_any": lambda c: "ecg.lbbb" in c or "ecg.ilbbb" in c,
    "LAFB": lambda c: "ecg.lafb" in c,
    "LPFB": lambda c: "ecg.lpfb" in c,
    "WPW": lambda c: "ecg.preexcitation" in c,
    "LVH": lambda c: "ecg.lvh" in c,
    "RVH": lambda c: "ecg.rvh" in c,
    "LAE": lambda c: "ecg.lae" in c,
    "RAE": lambda c: "ecg.rae" in c,
    "LQT": lambda c: "ecg.long_qt" in c,
    "SBRAD": lambda c: "ecg.sinus_bradycardia" in c,
    "STACH": lambda c: "ecg.sinus_tachycardia" in c,
    "SR": lambda c: "ecg.sinus_rhythm" in c,
    "MI_any": lambda c: any(x.startswith(("ecg.pathologic_q_", "ecg.st_elevation_")) for x in c),
    "MI_inferior": lambda c: bool(c & {"ecg.pathologic_q_inferior", "ecg.st_elevation_inferior"}),
    "MI_anterior": lambda c: bool(c & {"ecg.pathologic_q_anterior", "ecg.pathologic_q_anterolateral",
                                       "ecg.st_elevation_anterior", "ecg.st_elevation_anterolateral"}),
    "MI_lateral": lambda c: bool(c & {"ecg.pathologic_q_lateral", "ecg.pathologic_q_anterolateral",
                                      "ecg.st_elevation_lateral", "ecg.st_elevation_anterolateral"}),
    "STTC": lambda c: any(x.startswith(("ecg.st_depression_", "ecg.t_inversion_", "ecg.st_elevation_")) for x in c),
    "STE": lambda c: any(x.startswith("ecg.st_elevation_") for x in c),
    "STD": lambda c: any(x.startswith("ecg.st_depression_") for x in c),
    "LOWV": lambda c: bool(c & {"ecg.low_voltage", "ecg.low_voltage_precordial"}),
    "NORM": lambda c: "ecg.within_normal_limits" in c,
    "PACE": lambda c: "ecg.paced_rhythm" in c,
}
_MI = {"IMI", "ASMI", "ILMI", "AMI", "ALMI", "INJAS", "LMI", "INJAL", "IPLMI", "IPMI", "INJIN", "INJLA", "PMI",
       "INJIL", "MI"}
GOLD_SCP = {
    "AF": {"AFIB"}, "AF_AFL": {"AFIB", "AFLT"},
    "AV1": {"1AVB"}, "AV2": {"2AVB"}, "AV3": {"3AVB"},
    "RBBB_complete": {"CRBBB"}, "RBBB_incomplete": {"IRBBB"}, "RBBB_any": {"CRBBB", "IRBBB"},
    "LBBB_complete": {"CLBBB"}, "LBBB_any": {"CLBBB", "ILBBB"},
    "LAFB": {"LAFB"}, "LPFB": {"LPFB"}, "WPW": {"WPW"}, "LVH": {"LVH"}, "RVH": {"RVH"},
    "LAE": {"LAO/LAE", "LAO", "LAE"}, "RAE": {"RAO/RAE", "RAO", "RAE"}, "LQT": {"LNGQT"},
    "SBRAD": {"SBRAD"}, "STACH": {"STACH"}, "SR": {"SR"},
    "MI_any": _MI, "MI_inferior": {"IMI", "ILMI", "IPMI", "IPLMI", "INJIN", "INJIL"},
    "MI_anterior": {"ASMI", "AMI", "ALMI", "INJAS", "INJAL"}, "MI_lateral": {"LMI", "ALMI", "ILMI", "IPLMI", "INJLA"},
    "STTC": {"NDT", "NST_", "ISC_", "ISCAL", "ISCIN", "ISCIL", "ISCAS", "ISCLA", "ISCAN", "STD_", "STE_", "TAB_",
             "DIG", "EL", "STTC"},
    "STE": {"STE_"}, "STD": {"STD_"}, "LOWV": {"LVOLT"}, "NORM": {"NORM"}, "PACE": {"PACE"},
}
# AF_AFL is predicted by the AF rule or the spectral flutter rule
PRED["AF_AFL"] = lambda c: "ecg.atrial_fibrillation" in c or "ecg.atrial_flutter" in c
CLASS_DESC = {
    "AF": "atrial fibrillation (AFIB)", "AF_AFL": "AF or flutter (AFIB+AFLT)", "AV1": "1st-degree AV block (1AVB)",
    "AV2": "2nd-degree AV block (2AVB)", "AV3": "3rd-degree AV block (3AVB)",
    "RBBB_complete": "complete RBBB (CRBBB)", "RBBB_incomplete": "incomplete RBBB (IRBBB)",
    "RBBB_any": "RBBB any", "LBBB_complete": "complete LBBB (CLBBB)", "LBBB_any": "LBBB any",
    "LAFB": "left anterior fascicular block", "LPFB": "left posterior fascicular block", "WPW": "WPW",
    "LVH": "left ventricular hypertrophy", "RVH": "right ventricular hypertrophy", "LAE": "left atrial enlargement",
    "RAE": "right atrial enlargement", "LQT": "long QT (LNGQT)", "SBRAD": "sinus bradycardia", "STACH": "sinus tachycardia",
    "SR": "sinus rhythm", "MI_any": "any MI (Q waves or ST elevation)", "MI_inferior": "inferior MI (IMI etc.)",
    "MI_anterior": "anterior/anteroseptal MI", "MI_lateral": "lateral MI", "STTC": "ST/T change (any)",
    "STE": "ST elevation (STE_)", "STD": "ST depression (STD_)", "LOWV": "low voltage (LVOLT)", "NORM": "NORM",
    "PACE": "pacemaker rhythm (PACE)",
}


def parse_scp(rec: dict) -> dict[str, float]:
    ex = rec.get("extra") or {}
    v = ex.get("scp_codes")
    if isinstance(v, str):
        try:
            v = ast.literal_eval(v)
        except Exception:
            try:
                v = json.loads(v)
            except Exception:
                v = None
    if isinstance(v, dict):
        return {str(k): float(x) for k, x in v.items()}
    if isinstance(v, list):
        return {str(k): 100.0 for k in v}
    out = {}
    for lab in rec.get("labels") or []:
        tok = str(lab).split(":")[-1].split(".")[-1] if not str(lab).startswith("scp") else str(lab).split(".", 1)[-1]
        if tok:
            out[tok] = 100.0
    return out


def gold_classes(scp: dict[str, float]) -> set[str]:
    pos = {k for k, v in scp.items() if v >= 50 or v == 0}
    return {c for c, codes in GOLD_SCP.items() if pos & codes}


def ptbxl_task(rec: dict) -> dict:
    from app.ecg.analysis import analyze_signal
    from app.ecg.ingest import load_ecg
    p = resolve("ptbxl", rec["path"])
    t0 = time.time()
    sig = load_ecg(p)
    t1 = time.time()
    ex = rec.get("extra") or {}
    try:  # PTB-XL: age 300 = ">89"; sex 0 = male, 1 = female
        age = float(ex.get("age")) if ex.get("age") not in (None, "") else None
        age = None if age is not None and age > 120 else age
    except (TypeError, ValueError):
        age = None
    sex = {"0": "M", "1": "F"}.get(str(ex.get("sex")).split(".")[0])
    an = analyze_signal(sig, rec["id"], age=age, sex=sex)
    t2 = time.time()
    return {"findings": _findings(an), "gm": _gm_dict(an.global_measurements), "fs": sig.fs,
            "n_beats": len(an.r_peaks_ms), "warnings": len(an.warnings), "t_load_s": round(t1 - t0, 3),
            "t_analyze_s": round(t2 - t1, 3), "scp": parse_scp(rec),
            "axis": (rec.get("extra") or {}).get("heart_axis"),
            "age": (rec.get("extra") or {}).get("age"), "sex": (rec.get("extra") or {}).get("sex")}


# ---------------------------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------------------------
CAPTION_KW = {
    "AF": r"atrial fibrillation|\bafib\b|\ba-?fib\b",
    "AV1": r"first[- ]degree (av|atrioventricular|heart)|1st[- ]degree|prolonged pr",
    "AV2": r"second[- ]degree|mobitz|wenckebach|2nd[- ]degree",
    "AV3": r"third[- ]degree|complete heart block|complete av block|complete atrioventricular",
    "RBBB_any": r"right bundle|\brbbb\b",
    "LBBB_any": r"left bundle|\blbbb\b",
    "LAFB": r"left anterior fascicular|anterior hemiblock|\blafb\b",
    "LPFB": r"left posterior fascicular|posterior hemiblock|\blpfb\b",
    "WPW": r"wolff|\bwpw\b|pre-?excitation|delta wave",
    "LVH": r"left ventricular hypertrophy|\blvh\b",
    "RVH": r"right ventricular hypertrophy|\brvh\b",
    "LQT": r"long qt|prolonged qt|\blqts\b",
    "STACH": r"sinus tachycardia",
    "SBRAD": r"sinus bradycardia",
    "MI_any": r"infarct|\bstemi\b|\bnstemi\b|myocardial infarction",
    "STTC": r"ischemi|ischaemi|st[- ]depression|t[- ]wave inversion|st[- ]elevation|pericarditis|\bstemi\b",
}
CAPTION_UNCOVERED = r"flutter|brugada|hyperkal|hypokal|hypercalc|pericarditis|tamponade|torsades|ventricular tachycardia|" \
                    r"\bsvt\b|supraventricular|pacemaker|paced|\bpvc\b|premature|junctional|escape|long qt|hypothermia|" \
                    r"osborn|dextrocardia|pulmonary embol|digoxin|takotsubo|early repolarization"
LABEL_ALIAS = {  # label token -> class
    "atrial_fibrillation": "AF", "af": "AF", "afib": "AF", "av_block_1": "AV1", "av_block_2": "AV2",
    "av_block_2_mobitz1": "AV2", "av_block_2_mobitz2": "AV2", "av_block_3": "AV3", "rbbb": "RBBB_any",
    "irbbb": "RBBB_any", "lbbb": "LBBB_any", "ilbbb": "LBBB_any", "lafb": "LAFB", "lpfb": "LPFB",
    "preexcitation": "WPW", "wpw": "WPW", "lvh": "LVH", "rvh": "RVH", "long_qt": "LQT",
    "sinus_tachycardia": "STACH", "sinus_bradycardia": "SBRAD", "stemi": "MI_any", "mi": "MI_any",
    "infarction": "MI_any", "ischemia": "STTC", "normal": "NORM", "within_normal_limits": "NORM",
    "normal_ecg": "NORM", "normal_sinus_rhythm": "NORM",
}
_NEG_RE = re.compile(r"(\bno\b|\bnot\b|without|absence of|absent|rule[sd]? out|negative for)\W+(\w+\W+){0,3}$")


def caption_classes(rec: dict) -> tuple[set[str], bool]:
    """(classes asserted by labels/caption, caption_mentions_uncovered_entity)"""
    cls: set[str] = set()
    for lab in rec.get("labels") or []:
        tok = str(lab).lower().split(".", 1)[-1]
        if tok in LABEL_ALIAS:
            cls.add(LABEL_ALIAS[tok])
    cap = (rec.get("caption") or "").lower()
    for c, rx in CAPTION_KW.items():
        for m in re.finditer(rx, cap):
            if not _NEG_RE.search(cap[max(0, m.start() - 40):m.start()]):
                cls.add(c)
                break
    if not cls and re.search(r"normal (sinus rhythm|ecg|ekg|electrocardiogram|12[- ]lead)", cap) \
            and not re.search(r"abnormal", cap):
        cls.add("NORM")
    return cls, bool(re.search(CAPTION_UNCOVERED, cap))


def find_true_signal(rec: dict, source: str) -> Optional[Path]:
    ex = rec.get("extra") or {}
    cands = []
    for k, v in ex.items():
        if isinstance(v, str) and re.search(r"signal|wfdb|hea|dat|record|ref|ecg", k, re.I) and \
                re.search(r"\.(hea|dat)$|/[^/.]+$", v):
            cands.append(v)
        elif isinstance(v, str) and v.lower().endswith((".hea", ".dat")):
            cands.append(v)
    for v in cands:
        p = resolve(source, v)
        base = p.with_suffix("") if p.suffix.lower() in (".hea", ".dat") else p
        if Path(str(base) + ".hea").exists():
            return Path(str(base) + ".hea")
    return None


def _xcorr_best(a: np.ndarray, b: np.ndarray, max_lag: int) -> tuple[int, float]:
    """lag (samples) such that b[t+lag] ~ a[t]; plus pearson r at that lag."""
    best = (0, -2.0)
    a = a - a.mean()
    for lag in range(-max_lag, max_lag + 1, 2):
        s0, s1 = max(0, -lag), min(len(a), len(b) - lag)
        if s1 - s0 < len(a) * 0.5:
            continue
        x, y = a[s0:s1], b[s0 + lag:s1 + lag]
        sx, sy = x.std(), y.std()
        if sx < 1e-9 or sy < 1e-9:
            continue
        r = float(np.mean((x - x.mean()) * (y - y.mean())) / (sx * sy))
        if r > best[1]:
            best = (lag, r)
    return best


def compare_to_truth(dig, true, fs_cmp: float = 250.0) -> dict:
    from scipy.signal import resample_poly
    out = {}
    for lead, v in dig.leads.items():
        if lead not in true.leads:
            continue
        a = np.asarray(v, float)
        b = np.asarray(true.leads[lead], float)
        if len(a) < 50 or len(b) < 50:
            continue
        ra = resample_poly(a, int(fs_cmp), int(round(dig.fs))) if abs(dig.fs - fs_cmp) > 1e-6 else a
        rb = resample_poly(b, int(fs_cmp), int(round(true.fs))) if abs(true.fs - fs_cmp) > 1e-6 else b
        lag, r = _xcorr_best(ra, rb, int(0.75 * fs_cmp))
        s0, s1 = max(0, -lag), min(len(ra), len(rb) - lag)
        x, y = ra[s0:s1], rb[s0 + lag:s1 + lag]
        x, y = x - np.median(x), y - np.median(y)
        # least-squares gain (digitised vs truth) to expose calibration error separately from shape error
        g = float(np.dot(x, y) / max(np.dot(x, x), 1e-12))
        out[lead] = {"r": round(r, 4), "rmse_mv": round(float(np.sqrt(np.mean((x - y) ** 2))), 4),
                     "ref_std_mv": round(float(y.std()), 4), "gain": round(g, 3), "lag_ms": round(lag * 1000 / fs_cmp, 1)}
    return out


def image_task(rec: dict) -> dict:
    from app.ecg.analysis import analyze_signal
    from app.ecg.digitize import digitize_image
    from app.ecg.ingest import load_ecg, load_image_array
    src = rec["source"]
    p = resolve(src, rec["path"])
    out: dict[str, Any] = {"stage": "load"}
    img = load_image_array(p)
    out["shape"] = list(img.shape[:2])
    t0 = time.time()
    out["stage"] = "digitize"
    sig = digitize_image(img)
    t1 = time.time()
    out["t_digitize_s"] = round(t1 - t0, 3)
    out["n_leads"] = len(sig.leads)
    out["grid_conf"] = _num((sig.calibration or {}).get("grid_confidence"))
    out["px_per_mm"] = _num((sig.calibration or {}).get("px_per_mm"))
    out["quality_median"] = float(np.median(list(sig.quality.values()))) if sig.quality else None
    out["stage"] = "analyze"
    an = analyze_signal(sig, rec["id"])
    out["t_analyze_s"] = round(time.time() - t1, 3)
    out["findings"] = _findings(an)
    out["gm"] = _gm_dict(an.global_measurements)
    out["n_beats"] = len(an.r_peaks_ms)
    out["warnings"] = an.warnings[:6]
    cls, unc = caption_classes(rec)
    out["caption_classes"] = sorted(cls)
    out["caption_uncovered"] = unc
    tp = find_true_signal(rec, src)
    if tp is not None:
        out["stage"] = "truth"
        true = load_ecg(tp)
        out["lead_cmp"] = compare_to_truth(sig, true)
        tan = analyze_signal(true, rec["id"])
        out["truth_gm"] = _gm_dict(tan.global_measurements)
        out["truth_findings"] = _findings(tan)
    out["stage"] = "done"
    return out


# ---------------------------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------------------------
TASKS = {"ludb": ludb_task, "ptbxl": ptbxl_task, **{s: image_task for s in IMAGE_SOURCES}}


def _worker(args):
    source, rec = args
    t0 = time.time()
    res: dict[str, Any] = {"id": rec["id"], "source": source}
    try:
        _signal.signal(_signal.SIGALRM, _alarm)
        _signal.alarm(TASK_TIMEOUT_S)
        res["ok"] = True
        res["data"] = TASKS[source](rec)
    except BaseException as e:  # noqa: BLE001 - every record must produce a line
        res["ok"] = False
        res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        res["tb"] = traceback.format_exc(limit=4)[-600:]
        # keep the pipeline stage for images when available
    finally:
        try:
            _signal.alarm(0)
        except Exception:
            pass
    res["t_total_s"] = round(time.time() - t0, 3)
    return res


CACHE_TAG = ""   # set by --tag: separate cache file, report printed to stdout, docs/benchmarks/ecg.md untouched
SPLIT = "all"   # --split dev|test|all: PTB-XL strat_fold 1-8 = dev, 9-10 = official test folds


def ptbxl_fold_map() -> dict[str, int]:
    out = {}
    for r in read_manifest("ptbxl"):
        fo = (r.get("extra") or {}).get("strat_fold")
        if fo not in (None, ""):
            out[r["id"]] = int(float(fo))
    return out


def in_split(rid: str, split: str, folds: dict[str, int]) -> bool:
    if split == "all" or not rid.startswith("ptbxl-"):
        return True
    fo = folds.get(rid)
    return fo is not None and ((fo <= 8) if split == "dev" else (fo >= 9))


LITFL_SPLIT = "all"   # --litfl-split dev|test|all: deterministic split by LITFL page (hash of page_title/url), ~70/30


def litfl_split_of(rec: dict) -> str:
    import hashlib
    ex = rec.get("extra") or {}
    key = str(ex.get("page_title") or rec.get("url") or rec.get("group") or rec["id"])
    h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "dev" if h < 70 else "test"


RECORD_RANGE: Optional[tuple[int, int]] = None   # set by --records A-B (numeric suffix of the record id, inclusive)


def cache_path(source: str) -> Path:
    return OUT_ROOT / f"{source}{CACHE_TAG}.jsonl"


def load_cache(source: str) -> dict[str, dict]:
    p = cache_path(source)
    out = {}
    if p.exists():
        for line in p.open(encoding="utf-8"):
            try:
                r = json.loads(line)
                out[r["id"]] = r
            except Exception:
                pass
    return out


def run_source(source: str, limit: Optional[int], workers: int, force: bool) -> int:
    recs = read_manifest(source)
    recs = [r for r in recs if source != "ptbxl" or r.get("kind", "signal") != "image"]
    if source in IMAGE_SOURCES:
        recs = [r for r in recs if r.get("kind", "image") == "image"]
        for r in recs:
            r.setdefault("source", source)
    if not recs:
        print(f"[{source}] no manifest records; skipped")
        return 0
    if RECORD_RANGE:
        def _num_id(r):
            try:
                return int(str(r["id"]).rsplit("-", 1)[-1])
            except ValueError:
                return -1
        recs = [r for r in recs if RECORD_RANGE[0] <= _num_id(r) <= RECORD_RANGE[1]]
    if SPLIT != "all" and source == "ptbxl":
        _folds = ptbxl_fold_map()
        recs = [r for r in recs if in_split(r["id"], SPLIT, _folds)]
    if LITFL_SPLIT != "all" and source == "litfl":
        recs = [r for r in recs if litfl_split_of(r) == LITFL_SPLIT]
    recs = sample_records(recs, limit)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    cache = {} if force else load_cache(source)
    todo = [r for r in recs if r["id"] not in cache]
    print(f"[{source}] {len(recs)} selected, {len(recs) - len(todo)} cached, {len(todo)} to run", flush=True)
    if not todo:
        return 0
    mode = "w" if force else "a"
    done = 0
    t0 = time.time()
    with cache_path(source).open(mode, encoding="utf-8") as f:
        if workers <= 1:
            it = (_worker((source, r)) for r in todo)
            pool = None
        else:
            ctx = mp.get_context("fork")
            pool = ctx.Pool(workers, maxtasksperchild=50)
            it = pool.imap_unordered(_worker, [(source, r) for r in todo], chunksize=1)
        try:
            for res in it:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
                f.flush()
                done += 1
                if done % 25 == 0 or done == len(todo):
                    print(f"[{source}] {done}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
        finally:
            if pool:
                pool.terminate()
    return done


# ---------------------------------------------------------------------------------------------
# aggregation / report
# ---------------------------------------------------------------------------------------------
def _ms(xs) -> str:
    return f"{np.mean(xs):+.1f} ± {np.std(xs):.1f}" if len(xs) else "-"


def _q(xs, q):
    return float(np.percentile(xs, q)) if len(xs) else float("nan")


def _timing(rows: list[dict], keys=("t_load_s", "t_analyze_s")) -> str:
    tt = [r["t_total_s"] for r in rows]
    return f"median {_q(tt, 50):.2f} s, p95 {_q(tt, 95):.2f} s, max {max(tt):.1f} s per record (N={len(tt)})" if tt else "-"


def report_ludb(res: dict[str, dict]) -> tuple[str, dict]:
    ok = [r for r in res.values() if r["ok"]]
    bad = [r for r in res.values() if not r["ok"]]
    if not ok:
        return "No LUDB results.", {}
    agg = defaultdict(list)
    cnt = defaultdict(int)
    perrec_t = {}
    perrec = defaultdict(lambda: defaultdict(list))
    perlead = defaultdict(lambda: defaultdict(list))
    for r in ok:
        for lead, d in r["data"]["leads"].items():
            for k, v in d["err"].items():
                agg[k] += v
                perrec[r["id"]][k] += v
                perlead[lead][k] += v
            for k, v in d["cnt"].items():
                cnt[k] += v
    n_rec = len(ok)
    n_lead_rec = sum(len(r["data"]["leads"]) for r in ok)
    names = {"qrs_on": "QRS onset", "qrs_off": "QRS offset", "p_on": "P onset", "p_off": "P offset",
             "t_off": "T offset"}
    rows = []
    for k in ("p_on", "p_off", "qrs_on", "qrs_off", "t_off"):
        e = np.array(agg[k])
        tol = CSE_TOL[k]
        within = int(np.sum(np.abs(e) <= tol)) if len(e) else 0
        rows.append([names[k], len(e), _ms(e), fmt(float(np.median(np.abs(e))) if len(e) else None),
                     f"±{tol}", pct(within, len(e)),
                     pct(int(np.sum(np.abs(e) <= 2 * tol)), len(e))])
    t1 = table(rows, ["Fiducial", "N matched", "error ours-gold, mean ± SD (ms)", "median |err| (ms)",
                      "CSE 2SD tol", "within tol", "within 2x tol"])
    # detection
    drows = []
    qse = (cnt["qrs_tp"], cnt["gold_qrs"])
    qppv = (cnt["qrs_tp"], cnt["qrs_tp"] + cnt["qrs_fp"])
    drows.append(["QRS (beat match R ±75 ms)", pct(*qse), pct(*qppv)])
    # P: TP / gold_p ; PPV = p_tp / our_p (our P in matched beats)
    drows.append(["P wave", pct(cnt["p_tp"], cnt["gold_p"]), pct(cnt["p_tp"], cnt["our_p"])])
    drows.append(["T wave", pct(cnt["t_tp"], cnt["gold_t"]), pct(cnt["t_tp"], cnt["our_t"])])
    t2 = table(drows, ["Wave", "Sensitivity (detected / annotated)", "PPV (correct / ours, matched beats)"])
    # global intervals
    grows = []
    for key, lab, gk in (("pr_ms", "PR", "pr"), ("qrs_ms", "QRS", "qrs"), ("qt_ms", "QT", "qt"),
                         ("heart_rate_bpm", "HR (bpm)", "hr")):
        d = [(r["data"]["ours_global"].get(key), r["data"]["gold_global"].get(gk)) for r in ok]
        d = [(a, b) for a, b in d if a is not None and b is not None]
        if not d:
            grows.append([lab, 0, "-", "-", "-", "-"])
            continue
        a, b = np.array(d).T
        e = a - b
        tolr = {"pr": 20, "qrs": 20, "qt": 30, "hr": 5}[gk]
        corr = float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 and a.std() > 0 and b.std() > 0 else float("nan")
        grows.append([lab, len(d), _ms(e), fmt(float(np.median(np.abs(e)))),
                      pct(int(np.sum(np.abs(e) <= tolr)), len(d)) + f" (|err|<={tolr})", fmt(corr, 2)])
    n_med = len(ok)
    t3 = table(grows, ["Global interval", "N records", "error ours-gold mean ± SD", "median |err|",
                       "within tolerance", "Pearson r"])
    # per-lead
    lrows = []
    for lead in LUDB_EXT:
        if lead not in perlead:
            continue
        pl = perlead[lead]
        lrows.append([lead] + [(_ms(pl[k]) if pl[k] else "-") for k in ("p_on", "p_off", "qrs_on", "qrs_off", "t_off")])
    t4 = table(lrows, ["Lead", "P on", "P off", "QRS on", "QRS off", "T off"])
    # worst records
    def mae(rid, k):
        v = perrec[rid][k]
        return float(np.mean(np.abs(v))) if len(v) >= 5 else -1
    worst = []
    for k in ("qrs_on", "qrs_off", "p_on", "t_off"):
        top = sorted(perrec, key=lambda i: -mae(i, k))[:5]
        worst.append([names[k], ", ".join(f"{i} ({mae(i, k):.0f} ms)" for i in top)])
    lowdet = sorted(ok, key=lambda r: sum(d["cnt"].get("qrs_tp", 0) for d in r["data"]["leads"].values()) /
                    max(1, sum(d["cnt"].get("gold_qrs", 0) for d in r["data"]["leads"].values())))[:5]
    worst.append(["lowest QRS detection", ", ".join(r["id"] for r in lowdet)])
    t5 = table(worst, ["Criterion", "Worst record ids (mean |err|)"])
    # diagnosis agreement with LUDB header labels (cardiologist rhythm/axis/etc. statements)
    lab_rows = []
    cls_pos = defaultdict(set)
    for r in ok:
        for lab in r["data"].get("labels", []):
            c = LABEL_ALIAS.get(str(lab).lower().split(".", 1)[-1])
            if c and c in PRED:
                cls_pos[c].add(r["id"])
    for c, ids in sorted(cls_pos.items(), key=lambda kv: -len(kv[1])):
        tp = fp = fn = tn = 0
        miss = []
        for r in ok:
            codes = {f["code"] for f in r["data"]["findings"]}
            g, pr = r["id"] in ids, bool(PRED[c](codes))
            tp += g and pr
            fn += g and not pr
            fp += (not g) and pr
            tn += (not g) and not pr
            if g and not pr:
                miss.append(r["id"])
        if len(ids) >= 2:
            lab_rows.append([c, len(ids), _ci(tp, tp + fn), _ci(tn, tn + fp), _ci(tp, tp + fp), ", ".join(miss[:4]) or "-"])
    lab_tbl = ("\n\n### Diagnosis agreement with LUDB header statements (small N, indicative only)\n\nLUDB header statements are free-text from the cardiologist (e.g. 'left ventricular hypertrophy' is attached to >50% of records, mostly without voltage criteria; median Sokolow-Lyon here is ~1.3 mV), so low sensitivity for LVH/LAFB mostly reflects label definition, not necessarily detector error.\n\n" +
               table(lab_rows, ["Class", "N pos", "Sens % [CI]", "Spec % [CI]", "PPV % [CI]", "Missed ids"])) if lab_rows else ""
    body = (f"{n_rec} records analysed ({len(bad)} failed), {n_lead_rec} record-leads; annotated beats {cnt['gold_qrs']}, "
            f"P waves {cnt['gold_p']}, T waves {cnt['gold_t']}.  Timing: {_timing(ok)}.\n\n"
            "### Fiducial-point error vs cardiologist annotation (per lead, per matched beat)\n\n" + t1 +
            "\n\nTolerances: CSE 2-SD values (P on 10.2, P off 12.7, QRS on 6.5, QRS off 11.6, T off 30.6 ms) "
            "— Willems et al., _Methods Inf Med_ 1990;29:263; Martinez et al., _IEEE TBME_ 2004;51:570. "
            "Note: LUDB annotators place the QRS 'N' on the dominant deflection; error sign = ours - gold.\n\n"
            "### Wave detection\n\n" + t2 +
            "\n\nP/T counted detected when our peak lies within the annotated wave ±30 ms (P) / ±50 ms (T). "
            "PPV counts our waves in beats matched to an annotated beat.\n\n"
            "### Global intervals (our median beat vs annotation: earliest onset / latest offset across leads, median over beats)\n\n"
            + t3 + "\n\n### Per-lead mean ± SD error (ms)\n\n" + t4 + "\n\n### Worst examples\n\n" + t5 + lab_tbl)
    if bad:
        c = Counter(r["error"].split(":")[0] for r in bad)
        body += f"\n\nFailures: {dict(c)}; ids: {', '.join(r['id'] for r in bad[:10])}"
    head = {
        "N": n_rec,
        "qrs_on_within": (int(np.sum(np.abs(agg['qrs_on']) <= CSE_TOL['qrs_on'])), len(agg['qrs_on'])),
        "qrs_off_within": (int(np.sum(np.abs(agg['qrs_off']) <= CSE_TOL['qrs_off'])), len(agg['qrs_off'])),
        "p_on_within": (int(np.sum(np.abs(agg['p_on']) <= CSE_TOL['p_on'])), len(agg['p_on'])),
        "t_off_within": (int(np.sum(np.abs(agg['t_off']) <= CSE_TOL['t_off'])), len(agg['t_off'])),
        "qrs_se": qse, "p_se": (cnt["p_tp"], cnt["gold_p"]), "t_se": (cnt["t_tp"], cnt["gold_t"]),
        "failed": len(bad), "t": _q([r["t_total_s"] for r in ok], 50),
    }
    return body, head


def _prf(tp, fp, fn, tn):
    se = tp / (tp + fn) if tp + fn else float("nan")
    sp = tn / (tn + fp) if tn + fp else float("nan")
    ppv = tp / (tp + fp) if tp + fp else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float("nan")
    return se, sp, ppv, f1


def _ci(k, n):
    if n <= 0:
        return "-"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.0f} [{max(0, 100 * lo):.0f}-{100 * hi:.0f}]"


def axis_class(a):
    if a is None:
        return None
    return "left" if a < -30 else ("right" if a > 90 else "normal")


def ptbxl_prevalence() -> dict[str, float]:
    """Class prevalence in the FULL PTB-XL database (ptbxl_database.csv), used to correct PPV for the
    class-enriched subset the collector selected. Empty dict when the csv is not available."""
    import csv
    p = DATA_ROOT / "ptbxl" / "ptbxl_database.csv"
    if not p.exists():
        return {}
    cnt: Counter = Counter()
    n = 0
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            n += 1
            cnt.update(gold_classes(parse_scp({"extra": {"scp_codes": r.get("scp_codes", "")}})))
    return {c: v / n for c, v in cnt.items()} if n else {}


def report_ptbxl(res: dict[str, dict]) -> tuple[str, dict]:
    ok = [r for r in res.values() if r["ok"]]
    bad = [r for r in res.values() if not r["ok"]]
    if not ok:
        return "No PTB-XL results.", {}
    recs = []
    for r in ok:
        d = r["data"]
        recs.append({"id": r["id"], "gold": gold_classes(d["scp"]), "scp": d["scp"], "codes": {f["code"] for f in d["findings"]},
                     "sev": {f["code"]: f["sev"] for f in d["findings"]}, "gm": d["gm"], "axis": d.get("axis")})
    N = len(recs)
    rows, worst_rows, conf_rows = [], [], []
    head = {}
    prev = ptbxl_prevalence()
    for c in PRED:
        tp = fp = fn = tn = 0
        fps, fns = [], []
        fp_gold, fn_pred = Counter(), Counter()
        for r in recs:
            g, p = c in r["gold"], bool(PRED[c](r["codes"]))
            if g and p:
                tp += 1
            elif g:
                fn += 1
                fns.append(r["id"])
                for k in r["codes"]:
                    fn_pred[k.replace("ecg.", "")] += 1
            elif p:
                fp += 1
                fps.append(r["id"])
                for k, v in r["scp"].items():
                    if v >= 50 or v == 0:
                        fp_gold[k] += 1
            else:
                tn += 1
        npos = tp + fn
        if npos == 0 and tp + fp == 0:
            continue
        se, sp, ppv, f1 = _prf(tp, fp, fn, tn)
        pv = prev.get(c)
        adj = "-"
        if pv and se == se and sp == sp and (se * pv + (1 - sp) * (1 - pv)) > 0:
            adj = f"{100 * se * pv / (se * pv + (1 - sp) * (1 - pv)):.0f} (prev {100 * pv:.1f}%)"
        rows.append([c, CLASS_DESC[c], npos, tp, fp, _ci(tp, npos), _ci(tn, tn + fp), _ci(tp, tp + fp),
                     adj, fmt(f1, 2)])
        head[c] = (se, sp, ppv, f1, npos)
        if npos + fp:
            top_fp = ", ".join(f"{k}:{v}" for k, v in fp_gold.most_common(4)) or "-"
            top_fn = ", ".join(f"{k}:{v}" for k, v in fn_pred.most_common(4)) or "-"
            conf_rows.append([c, f"FP gold labels -> {top_fp}", f"FN our findings -> {top_fn}"])
            worst_rows.append([c, ", ".join(fps[:5]) or "-", ", ".join(fns[:5]) or "-"])
    t1 = table(rows, ["Class", "Meaning", "N pos", "TP", "FP", "Sens % [95% CI]", "Spec % [95% CI]",
                      "PPV % [95% CI] (this sample)", "PPV % at full-PTB-XL prevalence", "F1"])
    # NORM agreement
    norm = [r for r in recs if "NORM" in r["gold"]]
    abn = [r for r in recs if "NORM" not in r["gold"]]
    flag_any = lambda r: any(s != "normal" for s in r["sev"].values())
    flag_abn = lambda r: any(s in ("abnormal", "critical") for s in r["sev"].values())
    nrows = [
        ["gold NORM -> we say within normal limits", pct(sum(1 for r in norm if "ecg.within_normal_limits" in r["codes"]), len(norm), True)],
        ["gold NORM -> we raise >=1 abnormal/critical finding", pct(sum(1 for r in norm if flag_abn(r)), len(norm), True)],
        ["gold NORM -> we raise any non-normal finding (incl. borderline)", pct(sum(1 for r in norm if flag_any(r)), len(norm), True)],
        ["gold non-NORM -> we raise >=1 abnormal/critical finding", pct(sum(1 for r in abn if flag_abn(r)), len(abn), True)],
        ["gold non-NORM -> we say within normal limits (missed)", pct(sum(1 for r in abn if "ecg.within_normal_limits" in r["codes"]), len(abn), True)],
    ]
    t2 = table(nrows, ["Normal vs abnormal screening", "Rate"])
    # HR checks
    hrows = []
    for cls, lo, hi in (("SR", 60, 100), ("STACH", 100, 999), ("SBRAD", 0, 60)):
        v = [r["gm"]["heart_rate_bpm"] for r in recs if cls in r["gold"] and r["gm"]["heart_rate_bpm"] is not None]
        if v:
            hrows.append([cls, len(v), f"{_q(v, 50):.0f} ({_q(v, 10):.0f}-{_q(v, 90):.0f})",
                          pct(sum(1 for x in v if (lo <= x <= hi) or (cls == "STACH" and x > 100) or (cls == "SBRAD" and x < 60)), len(v)) +
                          f" in {lo}-{hi if hi < 999 else '+'} bpm"])
    t3 = table(hrows, ["SCP rhythm", "N", "our HR median (P10-P90)", "HR consistent with label"]) if hrows else "n/a"
    # axis
    cm = defaultdict(Counter)
    amap = {"MID": "normal", "LAD": "left", "ALAD": "left", "AXL": "left", "RAD": "right", "ARAD": "right", "AXR": "right"}
    for r in recs:
        g = amap.get(str(r["axis"]).upper()) if r["axis"] else None
        o = axis_class(r["gm"]["qrs_axis_deg"])
        if g and o:
            cm[g][o] += 1
    if cm:
        arows = [[g, sum(cm[g].values())] + [cm[g][o] for o in ("left", "normal", "right")] for g in ("left", "normal", "right") if g in cm]
        ok_ax = sum(cm[g][g] for g in cm)
        tot_ax = sum(sum(cm[g].values()) for g in cm)
        t4 = table(arows, ["metadata axis (rows)", "N", "ours: left (<-30)", "ours: normal", "ours: right (>90)"]) + \
            f"\n\nAxis category agreement: {pct(ok_ax, tot_ax, True)} (metadata `heart_axis`: LAD/ALAD/AXL = left, RAD/ARAD/AXR = right, MID = normal; SAG excluded)."
    else:
        t4 = "No `heart_axis` metadata found in manifest `extra` (or no axis computed)."
    cmt = table(worst_rows, ["Class", "False-positive ids (first 5)", "False-negative ids (first 5)"])
    cmt2 = table(conf_rows, ["Class", "What the FPs really are (gold SCP codes)", "What we reported for FNs"])
    nsr = Counter(r["scp"].get("NORM", None) is not None for r in recs)
    body = (f"{N} records analysed ({len(bad)} failed). Timing: {_timing(ok)}. Ground truth = SCP statements in PTB-XL "
            "(a code counts as positive when likelihood >= 50 or 0 for non-diagnostic statements; all other records are "
            "negatives, so **specificity/PPV are lower bounds because absent statements are not proof of absence** and "
            "labels are known to be noisy). The collector's PTB-XL subset is **class-enriched** (not the natural prevalence), so "
            "sample PPV is not prevalence-valid: the extra column re-computes PPV from sensitivity/specificity at the natural prevalence "
            "in the full ptbxl_database.csv (an approximation). Rare classes have wide CIs.\n\n"
            "### Per-class performance\n\n" + t1 +
            "\n\n### Normal-vs-abnormal screening\n\n" + t2 + "\n\n### Heart rate vs rhythm statements\n\n" + t3 +
            "\n\n### QRS axis vs metadata\n\n" + t4 + "\n\n### Confusion highlights\n\n" + cmt2 +
            "\n\n### Example ids for debugging\n\n" + cmt)
    if bad:
        c = Counter(r["error"].split(":")[0] for r in bad)
        body += f"\n\nFailures: {dict(c)}; ids: {', '.join(r['id'] for r in bad[:10])}"
    head["_N"] = N
    head["_norm"] = (sum(1 for r in norm if "ecg.within_normal_limits" in r["codes"]), len(norm))
    head["_norm_abn"] = (sum(1 for r in norm if flag_abn(r)), len(norm))
    head["_abn_abn"] = (sum(1 for r in abn if flag_abn(r)), len(abn))
    head["_failed"] = len(bad)
    head["_t"] = _q([r["t_total_s"] for r in ok], 50)
    return body, head


def report_images(allres: dict[str, dict[str, dict]]) -> tuple[str, dict]:
    sections = []
    summary = {}
    rows = []
    for src, res in allres.items():
        if not res:
            continue
        rs = list(res.values())
        n = len(rs)
        exc = [r for r in rs if not r["ok"]]
        oks = [r for r in rs if r["ok"]]
        lowgrid = [r for r in oks if (r["data"].get("grid_conf") or 0) < 0.3]
        few = [r for r in oks if r["data"].get("n_beats", 0) < 2]
        okfull = [r for r in oks if r not in lowgrid and r not in few]
        hr_ok = [r for r in oks if r["data"]["gm"].get("heart_rate_bpm") and 30 <= r["data"]["gm"]["heart_rate_bpm"] <= 250]
        nleads = [r["data"]["n_leads"] for r in oks]
        # failure stages
        stages = Counter(re.sub(r"[^A-Za-z]+", "_", r["error"].split(":")[0]) for r in exc)
        rows.append([src, n, pct(len(exc), n), pct(len(lowgrid), len(oks)) if oks else "-", pct(len(few), len(oks)) if oks else "-",
                     pct(len(okfull), n), f"{np.median(nleads):.0f}" if nleads else "-", pct(len(hr_ok), len(oks)) if oks else "-",
                     _timing(rs) if rs else "-"])
        summary[src] = {"n": n, "exc": len(exc), "usable": len(okfull)}
        # caption agreement
        cap = [r for r in oks if r["data"].get("caption_classes")]
        sec = []
        if cap:
            per = defaultdict(lambda: [0, 0, 0])  # class -> [n in caption, recovered, our extra]
            fpc = Counter()
            for r in cap:
                codes = {f["code"] for f in r["data"]["findings"]}
                cl = set(r["data"]["caption_classes"])
                for c in PRED:
                    if c in ("AF_AFL",):
                        continue
                    pr = bool(PRED[c](codes))
                    if c in cl:
                        per[c][0] += 1
                        per[c][1] += pr
                    elif pr and c in CAPTION_KW or (pr and c == "NORM"):
                        fpc[c] += 1
            prow = [[c, v[0], pct(v[1], v[0]), fpc[c]] for c, v in sorted(per.items(), key=lambda kv: -kv[1][0])]
            anyhit = sum(1 for r in cap if any(PRED[c]({f['code'] for f in r['data']['findings']}) for c in r["data"]["caption_classes"] if c in PRED))
            sec.append(f"**Agreement with caption** ({len(cap)} images whose caption/labels assert >=1 class we can detect; "
                       f"weak evidence: captions are incomplete and non-exhaustive, so 'extra' findings are not necessarily errors). "
                       f"Any asserted class recovered: {pct(anyhit, len(cap), True)}.\n\n" +
                       table(prow, ["Caption class", "N captions", "Recovered by our findings", "Our findings of this class on captions that don't mention it"]))
        unc = sum(1 for r in oks if r["data"].get("caption_uncovered"))
        if unc:
            sec.append(f"{unc} of {len(oks)} captions mention conditions our rules cannot detect (flutter, Brugada, hyperkalaemia, paced rhythm, VT...).")
        # truth comparison
        tr = [r for r in oks if r["data"].get("lead_cmp")]
        if tr:
            rr = [v["r"] for r in tr for v in r["data"]["lead_cmp"].values()]
            rm = [v["rmse_mv"] / max(v["ref_std_mv"], 1e-3) for r in tr for v in r["data"]["lead_cmp"].values()]
            gains = [v["gain"] for r in tr for v in r["data"]["lead_cmp"].values()]
            lagabs = [abs(v["lag_ms"]) for r in tr for v in r["data"]["lead_cmp"].values()]
            rec_rows = []
            for k, lab, tol in (("heart_rate_bpm", "HR (bpm)", 5), ("pr_ms", "PR (ms)", 20), ("qrs_ms", "QRS (ms)", 20),
                                ("qt_ms", "QT (ms)", 40), ("qrs_axis_deg", "QRS axis (deg)", 30)):
                d = [(r["data"]["gm"].get(k), r["data"]["truth_gm"].get(k)) for r in tr]
                d = [(a, b) for a, b in d if a is not None and b is not None]
                if d:
                    e = np.array([a - b for a, b in d])
                    rec_rows.append([lab, len(d), _ms(e), fmt(float(np.median(np.abs(e)))), pct(int(np.sum(np.abs(e) <= tol)), len(d)) + f" (<= {tol})"])
            agree = [len({f["code"] for f in r["data"]["findings"]} & {f["code"] for f in r["data"]["truth_findings"]}) /
                     max(1, len({f["code"] for f in r["data"]["findings"]} | {f["code"] for f in r["data"]["truth_findings"]})) for r in tr]
            worst = sorted(tr, key=lambda r: np.mean([v["r"] for v in r["data"]["lead_cmp"].values()]))[:6]
            sec.append(f"**Paired true signal** ({len(tr)} images, {len(rr)} leads): lead correlation r median {np.median(rr):.3f} "
                       f"(P10 {_q(rr, 10):.3f}), r>=0.9 in {pct(int(np.sum(np.array(rr) >= 0.9)), len(rr))}; RMSE/ref-SD median {np.median(rm):.2f}; "
                       f"least-squares gain digitised->true median {np.median(gains):.2f} (1.00 = calibrated); |alignment lag| median {np.median(lagabs):.0f} ms.  "
                       f"Findings Jaccard (image vs true signal) mean {np.mean(agree):.2f}.\n\n" +
                       table(rec_rows, ["Measurement", "N", "image - truth mean ± SD", "median |diff|", "within tolerance"]) +
                       "\n\nWorst correlation ids: " + ", ".join(f"{r['id']} (r={np.mean([v['r'] for v in r['data']['lead_cmp'].values()]):.2f})" for r in worst))
            summary[src]["pair_r"] = float(np.median(rr))
            summary[src]["pair_n"] = len(tr)
        fail_ids = [r["id"] for r in exc][:8]
        low_ids = [r["id"] for r in lowgrid][:8]
        few_ids = [r["id"] for r in few][:8]
        msgs = Counter(r["error"][:110] for r in exc).most_common(4)
        sec.append(f"Failure examples: exceptions {fail_ids or '-'}; low grid confidence (<0.3) {low_ids or '-'}; <2 beats detected {few_ids or '-'}. "
                   + ("Top errors: " + "; ".join(f"`{m}` x{c}" for m, c in msgs) if msgs else ""))
        sections.append((src, "\n\n".join(sec)))
    t0 = table(rows, ["Source", "N", "Exceptions", "Grid conf < 0.3", "< 2 beats found", "Usable (no failure flag)", "Median leads", "HR plausible (30-250)", "Timing"])
    body = "Failure flags are heuristic proxies (the true failure rate needs a ground-truth comparison, available only for paired sources).\n\n" + t0
    for s, b in sections:
        body += f"\n\n### {s}\n\n{b}"
    return body, summary


def build_report() -> Path:
    sections = []
    summ = []
    allr = {s: load_cache(s) for s in ["ludb", "ptbxl", *IMAGE_SOURCES]}
    for s in list(allr):  # only records of the current manifest (caches may hold ids from older/other selections)
        ids = {r["id"] for r in read_manifest(s)}
        if ids:
            allr[s] = {k: v for k, v in allr[s].items() if k in ids}
    missing = [s for s in ["ludb", "ptbxl", *IMAGE_SOURCES] if not allr[s]]
    if SPLIT != "all":
        _folds = ptbxl_fold_map()
        allr["ptbxl"] = {k: v for k, v in allr["ptbxl"].items() if in_split(k, SPLIT, _folds)}
    if allr["ludb"]:
        body, h = report_ludb(allr["ludb"])
        sections.append(("LUDB: wave delineation vs cardiologist annotations", body))
        if h:
            summ.append(["Delineation: QRS on/off within CSE tol", f"{100 * h['qrs_on_within'][0] / max(1, h['qrs_on_within'][1]):.0f}% / {100 * h['qrs_off_within'][0] / max(1, h['qrs_off_within'][1]):.0f}%", f"LUDB, {h['N']} records"])
            summ.append(["Delineation: P onset / T offset within CSE tol", f"{100 * h['p_on_within'][0] / max(1, h['p_on_within'][1]):.0f}% / {100 * h['t_off_within'][0] / max(1, h['t_off_within'][1]):.0f}%", f"LUDB, {h['N']} records"])
            summ.append(["Detection sensitivity QRS / P / T", f"{100 * h['qrs_se'][0] / max(1, h['qrs_se'][1]):.0f}% / {100 * h['p_se'][0] / max(1, h['p_se'][1]):.0f}% / {100 * h['t_se'][0] / max(1, h['t_se'][1]):.0f}%", f"LUDB, {h['qrs_se'][1]} beats"])
    if allr["ptbxl"]:
        body, h = report_ptbxl(allr["ptbxl"])
        sections.append(("PTB-XL: diagnostic statements", body))
        if h:
            for c in ("AF", "AV1", "RBBB_complete", "LBBB_complete", "LVH", "MI_any", "STACH", "SBRAD"):
                if c in h and h[c][4] > 0:
                    se, sp, ppv, f1, npos = h[c]
                    summ.append([f"Diagnosis {c}: sens / spec / PPV", f"{100 * se:.0f}% / {100 * sp:.0f}% / {fmt(100 * ppv, 0) if ppv == ppv else '-'}%", f"PTB-XL, {h['_N']} recs ({npos} pos)"])
            summ.append(["NORM -> within normal limits; abnormal flagged", f"{pct(*h['_norm'])}; {pct(*h['_abn_abn'])}", f"PTB-XL, {h['_N']} records"])
    imgs = {s: allr[s] for s in IMAGE_SOURCES if allr[s]}
    if imgs:
        body, sm = report_images(imgs)
        sections.append(("Images: digitisation + analysis", body))
        for s, v in sm.items():
            summ.append([f"Image pipeline usable ({s})", f"{100 * v['usable'] / max(1, v['n']):.0f}% (exceptions {v['exc']})", f"N={v['n']}"])
            if "pair_r" in v:
                summ.append([f"Digitised vs true signal r ({s})", f"median {v['pair_r']:.3f}", f"{v['pair_n']} paired images"])
    if not sections:
        sections.append(("No data", "No benchmark results yet: datasets missing in data/datasets."))
    head = ("## Summary\n\n" + (table(summ, ["Capability / metric", "Result", "Dataset, N"]) if summ else "_none_") +
            "\n\n**Caveats.** Not a medical-device validation. LUDB = 200 healthy-to-pathological 10 s records from one centre; PTB-XL labels "
            "are machine+human SCP statements with noise; absent statement != confirmed negative; image-caption agreement is weak evidence. "
            "Results are for the current rules/thresholds; re-run `python -m bench.ecg_bench` after changes.")
    if missing:
        head += ("\n\n**Sources with no results in this run** (manifest missing/empty or dataset not downloadable): "
                 + ", ".join(missing) + ".")
    return _write(head, sections)


def _write(head: str, sections) -> Path:
    p = write_markdown(REPORT_PATH, "ECG benchmark results", [(h, b) for h, b in sections])
    txt = p.read_text(encoding="utf-8")
    first = txt.index("\n## ")
    p.write_text(txt[:first] + "\n\n" + head + "\n" + txt[first:], encoding="utf-8")
    return p


# ---------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="all", choices=["ludb", "ptbxl", "images", "all", *IMAGE_SOURCES])
    ap.add_argument("--limit", type=int, default=None, help="max records per source (seeded random sample)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--force", action="store_true", help="ignore the cache and recompute")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"],
                    help="PTB-XL split by strat_fold: dev = folds 1-8, test = folds 9-10 (official test folds)")
    ap.add_argument("--records", default=None, help="restrict to numeric id range A-B (inclusive), e.g. 1-160 (LUDB dev) / 161-200 (test)")
    ap.add_argument("--tag", default="", help="cache-file suffix; with --tag only the LUDB table is printed and docs are not rewritten")
    ap.add_argument("--litfl-split", default="all", choices=["all", "dev", "test"],
                    help="LITFL images: deterministic page-level split (dev ~70%%, test ~30%%); prints the image report to stdout "
                         "and leaves docs/benchmarks/ecg.md untouched")
    a = ap.parse_args(argv)
    global CACHE_TAG, RECORD_RANGE, SPLIT, LITFL_SPLIT
    SPLIT = a.split
    LITFL_SPLIT = a.litfl_split
    if LITFL_SPLIT != "all" and not a.tag:
        a.tag = f"_split_{LITFL_SPLIT}"
    if a.records:
        lo, hi = a.records.split("-")
        RECORD_RANGE = (int(lo), int(hi))
    CACHE_TAG = a.tag
    srcs = {"all": ["ludb", "ptbxl", *IMAGE_SOURCES], "images": IMAGE_SOURCES}.get(a.source, [a.source])
    if not a.report_only:
        for s in srcs:
            run_source(s, a.limit, a.workers, a.force)
    if a.litfl_split != "all":
        res = {k: v for k, v in load_cache("litfl").items() if k in {r["id"] for r in read_manifest("litfl") if litfl_split_of(r) == a.litfl_split}}
        print(report_images({"litfl": res})[0])
        return 0
    if a.tag:
        body, _ = report_ludb(load_cache("ludb")) if "ludb" in srcs else ("", {})
        print(body.split("### Per-lead")[0])
        return 0
    p = build_report()
    print(f"report: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
