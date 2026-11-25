"""Measured PPV per rule code (PTB-XL dev, enlarged) -> backend/app/knowledge/rule_ppv.json (shown by the UI).

    cd backend && PYTHONPATH=. python -m bench.rule_ppv --tag <TAG> [--out app/knowledge/rule_ppv.json]

Reads the per-record cache of  python -m bench.ecg_bench --source ptbxl --split dev --set large --tag <TAG>;
nothing is re-analysed. DEV only (strat_fold 1-8; load_results refuses anything else).
PPV of a code = records where the code was emitted AND the mapped PTB-XL gold class is positive / records where it was
emitted. Codes without a mapped gold class are NOT in the file (UI: "não medido").
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from bench import ecg_bench as eb  # noqa: E402
from bench import ptbxl_large  # noqa: E402
from bench.r2_report import load_results  # noqa: E402
from bench.report import wilson  # noqa: E402

SOURCE = "PTB-XL dev"
MIN_N = 1

# emitted code (exact or prefix ending in "_") -> PTB-XL gold class that makes it a true positive
CODE_GOLD: dict[str, str] = {
    "ecg.atrial_fibrillation": "AF", "ecg.atrial_flutter": "AF_AFL", "ecg.av_block_1": "AV1",
    "ecg.av_block_2": "AV2", "ecg.av_block_3": "AV3", "ecg.rbbb": "RBBB_complete", "ecg.irbbb": "RBBB_incomplete",
    "ecg.lbbb": "LBBB_complete", "ecg.ilbbb": "LBBB_any", "ecg.lafb": "LAFB", "ecg.lpfb": "LPFB",
    "ecg.preexcitation": "WPW", "ecg.lvh": "LVH", "ecg.rvh": "RVH", "ecg.lae": "LAE", "ecg.rae": "RAE",
    "ecg.long_qt": "LQT", "ecg.sinus_bradycardia": "SBRAD", "ecg.sinus_tachycardia": "STACH",
    "ecg.sinus_rhythm": "SR", "ecg.pathologic_q_inferior": "MI_inferior", "ecg.pathologic_q_anterior": "MI_anterior",
    "ecg.pathologic_q_anterolateral": "MI_anterior", "ecg.pathologic_q_lateral": "MI_lateral",
    "ecg.st_elevation_": "STE_acute", "ecg.st_depression_": "STD_isch", "ecg.t_inversion_": "STTC",
    "ecg.low_voltage": "LOWV", "ecg.low_voltage_precordial": "LOWV", "ecg.within_normal_limits": "NORM",
    "ecg.paced_rhythm": "PACE",
}


def gold_for(code: str) -> str | None:
    if code in CODE_GOLD:
        return CODE_GOLD[code]
    for k, g in CODE_GOLD.items():
        if k.endswith("_") and code.startswith(k):
            return g
    if code.startswith("ecg.av_block_2"):
        return CODE_GOLD["ecg.av_block_2"]
    return None


def compute(res: dict[str, dict], meta: dict[str, dict]) -> dict[str, dict]:
    tp: dict[str, int] = {}
    n: dict[str, int] = {}
    for k, r in res.items():
        if not r["ok"]:
            continue
        d = r["data"]
        gold = eb.gold_classes(d["scp"], (meta.get(k) or {}).get("infarction_stadium1"))
        for code in {f["code"] for f in d["findings"]}:
            g = gold_for(code)
            if g is None:
                continue
            n[code] = n.get(code, 0) + 1
            tp[code] = tp.get(code, 0) + (g in gold)
    out = {}
    for code in sorted(n):
        if n[code] < MIN_N:
            continue
        lo, hi = wilson(tp[code], n[code])
        lo, hi = max(0.0, lo), min(1.0, hi)
        out[code] = {"ppv": round(tp[code] / n[code], 3), "ic_inf": round(lo, 3), "ic_sup": round(hi, 3),
                     "n": n[code], "tp": tp[code], "gold": gold_for(code), "fonte": SOURCE}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", type=Path, default=BACKEND / "app" / "knowledge" / "rule_ppv.json")
    a = ap.parse_args(argv)
    res = load_results(a.tag)
    meta = {ptbxl_large.rid_of(r): r for r in ptbxl_large.load_database(ptbxl_large.database_csv(eb.DATA_ROOT))}
    data = compute(res, meta)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"_meta": {"fonte": SOURCE, "tag": a.tag, "n_registros": sum(1 for r in res.values() if r["ok"]),
                                           "gerado_por": "python -m bench.rule_ppv --tag " + a.tag},
                                 "codes": data}, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {a.out} ({len(data)} codes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
