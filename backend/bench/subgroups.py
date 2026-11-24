"""Subgroup analysis of the PTB-XL diagnosis results (R2): sex, age band, device and PTB-XL noise flags.

Pure functions over the per-record results (bench.ecg_bench cache) + ptbxl_database.csv metadata; every cell has a bootstrap
IC95% (bench.report). Subgroup columns come from ptbxl_database.csv: sex (0 = male, 1 = female), age (300 = ">89"),
device, baseline_drift / static_noise / burst_noise / electrodes_problems (non-empty text = flag set by the PTB-XL annotators).
"""
from __future__ import annotations

from collections import Counter
from typing import Callable, Optional

from bench.report import bootstrap_binary_ci, fmt_ci, table

AGE_BANDS = [("<40", 0, 40), ("40-65", 40, 66), (">65", 66, 10_000)]
NOISE_FLAGS = ["baseline_drift", "static_noise", "burst_noise", "electrodes_problems"]
MIN_POS_WARN = 10
# class key (ecg_bench.PRED/gold name) -> label shown in the report
TARGETS = [("NORM", "NORM → normal"), ("AF", "AF"), ("AV1", "AV1"), ("RBBB_complete", "CRBBB"),
           ("LBBB_complete", "LBBB"), ("STD", "STD"), ("STE_acute", "STE_acute"), ("LVH", "LVH")]


def has_flag(v) -> bool:
    """PTB-XL noise columns hold free text (e.g. ', I-V1,  '); blank / only separators = no flag."""
    return bool(str(v or "").replace(",", "").strip())


def age_band(age) -> Optional[str]:
    try:
        a = float(age)
    except (TypeError, ValueError):
        return None
    if a != a:
        return None
    if a > 120:   # 300 = ">89" in PTB-XL: not a real age, belongs to the oldest band
        return ">65"
    for name, lo, hi in AGE_BANDS:
        if lo <= a < hi:
            return name
    return None


def sex_of(v) -> Optional[str]:
    return {"0": "M", "1": "F"}.get(str(v).split(".")[0])


def device_groups(meta_by_id: dict[str, dict], ids, top: int = 6) -> dict[str, str]:
    """device name -> itself for the top-N most frequent devices among ids, everything else -> 'other'."""
    cnt = Counter((meta_by_id[i].get("device") or "").strip() for i in ids if i in meta_by_id)
    keep = {d for d, _ in cnt.most_common(top) if d}
    return {d: (d if d in keep else "other") for d in cnt}


def groupings(meta: dict, dev_map: dict[str, str]) -> list[tuple[str, str]]:
    """[(dimension, level), ...] the record belongs to (one level per dimension; missing metadata -> skipped)."""
    out = []
    s = sex_of(meta.get("sex"))
    if s:
        out.append(("sexo", s))
    b = age_band(meta.get("age"))
    if b:
        out.append(("idade", b))
    d = (meta.get("device") or "").strip()
    if d:
        out.append(("aparelho", dev_map.get(d, "other")))
    for fl in NOISE_FLAGS:
        out.append((f"ruído: {fl}", "com" if has_flag(meta.get(fl)) else "sem"))
    return out


def confusion(rows: list[tuple[bool, bool]]) -> tuple[int, int, int, int]:
    tp = sum(1 for g, p in rows if g and p)
    fp = sum(1 for g, p in rows if p and not g)
    fn = sum(1 for g, p in rows if g and not p)
    return tp, fp, fn, len(rows) - tp - fp - fn


def subgroup_table(recs: list[dict], cls: str, pred_fn: Callable[[set], bool]) -> tuple[str, list]:
    """One table for one class: rows = overall + every subgroup level. recs: dicts with keys gold(set), codes(set), groups(list)."""
    by: dict[tuple[str, str], list[tuple[bool, bool]]] = {("todos", "todos"): []}
    for r in recs:
        gp = (cls in r["gold"], bool(pred_fn(r["codes"])))
        by[("todos", "todos")].append(gp)
        for g in r["groups"]:
            by.setdefault(g, []).append(gp)
    rows, raw = [], []
    for key in sorted(by, key=lambda k: (k != ("todos", "todos"), k[0], k[1])):
        tp, fp, fn, tn = confusion(by[key])
        npos = tp + fn
        bs = bootstrap_binary_ci(tp, fp, fn, tn)
        warn = " (!)" if 0 < npos < MIN_POS_WARN else ""
        rows.append([key[0], key[1], len(by[key]), f"{npos}{warn}", fmt_ci(*bs["sens"]) if npos else "-",
                     fmt_ci(*bs["spec"]), fmt_ci(*bs["ppv"]) if tp + fp else "-"])
        raw.append((key, tp, fp, fn, tn))
    return table(rows, ["dimensão", "nível", "N", "N pos", "Sens [IC95%]", "Espec [IC95%]", "VPP [IC95%]"]), raw


def build(recs: list[dict], pred_map: dict[str, Callable]) -> tuple[str, dict]:
    """Markdown for all TARGETS + {label: raw rows}. recs need 'groups' (see groupings)."""
    parts, raws = [], {}
    for cls, label in TARGETS:
        if cls not in pred_map:
            continue
        t, raw = subgroup_table(recs, cls, pred_map[cls])
        parts.append(f"**{label}**\n\n{t}")
        raws[label] = raw
    return "\n\n".join(parts), raws
