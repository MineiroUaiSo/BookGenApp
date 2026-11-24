"""Lead naming, aliases and derived limb leads."""
from __future__ import annotations

import re

import numpy as np

LIMB = ["I", "II", "III", "aVR", "aVL", "aVF"]
PRECORDIAL = ["V1", "V2", "V3", "V4", "V5", "V6"]
ALL_LEADS = LIMB + PRECORDIAL
# hexaxial angle (deg, 0 = left, +90 = down) of each limb lead
LIMB_ANGLE = {"I": 0.0, "II": 60.0, "III": 120.0, "aVR": -150.0, "aVL": -30.0, "aVF": 90.0}

_ALIAS = {"DI": "I", "D1": "I", "DII": "II", "D2": "II", "DIII": "III", "D3": "III",
          "AVR": "aVR", "AVL": "aVL", "AVF": "aVF"}


def canon(name: str) -> str:
    s = re.sub(r"^(MDC_ECG_LEAD_|LEAD[ _-]*)", "", str(name).strip(), flags=re.I).strip()
    u = s.upper().replace(" ", "")
    if u in _ALIAS:
        return _ALIAS[u]
    if u in ("I", "II", "III"):
        return u
    if re.fullmatch(r"V[1-6]", u):
        return u
    return s


def normalize(leads: dict) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for k, v in leads.items():
        out[canon(k)] = np.nan_to_num(np.asarray(v, dtype=float))
    return out


def derive_missing(d: dict[str, np.ndarray]) -> list[str]:
    """Fill missing limb leads from I and II (Einthoven/Goldberger). Returns derived names."""
    derived = []
    if "I" in d and "II" in d:
        I, II = d["I"], d["II"]
        cand = {"III": II - I, "aVR": -(I + II) / 2, "aVL": I - II / 2, "aVF": II - I / 2}
        for k, v in cand.items():
            if k not in d:
                d[k] = v
                derived.append(k)
    return derived
