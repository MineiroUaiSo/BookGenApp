"""LVH / strain / left atrial / HCM-pattern rules and measurement plausibility gates (pt-BR findings).

Called from rules.py (hook after the voltage block, plus small gates). Decision support only: the HCM item is
always 'sugestivo' and never a diagnosis. References: SBC Diretriz de Laudos ECG 2022 (Samesima et al., Arq Bras
Cardiol 119(4):638-680); Peguero et al., JACC 2017;69(13):1694-1703; Makavos et al., Heart Fail Rev 2019;24(4):439-459.
"""
from __future__ import annotations

from typing import Optional

from ...schemas import Reference
from . import indices as ix

STRAIN_LEADS = ("I", "aVL", "V4", "V5", "V6")
STRAIN_ST_MV = -0.05          # ST J+60 <= -0.5 mm, horizontal or downsloping
STRAIN_T_MV = -0.1            # inverted T (<= -1 mm)
STRAIN_R_MIN_MV = 0.5         # dominant R of at least 5 mm
STRAIN_T_ASYM = 1.1           # slow descent / abrupt return: (peak-onset) / (offset-peak) >= 1.1
STRAIN_MIN_LEADS = 3
DEEP_T_MV = -0.3              # T <= -3 mm
HCM_LEADS = ("I", "aVL", "V2", "V3", "V4", "V5", "V6")
HCM_SOKOLOW_MM, HCM_R_PREC_MM = 50.0, 30.0
HCM_CORNELL_MM = {"M": 35.0, "F": 30.0}
QRS_IMPLAUSIBLE_MS = 200.0
PR_IMPLAUSIBLE_MS = 100.0
IMAGE_QUALITY_MIN = 0.6
PR_CONF_MIN = 0.6
PR_PRINTED_TOL_MS = 30.0
LAE_P_MS = 120.0

R_PEGUERO = Reference(id="peguero_2017", source="Peguero JG et al. Electrocardiographic Criteria for the Diagnosis "
                      "of Left Ventricular Hypertrophy. J Am Coll Cardiol 2017;69(13):1694-1703")
R_HCM = Reference(id="makavos_2019", source="Makavos G et al. ECG in hypertrophic cardiomyopathy. Heart Fail Rev "
                  "2019;24(4):439-459")


def _amps(bd) -> tuple[dict, dict]:
    r = {l: float(d.r_max) * 10.0 for l, d in bd.leads.items()}
    s = {l: -float(d.s_min) * 10.0 for l, d in bd.leads.items()}
    return r, s


def _t_asym(ld) -> Optional[float]:
    t = ld.t
    if t is None or t.offset <= t.peak:
        return None
    return (t.peak - t.onset) / (t.offset - t.peak)


def strain_leads(c: dict) -> dict:
    """Leads with the LV strain pattern: dominant R + ST J60 <= -0.5 mm (not rising) + asymmetric inverted T."""
    L, bd = c["lm"], c["bd"]
    out = {}
    for l in STRAIN_LEADS:
        m, ld = L.get(l), bd.leads.get(l)
        if m is None or ld is None or m.st_j60_mv is None or m.t_amplitude_mv is None:
            continue
        j60, j80 = m.st_j60_mv, m.st_j80_mv
        r_dom = ld.r_max >= -ld.s_min and ld.r_max >= STRAIN_R_MIN_MV
        st_ok = j60 <= STRAIN_ST_MV and (j80 is None or j80 <= j60 + 0.03)
        asym = _t_asym(ld)
        if r_dom and st_ok and m.t_amplitude_mv <= STRAIN_T_MV and (asym is None or asym >= STRAIN_T_ASYM):
            out[l] = dict(st=j60 * 10.0, t=m.t_amplitude_mv * 10.0, asym=asym)
    return out


def _index_ev(idx: dict) -> list[str]:
    ev = []
    for key, lab in (("sokolow_lyon", "Sokolow-Lyon"), ("cornell_voltagem", "Cornell"), ("peguero_lo_presti", "Peguero-Lo Presti")):
        i = idx.get(key)
        if i:
            ev.append(f"{lab} {i['v']:.0f} mm (preenche: {i['preenche']})")
    re_ = idx.get("romhilt_estes")
    if re_:
        ev.append(f"Romhilt-Estes {re_['v']} pontos ({re_['componentes']['classe']})")
    return ev


def hcm_pattern(c: dict, idx: dict, strain: dict, out_codes: set) -> Optional[list[str]]:
    """Voltage very high + deep (>= 3 mm) lateral/precordial T inversion or strain, without LBBB/pacing."""
    if c.get("paced") or c.get("bbb") in ("lbbb", "ilbbb", "rbbb"):
        return None
    L, bd = c["lm"], c["bd"]
    r, _ = _amps(bd)
    sex = c.get("sex")
    sl = (idx.get("sokolow_lyon") or {}).get("v")
    cn = (idx.get("cornell_voltagem") or {}).get("v")
    rprec = max((r[l] for l in ("V3", "V4", "V5", "V6") if l in r), default=0.0)
    ev = []
    if sl is not None and sl >= HCM_SOKOLOW_MM:
        ev.append(f"Sokolow-Lyon {sl:.0f} mm (>=50)")
    cthr = HCM_CORNELL_MM.get(sex, HCM_CORNELL_MM["M"])
    if cn is not None and cn >= cthr:
        ev.append(f"Cornell {cn:.0f} mm (>={cthr:.0f})")
    if rprec >= HCM_R_PREC_MM:
        ev.append(f"R precordial {rprec:.0f} mm (>=30)")
    deep = [l for l in HCM_LEADS if l in L and L[l].t_amplitude_mv is not None and L[l].t_amplitude_mv <= DEEP_T_MV]
    if not ev or len(deep) < 2:
        return None
    return ev + [f"T invertida profunda (>=3 mm) em {', '.join(deep)}"] + (["com padrão de strain"] if strain else [])


def apply_lvh(c: dict, out: list) -> dict:
    """Mutates 'out' (LVH evidence/label, strain, HCM) and returns {'strain': {...}, 'indices': {...}}."""
    from .rules import R_GOLD, R_SBC, _f, pl
    L, bd, gm = c["lm"], c["bd"], c["gm"]
    r, s = _amps(bd)
    strain = strain_leads(c)
    has_strain = len(strain) >= STRAIN_MIN_LEADS
    p1 = bd.leads["V1"].p if "V1" in bd.leads else None
    nd = p1.extra.get("neg_depth") if p1 is not None else None
    nd_ms = p1.extra.get("neg_dur_ms") if p1 is not None else None
    idt = [L[l].intrinsicoid_deflection_ms for l in ("V5", "V6") if l in L and L[l].intrinsicoid_deflection_ms is not None]
    idx = ix.compute_indices(
        r, s, sex=c.get("sex"), qrs_ms=gm.qrs_ms, qrs_axis=gm.qrs_axis_deg, t_axis=gm.t_axis_deg,
        p_neg_depth_mm=None if nd is None else nd * 10.0, p_neg_dur_ms=nd_ms,
        strain=has_strain, idt_ms=max(idt) if idt else None)
    gm.indices = idx
    c["indices"] = idx
    re_ = idx.get("romhilt_estes") or {}
    re_def = bool(re_.get("preenche"))
    cur = next((f for f in out if f.code == "ecg.lvh"), None)
    if cur is None and re_def and has_strain:
        out[:] = [f for f in out if f.code != "ecg.lvh_voltage"]
    if cur is not None or (re_def and has_strain):
        ev = (list(cur.evidence) if cur else []) + _index_ev(idx)
        if has_strain:
            ev.append("padrão de strain (R dominante, ST descendente/horizontal, T invertida assimétrica) em " + pl(strain))
        new = _f("ecg.lvh", "Sobrecarga ventricular esquerda com padrão de strain" if has_strain
                 else "Sobrecarga ventricular esquerda (critérios de voltagem)", "abnormal", ev, [R_SBC, R_GOLD],
                 0.65 if has_strain else (cur.confidence if cur else 0.5))
        out[:] = [new if f is cur else f for f in out] if cur else out + [new]
    lvh_now = any(f.code == "ecg.lvh" for f in out)
    if has_strain and lvh_now:
        out.append(_f("ecg.secondary_repolarization_lvh", "Repolarização secundária à sobrecarga ventricular esquerda",
                      "borderline", ["ST-T em " + pl(strain) + ": " + ", ".join(
                          f"{LEAD_LABEL.get(l, l)} ST {v['st']:.1f} mm / T {v['t']:.1f} mm" for l, v in strain.items()),
                          "não interpretado como isquemia"], [R_SBC, R_GOLD], 0.5))
    elif not lvh_now:
        strain = {}
    hev = hcm_pattern(c, idx, strain, set()) if lvh_now or has_strain else None
    if hev:
        out.append(_f("ecg.hcm_pattern", "Padrão eletrocardiográfico sugestivo de miocardiopatia hipertrófica "
                      "(correlacionar com ecocardiograma/RM)", "abnormal", hev + ["achado sugestivo, não diagnóstico"],
                      [R_SBC, R_HCM], 0.35))
    c["lvh_strain"] = set(strain)
    return dict(strain=set(strain), indices=idx)


LEAD_LABEL = {"I": "D1"}


def preexc_block_reason(c: dict, pr: float, qrs: float) -> Optional[str]:
    """Why a pre-excitation call must not be emitted (None = allowed). Optional ctx keys: source, quality,
    pr_conf, printed_pr_ms."""
    q = c.get("quality") or {}
    if c.get("source") == "image" and q and min(q.values()) < IMAGE_QUALITY_MIN:
        return "fonte digitalizada de imagem com qualidade insuficiente"
    pc = c.get("pr_conf")
    if pc is not None and pc < PR_CONF_MIN:
        return f"confiança do PR baixa ({pc:.2f})"
    pp = c.get("printed_pr_ms")
    if pp is not None and abs(pr - pp) > PR_PRINTED_TOL_MS:
        return f"PR medido {pr:.0f} ms diverge do impresso ({pp:.0f} ms)"
    return implausible_reason(c, pr, qrs)


def implausible_reason(c: dict, pr: Optional[float], qrs: Optional[float]) -> Optional[str]:
    """QRS > 200 ms without BBB/pacing, or PR < 100 ms with a doubtful P wave: measurement is implausible."""
    if c.get("paced"):
        return None
    if qrs is not None and qrs > QRS_IMPLAUSIBLE_MS and c.get("bbb") is None:
        return f"QRS {qrs:.0f} ms (>200) sem bloqueio de ramo/marcapasso"
    if pr is not None and pr < PR_IMPLAUSIBLE_MS:
        p_ii = c["lm"]["II"].p_amplitude_mv if "II" in c["lm"] else None
        if not c.get("sinus_p") and c.get("frac_p", 1.0) < 0.6:
            return f"PR {pr:.0f} ms (<100) com onda P duvidosa"
    return None
