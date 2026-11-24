"""PhysioNet ECG collectors: LUDB (delineation), PTB-XL (SCP diagnostics), ECG-image database (see notes).

Usage (from backend/):
    python -m medlens_data.collectors.physionet_ecg ludb-download
    python -m medlens_data.collectors.physionet_ecg ludb-build
    python -m medlens_data.collectors.physionet_ecg ptbxl-select      # writes ptbxl/selected_files.txt
    python -m medlens_data.collectors.physionet_ecg ptbxl-download    # wget -c --input-file
    python -m medlens_data.collectors.physionet_ecg ptbxl-build

Pure python (no wfdb): LUDB annotation files are parsed with a tiny WFDB annotation reader.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import random
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Optional

from medlens_data import USER_AGENT, Record, source_dir, write_manifest

LUDB_VER = "1.0.1"
PTBXL_VER = "1.0.3"
LUDB_BASE = f"https://physionet.org/files/ludb/{LUDB_VER}/"
PTBXL_BASE = f"https://physionet.org/files/ptb-xl/{PTBXL_VER}/"
LUDB_LICENSE = "ODC-By 1.0 (Open Data Commons Attribution License v1.0)"
PTBXL_LICENSE = "CC BY 4.0"
LUDB_ATTR = ("Kalyakulina A. et al., LUDB: A New Open-Access Validation Tool for Electrocardiogram Delineation "
             "Algorithms, IEEE Access 8 (2020); PhysioNet https://physionet.org/content/ludb/1.0.1/")
PTBXL_ATTR = ("Wagner P. et al., PTB-XL, a large publicly available electrocardiography dataset, Sci Data 7:154 "
              "(2020); PhysioNet https://physionet.org/content/ptb-xl/1.0.3/")

LUDB_LEADS = ["i", "ii", "iii", "avr", "avl", "avf", "v1", "v2", "v3", "v4", "v5", "v6"]

# ------------------------------------------------------------------ WFDB annotation reader (no wfdb)
_ANN_SYMBOL = {1: "N", 27: "t", 24: "p", 39: "(", 40: ")"}  # only those used by LUDB


def read_wfdb_annotation(data: bytes) -> tuple[list[int], list[str]]:
    """Minimal reader of WFDB annotation (.i, .ii ...) -> (sample indices, symbols)."""
    samples: list[int] = []
    symbols: list[str] = []
    pos, t = 0, 0
    n = len(data)
    while pos + 2 <= n:
        w = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        code, dt = w >> 10, w & 0x3FF
        if w == 0:
            break
        if code == 59:  # SKIP: next 4 bytes = interval (high word first)
            hi, lo = struct.unpack_from("<hH", data, pos)
            pos += 4
            t += (hi << 16) + lo
        elif code in (60, 61, 62):  # NUM / SUB / CHN: no payload beyond word
            pass
        elif code == 63:  # AUX: dt bytes of text, padded to even
            pos += dt + (dt & 1)
        else:
            t += dt
            samples.append(t)
            symbols.append(_ANN_SYMBOL.get(code, f"?{code}"))
    return samples, symbols


def delineation_from_annotation(samples: list[int], symbols: list[str]) -> dict[str, list[list[int]]]:
    """Group '(' x ')' triplets into {"p": [[onset, peak, offset], ...], "N": [...], "t": [...]}.

    LUDB writes   (  p  )   (  N  )   (  t  )   per wave; incomplete triplets (record borders) are dropped.
    """
    out: dict[str, list[list[int]]] = {"p": [], "N": [], "t": []}
    i = 0
    n = len(symbols)
    while i + 2 < n:
        if symbols[i] == "(" and symbols[i + 1] in out and symbols[i + 2] == ")":
            out[symbols[i + 1]].append([int(samples[i]), int(samples[i + 1]), int(samples[i + 2])])
            i += 3
        else:
            i += 1
    return out


# ------------------------------------------------------------------ LUDB labels
_LUDB_RULES: list[tuple[str, list[str]]] = [
    (r"(?<!irregular )sinus rhythm", ["ecg.sinus_rhythm"]),
    (r"sinus tachycardia", ["ecg.sinus_tachycardia"]),
    (r"sinus bradycardia", ["ecg.sinus_bradycardia"]),
    (r"sinus arrhythmia|irregular sinus", ["ecg.irregular_rhythm", "ecg.sinus_arrhythmia"]),
    (r"atrial fibrillation", ["ecg.atrial_fibrillation", "ecg.irregular_rhythm", "ecg.no_p_wave"]),
    (r"atrial flutter", ["ecg.atrial_flutter"]),
    (r"left axis deviation", ["ecg.left_axis_deviation"]),
    (r"right axis deviation", ["ecg.right_axis_deviation"]),
    (r"\bi degree av|first degree", ["ecg.av_block_1"]),
    (r"\biii degree av|third degree", ["ecg.av_block_3"]),
    (r"\bii degree av|second degree", ["ecg.av_block_2"]),
    (r"incomplete right bundle", ["ecg.irbbb"]),
    (r"incomplete left bundle", ["ecg.ilbbb"]),
    (r"(?<!incomplete )(?<!in)complete right bundle", ["ecg.rbbb"]),
    (r"(?<!incomplete )(?<!in)complete left bundle", ["ecg.lbbb"]),
    (r"left anterior hemiblock", ["ecg.lafb"]),
    (r"left posterior hemiblock", ["ecg.lpfb"]),
    (r"intravent?ricular conduction", ["ecg.ivcd"]),
    (r"left ventricular hypertrophy", ["ecg.lvh"]),
    (r"right ventricular hypertrophy", ["ecg.rvh"]),
    (r"left atrial hypertrophy|left atrial overload", ["ecg.lae"]),
    (r"right atrial hypertrophy|right atrial overload", ["ecg.rae"]),
    (r"atrial extrasystole", ["ecg.pac"]),
    (r"ventricular extrasystole", ["ecg.pvc"]),
    (r"pacemaker|cardiac pacing|paced|pacing", ["ecg.paced"]),
    (r"stemi", ["ecg.st_elevation_stemi"]),
    (r"ischemia|ischaemia", ["ecg.ischemia"]),
    (r"non-specific repolarization", ["ecg.nonspecific_st_t"]),
]


def ludb_labels_from_header(comments: list[str]) -> tuple[list[str], dict]:
    """comments: '#...' header lines. Returns (normalised labels, raw dict of fields)."""
    raw: dict = {"lines": []}
    for c in comments:
        c = c.lstrip("#").strip()
        if not c:
            continue
        m = re.match(r"<(age|sex)>:\s*(.*)", c)
        if m:
            raw[m.group(1)] = m.group(2)
        elif c != "<diagnoses>:":
            raw["lines"].append(c)
    labels: list[str] = []
    for line in raw["lines"]:
        l = line.lower()
        if l.startswith("electric axis") and "none" in l:  # pacemaker records
            labels.append("ecg.paced")
        for pat, codes in _LUDB_RULES:
            if re.search(pat, l):
                labels += [c for c in codes if c not in labels]
    return labels, raw


def parse_hea(text: str) -> tuple[dict, list[str]]:
    lines = text.splitlines()
    first = lines[0].split()
    hdr = {"name": first[0], "n_sig": int(first[1]), "fs": float(first[2]), "n_samples": int(first[3])}
    return hdr, [l for l in lines if l.startswith("#")]


def build_ludb(limit: Optional[int] = None) -> Path:
    sd = source_dir("ludb")
    raw = sd / "raw"
    data = raw / "data"
    recs: list[Record] = []
    ids = sorted((int(p.stem) for p in data.glob("*.hea")))
    for rid in ids[:limit]:
        hdr, comments = parse_hea((data / f"{rid}.hea").read_text())
        labels, rawf = ludb_labels_from_header(comments)
        ann: dict = {}
        for lead in LUDB_LEADS:
            p = data / f"{rid}.{lead}"
            if p.exists():
                s, sym = read_wfdb_annotation(p.read_bytes())
                ann[lead] = delineation_from_annotation(s, sym)
        ann_path = data / f"{rid}.delineation.json"
        ann_path.write_text(json.dumps({"fs": hdr["fs"], "n_samples": hdr["n_samples"], "leads": ann}))
        recs.append(Record(
            id=f"ludb-{rid}", source="ludb", modality="ECG", kind="signal",
            path=f"raw/data/{rid}.hea", url=f"{LUDB_BASE}data/{rid}.hea",
            license=LUDB_LICENSE, attribution=LUDB_ATTR,
            caption="; ".join(rawf["lines"]), labels=labels, view="12-lead",
            extra={"fs": hdr["fs"], "n_samples": hdr["n_samples"], "leads": LUDB_LEADS,
                   "dat": f"raw/data/{rid}.dat", "annotations_json": f"raw/data/{rid}.delineation.json",
                   "age": rawf.get("age"), "sex": rawf.get("sex"),
                   "n_waves": {k: sum(len(a[k]) for a in ann.values()) for k in ("p", "N", "t")}},
        ))
    return write_manifest("ludb", recs)


def verify_sha256(root: Path, sums: Path, only_prefix: Optional[str] = None) -> tuple[int, list[str]]:
    ok, bad = 0, []
    for line in sums.read_text().splitlines():
        if not line.strip():
            continue
        h, name = line.split(None, 1)
        name = name.strip().lstrip("*")
        if only_prefix and not name.startswith(only_prefix):
            continue
        p = root / name
        if not p.exists():
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() == h:
            ok += 1
        else:
            bad.append(name)
    return ok, bad


# ------------------------------------------------------------------ PTB-XL
KEY_STATEMENTS = ["NORM", "1AVB", "CRBBB", "CLBBB", "IRBBB", "ILBBB", "LAFB", "LPFB", "WPW", "AFIB", "AFLT", "LVH",
                  "RVH", "IMI", "AMI", "ASMI", "ILMI", "ALMI", "LMI", "IPLMI", "IPMI", "PMI", "LNGQT", "STACH",
                  "SBRAD", "LAO/LAE", "RAO/RAE", "NDT", "ISC_", "ISCAL", "ISCAN", "ISCAS", "ISCIL", "ISCIN",
                  "ISCLA", "IVCD", "STD_", "STE_", "INVT", "LOWT", "LVOLT", "PACE", "PVC", "PAC", "3AVB", "2AVB",
                  "SARRH", "LPR", "SVTAC", "PSVT", "BIGU", "TRIGU", "DIG", "ABQRS"]
PTBXL_MAP: dict[str, list[str]] = {
    "NORM": ["ecg.within_normal_limits"], "SR": ["ecg.sinus_rhythm"], "1AVB": ["ecg.av_block_1"],
    "2AVB": ["ecg.av_block_2"], "3AVB": ["ecg.av_block_3"], "CRBBB": ["ecg.rbbb"], "CLBBB": ["ecg.lbbb"],
    "IRBBB": ["ecg.irbbb"], "ILBBB": ["ecg.ilbbb"], "LAFB": ["ecg.lafb"], "LPFB": ["ecg.lpfb"],
    "WPW": ["ecg.wpw", "ecg.preexcitation"], "AFIB": ["ecg.atrial_fibrillation", "ecg.irregular_rhythm"],
    "AFLT": ["ecg.atrial_flutter"], "LVH": ["ecg.lvh"], "RVH": ["ecg.rvh"], "SEHYP": ["ecg.biventricular_hypertrophy"],
    "LNGQT": ["ecg.long_qt"], "STACH": ["ecg.sinus_tachycardia"], "SBRAD": ["ecg.sinus_bradycardia"],
    "SARRH": ["ecg.irregular_rhythm", "ecg.sinus_arrhythmia"], "LAO/LAE": ["ecg.lae"], "RAO/RAE": ["ecg.rae"],
    "IVCD": ["ecg.ivcd"], "LVOLT": ["ecg.low_voltage"], "PACE": ["ecg.paced"], "PVC": ["ecg.pvc"],
    "PAC": ["ecg.pac"], "SVTAC": ["ecg.svt"], "PSVT": ["ecg.svt"], "LPR": ["ecg.long_pr"],
    "STD_": ["ecg.st_depression"], "NST_": ["ecg.st_depression", "ecg.nonspecific_st_t"],
    "STE_": ["ecg.st_elevation"], "INVT": ["ecg.t_inversion"], "NDT": ["ecg.nonspecific_st_t"],
    "ISC_": ["ecg.ischemia"], "ISCAL": ["ecg.ischemia"], "ISCAN": ["ecg.ischemia"], "ISCAS": ["ecg.ischemia"],
    "ISCIL": ["ecg.ischemia"], "ISCIN": ["ecg.ischemia"], "ISCLA": ["ecg.ischemia"],
    "IMI": ["ecg.mi", "ecg.mi_inferior", "ecg.q_waves"], "ILMI": ["ecg.mi", "ecg.mi_inferior", "ecg.mi_lateral"],
    "IPMI": ["ecg.mi", "ecg.mi_inferior", "ecg.mi_posterior"], "IPLMI": ["ecg.mi", "ecg.mi_inferior", "ecg.mi_posterior", "ecg.mi_lateral"],
    "AMI": ["ecg.mi", "ecg.mi_anterior"], "ASMI": ["ecg.mi", "ecg.mi_anterior", "ecg.mi_septal"],
    "ALMI": ["ecg.mi", "ecg.mi_anterior", "ecg.mi_lateral"], "LMI": ["ecg.mi", "ecg.mi_lateral"],
    "PMI": ["ecg.mi", "ecg.mi_posterior"], "INJAS": ["ecg.st_elevation"], "INJAL": ["ecg.st_elevation"],
    "INJIN": ["ecg.st_elevation"], "INJIL": ["ecg.st_elevation"], "INJLA": ["ecg.st_elevation"],
    "BIGU": ["ecg.bigeminy"], "TRIGU": ["ecg.trigeminy"], "LOWT": ["ecg.low_t_amplitude"], "DIG": ["ecg.digitalis_effect"],
}


def _parse_scp(s: str) -> dict[str, float]:
    try:
        return ast.literal_eval(s)
    except Exception:
        return {}


def ptbxl_labels(scp: dict[str, float], stmts: dict[str, dict]) -> tuple[list[str], list[str]]:
    labels: list[str] = []
    supers: list[str] = []
    for code, lik in scp.items():
        st = stmts.get(code, {})
        diagnostic = st.get("diagnostic") == "1.0"
        if diagnostic and lik < 50:
            continue
        for c in PTBXL_MAP.get(code, []):
            if c not in labels:
                labels.append(c)
        sc = st.get("diagnostic_class", "")
        if diagnostic and sc and f"ecg.super_{sc}" not in supers:
            supers.append(f"ecg.super_{sc}")
    return labels + supers, supers


def load_ptbxl_tables(root: Path):
    with (root / "scp_statements.csv").open(encoding="utf-8") as f:
        stmts = {r[""]: r for r in csv.DictReader(f)}
    with (root / "ptbxl_database.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return stmts, rows


def select_ptbxl(target: int = 3000, per_stmt: int = 100, per_super: int = 350, seed: int = 7) -> list[dict]:
    root = source_dir("ptbxl")
    stmts, rows = load_ptbxl_tables(root)
    rng = random.Random(seed)
    for r in rows:
        r["_scp"] = _parse_scp(r["scp_codes"])
        r["_prio"] = (0 if r["strat_fold"] in ("9", "10") else 1, 0 if r["validated_by_human"] == "True" else 1, rng.random())
        r["_supers"] = [sc for sc in {stmts.get(k, {}).get("diagnostic_class") for k, v in r["_scp"].items()
                                       if stmts.get(k, {}).get("diagnostic") == "1.0" and v >= 50} if sc]
    rows.sort(key=lambda r: r["_prio"])
    chosen: dict[str, dict] = {}

    def count(pred):
        return sum(1 for r in chosen.values() if pred(r))

    for st in KEY_STATEMENTS:
        pred = (lambda r, st=st: st in r["_scp"])
        need = per_stmt - count(pred)
        for r in rows:
            if need <= 0:
                break
            if r["ecg_id"] not in chosen and pred(r):
                chosen[r["ecg_id"]] = r
                need -= 1
    for sc in ("NORM", "MI", "STTC", "CD", "HYP"):
        pred = (lambda r, sc=sc: sc in r["_supers"])
        need = per_super - count(pred)
        for r in rows:
            if need <= 0:
                break
            if r["ecg_id"] not in chosen and pred(r):
                chosen[r["ecg_id"]] = r
                need -= 1
    for r in rows:
        if len(chosen) >= target:
            break
        if r["ecg_id"] not in chosen:
            chosen[r["ecg_id"]] = r
    return list(chosen.values())


def ptbxl_select_cmd() -> Path:
    sel = select_ptbxl()
    root = source_dir("ptbxl")
    out = root / "selected_files.txt"
    with out.open("w") as f:
        for r in sel:
            base = r["filename_hr"]
            f.write(f"{PTBXL_BASE}{base}.dat\n{PTBXL_BASE}{base}.hea\n")
    print(f"selected {len(sel)} records")
    return out


def ptbxl_download_cmd() -> int:
    root = source_dir("ptbxl")
    cmd = ["wget", "-q", "-c", "-x", "-nH", "--cut-dirs=3", "-e", "robots=off", "-U", USER_AGENT, "-P", str(root / "raw"),
           "--tries=5", "--waitretry=5", "-i", str(root / "selected_files.txt")]
    return subprocess.call(cmd)


def build_ptbxl() -> Path:
    root = source_dir("ptbxl")
    stmts, rows = load_ptbxl_tables(root)
    sel_names = set()
    for line in (root / "selected_files.txt").read_text().splitlines():
        if line.endswith(".hea"):
            sel_names.add(line[len(PTBXL_BASE):-4])
    recs: list[Record] = []
    for r in rows:
        base = r["filename_hr"]
        if base not in sel_names or not (root / "raw" / f"{base}.dat").exists():
            continue
        scp = _parse_scp(r["scp_codes"])
        labels, _ = ptbxl_labels(scp, stmts)
        recs.append(Record(
            id=f"ptbxl-{int(r['ecg_id']):05d}", source="ptbxl", modality="ECG", kind="signal",
            path=f"raw/{base}.hea", url=f"{PTBXL_BASE}{base}.hea", license=PTBXL_LICENSE, attribution=PTBXL_ATTR,
            caption=r["report"], labels=labels, view="12-lead", group=f"patient-{r['patient_id']}",
            extra={"fs": 500, "dat": f"raw/{base}.dat", "scp_codes": scp, "report_lang": "de/en (original, verbatim)",
                   "strat_fold": int(r["strat_fold"]), "validated_by_human": r["validated_by_human"] == "True",
                   "age": r["age"], "sex": r["sex"], "heart_axis": r["heart_axis"],
                   "infarction_stadium1": r["infarction_stadium1"], "pacemaker": r["pacemaker"],
                   "diagnostic_superclass": [l[10:] for l in labels if l.startswith("ecg.super_")]},
        ))
    return write_manifest("ptbxl", recs)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "ludb-download":
        sd = source_dir("ludb")
        sys.exit(subprocess.call(["wget", "-q", "-r", "-np", "-nH", "--cut-dirs=3", "-c", "-e", "robots=off", "-U",
                                  USER_AGENT, "-P", str(sd / "raw"), LUDB_BASE]))
    elif cmd == "ludb-build":
        print(build_ludb())
    elif cmd == "ptbxl-select":
        ptbxl_select_cmd()
    elif cmd == "ptbxl-download":
        sys.exit(ptbxl_download_cmd())
    elif cmd == "ptbxl-build":
        print(build_ptbxl())
    else:
        print(__doc__)
