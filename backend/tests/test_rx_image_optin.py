"""RX: envio da IMAGEM à IA na nuvem é opt-in explícito (consentimento por requisição), com chave geral MEDLENS_RX_IMAGE_AI
(optin = padrão | off). Sem consentimento: só medidas/regras. Sem rede (run_resilient substituído)."""
import pydicom
import pytest

from app import llm
from app.llm import client as C
from app.rx import analyze_image
from app.schemas import RXAnalysis
from test_burned_text import CORNER_LINES, _base, _draw

SEM_CONSENTIMENTO = "NÃO enviada"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("MEDLENS_RX_IMAGE_AI", raising=False)
    monkeypatch.delenv("MEDLENS_BURNED_TEXT", raising=False)


def _ds(tag="NO"):
    ds = pydicom.Dataset()
    ds.BurnedInAnnotation = tag
    return ds


def _analysis(img=None, tag="NO"):
    return RXAnalysis(study_id="s", images=[analyze_image(img if img is not None else _base(), "i1", _ds(tag))])


@pytest.fixture
def capturado(monkeypatch):
    """Substitui o provedor: registra cada payload e aborta como erro de provedor (sem rede)."""
    chamadas = []

    def fake_run(client, system, messages, max_tokens, schema=None, **kw):
        chamadas.append({"system": system, "messages": messages, "kw": kw})
        raise C.LLMProviderError("stop")

    monkeypatch.setattr(llm._client, "make_client", lambda: object())
    monkeypatch.setattr(llm._client, "run_resilient", fake_run)
    return chamadas


def _tem_imagem(o):
    if isinstance(o, dict):
        return o.get("type") in ("image", "image_url") or any(_tem_imagem(v) for v in o.values())
    if isinstance(o, (list, tuple)):
        return any(_tem_imagem(v) for v in o)
    return False


def _texto(o):
    if isinstance(o, str):
        return o
    if isinstance(o, dict):
        return " ".join(_texto(v) for v in o.values())
    if isinstance(o, (list, tuple)):
        return " ".join(_texto(v) for v in o)
    return ""


def test_sem_consentimento_nenhuma_imagem_no_payload_e_limitacao_explicita(capturado):
    rep = llm.rx_report(_analysis())
    assert capturado, "análise só por medidas ainda chama o provedor (texto)"
    assert not any(_tem_imagem(c["messages"]) or _tem_imagem(c["system"]) for c in capturado)
    assert all(c["kw"].get("allow_images") in (None, False) for c in capturado)
    assert any(SEM_CONSENTIMENTO in lim for lim in rep.limitations), rep.limitations
    assert not rep.external_ai_blocked


def test_com_consentimento_e_imagem_limpa_envia_a_imagem(capturado):
    llm.rx_report(_analysis(), send_images=True)
    assert capturado and _tem_imagem(capturado[0]["messages"])
    assert capturado[0]["kw"].get("allow_images") is True


def test_com_consentimento_e_texto_queimado_bloqueia_sem_chamar_o_provedor(capturado):
    rep = llm.rx_report(_analysis(tag="YES"), send_images=True)
    assert capturado == [] and rep.external_ai_blocked and rep.available is False


def test_consentimento_com_texto_queimado_detectado_e_nao_mascarado_tambem_bloqueia(capturado, monkeypatch):
    a = _analysis(_draw(_base(), CORNER_LINES))
    a.images[0].external_ai_blocked = True            # detectado e não mascarado com segurança
    rep = llm.rx_report(a, send_images=True)
    assert capturado == [] and rep.external_ai_blocked


def test_burned_text_off_com_consentimento_bloqueia_o_envio_externo(capturado, monkeypatch):
    monkeypatch.setenv("MEDLENS_BURNED_TEXT", "off")
    rep = llm.rx_report(_analysis(), send_images=True)
    assert capturado == []
    assert rep.external_ai_blocked and rep.available is False
    assert any("MEDLENS_BURNED_TEXT" in lim for lim in rep.limitations), rep.limitations


def test_burned_text_off_sem_consentimento_segue_so_com_medidas(capturado, monkeypatch):
    monkeypatch.setenv("MEDLENS_BURNED_TEXT", "off")
    llm.rx_report(_analysis())
    assert capturado and not any(_tem_imagem(c["messages"]) for c in capturado)


def test_chave_geral_off_ignora_o_consentimento(capturado, monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_IMAGE_AI", "off")
    rep = llm.rx_report(_analysis(), send_images=True)
    assert not any(_tem_imagem(c["messages"]) for c in capturado)
    assert any("MEDLENS_RX_IMAGE_AI" in lim for lim in rep.limitations), rep.limitations


@pytest.mark.parametrize("valor,esperado", [("", "optin"), ("optin", "optin"), ("OPTIN", "optin"), ("off", "off"),
                                            ("OFF", "off"), ("0", "off"), ("false", "off"), ("lixo", "optin")])
def test_modo_da_chave(monkeypatch, valor, esperado):
    monkeypatch.setenv("MEDLENS_RX_IMAGE_AI", valor)
    assert llm.rx_image_ai_mode() == esperado


def test_texto_enviado_sem_consentimento_declara_que_nao_ha_imagem(capturado):
    llm.rx_report(_analysis())
    assert "Nenhuma imagem" in _texto(capturado[0]["messages"])


# ---------------------------------------------------------------- API: campo send_images_to_ai (padrão false)
def test_modelo_de_requisicao_tem_send_images_to_ai_false_por_padrao():
    from app.api.analysis import RXAIRequest, RXRequest
    assert RXRequest().send_images_to_ai is False and RXAIRequest().send_images_to_ai is False


def test_api_repassa_o_consentimento_ao_rx_report(monkeypatch):
    from app.api import analysis as A
    vistos = []
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    monkeypatch.setattr(llm, "rx_report", lambda result, send_images=False: vistos.append(send_images) or llm.unavailable())
    vazio = RXAnalysis(study_id="s", images=[])
    A._run_rx_ai(vazio)
    A._run_rx_ai(vazio, send_images=True)
    assert vistos == [False, True]
