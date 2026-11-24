"""Physiological plausibility of a digitised ECG (K2 cross-check against the printed header + K3 sanity rules).

When the digitisation is suspect the findings that depend on it are withheld (abstention) and one explicit
"digitalização suspeita" finding says why. Applies to image-sourced signals only; never touches rules.py.
"""
from __future__ import annotations

import numpy as np

from ..schemas import ECGSignal, Finding, GlobalMeasurements, LeadMeasurements, SourceKind

# printed-vs-computed tolerances (ms) that trigger the cross-check warning
TOL_QRS, TOL_PR, TOL_QTC = 30.0, 40.0, 50.0
BBB = ("ecg.lbbb", "ecg.rbbb", "ecg.ilbbb", "ecg.irbbb", "ecg.ivcd", "ecg.qrs_borderline")
PREEXC = ("ecg.preexcitation", "ecg.short_pr")
STFIND = ("ecg.st_elevation_", "ecg.st_depression_", "ecg.secondary_repolarization")
QTF = ("ecg.long_qt", "ecg.short_qt")
VOLT = ("ecg.lvh", "ecg.lvh_voltage", "ecg.rvh", "ecg.low_voltage")
MAX_ST_MM_SINGLE = 4.0     # an ST shift above this in one lead only is a tracking error until proven otherwise
MAX_PEAK_TO_PEAK_MV = 8.0  # >80 mm peak-to-peak at the detected gain
EINTHOVEN_MAX, GOLDBERGER_MAX = 1.0, 0.8


def _matches(code: str, prefixes: tuple) -> bool:
    return any(code == p or (p.endswith("_") and code.startswith(p)) for p in prefixes)


def _window(signal: ECGSignal, names: list[str]) -> list[np.ndarray] | None:
    """Samples of leads recorded simultaneously (common time window), or None."""
    cal, fs = signal.calibration or {}, float(signal.fs)
    if any(n not in signal.leads for n in names):
        return None
    offs = [int(round(cal.get(f"offset_s.{n}", 0.0) * fs)) for n in names]
    a = max(offs)
    b = min(o + len(signal.leads[n]) for o, n in zip(offs, names))
    if b - a < int(1.5 * fs):
        return None
    return [np.asarray(signal.leads[n][a - o:b - o], float) for o, n in zip(offs, names)]


def physical_checks(signal: ECGSignal) -> list[str]:
    """Einthoven (II = I + III) and Goldberger (aVR+aVL+aVF = 0) on simultaneously recorded leads."""
    from ..ecg.digitize import trace
    out = []
    w = _window(signal, ["I", "II", "III"])
    if w is not None:
        ein, _, _ = trace.classify_triplet(w)
        if ein > EINTHOVEN_MAX:
            out.append(f"relação de Einthoven (II = I + III) não se sustenta no traçado digitalizado (razão {ein:.2f})")
    w = _window(signal, ["aVR", "aVL", "aVF"])
    if w is not None:
        _, gold, _ = trace.classify_triplet(w)
        if gold > GOLDBERGER_MAX:
            out.append(f"soma das derivações aumentadas diferente de zero (razão {gold:.2f})")
    return out


def printed_divergence(signal: ECGSignal, gm: GlobalMeasurements) -> list[str]:
    cal = signal.calibration or {}
    out = []
    for key, calc, tol, nm in (("printed.qrs_ms", gm.qrs_ms, TOL_QRS, "QRS"), ("printed.pr_ms", gm.pr_ms, TOL_PR, "PR"),
                               ("printed.qtc_ms", gm.qtc_bazett_ms, TOL_QTC, "QTc")):
        if key in cal and calc is not None and abs(calc - cal[key]) > tol:
            out.append(f"{nm} calculado {calc:.0f} ms x impresso {cal[key]:.0f} ms")
    return out


def sanity_reasons(signal: ECGSignal, gm: GlobalMeasurements, lms: list[LeadMeasurements], findings: list[Finding]) -> dict[str, list[str]]:
    """reason -> affected finding prefixes."""
    codes = [f.code for f in findings]
    r: dict[str, list] = {}
    if gm.qrs_ms is not None and gm.qrs_ms > 200 and not any(_matches(c, BBB + ("ecg.paced_rhythm",)) for c in codes):
        r[f"QRS {gm.qrs_ms:.0f} ms sem bloqueio de ramo/marcapasso"] = list(BBB + PREEXC)
    if gm.pr_ms is not None and gm.pr_ms < 100:
        ii = next((m for m in lms if m.lead in ("II", "I")), None)
        if ii is None or ii.p_amplitude_mv is None or ii.p_amplitude_mv < 0.05 or (ii.p_duration_ms or 0) < 60:
            r[f"PR {gm.pr_ms:.0f} ms com onda P duvidosa"] = list(PREEXC)
    big = [m.lead for m in lms if m.st_j60_mv is not None and abs(m.st_j60_mv) * 10 > MAX_ST_MM_SINGLE]
    if len(big) == 1:
        r[f"desvio de ST > {MAX_ST_MM_SINGLE:g} mm isolado em {big[0]}"] = list(STFIND)
    ptp = [m.lead for m in lms if m.r_amplitude_mv is not None and (m.r_amplitude_mv - (m.s_amplitude_mv or 0)) > MAX_PEAK_TO_PEAK_MV]
    if ptp:
        r["amplitude incompatível com a calibração detectada (" + ", ".join(ptp) + ")"] = list(STFIND + VOLT)
    return r


def apply(signal: ECGSignal, gm: GlobalMeasurements, lms: list[LeadMeasurements], findings: list[Finding],
          warnings: list[str]) -> list[Finding]:
    """Withhold findings that depend on a suspect digitisation. Adds warnings and one explicit finding."""
    if signal.source != SourceKind.IMAGE:
        return findings
    cal = signal.calibration or {}
    drop: list[str] = []
    reasons: list[str] = []
    div = printed_divergence(signal, gm)
    if div:
        reasons.append("digitalização divergente do impresso: " + "; ".join(div))
        drop += list(BBB + PREEXC + STFIND + QTF)
    for why, pref in sanity_reasons(signal, gm, lms, findings).items():
        reasons.append(why)
        drop += pref
    phys = physical_checks(signal)
    if phys:
        reasons += phys
        drop += list(BBB + PREEXC + STFIND)
    if cal.get("grid_confidence", 1.0) < 0.3:
        reasons.append("grade do papel pouco confiável")
    if min(cal.get("px_per_mm_x", 99.0), cal.get("px_per_mm_y", 99.0)) < 5.0:
        warnings.append("Resolução baixa (< 5 px/mm): intervalos pouco confiáveis.")
    if not reasons:
        return findings
    kept = [f for f in findings if not _matches(f.code, tuple(drop))]
    removed = [f.code for f in findings if _matches(f.code, tuple(drop))]
    for why in reasons:
        warnings.append("Digitalização suspeita: " + why)
    if removed:
        warnings.append("Achados não emitidos por dependerem da digitalização: " + ", ".join(sorted(set(removed))))
    kept.append(Finding(code="ecg.digitization_suspect", label="Digitalização suspeita: achados dependentes não emitidos",
                        severity="borderline", evidence=reasons, confidence=0.9, origin="rules"))
    return kept
