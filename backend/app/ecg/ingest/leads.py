"""Shared helpers: lead-name normalisation, unit conversion, derived limb leads, ECGSignal assembly."""
from __future__ import annotations

import re
from typing import Optional

import numpy as np

from app.schemas import ECGSignal, SourceKind

STD_LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
_CANON = {
    "I": "I", "II": "II", "III": "III", "AVR": "aVR", "AVL": "aVL", "AVF": "aVF",
    "V1": "V1", "V2": "V2", "V3": "V3", "V4": "V4", "V5": "V5", "V6": "V6",
    "DI": "I", "DII": "II", "DIII": "III", "D1": "I", "D2": "II", "D3": "III",
    "MCL1": "V1", "MCL6": "V6", "CM5": "V5",
}


def normalize_lead(label: Optional[str]) -> Optional[str]:
    """'Lead aVR', 'MDC_ECG_LEAD_V1', 'ECG II', 'I (rhythm)' -> standard name or None."""
    if not label:
        return None
    s = str(label).strip().upper()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.sub(r"MDC[_ ]ECG[_ ]LEAD[_ ]?", " ", s)
    s = re.sub(r"\b(LEAD|ECG|EKG|CANAL|DERIVACAO|DERIVAÇÃO|CHANNEL|RHYTHM|STRIP)\b", " ", s)
    s = re.sub(r"[\s_\-\.:]+", "", s)
    if s in _CANON:
        return _CANON[s]
    s2 = s.replace("-", "")
    return _CANON.get(s2)


def to_mv(arr: np.ndarray, unit: Optional[str]) -> np.ndarray:
    u = (unit or "").strip().lower().replace("µ", "u").replace("μ", "u")
    if u in ("uv", "microvolt", "microvolts", "uvolt"):
        return arr / 1000.0
    if u in ("mv", "millivolt", "millivolts"):
        return arr
    if u in ("v", "volt", "volts"):
        return arr * 1000.0
    if u in ("nv", "nanovolt"):
        return arr / 1e6
    # unknown: heuristic (ECG in mV rarely exceeds 20, in uV rarely below 50 peak-to-peak)
    return arr / 1000.0 if np.nanmax(np.abs(arr)) > 50 else arr


def add_derived_limb_leads(leads: dict[str, np.ndarray]) -> list[str]:
    """Derive III/aVR/aVL/aVF from I and II when absent. Returns the names derived."""
    derived = []
    if "I" in leads and "II" in leads:
        I, II = leads["I"], leads["II"]
        n = min(len(I), len(II))
        I, II = I[:n], II[:n]
        for name, v in (("III", II - I), ("aVR", -(I + II) / 2), ("aVL", I - II / 2), ("aVF", II - I / 2)):
            if name not in leads:
                leads[name] = v
                derived.append(name)
    return derived


def build_signal(leads: dict[str, np.ndarray], fs: float, source: SourceKind, derive: bool = True,
                 extra_cal: Optional[dict] = None) -> ECGSignal:
    leads = {k: np.asarray(v, dtype=float) for k, v in leads.items()}
    derived = add_derived_limb_leads(leads) if derive else []
    ordered = {k: leads[k] for k in STD_LEADS if k in leads}
    ordered.update({k: v for k, v in leads.items() if k not in ordered})
    if not ordered:
        raise ValueError("no ECG leads found")
    dur = max(len(v) for v in ordered.values()) / fs
    cal = dict(extra_cal or {})
    return ECGSignal(fs=float(fs), leads={k: np.nan_to_num(v).tolist() for k, v in ordered.items()},
                     duration_s=float(dur), source=source, quality={}, calibration=cal)
