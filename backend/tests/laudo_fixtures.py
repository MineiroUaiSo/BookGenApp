"""Fixtures do laudo de ECG: entradas estruturadas (fabricadas) + respostas de LLM gravadas/fabricadas.

Nenhum dado de paciente: valores sintéticos. O caso1 reproduz os FATOS do gabarito de cardiologista
(sem texto copiado): R/S, índices de HVE, P 120 ms e cabeçalho impresso PR 148/QRS 112/QT 438/QTc 482.
"""
from __future__ import annotations

import copy
import json


def _lead(lead, **kw):
    return {"lead": lead, **kw}


def _summary(g, leads=(), rules=(), printed=None, **extra):
    s = {"fonte": "digitalizado", "fs_hz": 500, "duracao_s": 10, "calibracao": "10 mm/mV, 25 mm/s",
         "medidas_globais": g, "medidas_por_derivacao": list(leads),
         "achados_por_regras": list(rules), "avisos": []}
    if printed:
        s["cabecalho_impresso"] = printed
    s.update(extra)
    return s


def _resp(**kw):
    base = {"aviso_topo": [], "qualidade_tecnica": "Traçado de qualidade adequada, 10 mm/mV e 25 mm/s.",
            "ritmo_frequencia": "", "intervalos": "", "qtc_formula": "Bazett", "eixos": "", "onda_p": "",
            "complexo_qrs": "", "st_t": "", "comparacao": "Sem ECG anterior para comparação.",
            "impressao": [], "limitrofes": [], "recomendacao": ""}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


# ------------------------------------------------------------------ few-shot 1: normal
NORMAL = _summary(
    {"heart_rate_bpm": 72, "rr_mean_ms": 833, "pr_ms": 160, "qrs_ms": 92, "qt_ms": 380, "qtc_bazett_ms": 416,
     "p_axis_deg": 45, "qrs_axis_deg": 50, "t_axis_deg": 40, "p_duration_ms": 100, "rhythm": "sinusal regular"},
    leads=[_lead("II", p_duration_ms=100, r_amplitude_mv=1.2, t_amplitude_mv=0.3, st_j_mv=0.0),
           _lead("V1", s_amplitude_mv=-0.9, r_amplitude_mv=0.2), _lead("V5", r_amplitude_mv=1.6, st_j_mv=0.0)])
NORMAL_RESP = _resp(
    ritmo_frequencia="Ritmo sinusal regular, frequência cardíaca de 72 bpm.",
    intervalos="PR 160 ms, QRS 92 ms, QT 380 ms, QTc 416 ms.",
    eixos="Eixo de P 45 graus, de QRS 50 graus e de T 40 graus, dentro do esperado.",
    onda_p="Onda P de 100 ms em D2, sem sinais de sobrecarga atrial.",
    complexo_qrs="QRS estreito, sem ondas Q patológicas nem critérios de voltagem para hipertrofia.",
    st_t="Segmento ST isoelétrico e ondas T concordantes, sem alterações por território.",
    impressao=["ECG dentro dos limites da normalidade."],
    recomendacao="Correlação clínica.")

# ------------------------------------------------------------------ few-shot 2: IAM com supra de ST
IAM = _summary(
    {"heart_rate_bpm": 84, "rr_mean_ms": 714, "pr_ms": 150, "qrs_ms": 96, "qt_ms": 360, "qtc_bazett_ms": 425,
     "p_axis_deg": 50, "qrs_axis_deg": 30, "t_axis_deg": 60, "rhythm": "sinusal regular"},
    leads=[_lead("V2", st_j_mv=0.3), _lead("V3", st_j_mv=0.35), _lead("V4", st_j_mv=0.25),
           _lead("III", st_j_mv=-0.1), _lead("aVF", st_j_mv=-0.1)],
    rules=[{"code": "ecg.st_elevation_anterior", "label": "Supra de ST anterior", "severity": "critical",
            "evidence": ["supra de ST de 3 mm em V2-V3"]}])
IAM_RESP = _resp(
    ritmo_frequencia="Ritmo sinusal regular, 84 bpm.",
    intervalos="PR 150 ms, QRS 96 ms, QT 360 ms, QTc 425 ms.",
    eixos="Eixo de QRS 30 graus.",
    st_t="Supradesnivelamento do segmento ST na parede anterior (V2 a V4) com infra de ST recíproco em D3 e aVF.",
    impressao=["Supradesnivelamento de ST em parede anterior, compatível com IAM com supra de ST (STEMI) até prova em contrário.",
               "Alteração recíproca em parede inferior."],
    recomendacao="Correlação clínica imediata e conduta conforme protocolo de síndrome coronariana aguda.")

# ------------------------------------------------------------------ few-shot 3: FA
FA = _summary(
    {"heart_rate_bpm": 118, "rr_mean_ms": 508, "rr_sd_ms": 180, "pr_ms": None, "qrs_ms": 88, "qt_ms": 320,
     "qtc_bazett_ms": 440, "qrs_axis_deg": 20, "rhythm": "irregularmente irregular"},
    leads=[_lead("V1", morphology="sem onda P definida")],
    rules=[{"code": "ecg.atrial_fibrillation", "label": "Fibrilação atrial", "severity": "abnormal",
            "evidence": ["RR irregular, sem onda P"]}])
FA_RESP = _resp(
    ritmo_frequencia="Ritmo irregularmente irregular, sem ondas P definidas, frequência ventricular média de 118 bpm.",
    intervalos="QRS 88 ms, QT 320 ms, QTc 440 ms; PR não mensurável.",
    eixos="Eixo de QRS 20 graus.",
    onda_p="Ausência de onda P organizada; atividade atrial fibrilatória.",
    complexo_qrs="QRS estreito.",
    impressao=["Fibrilação atrial com resposta ventricular elevada (118 bpm)."],
    recomendacao="Correlação clínica e avaliação de anticoagulação conforme escore de risco.")

# ------------------------------------------------------------------ caso-ouro caso1
PRINTED = {"pr_ms": 148, "qrs_ms": 112, "qt_ms": 438, "qtc_ms": 482}
_CASO1_LEADS = [
    _lead("I", r_amplitude_mv=2.4, t_amplitude_mv=-0.3, st_j_mv=-0.1),
    _lead("aVL", r_amplitude_mv=5.0, t_amplitude_mv=-0.4, st_j_mv=-0.1),
    _lead("II", p_duration_ms=120, r_amplitude_mv=1.4),
    _lead("aVF", r_amplitude_mv=1.0, st_j_mv=0.0),
    _lead("V1", s_amplitude_mv=-0.5, r_amplitude_mv=0.2),
    _lead("V2", s_amplitude_mv=-1.0, r_amplitude_mv=1.2),
    _lead("V3", r_amplitude_mv=3.2, s_amplitude_mv=-0.8, t_amplitude_mv=-0.3),
    _lead("V4", r_amplitude_mv=4.8, s_amplitude_mv=-0.4, t_amplitude_mv=-0.4, st_j_mv=-0.1),
    _lead("V5", r_amplitude_mv=5.5, s_amplitude_mv=-0.3, t_amplitude_mv=-0.4, st_j_mv=-0.1),
    _lead("V6", r_amplitude_mv=4.2, s_amplitude_mv=-0.2, t_amplitude_mv=-0.3, st_j_mv=-0.1),
]
CASO1_OK = _summary(
    {"heart_rate_bpm": 68, "rr_mean_ms": 882, "p_duration_ms": 120, "pr_ms": 148, "qrs_ms": 112, "qt_ms": 438,
     "qtc_bazett_ms": 482, "p_axis_deg": 49, "qrs_axis_deg": 20, "t_axis_deg": 171,
     "sokolow_lyon_mv": 6.0, "cornell_mv": 5.8, "rhythm": "sinusal regular"},
    leads=_CASO1_LEADS,
    rules=[{"code": "ecg.lvh_voltage", "label": "Critérios de voltagem para HVE", "severity": "abnormal",
            "evidence": ["Cornell 58 mm", "Sokolow-Lyon 60 mm"]},
           {"code": "ecg.left_atrial_enlargement", "label": "Sobrecarga atrial esquerda", "severity": "borderline",
            "evidence": ["P 120 ms em D2"]},
           {"code": "ecg.qtc_prolonged", "label": "QTc prolongado", "severity": "borderline",
            "evidence": ["QTc 482 ms (QRS 112 ms)"]}],
    printed=PRINTED, indices_calculados={"romhilt_estes_pontos": 6}, contexto={"sexo": "M"})

CASO1_OK_RESP = _resp(
    qualidade_tecnica="Medidas coerentes com o cabeçalho impresso do aparelho (PR 148 ms, QRS 112 ms).",
    ritmo_frequencia="Ritmo sinusal regular, normocárdico, 68 bpm.",
    intervalos="PR 148 ms, QRS 112 ms, QT 438 ms, QTc 482 ms; QTc possivelmente superestimado pela duração do QRS (limítrofe).",
    eixos="Eixo de P 49 graus, de QRS 20 graus e de T 171 graus; sem desvio de eixo do QRS para a esquerda.",
    onda_p="Duração da onda P de 120 ms em D2, sugestiva de aumento atrial esquerdo.",
    complexo_qrs=("Voltagens aumentadas: R de 24 mm em D1 e de 50 mm em aVL; R de 32 a 55 mm de V3 a V6. "
                  "Cornell 58 mm (limite 28 mm em homens) e Sokolow-Lyon 60 mm (limite 35 mm) preenchidos; "
                  "Romhilt-Estes 6 pontos. Critério de Peguero-Lo Presti não preenchido (18 mm), com ondas S baixas nas "
                  "precordiais, o que sugere hipertrofia de distribuição focal."),
    st_t="Infra de ST discreto com onda T invertida assimétrica em D1, aVL e V3 a V6, em padrão de repolarização secundária à sobrecarga (strain), sem regra de isquemia disparada.",
    impressao=["Sobrecarga de câmaras esquerdas (hipertrofia ventricular esquerda com strain e aumento atrial esquerdo).",
               "Padrão eletrocardiográfico sugestivo de miocardiopatia hipertrófica (CMH): correlacionar com ecocardiograma/RM.",
               "Alterações de ST-T interpretadas como repolarização secundária à sobrecarga, não como isquemia."],
    limitrofes=["QTc 482 ms (limítrofe, QRS 112 ms)"],
    recomendacao="Correlação com ecocardiograma ou ressonância magnética e avaliação clínica.")

# versão ERRADA: digitalização divergente do impresso
CASO1_ERRADA = copy.deepcopy(CASO1_OK)
CASO1_ERRADA["medidas_globais"].update({"pr_ms": 88, "qrs_ms": 270})
CASO1_ERRADA["medidas_por_derivacao"] = [dict(m) for m in CASO1_ERRADA["medidas_por_derivacao"]]
for _m in CASO1_ERRADA["medidas_por_derivacao"]:
    if _m["lead"] == "aVF":
        _m["st_j_mv"] = -0.49
CASO1_ERRADA["achados_por_regras"] = [
    {"code": "ecg.wpw_preexcitation", "label": "Pré-excitação ventricular (onda delta)", "severity": "abnormal",
     "evidence": ["PR 88 ms", "QRS 270 ms"]},
    {"code": "ecg.st_depression_inferior", "label": "Infra de ST inferior", "severity": "abnormal",
     "evidence": ["ST -4,9 mm em aVF"]}]
CASO1_ERRADA["avisos"] = ["delineação pouco confiável"]

CASO1_ERRADA_RESP = _resp(
    aviso_topo=["Discordância: PR 88 ms e QRS 270 ms do algoritmo divergem do impresso no aparelho (PR 148 ms, QRS 112 ms); provável erro de digitalização."],
    qualidade_tecnica="Digitalização suspeita; medidas de intervalo e ST não confiáveis.",
    ritmo_frequencia="Ritmo sinusal regular, 68 bpm.",
    intervalos="PR e QRS do algoritmo (88 ms e 270 ms) não confiáveis; considerar os valores impressos (148 ms e 112 ms).",
    eixos="Eixo de QRS 20 graus.",
    complexo_qrs="Voltagens elevadas em derivações laterais (Sokolow-Lyon 60 mm, Cornell 58 mm). Pré-excitação não avaliável com segurança: possível erro de digitalização.",
    st_t="Alterações de ST não avaliáveis com segurança: possível erro de digitalização.",
    impressao=["Medidas do algoritmo discordantes do impresso; achados de condução e de ST não diagnosticados.",
               "Critérios de voltagem para hipertrofia ventricular esquerda presentes."],
    recomendacao="Conferir PR, QRS e ST no traçado original antes de qualquer conclusão.")

# LLM "mal comportada": afirma pré-excitação e isquemia a partir da medida errada
CASO1_ERRADA_BAD_RESP = _resp(
    ritmo_frequencia="Ritmo sinusal regular.",
    intervalos="PR 88 ms e QRS 270 ms.",
    complexo_qrs="Padrão de pré-excitação ventricular com onda delta.",
    st_t="Infra de ST inferior e anterolateral extenso, sugestivo de isquemia miocárdica.",
    impressao=["Síndrome de pré-excitação (WPW).", "Isquemia miocárdica inferior e anterolateral.",
               "Hipertrofia ventricular esquerda por voltagem."])

FEWSHOT = {"normal": (NORMAL, NORMAL_RESP), "iam": (IAM, IAM_RESP), "fa": (FA, FA_RESP)}
