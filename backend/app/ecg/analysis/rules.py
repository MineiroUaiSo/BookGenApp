"""Rules-based ECG findings (pt-BR). Thresholds are sex-agnostic unless noted; all are
decision-support heuristics from AHA/ACC/HRS 2009, SBC 2022 and UDMI-4, not diagnoses."""
from __future__ import annotations

import numpy as np

from ...schemas import Finding, Reference
from . import rules_lvh, rules_st

R_AHA = Reference(id="aha_2009_part_iii", source="Surawicz B et al. AHA/ACCF/HRS Recommendations for the "
                  "Standardization and Interpretation of the ECG, Part III: Intraventricular Conduction "
                  "Disturbances. Circulation 2009;119:e235", note="Critérios de BRD/BRE/BDAS/BDPI")
R_SBC = Reference(id="sbc_laudos_2022", source="Diretriz sobre a Análise e Emissão de Laudos "
                  "Eletrocardiográficos, Sociedade Brasileira de Cardiologia, 2022")
R_UDMI = Reference(id="udmi4_2018", source="Thygesen K et al. Fourth Universal Definition of Myocardial "
                   "Infarction (2018). Circulation 2018;138:e618", note="Limiares de supradesnivelamento de ST e ondas Q")
R_GOLD = Reference(id="goldberger_2023", source="Goldberger's Clinical Electrocardiography: A Simplified "
                   "Approach, 10th ed., Elsevier 2023")

LEAD_PRETTY = {"I": "D1", "II": "D2", "III": "D3"}


ST_NOT_ASSESSABLE_CODE = "ecg.st_not_assessable"
ST_WIDE_QRS_MS = 120
# Texto neutro de propósito: ausência de regra disparada não é um laudo de normalidade.
NORMAL_LABEL = "Nenhuma regra automática disparou; isso não exclui IAM, BAV ou outras alterações."


def _st_not_assessable_reasons(out, pc, qrs_ms, bbb=None):
    """Motivos pelos quais o ST não é avaliável com confiança (lista vazia = avaliável).

    BRD/BRD incompleto NÃO entra pelo critério de QRS largo: o ST segue avaliável (supra V1-V3 não é esperado no BRD).
    Sgarbossa/Smith valem para BRE e marca-passo; aqui só se avisa, não se calcula."""
    why = []
    if any(f.code == "ecg.lbbb" for f in out):
        why.append("bloqueio de ramo esquerdo (BRE): repolarização secundária discordante em todas as derivações")
    if pc and pc.get("type") in ("ventricular", "dual"):
        why.append("ritmo de marca-passo ventricular: QRS estimulado, ST/T secundários")
    if qrs_ms is not None and qrs_ms >= ST_WIDE_QRS_MS and bbb not in ("rbbb", "irbbb"):
        why.append(f"QRS {qrs_ms:.0f} ms (>= {ST_WIDE_QRS_MS} ms): ST/T secundários possíveis")
    return why


def pl(leads):
    return ", ".join(LEAD_PRETTY.get(l, l) for l in leads)


def _f(code, label, sev, ev, refs, conf=0.6):
    return Finding(code=code, label=label, severity=sev, evidence=ev, references=refs, confidence=conf,
                   origin="rules")


ADJ = [("V1", "V2"), ("V2", "V3"), ("V3", "V4"), ("V4", "V5"), ("V5", "V6"), ("II", "aVF"), ("aVF", "III"),
       ("aVL", "I"), ("I", "II")]
ADJ_SET = set(ADJ) | {(b, a) for a, b in ADJ}
INF, ANT, LAT = {"II", "III", "aVF"}, {"V1", "V2", "V3", "V4"}, {"I", "aVL", "V5", "V6"}


def territories(leads):
    """Group leads that have >=1 contiguous neighbour in the set into territory labels."""
    S = {l for l in leads if any((l, m) in ADJ_SET for m in leads)}
    out = []
    inf, ant, lat = S & INF, S & ANT, S & LAT
    # I-II adjacency is not a territory link by itself
    if len(inf) >= 2:
        out.append(("inferior", sorted(inf, key=["II", "III", "aVF"].index)))
    ant_ord = sorted(ant, key=lambda l: int(l[1]))
    lat_ord = [l for l in ["I", "aVL", "V5", "V6"] if l in lat]
    if len(ant) >= 2 and len(lat) >= 2:
        out.append(("anterolateral", ant_ord + lat_ord))
    elif len(ant) >= 2:
        out.append(("anterior", ant_ord))
    elif len(lat) >= 2:
        out.append(("lateral", lat_ord))
    elif len(ant) + len(lat) >= 2 and ("V4" in ant and "V5" in lat):
        out.append(("anterolateral", ant_ord + lat_ord))
    return out


# thresholds (mV / ratios) for bundle branch blocks; AHA 2009 Part III, tuned only inside published ranges
RBBB_TERM_R_MV = 0.25      # terminal R/R' >= 2.5 mm in V1 (R' is usually the tallest deflection in V1)
RBBB_LAT_S_MV = 0.1        # S wave >= 1 mm in I/V6 ("wide S"; width is unreliable in the delineation)
RBBB_LAT_S_RATIO = 0.15    # ... and >= 25% of the R in that lead
IRBBB_TERM_R_MV = 0.15
IRBBB_MIN_QRS = 100        # AHA 2009: incomplete RBBB 110-119 ms (adults); 100-119 ms is used by SBC for screening
Q_DUR_MS, Q_DUR_V23_MS, Q_AMP_MV, Q_RATIO, Q_RATIO_MIN_MV = 30, 20, 0.1, 0.25, 0.2   # AHA 2009 Part VI / UDMI-4
STD_MV = 0.05            # UDMI-4 / AHA 2009 Part VI: >=0.5 mm (0.05 mV) horizontal or downsloping, 2 contiguous leads
STE_MV, STE_V23_MV = 0.1, 0.2


def ste_threshold_mv(lead, age=None, sex=None):
    """UDMI-4 STE threshold at the J point (mV). V2-V3: men <40 y 0.25, men >=40 y 0.20, women 0.15;
    other leads 0.10. Unknown sex (or unknown age in men) -> the pre-existing conservative 0.20 mV."""
    if lead not in ("V2", "V3"):
        return STE_MV
    if sex == "F":
        return 0.15
    if sex == "M" and age is not None:
        return 0.25 if age < 40 else 0.20
    return STE_V23_MV
TINV_MV = 0.1
LVH_R56_MV = 2.6          # R V5/V6 > 26 mm (Minnesota 3.1 / AHA 2009 Part V)
LBBB_V1_NEG_RATIO = 2.0
LBBB_LAT_R_MV = 0.4
LBBB_Q_MAX_MV = 0.1
LBBB_LAT_S_RATIO = 0.5

def _lead_ctx(bd, l):
    """Amplitude features of one lead from the median-beat delineation: r (max +), s (min -, <=0), the last
    QRS component (kind, amp) and the first-wave q amplitude (<=0, 0 when absent)."""
    ld = bd.leads.get(l)
    if ld is None:
        return None
    ws = ld.waves
    last = (ws[-1].kind, ws[-1].amp) if ws else (None, 0.0)
    q = min([w.amp for w in ws if w.kind == "Q"], default=0.0)
    return dict(r=ld.r_max, s=ld.s_min, last=last, q=q)


def rb_inc_lbbb_excl(v1):
    """A clear terminal R' in V1 (>= 1.5 mm and >= 20% of S) argues against LBBB (rSr' = right delay)."""
    k, a = v1["last"]
    return k in ("R", "R'") and a >= 0.15 and a >= 0.2 * abs(v1["s"])


def _classify_bbb(bd, dur, fs_ms, L=None):
    """Returns (kind|None, evidence). kind in rbbb|lbbb|irbbb|ilbbb."""
    if dur < 100:
        return None, ""
    F = {l: _lead_ctx(bd, l) for l in ("I", "aVL", "V1", "V2", "V5", "V6")}
    v1, v2 = F["V1"], F["V2"]
    if v1 is None:
        return None, ""
    # terminal positive deflection dominating V1 (or V2) -> RBBB family
    def term_r(f, thr):
        k, a = f["last"]
        return k in ("R", "R'") and a >= thr and a >= 0.5 * abs(f["s"])
    rb_v1 = term_r(v1, RBBB_TERM_R_MV) or (v2 is not None and term_r(v2, RBBB_TERM_R_MV) and v1["r"] >= 0.1 and
                                           v1["last"][0] in ("R", "R'"))
    s_wide = [l for l in ("I", "V6", "V5") if F.get(l) and F[l]["s"] <= -RBBB_LAT_S_MV and
              abs(F[l]["s"]) >= RBBB_LAT_S_RATIO * F[l]["r"]]
    # LBBB: V1/V2 negative dominant + lateral R without q
    neg_v1 = abs(v1["s"]) >= LBBB_V1_NEG_RATIO * max(v1["r"], 0.05) and abs(v1["s"]) >= 0.3
    lat_ok = [l for l in ("I", "V5", "V6") if F.get(l) and F[l]["r"] >= LBBB_LAT_R_MV and
              F[l]["q"] > -LBBB_Q_MAX_MV and abs(F[l]["s"]) <= LBBB_LAT_S_RATIO * F[l]["r"]]
    # incomplete RBBB: rSr' in V1 with a smaller terminal R' (>=1.5 mm, >=30% of S) and QRS < 120 ms
    rb_inc = (v1["last"][0] in ("R", "R'") and v1["last"][1] >= IRBBB_TERM_R_MV and
              v1["last"][1] >= 0.3 * abs(v1["s"]) and v1["r"] >= IRBBB_TERM_R_MV)
    # rSR' with a tall R' (>= 5 mm) and QRS >= 130 ms is RBBB even when the lateral S is small (AHA 2009 Part III)
    tall_rbbb = rb_v1 and v1["last"][1] >= 0.5 and dur >= 130
    if rb_v1 and (s_wide or tall_rbbb):
        note = (f"R/R' terminal em V1 ({v1['last'][1]*10:.0f} mm)" +
                (f" e onda S em {pl(s_wide)} ({', '.join(f'{F[l][chr(115)]*10:.0f} mm' for l in s_wide)})"
                 if s_wide else " (R' alta, QRS >= 130 ms)"))
        if dur >= 120:
            return "rbbb", note
        if dur >= IRBBB_MIN_QRS:
            return "irbbb", note
    elif rb_inc and s_wide and IRBBB_MIN_QRS <= dur < 120:
        return "irbbb", (f"rSR' em V1 (R' {v1['last'][1]*10:.0f} mm) e onda S em {pl(s_wide)}, QRS < 120 ms")
    elif neg_v1 and len(lat_ok) >= 2 and not rb_v1 and not rb_inc_lbbb_excl(v1):
        note = f"V1 predominantemente negativo ({v1['s']*10:.0f} mm), R sem q em {pl(lat_ok)}"
        if dur >= 120:
            return "lbbb", note
        # incomplete LBBB (AHA 2009): QRS 110-119 ms, no q in I/V5/V6 and R peak time > 60 ms in V5-V6
        idt = [L[l].intrinsicoid_deflection_ms for l in ("V5", "V6") if L and l in L and
               L[l].intrinsicoid_deflection_ms is not None]
        if dur >= 110 and idt and max(idt) > 60:
            return "ilbbb", note + f"; tempo de pico da R {max(idt):.0f} ms (>60)"
    return None, ""



# rhythm thresholds. HR: sinus bradycardia <50 bpm (SBC 2022 report guideline; ESC brady 2021 uses <50 for
# pathological significance; 50-59 bpm is the normal lower range in athletes/sleep), tachycardia >100 bpm.
QRS_BORDERLINE_MS = 110   # E4: 110-119 ms without BBB morphology is only "limítrofe"
QT_ONSET_COMP_MS = 10.0     # E2: compensates the earlier QRS onset in the QT used for QTc decisions
QRS_GLOBAL_W = 0.25       # E4: weight of the global (wider) QRS in the width used for BBB/IVCD criteria
IVCD_MS = 120             # unspecific IVCD reported as abnormal from here
AV1_PEAK_MS = 165.0   # P peak -> QRS onset (about PR - 45 ms) for PR > 200 ms
AV3_SLOW_HR = 60.0     # E5: AF/flutter/no-P with regular slow RR => complete block (suggestive)
AV3_SLOW_CV = 0.04
AV1_BEAT_FRAC = 0.6   # E5: share of beats with PR > 200 ms
AV1_MIN_BEATS = 4
SBRAD_HR = 50.0
STACH_HR = 100.0
STACH_REG_CV = 0.10      # regular tachycardia: RR CV below this
STACH_PFRAC, STACH_PR_SD = 0.4, 30.0   # P locked to the QRS (looser than AF_PFRAC/AF_PR_SD) for tachycardia with ectopy
# AF = irregularly irregular RR (cv>=9%, RMSSD>=10%, >=30% of successive RR differing by >10%) without a P
# wave locked to the QRS (Goldberger 10th ed. ch. 'atrial fibrillation'; AHA/ACC/HRS AF guideline 2023)
AF_CV, AF_RMSSD, AF_DFRAC = 0.09, 0.10, 0.30
AF_PFRAC, AF_PR_SD = 0.5, 20.0
QTC_LIM_M, QTC_LIM_F = 450.0, 460.0
FLUTTER_F_RATIO = 0.75    # E3: F-wave peak ratio (240-340/min, best of II/III/aVF/V1) that outranks the AF test
FLUTTER_RATIO = 0.35     # share of 1-15 Hz power within +-0.5 Hz of the 3.5-6.7 Hz peak (see rhythm.flutter_features)


def classify_rhythm(c):
    """Returns (rhythm string, kind)."""
    hr, cv, rmssd = c["hr"], c["cv"], c["rmssd"]
    av = c.get("av") or {}
    irr = c.get("irr") or dict(cv=cv, rmssd=rmssd, dfrac=1.0)
    irregular = irr["cv"] >= AF_CV and irr["rmssd"] >= AF_RMSSD and irr["dfrac"] >= AF_DFRAC
    ectopy = bool(c.get("ectopy"))
    p_locked = av.get("p_frac", 1.0) >= AF_PFRAC and av.get("pr_sd", 0.0) <= AF_PR_SD
    if av.get("type") == "av3":
        return "Bloqueio atrioventricular total com ritmo de escape (dissociação AV)", "av3"
    if (av.get("type") or "").startswith("av2"):
        return "Ritmo sinusal com bloqueio atrioventricular de 2º grau", "av2"
    alt = bool(c.get("rr_alt"))
    ff = c.get("flutter_f") or {}
    if ff.get("peak_ratio", 0.0) >= FLUTTER_F_RATIO and not p_locked and not ectopy and not alt \
            and ff.get("freq_hz") and 4.0 <= ff["freq_hz"] <= 5.67:
        return "Flutter atrial", "flutter"
    if irregular and not ectopy and not p_locked and not alt:
        return "Fibrilação atrial", "af"
    # atrial flutter: narrow spectral peak at 3.5-6.7 Hz in the QRS-blanked trace and no P locked to the QRS
    fl = c.get("flutter") or {}
    if fl.get("peak_ratio", 0.0) >= FLUTTER_RATIO and not p_locked and not ectopy:
        return "Flutter atrial", "flutter"
    # P polarity: non-sinus only with clear evidence (negative P in D2 or positive P in aVR)
    p_ii = c["lm"]["II"].p_amplitude_mv if "II" in c["lm"] else None
    p_avr = c["lm"]["aVR"].p_amplitude_mv if "aVR" in c["lm"] else None
    clear_nonsinus = bool(c["p_present"]) and ((p_ii is not None and p_ii < -0.05) or
                                               (p_avr is not None and p_avr > 0.08 and (p_ii or 0) < 0.05))
    tachy_reg = hr is not None and hr > STACH_HR and cv < STACH_REG_CV
    if c["p_present"] and c["frac_p"] >= 0.6 and clear_nonsinus and tachy_reg:
        # P fused into the T wave of the previous beat looks negative/absent: regular > 100 bpm without AF/flutter
        c["stach_prob"] = "fused"
        return "Taquicardia sinusal (provável; onda P fundida à T)", "sinus"
    if c["p_present"] and c["frac_p"] >= 0.6 and clear_nonsinus:
        return "Ritmo atrial ectópico ou juncional (onda P não sinusal)", "ectopic"
    if (irregular or cv > 0.12) and (ectopy or alt or p_locked or c["p_present"]):
        if hr is not None and hr > STACH_HR and av.get("p_frac", 0.0) >= STACH_PFRAC and av.get("pr_sd", 1e9) <= STACH_PR_SD:
            c["stach_prob"] = "irreg"
        return "Ritmo sinusal irregular (arritmia sinusal ou extrassístoles)", "sinus_irreg"
    if c["p_present"] and c["frac_p"] >= 0.6:
        if hr is not None and hr < SBRAD_HR:
            return "Bradicardia sinusal", "sinus"
        if hr is not None and hr > STACH_HR:
            return "Taquicardia sinusal", "sinus"
        return "Ritmo sinusal regular", "sinus"
    if irregular and not alt:
        return "Fibrilação atrial", "af"
    if tachy_reg:
        c["stach_prob"] = "fused"
        return "Taquicardia sinusal (provável; onda P fundida à T)", "sinus"
    return "Ritmo regular sem onda P identificável (juncional ou indeterminado)", "no_p"


def build_findings(c):
    """c: context dict from analyze_signal. Returns list[Finding]."""
    gm, L, bd = c["gm"], c["lm"], c["bd"]
    kind = c["rhythm_kind"]
    fs_ms = 1000.0 / c["fs"]
    out = []
    hr = gm.heart_rate_bpm
    sinus = kind in ("sinus", "sinus_irreg", "av2")
    g = lambda l, a: getattr(L[l], a) if l in L else None

    # ---- rhythm / rate
    if kind == "af":
        out.append(_f("ecg.atrial_fibrillation", "Fibrilação atrial", "abnormal",
                      [f"RR irregularmente irregular (CV {c['cv']:.2f}, RMSSD/RR {c['rmssd']:.2f})",
                       "ondas P não identificadas", f"FC média {hr:.0f} bpm"], [R_SBC, R_GOLD], 0.6))
    elif kind == "flutter":
        fl = c.get("flutter") or {}
        out.append(_f("ecg.atrial_flutter", "Flutter atrial (provável)", "abnormal",
                      [f"atividade atrial regular a ~{(fl.get('freq_hz') or 0) * 60:.0f}/min na derivação D2 "
                       f"(pico espectral {fl.get('peak_ratio', 0):.2f} da potência 1-15 Hz)",
                       "sem onda P ligada ao QRS", f"FC ventricular {hr:.0f} bpm"],
                      [R_SBC, R_GOLD], 0.4))
    elif kind == "sinus":
        if hr < SBRAD_HR:
            sev = "critical" if hr < 40 else "abnormal"
            out.append(_f("ecg.sinus_bradycardia", "Bradicardia sinusal", sev, [f"FC {hr:.0f} bpm (<{SBRAD_HR:.0f})"],
                          [R_SBC, R_GOLD], 0.7))
        elif hr > STACH_HR:
            fused = c.get("stach_prob") == "fused"
            sev = "critical" if hr > 150 and not fused else "abnormal"
            out.append(_f("ecg.sinus_tachycardia", "Taquicardia sinusal (provável)" if fused else "Taquicardia sinusal", sev,
                          [f"FC {hr:.0f} bpm (>100)"] + (["ritmo regular sem FA/flutter; onda P não individualizada (provável fusão P-T)"]
                                                        if fused else []),
                          [R_SBC, R_GOLD], 0.5 if fused else 0.7))
        else:
            out.append(_f("ecg.sinus_rhythm", "Ritmo sinusal regular", "normal",
                          [f"FC {hr:.0f} bpm", f"RR CV {c['cv']:.2f}", "onda P positiva em D2 e negativa em aVR"],
                          [R_GOLD], 0.7))
    elif kind == "sinus_irreg":
        out.append(_f("ecg.irregular_rhythm", "Ritmo sinusal irregular", "borderline",
                      [f"RR CV {c['cv']:.2f}", f"FC média {hr:.0f} bpm"], [R_GOLD], 0.5))
        if c.get("stach_prob") == "irreg":
            out.append(_f("ecg.sinus_tachycardia", "Taquicardia sinusal (provável, com irregularidade do RR)", "abnormal",
                          [f"FC média {hr:.0f} bpm (>100)", "onda P ligada ao QRS (sem FA/flutter); irregularidade por ectopia/arritmia"],
                          [R_SBC, R_GOLD], 0.5))
    elif kind == "ectopic":
        out.append(_f("ecg.non_sinus_p", "Onda P de morfologia não sinusal (ritmo atrial ectópico ou juncional)",
                      "abnormal", ["P não positiva em D2 e/ou não negativa em aVR"], [R_GOLD], 0.4))
    elif kind == "no_p":
        out.append(_f("ecg.no_p_wave", "Ritmo regular sem onda P identificável", "abnormal",
                      [f"FC {hr:.0f} bpm", "sem onda P consistente antes do QRS"], [R_GOLD], 0.4))

    # ---- AV conduction
    av = c.get("av")
    pr = gm.pr_ms
    if av and av.get("type") == "av3":
        out.append(_f("ecg.av_block_3", "Bloqueio atrioventricular de 3º grau (total) (sugestivo)", "critical",
                      [f"frequência atrial ~{av['atrial_rate']:.0f} bpm, ventricular ~{av['vent_rate']:.0f} bpm",
                       "ondas P regulares dissociadas dos QRS, intervalo PR variável",
                       "achado sugestivo: confirmar no traçado/clínica"], [R_SBC, R_GOLD], 0.5))
    elif kind in ("no_p", "flutter") and hr is not None and hr < AV3_SLOW_HR and c["cv"] < AV3_SLOW_CV:
        # E5: regular slow ventricular rhythm without an identifiable P (AF/flutter with a regular escape rhythm)
        out.append(_f("ecg.av_block_3", "Bloqueio atrioventricular total (sugestivo)", "critical",
                      [f"ritmo ventricular regular e lento (~{hr:.0f} bpm, CV RR {c['cv']:.2f}) sem onda P conduzida identificável",
                       "possível fibrilação/flutter atrial com resposta ventricular regular (escape)",
                       "achado sugestivo: confirmar no traçado/clínica"], [R_SBC, R_GOLD], 0.4))
    elif av and av.get("type") in ("av2_m1", "av2_m2", "av2_21", "av2_unspec"):
        t = av["type"]
        lab = {"av2_m1": "Bloqueio AV de 2º grau Mobitz I (Wenckebach)",
               "av2_m2": "Bloqueio AV de 2º grau Mobitz II",
               "av2_21": "Bloqueio AV de 2º grau 2:1 (tipo indeterminado)",
               "av2_unspec": "Bloqueio AV de 2º grau"}[t]
        out.append(_f("ecg." + t.replace("av2_m1", "av_block_2_mobitz1").replace("av2_m2", "av_block_2_mobitz2")
                      .replace("av2_21", "av_block_2_21").replace("av2_unspec", "av_block_2"), lab,
                      "critical" if t == "av2_m2" else "abnormal",
                      [f"{av.get('n_drops', 0)} onda(s) P bloqueada(s) (sem QRS)",
                       f"PR condutivos: {', '.join(f'{x:.0f}' for x in av['prs'][~__import__('numpy').isnan(av['prs'])][:8])} ms (pico P até QRS)"],
                      [R_SBC, R_GOLD], 0.5))
    elif sinus and pr is not None:
        # 1st-degree AV block needs a consistent PR > 200 ms (AHA 2009 Part II; SBC 2022). The global PR
        # (earliest P onset in any lead) is inflated by noisy onsets, so the decision uses the median
        # per-lead PR plus an independent P-peak -> QRS interval (PR minus about half of the P duration).
        # E5: global P onset is now the median over the leads (no early bias), so the decision is the per-beat PR:
        # median PR > 200 ms with >= 60% of the beats above 200 ms, plus the independent P-peak -> QRS interval.
        pb = np.asarray(c.get("pr_beats") or [], float)
        pk_med = (av or {}).get("pr_med")
        if len(pb) >= AV1_MIN_BEATS and float(np.median(pb)) > 200 and float(np.mean(pb > 200)) >= AV1_BEAT_FRAC \
                and pk_med is not None and pk_med >= AV1_PEAK_MS:
            out.append(_f("ecg.av_block_1", "Bloqueio atrioventricular de 1º grau", "abnormal",
                          [f"PR mediano {float(np.median(pb)):.0f} ms (>200 ms) em {float(np.mean(pb > 200)) * 100:.0f}% dos batimentos; "
                           f"pico P ao QRS {pk_med:.0f} ms, consistente entre batimentos"],
                          [R_SBC, R_GOLD], 0.7))
        else:
            qrs = gm.qrs_ms or 0
            lq = sorted(m.qrs_ms for m in L.values() if m.qrs_ms)
            qrs_pre = float(np.median(lq)) if len(lq) >= 6 else qrs   # E4: robust width (global is earliest/latest)
            esr = bd.early_slope_ratio
            # Pre-excitation (AHA 2009 Part II/III): short PR + slurred QRS upstroke (delta wave) + wide QRS. The
            # global PR is biased long by early P onsets, so PR < 140 ms is accepted when the delta wave is
            # clear (initial slope < 45% of the maximum slope) and QRS >= 100 ms.
            blk = rules_lvh.preexc_block_reason(c, pr, qrs_pre)   # image quality / PR confidence / implausible
            if (pr < 120 or (pr < 140 and _classify_bbb(bd, qrs, fs_ms, L)[0] is None)) and qrs_pre >= 100 \
                    and esr is not None and esr < 0.45 and not blk:
                out.append(_f("ecg.preexcitation", "Padrão de pré-excitação ventricular (onda delta)", "abnormal",
                              [f"PR {pr:.0f} ms", f"QRS {qrs:.0f} ms (>=100)",
                               f"início do QRS lentificado (razão de velocidade inicial {esr:.2f})"],
                              [R_SBC, R_GOLD], 0.5))
            elif blk and (pr < 140 or qrs_pre > rules_lvh.QRS_IMPLAUSIBLE_MS):
                out.append(_f("ecg.implausible_measurement", "Medida de PR/QRS implausível ou não confiável (achados dependentes não emitidos)",
                      "borderline", [blk], [R_AHA, R_SBC], 0.4))
            elif pr < 120 and not blk:
                out.append(_f("ecg.short_pr", "Intervalo PR curto", "borderline", [f"PR {pr:.0f} ms (<120)"],
                              [R_SBC, R_GOLD], 0.6))

    # ---- axis
    ax = gm.qrs_axis_deg
    qrs = gm.qrs_ms or 0
    morph = {l: (L[l].morphology or "") for l in L}
    if ax is not None:
        if ax < -30:
            sev = "borderline" if ax >= -45 else "abnormal"
            lab = "Desvio do eixo elétrico do QRS para a esquerda" if ax >= -90 else "Desvio extremo do eixo do QRS (indeterminado)"
            out.append(_f("ecg.left_axis_deviation", lab, sev, [f"eixo do QRS {ax:.0f}° (normal -30° a +90°)"],
                          [R_AHA, R_SBC], 0.7))
            # LAFB (AHA 2009 Part III): axis -45 to -90, QRS < 120 ms, qR in aVL, rS in II/III/aVF
            # (the q in aVL is often <0.1 mV or lost in the median beat, so rS in >=2 inferior leads is used)
            rs_inf = [l for l in ("II", "III", "aVF") if l in bd.leads and -bd.leads[l].s_min > bd.leads[l].r_max]
            if -90 <= ax <= -45 and qrs < 120 and len(rs_inf) >= 2:
                out.append(_f("ecg.lafb", "Bloqueio divisional anterossuperior esquerdo (BDAS)", "abnormal",
                              [f"eixo {ax:.0f}°", f"rS em {pl(rs_inf)}", f"aVL {morph.get('aVL')}", f"QRS {qrs:.0f} ms"],
                              [R_AHA, R_SBC], 0.55))
        elif ax < -15:
            # not a deviation by AHA/SBC (LAD <= -30 deg is kept); reported as a mild leftward axis for the reader
            out.append(_f("ecg.left_axis_mild", "Eixo do QRS desviado levemente para a esquerda", "borderline",
                          [f"eixo do QRS {ax:.0f}° (-15° a -30°, ainda dentro do normal)"], [R_AHA, R_SBC], 0.5))
        elif ax > 90:
            out.append(_f("ecg.right_axis_deviation", "Desvio do eixo elétrico do QRS para a direita", "abnormal",
                          [f"eixo do QRS {ax:.0f}° (normal -30° a +90°)"], [R_AHA, R_SBC], 0.7))
            # LPFB (AHA 2009 Part III): axis +90 to +180, rS in I, qR in III/aVF, QRS < 120 ms, no RVH
            if ax <= 180 and qrs < 120 and "I" in bd.leads and "III" in bd.leads and "aVF" in bd.leads and \
                    -bd.leads["I"].s_min >= 0.5 * bd.leads["I"].r_max and \
                    all(bd.leads[l].r_max > -bd.leads[l].s_min for l in ("III", "aVF")):
                out.append(_f("ecg.lpfb", "Bloqueio divisional posteroinferior esquerdo (BDPI)", "abnormal",
                              [f"eixo {ax:.0f}°", "rS em D1, qR em D3/aVF", f"QRS {qrs:.0f} ms"], [R_AHA, R_SBC], 0.5))

    # ---- intraventricular conduction (AHA/ACCF/HRS 2009 Part III; SBC 2022)
    # Morphology letters from the delineator are noisy (small terminal r/s deflections), so the criteria
    # use amplitudes of the main deflections instead of letter patterns:
    #  RBBB: QRS >=120 ms, terminal R/R' in V1 (dominant over S), wide S in I and/or V6.
    #  LBBB: QRS >=120 ms, V1-V2 predominantly negative (rS/QS), monophasic R without q in I/V5/V6.
    v1, v6, d1 = morph.get("V1", ""), morph.get("V6", ""), morph.get("I", "")
    lead_q = sorted(m.qrs_ms for m in L.values() if m.qrs_ms)
    # E4: QRS width for the conduction criteria = median of the per-lead durations (robust to one lead with a
    # slow start/ST absorbed); the global earliest-onset/latest-offset width is kept when there are too few leads
    dur = float(np.median(lead_q)) + QRS_GLOBAL_W * (qrs - float(np.median(lead_q))) if len(lead_q) >= 6 else qrs
    cbbb, bbb_note = _classify_bbb(bd, dur, fs_ms, L)
    if cbbb in ("lbbb", "rbbb", "ilbbb", "irbbb") and any(f.code == "ecg.preexcitation" for f in out):
        cbbb = None  # delta wave widens the QRS and mimics a bundle branch block (AHA 2009 Part III, exclusions)
    ev = [f"QRS {dur:.0f} ms", f"V1 {v1 or '-'}", f"V6 {v6 or '-'}", f"D1 {d1 or '-'}"]
    if cbbb == "rbbb":
        out.append(_f("ecg.rbbb", "Bloqueio completo de ramo direito (BRD)", "abnormal",
                      ev + [bbb_note], [R_AHA, R_SBC], 0.7))
    elif cbbb == "lbbb":
        out.append(_f("ecg.lbbb", "Bloqueio completo de ramo esquerdo (BRE)", "abnormal",
                      ev + [bbb_note], [R_AHA, R_SBC], 0.7))
    elif cbbb == "irbbb":
        out.append(_f("ecg.irbbb", "Bloqueio incompleto de ramo direito", "borderline", ev + [bbb_note],
                      [R_AHA, R_SBC], 0.5))
    elif cbbb == "ilbbb":
        out.append(_f("ecg.ilbbb", "Bloqueio incompleto de ramo esquerdo", "borderline", ev + [bbb_note],
                      [R_AHA, R_SBC], 0.45))
    elif dur > rules_lvh.QRS_IMPLAUSIBLE_MS and not c.get("paced"):
        if not any(f.code == "ecg.implausible_measurement" for f in out):
            blk = f"QRS {dur:.0f} ms (>200) sem bloqueio de ramo/marcapasso"
            out.append(_f("ecg.implausible_measurement", "Medida de PR/QRS implausível ou não confiável (achados dependentes não emitidos)",
                      "borderline", [blk], [R_AHA, R_SBC], 0.4))
    elif dur >= IVCD_MS and not any(f.code == "ecg.preexcitation" for f in out):
        out.append(_f("ecg.ivcd", "Distúrbio inespecífico da condução intraventricular", "abnormal",
                      [f"QRS {dur:.0f} ms (>={IVCD_MS})", "critérios de BRD/BRE não preenchidos"], [R_AHA, R_SBC], 0.5))
    elif dur >= QRS_BORDERLINE_MS and not any(f.code == "ecg.preexcitation" for f in out):
        out.append(_f("ecg.qrs_borderline", "QRS limítrofe (110-119 ms)", "borderline",
                      [f"QRS {dur:.0f} ms (zona limítrofe {QRS_BORDERLINE_MS}-{IVCD_MS - 1} ms)",
                       "critérios de BRD/BRE não preenchidos; sem distúrbio de condução definido"], [R_AHA, R_SBC], 0.4))
    c["bbb"] = cbbb

    # ---- atrial overload
    if sinus and c["p_present"]:
        ev_l, ev_r = [], []
        pII = L.get("II")
        pd = bd.leads["II"].p if "II" in bd.leads else None
        p_long = bool(pII and pII.p_duration_ms and pII.p_duration_ms >= rules_lvh.LAE_P_MS)
        bifid = pd is not None and pd.morph == "bífida" and pd.extra.get("interpeak_ms", 0) >= 40
        p1 = bd.leads["V1"].p if "V1" in bd.leads else None
        morris = p1 is not None and p1.extra.get("neg_depth") is not None and p1.extra["neg_depth"] >= 0.1 \
            and p1.extra.get("neg_dur_ms", 0) >= 40
        # P >= 120 ms in D2 is enough on its own (SBC 2022), as is the Morris index (AHA 2009 Part V)
        lae_ctx = gm.sokolow_lyon_mv is not None and gm.sokolow_lyon_mv > 3.5   # isolated P >= 120 ms counts only with LVH voltage
        if (p_long and (bifid or lae_ctx)) or morris:
            if p_long:
                ev_l.append(f"P em D2 com {pII.p_duration_ms:.0f} ms (>120)")
            if bifid:
                ev_l.append(f"P bífida em D2 (intervalo entre picos {pd.extra['interpeak_ms']:.0f} ms)")
            if morris:
                ev_l.append(f"índice de Morris: componente negativo terminal em V1 {p1.extra['neg_depth']*10:.1f} mm x "
                            f"{p1.extra['neg_dur_ms']:.0f} ms")
        for l in ("II", "III", "aVF"):
            a = g(l, "p_amplitude_mv")
            if a is not None and a >= 0.25:
                ev_r.append(f"P de {a*10:.1f} mm em {LEAD_PRETTY.get(l, l)} (>=2,5 mm)")
        if ev_l:
            out.append(_f("ecg.lae", "Sobrecarga atrial esquerda", "abnormal", ev_l, [R_SBC, R_GOLD], 0.5))
        if ev_r:
            out.append(_f("ecg.rae", "Sobrecarga atrial direita", "abnormal", ev_r, [R_SBC, R_GOLD], 0.5))

    # ---- ventricular hypertrophy (AHA/ACCF/HRS 2009 Part V; SBC 2022)
    # Sokolow-Lyon >35 mm (>45 mm below 40 y, where voltage criteria lose specificity); R V5/V6 >26 mm;
    # Cornell (S V3 + R aVL) >28 mm men / >20 mm women, which on its own over-calls (measurement of S V3 /
    # R aVL is the least reliable) and so needs lateral repolarisation strain (ST depression / T inversion
    # in >=1 of I, aVL, V4-V6) to be called LVH; voltage-only Cornell / R aVL > 11 mm stays "limítrofe".
    sl, cn = gm.sokolow_lyon_mv, gm.cornell_mv
    age_, sex_ = c.get("age"), c.get("sex")
    sl_thr = 3.5 if (age_ is None or age_ >= 40) else 4.5
    cn_thr = 2.8 if sex_ == "M" else (2.0 if sex_ == "F" else 2.4)
    r56 = max([bd.leads[l].r_max for l in ("V5", "V6") if l in bd.leads], default=0.0)
    ravl = bd.leads["aVL"].r_max if "aVL" in bd.leads else 0
    strain_l = [l for l in ("I", "aVL", "V4", "V5", "V6") if l in L and (
        (L[l].st_j60_mv is not None and L[l].st_j60_mv <= -0.05) or
        (L[l].t_amplitude_mv is not None and L[l].t_amplitude_mv <= -0.1))]
    strong, weak = [], []
    if sl is not None and sl > sl_thr:
        # E4: < 40 anos a voltagem de Sokolow-Lyon sozinha e achado limitrofe; so vira HVE com strain lateral
        (strong if (age_ is None or age_ >= 40 or strain_l) else weak).append(
            f"Sokolow-Lyon {sl*10:.0f} mm (>{sl_thr*10:.0f} mm)")
    if r56 > LVH_R56_MV:
        strong.append(f"R em V5/V6 {r56*10:.0f} mm (>{LVH_R56_MV*10:.0f} mm)")
    if cn is not None and cn > cn_thr:
        (strong if strain_l else weak).append(
            f"Cornell {cn*10:.0f} mm (>{cn_thr*10:.0f} mm" + (", homens >28 / mulheres >20)" if sex_ is None else ")"))
    if ravl > 1.1:
        weak.append(f"R em aVL {ravl*10:.0f} mm (>11 mm)")
    if strong:
        ev_l = strong + weak + ([f"alteração de ST-T lateral ({pl(strain_l)})"] if strain_l else [])
        out.append(_f("ecg.lvh", "Sobrecarga ventricular esquerda (critérios de voltagem)", "abnormal", ev_l,
                      [R_SBC, R_GOLD], 0.6 if strain_l else 0.5))
    elif weak:
        out.append(_f("ecg.lvh_voltage", "Voltagem elevada isolada (critério único limítrofe para sobrecarga "
                      "ventricular esquerda)", "borderline", weak, [R_SBC, R_GOLD], 0.35))
    rules_lvh.apply_lvh(c, out)   # Romhilt-Estes/indices, strain, HCM pattern; sets c["lvh_strain"]
    # RVH (AHA 2009 Part V): R in V1 >= 7 mm with R > S, or R/S > 1 with R >= 5 mm plus right axis > 110 deg;
    # with complete RBBB (terminal R' mimics it) the right axis > 110 deg is also required; not scored with
    # pre-excitation (delta wave).
    rv = []
    if "V1" in bd.leads and not any(f.code == "ecg.preexcitation" for f in out):
        r1, s1 = bd.leads["V1"].r_max, -bd.leads["V1"].s_min
        rbbb_ok = c["bbb"] != "rbbb" or (ax is not None and ax > 110)
        if r1 >= 0.7 and r1 > s1 and rbbb_ok:
            rv.append(f"R em V1 {r1*10:.0f} mm (>=7 mm) com R/S {r1/max(s1, 1e-3):.1f} (>1)")
        elif r1 > s1 and r1 >= 0.5 and ax is not None and ax > 110:
            rv.append(f"R/S em V1 {r1/max(s1, 1e-3):.1f} (>1), R {r1*10:.0f} mm (>=5 mm)")
            rv.append(f"eixo do QRS {ax:.0f}° (>110°)")
    if rv:
        out.append(_f("ecg.rvh", "Sobrecarga ventricular direita", "abnormal", rv, [R_AHA, R_SBC], 0.45))

    # ---- QT
    # The global QT (earliest QRS onset to latest T offset over 12 leads) is biased long by one noisy T offset;
    # the decision uses the median per-lead QT (>=6 leads), and for QRS >=120 ms the QT is reduced by the QRS
    # excess over 100 ms (JT-based correction; AHA 2009 Part IV). Report keeps the global value.
    qtc_val = None
    if gm.qtc_bazett_ms is not None and gm.rr_mean_ms:
        qts = sorted(m.qt_ms for m in L.values() if m.qt_ms)
        qt_dec = float(qts[len(qts) // 2]) if len(qts) >= 6 else float(gm.qt_ms)
        qt_dec -= QT_ONSET_COMP_MS   # E2 moved QRS onset ~10 ms earlier: keep the QTc thresholds calibrated
        lq_qt = sorted(m.qrs_ms for m in L.values() if m.qrs_ms)
        qrs_adj = float(np.median(lq_qt)) if len(lq_qt) >= 6 else qrs   # E4: lead median (global is earliest/latest)
        if qrs_adj >= 120:
            qt_dec -= qrs_adj - 100
        rr_s = gm.rr_mean_ms / 1000.0
        qt_baz, qt_fri = qt_dec / rr_s ** 0.5, qt_dec / rr_s ** (1 / 3)
        qt_lim = QTC_LIM_F if c.get("sex") == "F" else QTC_LIM_M   # E4: mulher > 460, homem > 450 (ms)
        use_fr = hr is not None and (hr < 60 or hr > 100)
        qtc_val = qt_fri if use_fr else qt_baz
        nm = "Fridericia" if use_fr else "Bazett"
        evq = [f"QT {gm.qt_ms:.0f} ms (global), {qt_dec:.0f} ms (mediana das derivações, ajustada ao QRS)",
               f"QTc {nm} {qtc_val:.0f} ms (Bazett {qt_baz:.0f}, Fridericia {qt_fri:.0f})",
               f"limiares: >{qt_lim:.0f} limítrofe ({'mulher' if c.get('sex') == 'F' else 'homem/sexo não informado'}), >470 alterado, >500 crítico"]
        if qtc_val > qt_lim:
            sev = "critical" if qtc_val > 500 else ("abnormal" if qtc_val > 470 else "borderline")
            out.append(_f("ecg.long_qt", "QT longo", sev, evq, [R_SBC, R_GOLD], 0.6))
        elif qtc_val <= 340:
            out.append(_f("ecg.short_qt", "QT curto", "abnormal", evq[:2] + ["QTc <= 340 ms"], [R_SBC, R_GOLD], 0.5))

    # ---- ST elevation / depression
    ste, std = {}, {}
    noisy = set(rules_st.noisy_leads(bd, c.get("quality")))   # ST/Q abstention on noisy leads (R3 T5-T1)
    c["st_q_skipped"] = [l for l in L if l in noisy]
    for l, m in L.items():
        if l == "aVR" or m.st_j_mv is None or l in noisy:
            continue
        thr = ste_threshold_mv(l, c.get("age"), c.get("sex"))
        if m.st_j_mv >= thr - 1e-9 and rules_st.ste_confirmed(m.st_j_mv, m.st_j60_mv):
            ste[l] = m.st_j_mv
        j60, j80 = m.st_j60_mv, m.st_j80_mv
        # horizontal/downsloping depression: J+60 (and J+80 when available) below -STD_MV, ST not rising
        if j60 is not None and j60 <= -STD_MV and (j80 is None or j80 <= -STD_MV) and m.st_j_mv <= 0.02 \
                and (j80 is None or j80 <= j60 + 0.03):
            std[l] = j60
    caution = []
    # Secondary repolarisation changes of bundle branch block are expected (AHA 2009 Part III/IV): with LBBB the
    # ST-T of every lead is discordant to the QRS; with RBBB it is V1-V3. They are not reported as ischaemia.
    # Only the EXPECTED discordant pattern is dropped: with RBBB that is ST depression / T inversion in V1-V3
    # (discordant to the terminal R'). ST ELEVATION in V1-V3 is not expected with RBBB (and may be Brugada-like
    # or ischaemic), so it stays a finding (still downgraded + cautioned by the wide-QRS rule below).
    sec_leads = set(L) if c["bbb"] == "lbbb" else ({"V1", "V2", "V3"} if c["bbb"] in ("rbbb", "irbbb") else set())
    suppressed = [l for l in set(ste) | set(std) if l in sec_leads and (c["bbb"] == "lbbb" or l in std)]
    for l in suppressed:
        if c["bbb"] == "lbbb":
            ste.pop(l, None)
        std.pop(l, None)
    # Strain leads: STD is suppressed only if it is mild, lateral and not accompanied by ischaemic signs
    # (rules_lvh.strain_std_suppressed); otherwise it is reported as a normal ST depression.
    strain_ls = set(c.get("lvh_strain", ()))
    std_all, ste_all = dict(std), dict(ste)
    strain_supp = {l for l in strain_ls if l in std_all and rules_lvh.strain_std_suppressed(
        l, strain_ls, c.get("indices") or {}, std_all, ste_all)}
    for l in strain_supp:
        std.pop(l, None)
    if strain_ls and any(l in std for l in strain_ls) and not strain_supp:
        out[:] = [f for f in out if f.code != "ecg.secondary_repolarization_lvh"]
    if c["bbb"] in ("lbbb", "rbbb", "irbbb"):
        caution.append("interpretar com cautela na presença de bloqueio de ramo")
    if any(f.code == "ecg.lvh" for f in out) or rules_lvh.has_voltage_hve(c.get("indices") or {}):
        caution.append("pode ser secundário à sobrecarga ventricular")
    hve_v = rules_lvh.has_voltage_hve(c.get("indices") or {})
    s_min = {l: bd.leads[l].s_min for l in bd.leads}
    # QRS width from leads without STE: an elevated plateau inflates the J/offset of the leads that carry it
    _w = [m.qrs_ms for l, m in L.items() if l not in ste and m.qrs_ms]
    qrs_ref = float(np.median(_w)) if len(_w) >= 4 else gm.qrs_ms
    for name, lds in territories(list(ste)):
        why = rules_st.ste_downgrade_reason(qrs_ref, hve_v, {l: ste[l] for l in lds}, s_min)
        recip = rules_st.reciprocal_depression(name, std)
        ev = [f"ST em J: " + ", ".join(f"{LEAD_PRETTY.get(l, l)} +{ste[l]*10:.1f} mm" for l in lds),
              "J e J+60 elevados; limiar UDMI-4: >=1 mm (V2-V3: homem <40 a >=2,5 mm, homem >=40 a >=2 mm, mulher >=1,5 mm; sexo/idade desconhecidos: >=2 mm)"]
        if recip:
            ev.append("depressão recíproca de ST presente")
        if c["bbb"] in ("rbbb", "irbbb") and {"V1", "V2", "V3"} & set(lds):
            ev.append("supra em V1-V3 não esperado no BRD; considerar IAM anterior/padrão Brugada")
        if why:
            out.append(_f("ecg.st_elevation_" + name, f"Supradesnivelamento do segmento ST limítrofe/inespecífico ({name}: {pl(lds)})",
                          "borderline", ev + [why] + caution, [R_UDMI, R_SBC], 0.35))
            continue
        out.append(_f("ecg.st_elevation_" + name, f"Supradesnivelamento do segmento ST sugestivo ({name}: {pl(lds)})",
                      "critical", ev + caution, [R_UDMI, R_SBC], 0.75 if recip else 0.6))
    for name, lds in territories(list(std)):
        out.append(_f("ecg.st_depression_" + name, f"Infradesnivelamento do segmento ST ({name}: {pl(lds)})",
                      "abnormal", ["ST em J+60: " + ", ".join(f"{LEAD_PRETTY.get(l, l)} {std[l]*10:.1f} mm" for l in lds),
                                   "limiar UDMI-4: >=0,5 mm em 2 derivações contíguas"] + caution,
                      [R_UDMI, R_SBC], 0.55))

    # ---- pathological Q
    qpos = {}
    for l in ["I", "II", "aVL", "aVF", "V2", "V3", "V4", "V5", "V6"]:
        if l not in L or l in noisy or (c["bbb"] == "lbbb" and l in ("V2", "V3")):  # QS in V1-V3 is part of LBBB
            continue
        m = L[l]
        if m.q_amplitude_mv is None:
            continue
        qa, qd = abs(m.q_amplitude_mv), m.q_duration_ms or 0
        rr_ = m.r_amplitude_mv or 0
        isqs = (m.morphology == "QS" and l in ("V2", "V3") and qa >= Q_AMP_MV)
        # UDMI-4 / AHA 2009 Part VI: Q >= 30 ms and >= 1 mm (>= 20 ms in V2-V3); or QS in V2-V3. The ratio
        # criterion (Q >= 25% of R) needs a deep Q (>= 2 mm) to avoid septal q waves.
        qd_min = Q_DUR_V23_MS if l in ("V2", "V3") else Q_DUR_MS
        if (qd >= qd_min and qa >= Q_AMP_MV) or (qa >= Q_RATIO * rr_ and qa >= Q_RATIO_MIN_MV) or isqs:
            qpos[l] = (qa, qd)
    for name, lds in territories(list(qpos)):
        out.append(_f("ecg.pathologic_q_" + name, f"Ondas Q patológicas ({name}: {pl(lds)})", "abnormal",
                      ["; ".join(f"{LEAD_PRETTY.get(l, l)} Q {qpos[l][0]*10:.1f} mm / {qpos[l][1]:.0f} ms" for l in lds),
                       "critério: Q >=40 ms e >=1 mm, ou >=25% da R, em 2 derivações contíguas"],
                      [R_UDMI, R_SBC], 0.5))

    # ---- low voltage
    def pp(l):
        return bd.leads[l].r_max - bd.leads[l].s_min
    limb = [pp(l) for l in ("I", "II", "III", "aVR", "aVL", "aVF") if l in bd.leads]
    prec = [pp(l) for l in ("V1", "V2", "V3", "V4", "V5", "V6") if l in bd.leads]
    if len(limb) == 6 and max(limb) < 0.5:
        out.append(_f("ecg.low_voltage", "Baixa voltagem do QRS nas derivações dos membros", "abnormal",
                      [f"amplitude máxima QRS nos membros {max(limb)*10:.1f} mm (<5 mm)"], [R_SBC, R_GOLD], 0.6))
    elif len(prec) == 6 and max(prec) < 1.0:
        out.append(_f("ecg.low_voltage_precordial", "Baixa voltagem do QRS nas derivações precordiais", "borderline",
                      [f"amplitude máxima QRS precordial {max(prec)*10:.1f} mm (<10 mm)"], [R_SBC], 0.5))

    # ---- T inversion
    tinv = {l: L[l].t_amplitude_mv for l in ("I", "II", "aVL", "aVF", "V2", "V3", "V4", "V5", "V6")
            if l in L and L[l].t_amplitude_mv is not None and L[l].t_amplitude_mv <= -TINV_MV and l not in sec_leads
            and l not in c.get("lvh_strain", ())}
    if suppressed or (sec_leads and any(L[l].t_amplitude_mv is not None and L[l].t_amplitude_mv <= -TINV_MV
                                        for l in sec_leads if l in L)):
        out.append(_f("ecg.secondary_repolarization", "Alterações secundárias da repolarização ventricular "
                      "(esperadas com o bloqueio de ramo)", "borderline",
                      ["ST-T discordante do QRS, não interpretado como isquemia"], [R_AHA, R_SBC], 0.5))
    for name, lds in territories(list(tinv)):
        # E4: T invertida isolada em V2-V3 de mulher < 40 anos = variante habitual (limitrofe)
        variant = c.get("sex") == "F" and c.get("age") is not None and c["age"] < 40 and set(lds) <= {"V1", "V2", "V3"}
        out.append(_f("ecg.t_inversion_" + name, f"Inversão da onda T ({name}: {pl(lds)})",
                      "borderline" if variant else "abnormal",
                      ["T: " + ", ".join(f"{LEAD_PRETTY.get(l, l)} {tinv[l]*10:.1f} mm" for l in lds),
                       "limiar: T <= -1 mm em 2 derivações contíguas"] + caution, [R_UDMI, R_SBC, R_GOLD], 0.5))

    # ---- pacemaker (spike detected on the raw signal): the paced QRS invalidates the morphology rules
    pc = c.get("paced")
    if pc:
        vent = pc["type"] in ("ventricular", "dual")
        drop = ("ecg.sinus_rhythm", "ecg.within_normal_limits")
        if vent:
            drop += ("ecg.st_elevation_", "ecg.st_depression_", "ecg.pathologic_q_", "ecg.t_inversion_", "ecg.lbbb",
                     "ecg.rbbb", "ecg.irbbb", "ecg.ilbbb", "ecg.ivcd", "ecg.secondary_repolarization", "ecg.lafb",
                     "ecg.lpfb", "ecg.left_axis", "ecg.right_axis", "ecg.lvh", "ecg.rvh", "ecg.preexcitation",
                     "ecg.long_qt", "ecg.short_qt")
        out = [f for f in out if not f.code.startswith(drop)]
        kind_pt = {"ventricular": "ventricular", "atrial": "atrial", "dual": "atrioventricular"}[pc["type"]]
        ev = [f"{pc['n_spikes']} espículas estreitas (<= 6 ms) multiderivação no sinal bruto",
              f"espícula precede o QRS em ~{pc['delay_ms']:.0f} ms"]
        if vent:
            ev.append("QRS alargado estimulado: critérios de isquemia/bloqueio de ramo não aplicáveis")
        out.append(_f("ecg.paced_rhythm", f"Ritmo de marca-passo {kind_pt} (sugestivo)", "abnormal", ev,
                      [R_AHA], 0.45 if pc.get("relaxed") else 0.7))

    # ST/isquemia não avaliável de forma confiável com BRE, marca-passo ventricular ou QRS largo (só aviso: os
    # critérios de Sgarbossa/Smith são decisão clínica e NÃO são implementados aqui).
    why_st = _st_not_assessable_reasons(out, pc, gm.qrs_ms, c["bbb"])
    if why_st:
        out.append(_f(ST_NOT_ASSESSABLE_CODE, "Isquemia/supradesnivelamento de ST não avaliável de forma confiável "
                      "com este padrão (considerar critérios de Sgarbossa/Smith; avaliação médica)",
                      "borderline", why_st, [R_AHA, R_UDMI], 0.9))

    # Isolated borderline observations (SBC 2022 "limítrofe"/variants) do not make an ECG abnormal.
    abn = [f for f in out if f.severity in ("abnormal", "critical")]
    if not abn:
        bl = [f.label for f in out if f.severity == "borderline" and f.code != ST_NOT_ASSESSABLE_CODE]
        out.append(_f("ecg.within_normal_limits", NORMAL_LABEL,
                      "normal", ["nenhuma regra de anormalidade foi acionada"] +
                      ([f"achados limítrofes isolados: {'; '.join(bl)}"] if bl else []), [R_GOLD], 0.5))
    return out
