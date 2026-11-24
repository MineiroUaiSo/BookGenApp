"""Validador pós-LLM com saídas de LLM fabricadas (sem rede)."""
import json

from app import llm
from app.llm import validate as V
from app.llm.schema import to_report
from app.schemas import Finding

ECG_SUMMARY = {
    "medidas_globais": {"heart_rate_bpm": 72, "pr_ms": 210, "qrs_ms": 96, "qt_ms": 400, "qtc_bazett_ms": 438,
                        "rr_mean_ms": 833, "sokolow_lyon_mv": 2.8},
    "medidas_por_derivacao": [{"lead": "V2", "st_j_mv": 0.05, "r_amplitude_mv": 1.2}],
    "achados_por_regras": [{"code": "ecg.av_block_1", "label": "BAV 1º grau", "severity": "abnormal",
                            "evidence": ["PR 210 ms"]}],
}
RX_SUMMARY = {
    "imagens": [{"medidas": [{"key": "cardiothoracic_ratio", "label": "ICT", "value": 0.45},
                             {"key": "tracheal_deviation_mm", "label": "desvio", "value": 2.0, "unit": "mm"}],
                 "probabilidades_modelo_auxiliar": {"Pneumothorax": 0.1, "Cardiomegaly": 0.2}}],
    "achados_por_regras": [{"code": "rx.cardiothoracic_ratio_normal", "label": "ICT normal", "severity": "normal"}],
}


def _rep(desc="", findings=None, diffs=None):
    return to_report({"description": desc, "findings": findings or [], "differentials": diffs or [],
                      "disagreements_with_measurements": [], "limitations": []}, "m")


def _f(code, label, ev=(), sev="abnormal", conf=0.9):
    return {"code": code, "label": label, "severity": sev, "evidence": list(ev), "references": [], "confidence": conf}


def test_numbers_matching_measurements_are_not_flagged():
    rep = V.validate_report(_rep("PR de 214 ms e QRS 100 ms, FC 74 bpm."), ECG_SUMMARY)
    assert rep.validation["numeros_divergentes"] == 0 and rep.validation["numeros_conferem"] == 3
    assert "⚠" not in rep.description and rep.disagreements_with_measurements == []


def test_divergent_ms_is_marked_in_sentence_and_listed():
    rep = V.validate_report(_rep("O intervalo PR mede 280 ms. Ritmo regular."), ECG_SUMMARY)
    assert rep.validation["numeros_divergentes"] == 1
    assert "[⚠ valor 280 ms não confere com a medida PR 210 ms]" in rep.description
    assert "Ritmo regular." in rep.description
    assert any("280 ms" in d and "210 ms" in d for d in rep.disagreements_with_measurements)


def test_divergent_bpm_and_tolerances():
    ok = V.validate_report(_rep("FC 76 bpm."), ECG_SUMMARY)
    bad = V.validate_report(_rep("FC 110 bpm."), ECG_SUMMARY)
    assert ok.validation["numeros_divergentes"] == 0
    assert bad.validation["numeros_divergentes"] == 1


def test_finding_evidence_divergence_flags_item():
    rep = V.validate_report(_rep(findings=[_f("ecg.wide_qrs", "QRS largo", ["QRS 150 ms"])]), ECG_SUMMARY)
    f = rep.findings[0]
    assert V.FLAG_DIVERGENT in f.validation_flags and "⚠" in f.evidence[0]


def test_reference_ranges_and_grid_constants_ignored():
    txt = "PR normal 120-200 ms. Grade 25 mm/s, 1 mm = 40 ms. QRS acima de 120 ms é alargado."
    rep = V.validate_report(_rep(txt), ECG_SUMMARY)
    v = rep.validation
    assert v["numeros_conferem"] + v["numeros_divergentes"] + v["numeros_nao_verificaveis"] == 0


def test_ict_ratio_checked():
    ok = V.validate_report(_rep("ICT 0,46."), RX_SUMMARY)
    bad = V.validate_report(_rep("Índice cardiotorácico de 0,62."), RX_SUMMARY)
    pct = V.validate_report(_rep("ICT de 45%."), RX_SUMMARY)
    assert ok.validation["numeros_divergentes"] == 0 and ok.validation["numeros_conferem"] == 1
    assert bad.validation["numeros_divergentes"] == 1
    assert pct.validation["numeros_conferem"] == 1


def test_rx_mm_checked_and_ecg_mm_uses_mv_times_ten():
    assert V.validate_report(_rep("Desvio traqueal de 8 mm."), RX_SUMMARY).validation["numeros_divergentes"] == 1
    assert V.validate_report(_rep("Desvio traqueal de 2,3 mm."), RX_SUMMARY).validation["numeros_divergentes"] == 0
    assert V.validate_report(_rep("R de 12 mm em V2."), ECG_SUMMARY).validation["numeros_divergentes"] == 0
    assert V.validate_report(_rep("Onda R de 30 mm."), ECG_SUMMARY).validation["numeros_divergentes"] == 1


def test_unverifiable_when_no_measurement():
    rep = V.validate_report(_rep("Área de 40 %."), ECG_SUMMARY)
    assert rep.validation["numeros_nao_verificaveis"] == 1 and rep.validation["numeros_divergentes"] == 0


def test_critical_without_support_is_not_corroborated():
    rep = V.validate_report(_rep(findings=[_f("llm.iam", "Supradesnivelamento de ST em V2 (IAM)", sev="critical")],
                                 diffs=[{"diagnosis": "Taquicardia ventricular", "rationale": "r", "supporting": [],
                                         "against": [], "references": [], "confidence": 0.9}]), ECG_SUMMARY)
    assert V.FLAG_UNSUPPORTED in rep.findings[0].validation_flags
    assert "não corroborado" in rep.findings[0].label
    assert V.FLAG_UNSUPPORTED in rep.differentials[0].validation_flags
    assert rep.validation["criticos_sem_lastro"] == 2
    assert any("sem regra/escore de apoio" in d for d in rep.disagreements_with_measurements)


def test_critical_with_rule_support_is_kept():
    summ = dict(ECG_SUMMARY, achados_por_regras=[{"code": "ecg.st_elevation_V2", "label": "Supra ST V2",
                                                  "severity": "critical"}])
    rep = V.validate_report(_rep(findings=[_f("ecg.st_elevation_V2", "Supradesnivelamento de ST")]), summ)
    assert rep.validation["criticos_sem_lastro"] == 0 and rep.findings[0].validation_flags == []


def test_negated_critical_in_description_is_ignored():
    rep = V.validate_report(_rep("Sem supradesnivelamento de ST. Pneumotórax descartado."), ECG_SUMMARY)
    assert rep.validation["criticos_sem_lastro"] == 0


def test_description_critical_without_support_counts():
    rep = V.validate_report(_rep("Há pneumotórax à direita."), RX_SUMMARY)
    assert rep.validation["criticos_sem_lastro"] == 1


def test_cardiomegaly_support_by_ctr_and_unsupported_when_normal():
    unsup = V.validate_report(_rep(findings=[_f("llm.cm", "Cardiomegalia")]), RX_SUMMARY)
    assert unsup.validation["criticos_sem_lastro"] == 1
    big = {"imagens": [{"medidas": [{"key": "cardiothoracic_ratio", "value": 0.58}]}], "achados_por_regras": []}
    sup = V.validate_report(_rep(findings=[_f("llm.cm", "Cardiomegalia")]), big)
    assert sup.validation["criticos_sem_lastro"] == 0


def test_fa_alta_resposta_needs_rule_and_hr():
    f = [_f("llm.fa", "Fibrilação atrial de alta resposta ventricular")]
    assert V.validate_report(_rep(findings=f), ECG_SUMMARY).validation["criticos_sem_lastro"] == 1
    summ = {"medidas_globais": {"heart_rate_bpm": 140},
            "achados_por_regras": [{"code": "ecg.atrial_fibrillation", "label": "FA", "severity": "abnormal"}]}
    assert V.validate_report(_rep(findings=f), summ).validation["criticos_sem_lastro"] == 0


def test_says_normal_with_critical_rule_alerts():
    summ = dict(ECG_SUMMARY, achados_por_regras=[{"code": "ecg.av_block_3", "label": "BAV total",
                                                  "severity": "critical"}])
    rep = V.validate_report(_rep("ECG dentro dos limites da normalidade."), summ)
    assert rep.validation["normal_com_regra_critica"] == 1
    assert any(x.startswith("ALERTA") for x in rep.disagreements_with_measurements)
    assert any(x.startswith("ALERTA") for x in rep.limitations)


def test_normal_without_critical_rule_no_alert():
    rep = V.validate_report(_rep("ECG normal."), ECG_SUMMARY)
    assert rep.validation["normal_com_regra_critica"] == 0


def test_self_declared_confidence_not_shown_as_number():
    rule = Finding(code="ecg.av_block_1", label="BAV 1", confidence=0.77, origin="rules")
    rep = V.validate_report(_rep(findings=[_f("ecg.av_block_1", "BAV 1º grau", conf=0.99),
                                           _f("llm.x", "Outro", conf=0.95)],
                                 diffs=[{"diagnosis": "d", "rationale": "", "supporting": [], "against": [],
                                         "references": [], "confidence": 0.9}]), ECG_SUMMARY, [rule])
    a, b = rep.findings
    assert a.confidence == 0.77 and a.confidence_source == "rules" and a.confidence_display is None
    assert b.confidence == 0.0 and b.confidence_source == "n/a" and b.confidence_display == "não aplicável"
    assert rep.differentials[0].confidence_display == "não aplicável"


def test_unavailable_report_untouched():
    from app.schemas import AIReport
    rep = AIReport(available=False)
    assert V.validate_report(rep, ECG_SUMMARY) is rep


def test_pipeline_applies_validator(monkeypatch):
    from tests.test_llm import FakeClient, _ecg, _png
    out = {"description": "PR de 300 ms.", "findings": [_f("llm.iam", "IAM com supra de ST")],
           "differentials": [], "disagreements_with_measurements": [], "limitations": []}
    fake = FakeClient(["desc", json.dumps(out)])
    monkeypatch.setattr(llm._client, "make_client", lambda: fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    rep = llm.ecg_report(_ecg(), _png())
    assert rep.validation["numeros_divergentes"] == 1 and rep.validation["criticos_sem_lastro"] == 1
    assert rep.findings[0].confidence_display == "não aplicável"
