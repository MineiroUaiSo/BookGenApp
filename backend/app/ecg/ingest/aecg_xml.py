"""HL7 v3 aECG (annotated ECG) XML reader (SLIST_PQ / GLIST_PQ digit sequences)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from app.schemas import SourceKind

from .leads import build_signal, normalize_lead, to_mv


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el, name):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _num(el, attr="value", default=None):
    if el is None:
        return default
    try:
        return float(el.get(attr))
    except (TypeError, ValueError):
        return default


def load_aecg(path: Path):
    root = ET.parse(str(path)).getroot()
    fs = None
    leads: dict[str, np.ndarray] = {}
    for seq in root.iter():
        if _local(seq.tag) != "sequence":
            continue
        code = _child(seq, "code")
        val = _child(seq, "value")
        if val is None:
            continue
        cname = (code.get("code") if code is not None else "") or ""
        digits = _child(val, "digits")
        inc = _child(val, "increment")
        if inc is not None and fs is None and ("TIME" in cname.upper() or digits is None):
            step = _num(inc)
            unit = (inc.get("unit") or "s").lower()
            if step:
                step_s = step * {"s": 1.0, "ms": 1e-3, "us": 1e-6}.get(unit, 1.0)
                fs = 1.0 / step_s
        if digits is None or not (digits.text or "").strip():
            continue
        lead = normalize_lead(cname) or normalize_lead(code.get("displayName") if code is not None else None)
        if lead is None or lead in leads:
            continue
        origin = _child(val, "origin")
        scale = _child(val, "scale")
        o, sc = _num(origin, default=0.0), _num(scale, default=1.0)
        unit = (scale.get("unit") if scale is not None else None) or (origin.get("unit") if origin is not None else None)
        d = np.array(re.split(r"\s+", digits.text.strip()), dtype=float)
        leads[lead] = to_mv(o + sc * d, unit or "uV")
    if not leads:
        raise ValueError("no ECG lead sequences found in aECG XML")
    if not fs:
        fs = 500.0
    return build_signal(leads, fs, SourceKind.AECG_XML)
