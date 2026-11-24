"""Cardiac conduction timeline mapped to the ECG of a representative beat.

Times (ms) are relative to the global P-wave onset of that beat (SA phase is slightly negative);
with no P wave (atrial fibrillation) they are relative to R - 200 ms.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..schemas import ConductionPhase, Finding, GlobalMeasurements, Wave, WaveKind


def _pick_beat(waves: list[Wave]) -> list[Wave]:
    groups: dict[int, list[Wave]] = {}
    for w in waves:
        groups.setdefault(w.beat_index, []).append(w)
    ok = [k for k, g in groups.items() if any(w.kind == WaveKind.QRS for w in g)]
    if not ok:
        return []
    if -1 in ok:
        return groups[-1]
    ok.sort()
    return groups[ok[len(ok) // 2]]


def _span(ws: list[Wave], rel=0.6):
    ws = [w for w in ws if w.onset_ms is not None and w.offset_ms is not None]
    if not ws:
        return None
    mx = max(abs(w.amplitude_mv or 0) for w in ws)
    sig = [w for w in ws if abs(w.amplitude_mv or 0) >= rel * mx] or ws
    return min(w.onset_ms for w in sig), max(w.offset_ms for w in sig)


def conduction_timeline(gm: GlobalMeasurements, waves: list[Wave],
                        findings: Optional[list[Finding]] = None) -> list[ConductionPhase]:
    codes = {f.code for f in (findings or [])}
    beat = _pick_beat(waves)
    rhythm = (gm.rhythm or "")
    af = "ecg.atrial_fibrillation" in codes or rhythm.startswith("Fibrilação")
    qrs = _span([w for w in beat if w.kind == WaveKind.QRS], rel=0.0)
    p = _span([w for w in beat if w.kind == WaveKind.P])
    t = _span([w for w in beat if w.kind == WaveKind.T])
    if qrs is None:
        if gm.qrs_ms is None:
            return []
        pr = gm.pr_ms or 160.0
        qrs = (pr, pr + gm.qrs_ms)
        p = (0.0, gm.p_duration_ms or 90.0) if gm.pr_ms else None
        t = (qrs[1] + 60, gm.qt_ms + (qrs[0]) if gm.qt_ms else qrs[1] + 280)
    qon, qoff = qrs
    if p is None or af:
        r = np.median([w.peak_ms for w in beat if w.kind == WaveKind.QRS and w.peak_ms is not None] or [qon + 40])
        origin = r - 200.0
        p0, p1 = origin, max(origin + 40.0, qon - 60.0)
        has_p = False
    else:
        origin, (p0, p1), has_p = p[0], p, True
    R = lambda x: round(float(x - origin), 1)
    pr_seg = max(qon - p1, 0.0)
    hv = min(50.0, 0.55 * pr_seg)
    qd = qoff - qon
    t_off = t[1] if t else qoff + 280.0
    ph: list[ConductionPhase] = []

    ph.append(ConductionPhase(
        structure="SA", start_ms=R(p0 - 20), end_ms=R(p0), ecg_correlate="invisível no ECG (antecede a onda P)",
        note=("Despolarização espontânea das células marca-passo do nó sinusal; o impulso não é visível no ECG de "
              "superfície e precede a onda P em ~20 ms."
              if has_p else "Sem onda P: não há ativação sinusal organizada identificável."),
        abnormal=not has_p))
    if af:
        atria_note = ("Fibrilação atrial: ativação atrial caótica e desorganizada (>350/min); não há contração "
                      "atrial coordenada nem onda P, apenas atividade fibrilatória de linha de base.")
    elif "ecg.lae" in codes or "ecg.rae" in codes:
        atria_note = ("Despolarização atrial (átrio direito primeiro, depois esquerdo) = onda P. Há sinais de "
                      "sobrecarga atrial: P alargada/bífida (AE) ou apiculada (AD).")
    else:
        atria_note = ("Despolarização dos átrios, do direito para o esquerdo (feixe de Bachmann) = onda P; a "
                      "duração normal é <120 ms.")
    ph.append(ConductionPhase(structure="atria", start_ms=R(p0), end_ms=R(p1), ecg_correlate="onda P" if has_p else "ausente",
                              note=atria_note, abnormal=af or "ecg.lae" in codes or "ecg.rae" in codes))
    av_abn, av_note = False, ("Retardo fisiológico no nó AV (condução decremental), ~70% do segmento PR; protege os "
                              "ventrículos de frequências atriais altas e permite o enchimento ventricular.")
    if "ecg.av_block_1" in codes:
        av_abn, av_note = True, (f"Bloqueio AV de 1º grau: condução no nó AV prolongada (PR {gm.pr_ms:.0f} ms >200 ms); "
                                 "todos os impulsos atriais chegam aos ventrículos, porém com retardo.")
    elif "ecg.av_block_3" in codes:
        av_abn, av_note = True, ("Bloqueio AV total: nenhum impulso atrial atravessa o nó AV/His; átrios e ventrículos "
                                 "batem independentes (dissociação AV) e o ritmo ventricular é de escape. A relação "
                                 "temporal mostrada é apenas ilustrativa.")
    elif any(c.startswith("ecg.av_block_2") for c in codes):
        av_abn, av_note = True, ("Bloqueio AV de 2º grau: alguns impulsos atriais não são conduzidos "
                                 "(Mobitz I: fadiga progressiva do nó AV com PR crescente; Mobitz II: falha súbita, "
                                 "geralmente infranodal). Batimento ilustrado é um batimento conduzido.")
    elif "ecg.preexcitation" in codes:
        av_abn, av_note = True, ("Pré-excitação: parte da ativação ventricular passa por via acessória (feixe de Kent) "
                                 "que contorna o retardo do nó AV, encurtando o PR e produzindo a onda delta.")
    elif "ecg.short_pr" in codes:
        av_abn, av_note = True, "PR curto: condução AV acelerada ou via acessória/juncional."
    elif af:
        av_note = ("Nó AV recebe bombardeio atrial caótico e conduz de forma irregular (condução decremental "
                   "variável), gerando RR irregularmente irregular.")
    ph.append(ConductionPhase(structure="AV_node", start_ms=R(p1), end_ms=R(qon - hv), ecg_correlate="segmento PR",
                              note=av_note, abnormal=av_abn))
    ph.append(ConductionPhase(structure="His", start_ms=R(qon - hv), end_ms=R(qon), ecg_correlate="final do segmento PR (intervalo HV)",
                              note="Feixe de His e troncos dos ramos: condução rápida (HV ~35-55 ms), silenciosa no ECG de "
                                   "superfície.", abnormal="ecg.av_block_2_mobitz2" in codes))
    early = min(40.0, 0.4 * qd)
    rb_note = "Ramo direito ativa o septo direito e o ventrículo direito."
    lb_note = ("Ramo esquerdo (fascículos anterossuperior, posteroinferior e septal) ativa o septo esquerdo "
               "(vetor septal inicial, q em V5-V6) e o ventrículo esquerdo.")
    rb_end, lb_end, rb_abn, lb_abn = qon + early, qon + early, False, False
    if "ecg.rbbb" in codes or "ecg.irbbb" in codes:
        rb_abn, rb_end = True, qoff
        rb_note = ("Bloqueio de ramo direito: o ramo direito conduz lentamente/não conduz; o VD é ativado tardiamente "
                   "por condução célula a célula a partir do VE (R' em V1, S empastada em D1/V6).")
    if "ecg.lbbb" in codes or "ecg.ilbbb" in codes:
        lb_abn, lb_end = True, qoff
        lb_note = ("Bloqueio de ramo esquerdo: o VE é ativado tardiamente por condução célula a célula a partir do VD "
                   "(QRS alargado, R monofásica em D1/V5-V6, septo ativado da direita para a esquerda).")
    if "ecg.lafb" in codes:
        lb_abn = True
        lb_note += " Há bloqueio do fascículo anterossuperior (desvio do eixo para a esquerda)."
    if "ecg.lpfb" in codes:
        lb_abn = True
        lb_note += " Há bloqueio do fascículo posteroinferior (desvio do eixo para a direita)."
    ph.append(ConductionPhase(structure="LBB", start_ms=R(qon), end_ms=R(lb_end), ecg_correlate="início do QRS",
                              note=lb_note, abnormal=lb_abn))
    ph.append(ConductionPhase(structure="RBB", start_ms=R(qon), end_ms=R(rb_end), ecg_correlate="início do QRS",
                              note=rb_note, abnormal=rb_abn))
    ph.append(ConductionPhase(structure="purkinje", start_ms=R(qon + 10), end_ms=R(qon + min(60.0, 0.6 * qd)),
                              ecg_correlate="início/meio do QRS",
                              note="Rede de Purkinje distribui o impulso ao endocárdio; despolarização subendocárdio → "
                                   "subepicárdio.", abnormal=rb_abn or lb_abn))
    ph.append(ConductionPhase(structure="ventricles_depol", start_ms=R(qon), end_ms=R(qoff), ecg_correlate="complexo QRS",
                              note=f"Despolarização ventricular (QRS {qd:.0f} ms; normal <100-110 ms)."
                                   + (" Alargado: ativação ventricular lenta." if qd >= 120 else ""),
                              abnormal=qd >= 120))
    ph.append(ConductionPhase(structure="ventricles_repol", start_ms=R(qoff), end_ms=R(t_off), ecg_correlate="segmento ST e onda T",
                              note="Repolarização ventricular (platô → fase 3), do epicárdio ao endocárdio: segmento ST "
                                   "(J → início da T) e onda T; o fim da T define o QT."
                                   + (" Alterações de ST/T detectadas." if any(c.startswith(("ecg.st_", "ecg.t_inv")) for c in codes) else ""),
                              abnormal=any(c.startswith(("ecg.st_", "ecg.t_inv", "ecg.long_qt", "ecg.short_qt")) for c in codes)))
    return ph
