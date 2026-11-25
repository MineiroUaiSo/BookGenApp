"""ST/Q helpers: per-lead noise abstention (R3 T7/T5-T1) and the STE confirmation / downgrade rules (R3 T7 T2).

Pure functions on the context built by analyze_signal; no side effects.
"""
from __future__ import annotations

from typing import Optional

NOISE_MV = 0.05        # same cut as the global "Ruído elevado" warning (sigma 50 uV, second-difference MAD)
QUALITY_MIN = 0.5      # same cut as the per-lead photo quality warning
STE_J60_MIN_MV = 0.05  # J+60 must also be elevated (>= 0.5 mm): J-only elevation is a notch/early-repolarisation sign
WIDE_QRS_MS = 120.0
STE_S_RATIO_MIN = 0.25   # in LVH, ST/S below 25% is the expected repolarisation, not an injury current
RECIPROCAL = {"inferior": ("I", "aVL"), "anterior": ("II", "III", "aVF"), "lateral": ("II", "III", "aVF"),
              "anterolateral": ("II", "III", "aVF")}


def noisy_leads(bd, quality: Optional[dict] = None) -> list[str]:
    """Leads whose noise (median-beat delineation sigma) or photo quality is beyond the existing thresholds."""
    q = quality or {}
    return [l for l, ld in bd.leads.items()
            if getattr(ld, "noise", 0.0) > NOISE_MV or (l in q and q[l] < QUALITY_MIN)]


def ste_confirmed(j_mv: Optional[float], j60_mv: Optional[float]) -> bool:
    """J elevated (threshold applied by the caller) and, when measurable, J+60 also elevated."""
    return j60_mv is None or (j_mv is not None and j60_mv >= STE_J60_MIN_MV)


def reciprocal_depression(territory: str, std: dict) -> bool:
    return any(l in std for l in RECIPROCAL.get(territory, ()))


def ste_downgrade_reason(qrs_ms: Optional[float], hve: bool, ste: dict, s_min: dict) -> Optional[str]:
    """Reason to report STE only as borderline/non-specific: wide QRS (secondary ST-T) or, with LVH by voltage,
    every elevated lead has ST/|S| < 25% (expected repolarisation of deep-S leads)."""
    if qrs_ms is not None and qrs_ms >= WIDE_QRS_MS:
        return f"QRS largo ({qrs_ms:.0f} ms): repolarização secundária possível"
    if hve and ste:
        ratios = [ste[l] / abs(s_min[l]) for l in ste if s_min.get(l) and s_min[l] < -1e-6]
        if len(ratios) == len(ste) and all(r < STE_S_RATIO_MIN for r in ratios):
            return "HVE por voltagem com ST/S < 25% nas derivações elevadas"
    return None
