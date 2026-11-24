"""CSV/TSV ECG reader: header with lead names, optional time column, optional units."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np

from app.schemas import SourceKind

from .leads import STD_LEADS, build_signal, normalize_lead, to_mv

_TIME_NAMES = {"time", "t", "seconds", "sec", "s", "time_s", "timestamp", "tempo", "time_ms", "ms", "ms_time"}


def _is_num(s: str) -> bool:
    try:
        float(s.strip().replace(",", "."))
        return True
    except ValueError:
        return False


def load_csv(path: Path, fs: float | None = None):
    text = Path(path).read_text(errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    meta_fs = None
    body = []
    for ln in lines:
        if ln.lstrip().startswith(("#", "//")):
            m = re.search(r"(?:fs|sampling[_ ]?(?:rate|frequency)|freq(?:uency)?)\s*[=:]\s*([0-9.]+)", ln, re.I)
            if m:
                meta_fs = float(m.group(1))
            continue
        body.append(ln)
    if not body:
        raise ValueError("empty CSV")
    sample = "\n".join(body[:20])
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t |").delimiter
    except csv.Error:
        delim = ","
    if delim == " ":
        rows = [re.split(r"\s+", ln.strip()) for ln in body]
    else:
        rows = list(csv.reader(body, delimiter=delim))
    dec_comma = delim == ";" and any("," in c for c in rows[-1])
    first = rows[0]
    has_header = not all(_is_num(c.strip()) for c in first if c.strip())
    header = [c.strip() for c in first] if has_header else None
    data_rows = rows[1:] if has_header else rows
    arr = np.array([[float(c.replace(",", ".") if dec_comma else c) if c.strip() else np.nan for c in r]
                    for r in data_rows if len(r) == len(first)], dtype=float)
    if arr.size == 0:
        raise ValueError("CSV has no numeric rows")
    ncol = arr.shape[1]
    t_col, units, names = None, {}, [None] * ncol
    if header:
        for j, h in enumerate(header):
            base = re.sub(r"\(.*?\)|\[.*?\]", "", h).strip()
            um = re.search(r"[\(\[]\s*([A-Za-zµμ]+)\s*[\)\]]", h)
            units[j] = um.group(1) if um else None
            if base.lower() in _TIME_NAMES and t_col is None:
                t_col = j
                continue
            names[j] = normalize_lead(base)
        # tolerate unnamed index column
        if t_col is None and header and header[0].lower() in ("", "index", "sample", "n"):
            names[0] = None
    else:
        if ncol in (12, 8):
            std = STD_LEADS if ncol == 12 else ["I", "II", "V1", "V2", "V3", "V4", "V5", "V6"]
            names = list(std)
        elif ncol in (13, 9):
            t_col = 0
            std = STD_LEADS if ncol == 13 else ["I", "II", "V1", "V2", "V3", "V4", "V5", "V6"]
            names = [None] + list(std)
        elif ncol == 1:
            names = ["II"]
    if t_col is not None:
        t = arr[:, t_col]
        dt = np.median(np.diff(t))
        tname = (header[t_col].lower() if header else "")
        if "ms" in tname or (dt > 1.0 and not fs):
            dt = dt / 1000.0
        if dt > 0:
            fs = fs or 1.0 / dt
    fs = fs or meta_fs or 500.0
    leads = {}
    for j in range(ncol):
        if names[j] and names[j] not in leads:
            col = arr[:, j]
            leads[names[j]] = to_mv(col, units.get(j) if units.get(j) else None)
    if not leads:
        raise ValueError("no recognisable lead columns in CSV")
    return build_signal(leads, fs, SourceKind.CSV)
