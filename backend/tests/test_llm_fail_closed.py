"""R2: falha FECHADA das barreiras de texto de IA (ECG validate_report, RX sanitize_report): exceção -> a narrativa é
descartada (nunca texto cru), regras/medidas ficam, a limitação é explícita e o log não carrega o texto."""
import logging

from app import llm
from app.rx import claim_check
from app.schemas import (AIReport, BodyRegion, Differential, ECGAnalysis, Finding, RXAnalysis, RXImageAnalysis,
                         RXMeasurement, RXView)

CRU = "TEXTO-CRU-SEM-LASTRO: sem isquemia aguda, ECG normal."
LIMITACAO = "barreira de verificação falhou: narrativa descartada"


def _rep_crua() -> AIReport:
    return AIReport(available=True, model="m", description=CRU,
                    findings=[Finding(code="ia.x", label=CRU, severity="critical", evidence=[CRU])],
                    differentials=[Differential(diagnosis=CRU, rationale=CRU)],
                    disagreements_with_measurements=[CRU], laudo={"texto": CRU}, laudo_markdown=CRU,
                    laudo_curto=CRU, limitations=["limitação prévia"])


def _sem_texto_cru(rep: AIReport) -> None:
    assert CRU not in rep.model_dump_json()
    assert rep.description == "" and rep.findings == [] and rep.differentials == []
    assert rep.laudo is None and rep.laudo_markdown == "" and rep.laudo_curto == ""
    assert any(LIMITACAO in x for x in rep.limitations)
    assert "limitação prévia" in rep.limitations


def test_llm_ecg_validate_report_excecao_descarta_narrativa(monkeypatch, caplog):
    c = llm._client
    monkeypatch.setattr(c, "make_client", lambda: object())
    monkeypatch.setattr(c, "run_resilient", lambda *a, **k: ("etapa", object(), "prov"))
    monkeypatch.setattr(c, "parse_json", lambda t: {})
    monkeypatch.setattr(llm, "to_report", lambda *a, **k: _rep_crua())

    def boom(*a, **k):
        raise RuntimeError(CRU)

    monkeypatch.setattr(llm, "validate_report", boom)
    with caplog.at_level(logging.DEBUG, logger="medlens.llm"):
        out = llm._two_stage("ecg", [], "ctx", {"qualquer": 1}, [])
    _sem_texto_cru(out)
    assert CRU not in caplog.text


def test_llm_rx_sanitize_report_excecao_descarta_narrativa(monkeypatch, caplog):
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    monkeypatch.setenv("MEDLENS_RX_IMAGE_AI", "off")
    monkeypatch.setattr(llm, "_two_stage", lambda *a, **k: _rep_crua())

    def boom(*a, **k):
        raise RuntimeError(CRU)

    monkeypatch.setattr(claim_check, "sanitize_report", boom)
    img = RXImageAnalysis(instance_id="i1", view=RXView.PA, region=BodyRegion.CHEST, image_png_b64="", width=64,
                          height=64, measurements=[RXMeasurement(key="cardiothoracic_ratio", label="ICT",
                                                                 value=0.46)])
    with caplog.at_level(logging.DEBUG, logger="medlens.llm"):
        out = llm.rx_report(RXAnalysis(study_id="s1", images=[img]))
    _sem_texto_cru(out)
    assert CRU not in caplog.text
    assert any("Imagem NÃO enviada" in x for x in out.limitations)  # limitações do fluxo seguem


def test_llm_ecg_validate_report_ok_nao_descarta(monkeypatch):
    c = llm._client
    monkeypatch.setattr(c, "make_client", lambda: object())
    monkeypatch.setattr(c, "run_resilient", lambda *a, **k: ("etapa", object(), "prov"))
    monkeypatch.setattr(c, "parse_json", lambda t: {})
    monkeypatch.setattr(llm, "to_report", lambda *a, **k: AIReport(available=True, description="FC 72 bpm."))
    monkeypatch.setattr(llm, "validate_report", lambda rep, s, rf: rep)
    out = llm._two_stage("ecg", [], "ctx", {"qualquer": 1}, [])
    assert out.description == "FC 72 bpm."
