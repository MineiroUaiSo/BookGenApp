"""Barreira LGPD em TODA chamada ao provedor (run_resilient): imagem/base64 em texto, CPF, datas, e-mail,
telefone BR, CNS/RG. Sem rede (cliente falso); valores clínicos (mm, ms, bpm...) nunca são bloqueados."""
import json

import pytest

import laudo_fixtures as F
from app import llm
from app.ecg import features as FT
from app.llm import client as C
from app.llm import laudo as L
from test_llm import FakeClient, _ecg, _png

try:
    from app.llm import guard as G
except ImportError:      # RED: módulo ainda não existe
    G = None

VENENOS = {
    "data-uri": "data:image/png;base64,AAAA",
    "base64-longo": "A" * 250,
    "png-base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk",
    "jpeg-base64": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgF",
    "cpf-formatado": "CPF 529.982.247-25",
    "cpf-sem-pontuacao": "documento 52998224725",
    "data-barra": "nasc 01/02/1960",
    "data-hifen": "exame em 12-03-2024",
    "data-ponto": "coleta 12.03.2024",
    "data-iso": "realizado 2024-03-12",
    "data-iso-hora": "2024-03-12T10:30:00",
    "data-extenso": "em 12 de março de 2024",
    "data-extenso-sem-ano": "dia 5 de janeiro",
    "mes-ano": "internado em março de 2024",
    "email": "contato fulano@example.com",
    "telefone-ddd": "tel (27) 99876-5432",
    "telefone-mais55": "tel +55 27 99876-5432",
    "telefone-ddd-fixo": "tel (27) 3345-6789",
    "cns": "cartão 898000123000000",
    "cns-espacado": "cartão 898 0001 2300 0000",
    "cns-rotulado": "CNS: 123456",
    "rg-pontuado": "identidade 12.345.678-9",
    "rg-rotulado": "RG 1234567",
    "exame": "ORDER ECG22125996",
}

CLINICOS = [
    "QRS 112 ms", "PR 148 ms", "FC 68 bpm", "calibração 25 mm/s e 10 mm/mV", "ST J -1 mm", "Sokolow-Lyon 60 mm",
    "Cornell (produto) 6496 mm.ms (limiar 2440; preenche)", "QTc (Bazett) 482 ms", "RR 882 ms", "ICT 0,52",
    "V2: R 12 mm, S 10 mm", "Romhilt-Estes 4 pontos (limiar provavel 4/definida 5; não preenche)",
    "eixo do QRS 20 graus", "intervalo de 110-119 ms", "pressão 120/80", "razão ST/S <= -0,25", "Fridericia 455 ms",
    "Resolução 1024x768", "Ann Emerg Med 2012;60:766", "Arq Bras Cardiol 2022;119(4):638-680", "idade 67 anos",
    "ID F26 e C1", "pixel 0.45 mm", "01/02", "1-2 mm", "2019-2023 revisões",
]


def _chamar(client, user, **kw):
    return C.run_resilient(client, [{"type": "text", "text": "sistema"}], [{"role": "user", "content": user}],
                           C.MAX_TOKENS_LAUDO, **kw)


def _fake(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return FakeClient(["{}"])


# ---------------------------------------------------------------- ponto único: run_resilient
@pytest.mark.parametrize("nome", sorted(VENENOS))
def test_run_resilient_bloqueia_identificacao_no_texto_do_usuario_sem_chamar_o_provedor(monkeypatch, nome):
    fake = _fake(monkeypatch)
    with pytest.raises(L.PayloadBloqueado):
        _chamar(fake, "dados: " + VENENOS[nome])
    assert fake.calls == []


@pytest.mark.parametrize("nome", ["cpf-formatado", "data-extenso", "email"])
def test_run_resilient_bloqueia_identificacao_no_system_e_em_blocos_de_texto(monkeypatch, nome):
    fake = _fake(monkeypatch)
    with pytest.raises(L.PayloadBloqueado):
        C.run_resilient(fake, [{"type": "text", "text": "x " + VENENOS[nome]}],
                        [{"role": "user", "content": "ok"}], 100)
    with pytest.raises(L.PayloadBloqueado):
        C.run_resilient(fake, [{"type": "text", "text": "sistema"}],
                        [{"role": "user", "content": [{"type": "text", "text": "ok"},
                                                      {"type": "text", "text": VENENOS[nome]}]}], 100)
    assert fake.calls == []


def test_run_resilient_aceita_bloco_de_imagem_estruturado_quando_permitido(monkeypatch):
    fake = _fake(monkeypatch)
    msg = [{"role": "user", "content": [{"type": "text", "text": "plot"}, C.image_block(_png())]}]
    C.run_resilient(fake, [{"type": "text", "text": "sistema"}], msg, 100, allow_images=True)
    assert len(fake.calls) == 1


def test_run_resilient_sem_flag_rejeita_bloco_de_imagem_e_nao_chama_o_provedor(monkeypatch):
    """Padrão seguro: imagem só sai com allow_images=True explícito."""
    fake = _fake(monkeypatch)
    msg = [{"role": "user", "content": [{"type": "text", "text": "plot"}, C.image_block(_png())]}]
    with pytest.raises(L.PayloadBloqueado):
        C.run_resilient(fake, [{"type": "text", "text": "sistema"}], msg, 100)
    assert fake.calls == []


def test_run_resilient_sem_imagens_rejeita_bloco_de_imagem(monkeypatch):
    fake = _fake(monkeypatch)
    msg = [{"role": "user", "content": [{"type": "text", "text": "plot"}, C.image_block(_png())]}]
    with pytest.raises(L.PayloadBloqueado):
        C.run_resilient(fake, [{"type": "text", "text": "sistema"}], msg, 100, allow_images=False)
    assert fake.calls == []


def test_two_stage_passa_allow_images_true_explicitamente(monkeypatch):
    """O caminho v1 (ECG/RX com imagem) segue enviando a imagem, mas pedindo isso de forma explícita."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    vistos = []

    def fake_run(client, system, messages, max_tokens, schema=None, **kw):
        vistos.append(kw.get("allow_images"))
        raise C.LLMProviderError("stop")

    monkeypatch.setattr(llm._client, "make_client", lambda: object())
    monkeypatch.setattr(llm._client, "run_resilient", fake_run)
    llm._two_stage("rx", [("img", _png())], "contexto")
    assert vistos and all(v is True for v in vistos)


def test_base64_dentro_de_bloco_de_imagem_nao_dispara_o_falso_positivo_de_base64_em_texto(monkeypatch):
    fake = _fake(monkeypatch)
    msg = [{"role": "user", "content": [C.image_block(_png((300, 300))), {"type": "text", "text": "legenda"}]}]
    C.run_resilient(fake, [{"type": "text", "text": "sistema"}], msg, 100, allow_images=True)
    assert len(fake.calls) == 1


@pytest.mark.parametrize("texto", CLINICOS)
def test_run_resilient_nao_bloqueia_valores_clinicos(monkeypatch, texto):
    fake = _fake(monkeypatch)
    _chamar(fake, "medidas: " + texto)
    assert len(fake.calls) == 1


def test_run_resilient_nao_bloqueia_ficha_v2_nem_prompts_do_caso1(monkeypatch):
    fake = _fake(monkeypatch)
    ficha = FT.features_from_summary(F.CASO1_OK, sexo="M")
    C.run_resilient(fake, [{"type": "text", "text": L.system_prompt_v2()}],
                    [{"role": "user", "content": L.user_message_v2(ficha)}], 100)
    C.run_resilient(FakeClient(["{}"]), [{"type": "text", "text": L.system_prompt()}],
                    [{"role": "user", "content": L.user_message(F.CASO1_OK)}], 100)
    assert len(fake.calls) == 1


# ---------------------------------------------------------------- caminhos reais: v1 (_two_stage, _laudo_call) e v2
def _setup_v1(monkeypatch, outputs, laudo="0"):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("MEDLENS_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("MEDLENS_LAUDO", laudo)
    monkeypatch.delenv("MEDLENS_LAUDO_V2", raising=False)
    fake = FakeClient(outputs)
    monkeypatch.setattr(C, "make_client", lambda: fake)
    return fake


def test_two_stage_v1_bloqueia_identificacao_no_contexto_e_nao_envia_nada(monkeypatch):
    fake = _setup_v1(monkeypatch, ["{}", "{}"])
    monkeypatch.setattr(llm, "_user_context", lambda *a, **k: "paciente nasc 01/02/1960")
    rep = llm.ecg_report(_ecg(), _png())
    assert fake.calls == []
    assert rep.available is False and "bloquead" in " ".join(rep.limitations).lower()


def test_two_stage_v1_continua_enviando_o_plot_renderizado(monkeypatch):
    desc = "descrição do traçado"
    resposta = json.dumps({"description": "d", "findings": [], "differentials": [],
                           "disagreements_with_measurements": [], "limitations": []})
    fake = _setup_v1(monkeypatch, [desc, resposta])
    rep = llm.ecg_report(_ecg(), None)
    assert len(fake.calls) == 2 and rep.available
    assert "image" in json.dumps(fake.calls[0]["messages"])


def test_laudo_call_v1_bloqueia_identificacao_e_nao_chama_o_provedor(monkeypatch):
    resposta = json.dumps({"description": "d", "findings": [], "differentials": [],
                           "disagreements_with_measurements": [], "limitations": []})
    fake = _setup_v1(monkeypatch, [resposta, resposta, "{}"], laudo="1")
    monkeypatch.setattr(L, "user_message", lambda summary: "ENTRADA exame 12 de março de 2024")
    rep = llm.ecg_report(_ecg(), None)
    assert len(fake.calls) == 2           # só as duas etapas do v1; a 3a chamada (laudo) foi barrada
    assert rep.laudo is None


def test_v2_chamada_real_rejeita_bloco_de_imagem_mesmo_se_a_guarda_do_laudo_for_contornada(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("MEDLENS_LAUDO", "1")
    monkeypatch.setenv("MEDLENS_LAUDO_V2", "1")
    fake = FakeClient(["{}"])
    monkeypatch.setattr(C, "make_client", lambda: fake)
    monkeypatch.setattr(L, "assert_text_only", lambda s, u: None)            # guarda do laudo desligada
    monkeypatch.setattr(L, "user_message_v2", lambda f: "ENTRADA data:image/png;base64,AAAA")
    rep = llm.ecg_report(_ecg(), _png())
    assert fake.calls == []
    assert rep.laudo is not None and rep.laudo["abstencao"] is not None


def test_guard_modulo_unico_expoe_scan_e_mantem_api_do_laudo():
    assert G is not None
    assert L.PayloadBloqueado is G.PayloadBloqueado
    with pytest.raises(G.PayloadBloqueado):
        L.assert_text_only("s", "u 01/02/1960")
