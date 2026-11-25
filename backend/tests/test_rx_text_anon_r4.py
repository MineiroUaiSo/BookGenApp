"""R4 T3: o texto do RX enviado a IA sem consentimento de imagem tambem passa pela barreira LGPD e sai anonimizado
(sem study_id, UIDs, datas nem idade exata; idade so por faixa). Sem rede (run_resilient substituido)."""
import re

import pydicom
import pytest

from app import llm
from app.llm import client as C
from app.llm.anon import age_band
from app.rx import analyze_image
from app.schemas import RXAnalysis
from test_burned_text import _base

STUDY = "STUDY-ZX9981"
UID = "1.2.840.113619.2.55.3.604688119.971.1234567890.123"
DICOM_TAGS = re.compile(r"\(\s*[0-9A-Fa-f]{4}\s*,\s*[0-9A-Fa-f]{4}\s*\)|PatientName|PatientID|PatientBirthDate|"
                        r"StudyInstanceUID|SOPInstanceUID|SeriesInstanceUID|AccessionNumber|StudyDate|InstitutionName")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("MEDLENS_RX_IMAGE_AI", raising=False)
    monkeypatch.delenv("MEDLENS_BURNED_TEXT", raising=False)


@pytest.fixture
def capturado(monkeypatch):
    chamadas = []

    def fake_run(client, system, messages, max_tokens, schema=None, **kw):
        chamadas.append({"system": system, "messages": messages})
        raise C.LLMProviderError("stop")

    monkeypatch.setattr(llm._client, "make_client", lambda: object())
    monkeypatch.setattr(llm._client, "run_resilient", fake_run)
    return chamadas


def _texto(o):
    if isinstance(o, str):
        return o
    if isinstance(o, dict):
        return " ".join(_texto(v) for v in o.values())
    if isinstance(o, (list, tuple)):
        return " ".join(_texto(v) for v in o)
    return ""


def _analysis(warnings=(), instance=UID):
    ds = pydicom.Dataset()
    ds.BurnedInAnnotation = "NO"
    img = analyze_image(_base(), instance, ds)
    return RXAnalysis(study_id=STUDY, images=[img], warnings=list(warnings))


def test_rx_texto_sem_consentimento_nao_leva_study_id_uid_data_nem_idade_exata(capturado):
    a = _analysis(warnings=[f"estudo {STUDY} instancia {UID}", "paciente de 63 anos, exame em 12/03/2024"])
    llm.rx_report(a)
    payload = _texto(capturado[0]["messages"]) + " " + _texto(capturado[0]["system"])
    assert STUDY not in payload and UID not in payload and "1.2.840" not in payload
    assert "12/03/2024" not in payload and "63 anos" not in payload
    assert "60-69 anos" in payload


def test_rx_payload_nao_contem_nenhuma_tag_dicom(capturado):
    llm.rx_report(_analysis())
    payload = _texto(capturado[0]["messages"])
    assert not DICOM_TAGS.search(payload), DICOM_TAGS.search(payload)


def test_rx_assert_text_only_obrigatorio_mesmo_sem_imagem(capturado, monkeypatch):
    vistos = []
    real = llm.assert_text_only
    monkeypatch.setattr(llm, "assert_text_only", lambda s, u: vistos.append((s, u)) or real(s, u))
    llm.rx_report(_analysis(), send_images=False)
    assert len(vistos) == 1


def test_rx_texto_com_cpf_e_barrado_antes_do_provedor_sem_imagem(capturado):
    rep = llm.rx_report(_analysis(warnings=["CPF 123.456.789-09 no cabecalho"]), send_images=False)
    assert capturado == []
    assert rep.available is False
    assert any("LGPD" in lim for lim in rep.limitations), rep.limitations


@pytest.mark.parametrize("n,faixa", [(5, "0-9 anos"), (17, "10-19 anos"), (63, "60-69 anos"), (101, "90+ anos")])
def test_age_band(n, faixa):
    assert age_band(n) == faixa
