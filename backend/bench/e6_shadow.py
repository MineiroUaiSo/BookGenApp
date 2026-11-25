"""E6 shadow-mode report (bench only, NOT wired into app/): Ribeiro 2020 classifier vs MedLens rules on PTB-XL DEV.

Inputs : MEDLENS_BENCH/e6/probs_<tag>.npz (bench/e6_infer.py) and the rules cache MEDLENS_BENCH/ecg/ptbxl<RULES_TAG>.jsonl
         (bench/ecg_bench.py --source ptbxl --split dev --set large). Only PTB-XL folds 1-8 (DEV); folds 9-10 never read.
Output : markdown on stdout (and --out FILE). Metrics per label: AUC, sens at 90% spec, sens/spec/PPV at the paper
         threshold, with bootstrap 95% CI; rules sens/spec/PPV on the same records; Cohen kappa model x rules, model x gold,
         rules x gold; complementarity (gold positive missed by rules but flagged by the model).
Usage (backend venv, from backend/): python -m bench.e6_shadow --tag s1 [--rules-tag E6base] [--out ../docs/benchmarks/e6_shadow.md]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from bench import ecg_bench  # noqa: E402

BENCH = Path(os.environ.get("MEDLENS_BENCH", BACKEND.parent / "data" / "bench"))
CLASSES = ["1dAVb", "RBBB", "LBBB", "SB", "AF", "ST"]
# paper thresholds (max-F1 on the CODE validation set): automatic-ecg-diagnosis/generate_figures_and_tables.py, line 120
PAPER_THR = dict(zip(CLASSES, [0.124, 0.07, 0.05, 0.278, 0.390, 0.174]))
# model label -> (MedLens/PTB-XL class used as gold AND as rules prediction)
MAP = {"1dAVb": "AV1", "RBBB": "RBBB_complete", "LBBB": "LBBB_complete", "SB": "SBRAD", "AF": "AF", "ST": "STACH"}
EXTRA = {"RBBB": "RBBB_any", "LBBB": "LBBB_any", "AF": "AF_AFL"}   # sensitivity analyses (gold variants)
N_BOOT = 1000


def auc(y: np.ndarray, s: np.ndarray) -> float:
    """Mann-Whitney AUC with average ranks for ties."""
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ss = s[order]
    ranks = np.empty(len(s))
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i: j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def sens_at_spec(y: np.ndarray, s: np.ndarray, spec: float = 0.90) -> float:
    neg = s[y == 0]
    if len(neg) == 0 or y.sum() == 0:
        return float("nan")
    thr = np.quantile(neg, spec)
    return float((s[y == 1] > thr).mean())


def counts(y: np.ndarray, p: np.ndarray) -> tuple[int, int, int, int]:
    return int((y & p).sum()), int((~y & p).sum()), int((y & ~p).sum()), int((~y & ~p).sum())


def prf(tp: int, fp: int, fn: int, tn: int) -> tuple[float, float, float]:
    se = tp / (tp + fn) if tp + fn else float("nan")
    sp = tn / (tn + fp) if tn + fp else float("nan")
    ppv = tp / (tp + fp) if tp + fp else float("nan")
    return se, sp, ppv


def kappa(a: np.ndarray, b: np.ndarray) -> float:
    n = len(a)
    po = float((a == b).mean())
    pe = float(a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean()))
    return float((po - pe) / (1 - pe)) if pe < 1 else float("nan")


def ci(vals: list[float]) -> tuple[float, float]:
    v = np.array([x for x in vals if x == x])
    return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if len(v) else (float("nan"), float("nan"))


def f(x: float, pct: bool = True) -> str:
    return "-" if x != x else (f"{100 * x:.1f}" if pct else f"{x:.3f}")


def fci(x: float, lo_hi: tuple[float, float], pct: bool = True) -> str:
    return f"{f(x, pct)} [{f(lo_hi[0], pct)}-{f(lo_hi[1], pct)}]"


def load(tag: str, rules_tag: str):
    z = np.load(BENCH / "e6" / f"probs_{tag}.npz")
    probs = {str(i): p for i, p in zip(z["ids"], z["probs"])}
    rules = {}
    for line in (BENCH / "ecg" / f"ptbxl{rules_tag}.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("ok") and r["id"] in probs:
            rules[r["id"]] = r["data"]
    ecg_bench.SET = "large"
    folds = ecg_bench.ptbxl_fold_map()
    ids = sorted(i for i in rules if ecg_bench.in_split(i, "dev", folds) and folds.get(i, 99) <= 8)   # DEV only
    return ids, probs, rules


def evaluate(tag: str, rules_tag: str, seed: int = 0) -> tuple[str, dict]:
    ids, probs, rules = load(tag, rules_tag)
    P = np.stack([probs[i] for i in ids])
    gold = [ecg_bench.gold_classes(rules[i]["scp"], rules[i].get("stadium1")) for i in ids]
    codes = [{x["code"] for x in rules[i]["findings"]} for i in ids]
    rng = np.random.default_rng(seed)
    n = len(ids)
    boots = [rng.integers(0, n, n) for _ in range(N_BOOT)]
    rows_m, rows_r, rows_k, rows_c = [], [], [], []
    summary: dict = {}
    variants = [(c, MAP[c], "") for c in CLASSES] + [(c, v, " (gold " + v + ")") for c, v in EXTRA.items()]
    for k, (c, cls, note) in enumerate(variants):
        j = CLASSES.index(c)
        y = np.array([cls in g for g in gold])
        s = P[:, j]
        rp = np.array([bool(ecg_bench.PRED[cls](cd)) for cd in codes])
        mp_ = s > PAPER_THR[c]
        a = auc(y, s)
        s90 = sens_at_spec(y, s)
        tp, fp, fn, tn = counts(y, mp_)
        se, sp, ppv = prf(tp, fp, fn, tn)
        rtp, rfp, rfn, rtn = counts(y, rp)
        rse, rsp, rppv = prf(rtp, rfp, rfn, rtn)
        ba, bs, bse, bsp, bppv, brse, brsp, brppv, bkmr = ([] for _ in range(9))
        for b in boots:
            yb, sb_, mb, rb = y[b], s[b], mp_[b], rp[b]
            if yb.sum() == 0:
                continue
            ba.append(auc(yb, sb_)); bs.append(sens_at_spec(yb, sb_))
            t = prf(*counts(yb, mb)); bse.append(t[0]); bsp.append(t[1]); bppv.append(t[2])
            t = prf(*counts(yb, rb)); brse.append(t[0]); brsp.append(t[1]); brppv.append(t[2])
            bkmr.append(kappa(mb, rb))
        name = c + note
        rows_m.append([name, int(y.sum()), fci(a, ci(ba), False), fci(s90, ci(bs)), fci(se, ci(bse)), fci(sp, ci(bsp)), fci(ppv, ci(bppv))])
        rows_r.append([name, int(y.sum()), fci(rse, ci(brse)), fci(rsp, ci(brsp)), fci(rppv, ci(brppv)),
                       f"{rse - se:+.3f}".replace("nan", "-") if se == se and rse == rse else "-"])
        rows_k.append([name, fci(kappa(mp_, rp), ci(bkmr), False), f(kappa(mp_, y), False), f(kappa(rp, y), False),
                       int((mp_ & rp).sum()), int((mp_ & ~rp).sum()), int((~mp_ & rp).sum())])
        rows_c.append([name, int((y & ~rp & mp_).sum()), int((y & rp & ~mp_).sum()), int((y & ~rp & ~mp_).sum()),
                       int((~y & mp_ & ~rp).sum()), int((~y & ~mp_ & rp).sum())])
        summary[name] = {"auc": a, "sens90": s90, "m_se": se, "m_sp": sp, "m_ppv": ppv, "r_se": rse, "r_sp": rsp, "r_ppv": rppv}
    hdr_m = ["Label", "N pos", "AUC [IC95%]", "Sens @ spec 90% [IC]", "Sens @ paper thr [IC]", "Spec @ paper thr [IC]", "PPV @ paper thr [IC]"]
    hdr_r = ["Label", "N pos", "Rules sens [IC]", "Rules spec [IC]", "Rules PPV [IC]", "rules sens - model sens"]
    hdr_k = ["Label", "kappa model x rules [IC]", "kappa model x gold", "kappa rules x gold", "both +", "model + only", "rules + only"]
    hdr_c = ["Label", "gold+, rules miss, model hits", "gold+, rules hit, model miss", "gold+, both miss", "gold-, model FP only", "gold-, rules FP only"]

    def tab(h, rows):
        return "\n".join(["| " + " | ".join(h) + " |", "|" + "---|" * len(h)] + ["| " + " | ".join(str(x) for x in r) + " |" for r in rows])
    md = (f"N = {n} PTB-XL records (DEV, folds 1-8, large class-enriched sample). Probabilities tag: {tag}; rules cache tag: {rules_tag}.\n\n"
          "### Model (Ribeiro 2020)\n\n" + tab(hdr_m, rows_m) + "\n\n### MedLens rules, same records\n\n" + tab(hdr_r, rows_r)
          + "\n\n### Agreement (Cohen kappa; model at the paper threshold)\n\n" + tab(hdr_k, rows_k)
          + "\n\n### Complementarity (counts)\n\n" + tab(hdr_c, rows_c) + "\n")
    return md, summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--rules-tag", default="E6base")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    md, _ = evaluate(a.tag, a.rules_tag)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
