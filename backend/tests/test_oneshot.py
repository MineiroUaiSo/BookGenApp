"""P1a: POST /api/oneshot/{ecg|rx}: sem estado, sem IA, modo pediátrico. Nenhum teste usa rede."""
import importlib.util
import io
import json
import logging
import os
import socket
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api import oneshot
from app.main import app
from pediatric_schema import VETADO, textos_filtrados, validar_contrato
from test_pediatric_mode import _ecg, _rx

TOKEN = "t0ken-de-teste-0123456789"
HDR = {"Authorization": f"Bearer {TOKEN}"}
BACKEND = Path(__file__).resolve().parents[1]
MB = 1024 * 1024


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tmp_raiz(tmp_path, monkeypatch):
    """Diretório raiz dos temporários do processo; o oneshot deve deixá-lo vazio."""
    raiz = tmp_path / "tmp-raiz"
    raiz.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(raiz))
    return raiz


@pytest.fixture
def stub_analise(monkeypatch):
    """Troca o motor pesado por análises fixture (os testes de plumbing não digitalizam imagem)."""
    def _stub(tipo, caminho):
        return _ecg() if tipo == "ecg" else _rx()
    monkeypatch.setattr(oneshot, "_analisar", _stub)


def _png(w=64, h=64, valor=120) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.full((h, w), valor, np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


def _post(client, tipo, dados=None, nome="exame.png", conteudo=None, headers=HDR, files=None, **form):
    conteudo = _png() if conteudo is None else conteudo
    files = files if files is not None else [("file", (nome, conteudo, "application/octet-stream"))]
    return client.post(f"/api/oneshot/{tipo}", files=files, data={k: str(v) for k, v in form.items()},
                       headers=headers)


# ------------------------------------------------------------------ autenticação
def test_oneshot_sem_bearer_responde_401(client, stub_analise):
    assert _post(client, "ecg", headers={}, idade_meses=24).status_code == 401


def test_oneshot_token_errado_responde_401(client, stub_analise):
    assert _post(client, "rx", headers={"Authorization": "Bearer errado"}, idade_meses=24).status_code == 401


def test_oneshot_esquema_diferente_de_bearer_responde_401(client, stub_analise):
    assert _post(client, "rx", headers={"Authorization": f"Basic {TOKEN}"}, idade_meses=24).status_code == 401


def test_oneshot_sem_env_do_token_falha_fechada_com_503(client, stub_analise, monkeypatch):
    monkeypatch.delenv("MEDLENS_API_TOKEN")
    assert _post(client, "ecg", idade_meses=24).status_code == 503
    assert _post(client, "ecg", idade_meses=24, headers={"Authorization": "Bearer qualquer"}).status_code == 503


def test_oneshot_compara_token_em_tempo_constante():
    import inspect

    assert "compare_digest" in inspect.getsource(oneshot)


def test_oneshot_token_certo_responde_200(client, stub_analise):
    assert _post(client, "ecg", idade_meses=24).status_code == 200


def test_health_continua_aberto_e_diz_que_nao_ha_estado(client):
    r = client.get("/api/health")
    assert r.status_code == 200


# ------------------------------------------------------------------ diretório temporário
def test_oneshot_apaga_o_diretorio_temporario_depois_da_chamada(client, tmp_raiz, stub_analise):
    assert _post(client, "ecg", idade_meses=24).status_code == 200
    assert list(tmp_raiz.iterdir()) == []


def test_oneshot_apaga_o_diretorio_temporario_mesmo_com_excecao(client, tmp_raiz, monkeypatch):
    vistos = []

    def _boom(tipo, caminho):
        vistos.append((Path(caminho).parent, Path(caminho).exists()))
        raise RuntimeError("falha qualquer")
    monkeypatch.setattr(oneshot, "_analisar", _boom)
    r = _post(client, "ecg", idade_meses=24)
    assert r.status_code == 500 and r.json()["detail"]["codigo"] == "analise_falhou"
    assert vistos and vistos[0][1] is True                    # o arquivo existiu durante a análise
    assert not vistos[0][0].exists() and list(tmp_raiz.iterdir()) == []


def test_oneshot_grava_a_entrada_com_nome_fixo_nunca_o_nome_do_cliente(client, tmp_raiz, monkeypatch):
    nomes = []
    monkeypatch.setattr(oneshot, "_analisar", lambda t, c: (nomes.append(Path(c).name), _ecg())[1])
    _post(client, "ecg", nome="joao_da_silva_prontuario123.png", idade_meses=24)
    assert nomes and "joao" not in nomes[0].lower() and nomes[0].endswith(".png")


def test_oneshot_nao_grava_em_disco_persistente(client, stub_analise, tmp_path, monkeypatch):
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path / "data")
    assert _post(client, "rx", idade_meses=60).status_code == 200
    assert not (tmp_path / "data").exists()


# ------------------------------------------------------------------ tamanho e tipo
def test_arquivo_acima_de_4mb_responde_413(client, stub_analise):
    grande = b"\x89PNG\r\n\x1a\n" + b"\0" * (4 * MB)
    assert _post(client, "ecg", conteudo=grande, idade_meses=24).status_code == 413


def test_corpo_acima_de_4_5mb_responde_413_antes_de_ler(client, stub_analise):
    grande = b"\x89PNG\r\n\x1a\n" + b"\0" * (int(4.6 * MB))
    assert _post(client, "ecg", conteudo=grande, idade_meses=24).status_code == 413


def test_arquivo_no_limite_de_4mb_e_aceito(client, stub_analise):
    base = _png()
    ok = base + b"\0" * (4 * MB - len(base))                  # PNG válido + lixo após o IEND, exatamente 4 MB
    assert _post(client, "ecg", conteudo=ok, idade_meses=24).status_code == 200


@pytest.mark.parametrize("nome", ["a.exe", "a.zip", "a.dcm", "a.pdf", "a.svg", "a.gif", "semextensao", "a.png.exe"])
def test_extensao_nao_permitida_responde_415(client, stub_analise, nome):
    assert _post(client, "rx", nome=nome, idade_meses=24).status_code == 415


@pytest.mark.parametrize("nome,conteudo", [
    ("a.png", b"PK\x03\x04conteudo-de-zip"),
    ("a.jpg", b"\x89PNG\r\n\x1a\n" + b"x" * 20),       # extensão e conteúdo discordam
    ("a.png", b"%PDF-1.7 ..."),
    ("a.jpeg", b"MZ\x90\x00 executavel"),
])
def test_conteudo_que_nao_confere_com_a_extensao_responde_415(client, stub_analise, nome, conteudo):
    assert _post(client, "rx", nome=nome, conteudo=conteudo, idade_meses=24).status_code == 415


@pytest.mark.parametrize("nome", ["a.png", "A.PNG", "a.jpg", "a.JPEG"])
def test_extensoes_permitidas_png_jpg_jpeg(client, stub_analise, nome):
    if nome.lower().endswith("png"):
        conteudo = _png()
    else:
        buf = io.BytesIO()
        Image.fromarray(np.full((8, 8), 90, np.uint8)).save(buf, format="JPEG")
        conteudo = buf.getvalue()
    assert _post(client, "rx", nome=nome, conteudo=conteudo, idade_meses=24).status_code == 200


def test_arquivo_vazio_responde_400(client, stub_analise):
    assert _post(client, "rx", conteudo=b"", idade_meses=24).status_code in (400, 415)


def test_mais_de_um_arquivo_responde_400(client, stub_analise):
    dois = [("file", ("a.png", _png(), "image/png")), ("file", ("b.png", _png(), "image/png"))]
    assert _post(client, "rx", files=dois, idade_meses=24).status_code == 400


def test_sem_arquivo_falha_fechada(client, stub_analise):
    r = client.post("/api/oneshot/rx", data={"idade_meses": "24"}, headers=HDR)
    assert r.status_code in (400, 422)


def test_imagem_com_pixels_demais_responde_413(client, stub_analise, monkeypatch):
    monkeypatch.setattr(oneshot, "MAX_PIXELS", 1000)
    assert _post(client, "rx", conteudo=_png(64, 64), idade_meses=24).status_code == 413


def test_imagem_corrompida_com_cabecalho_valido_responde_422(client):
    r = _post(client, "rx", conteudo=b"\x89PNG\r\n\x1a\n" + b"lixo" * 20, idade_meses=24)
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == "imagem_invalida"


def test_tipo_desconhecido_responde_404(client, stub_analise):
    assert _post(client, "tc", idade_meses=24).status_code == 404


# ------------------------------------------------------------------ idade, sexo, modo
@pytest.mark.parametrize("idade,esperado", [(0, 200), (204, 200), (215, 200), (216, 400), (240, 400), (-1, 400)])
def test_idade_17a11m_passa_e_18_anos_falha_fechado(client, stub_analise, idade, esperado):
    assert _post(client, "ecg", idade_meses=idade).status_code == esperado


def test_idade_17_anos_e_pediatrica_e_18_anos_e_rejeitada(client, stub_analise):
    ok = _post(client, "rx", idade_meses=17 * 12)
    assert ok.status_code == 200 and ok.json()["modo"] == "pediatrico" and ok.json()["idade_meses"] == 204
    rej = _post(client, "rx", idade_meses=18 * 12)
    assert rej.status_code == 400 and rej.json()["detail"]["codigo"] == "idade_fora_da_faixa"
    assert "medidas" not in rej.json()


@pytest.mark.parametrize("valor", ["abc", "1.5", "", "12 meses", "1e2"])
def test_idade_nao_inteira_responde_400(client, stub_analise, valor):
    r = _post(client, "ecg", idade_meses=valor)
    assert r.status_code == 400 or (valor == "" and r.status_code == 200 and r.json()["idade_meses"] is None)


@pytest.mark.parametrize("tipo", ["ecg", "rx"])
def test_idade_ausente_cai_no_modo_pediatrico_sem_classificar(client, stub_analise, tipo):
    r = _post(client, tipo)
    assert r.status_code == 200
    j = r.json()
    validar_contrato(j)
    assert j["modo"] == "pediatrico" and j["idade_meses"] is None
    assert not ({"findings", "laudo"} & set(j))
    assert any("Idade não informada" in a for a in j["avisos"])


def test_modo_adulto_nao_existe_neste_servico(client, stub_analise):
    r = _post(client, "ecg", idade_meses=24, modo="adulto")
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "modo_invalido"
    assert _post(client, "ecg", idade_meses=24, modo="pediatrico").status_code == 200


@pytest.mark.parametrize("sexo,esperado", [("M", 200), ("F", 200), ("", 200), ("X", 400), ("masculino", 400)])
def test_sexo_validado_e_opcional(client, stub_analise, sexo, esperado):
    assert _post(client, "ecg", idade_meses=24, sexo=sexo).status_code == esperado


def test_sexo_nao_aparece_na_resposta(client, stub_analise):
    assert "sexo" not in _post(client, "ecg", idade_meses=24, sexo="F").json()


# ------------------------------------------------------------------ contrato de resposta
@pytest.mark.parametrize("tipo", ["ecg", "rx"])
def test_resposta_passa_no_esquema_estrito_e_no_filtro_de_vocabulario(client, stub_analise, tipo):
    j = _post(client, tipo, idade_meses=36).json()
    validar_contrato(j)
    for t in textos_filtrados(j):
        assert not VETADO.search(t), t
    assert j["tipo"] == tipo and j["idade_meses"] == 36


def test_resposta_pediatrica_nao_tem_valor_nem_classificacao_adulta(client, stub_analise):
    for tipo in ("ecg", "rx"):
        raw = _post(client, tipo, idade_meses=36).text.lower()
        for proibido in ("hipertrofia", "prolongado", "cardiomegalia", "derrame", "severity", "abnormal",
                         "cardiothoracic", "image_png", "sokolow", "fridericia", "ritmo sinusal"):
            assert proibido not in raw, (tipo, proibido)


def test_resposta_vai_sem_cache_e_sem_o_nome_do_arquivo(client, stub_analise):
    r = _post(client, "ecg", nome="maria_souza_cpf123.png", idade_meses=24)
    assert "no-store" in r.headers.get("cache-control", "")
    assert "maria" not in r.text.lower() and "cpf123" not in r.text.lower()


# ------------------------------------------------------------------ sem IA e sem rede
def _bloqueia_rede(monkeypatch):
    def _proibido(*a, **k):
        raise AssertionError("chamada de rede proibida no oneshot")
    monkeypatch.setattr(socket.socket, "connect", _proibido)
    monkeypatch.setattr(socket, "create_connection", _proibido)
    import httpx

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _proibido)           # transporte de rede real
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _proibido)  # (o TestClient usa outro)
    monkeypatch.setattr(httpx, "post", _proibido)


@pytest.mark.parametrize("tipo", ["ecg", "rx"])
def test_nenhuma_chamada_de_llm_nem_de_rede_mesmo_com_chaves_no_ambiente(client, stub_analise, monkeypatch, tipo):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-falsa")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-falsa")
    for flag in ("MEDLENS_DESCRICAO_IA", "MEDLENS_RX_DESCRICAO_IA", "MEDLENS_RX_IMAGE_AI", "MEDLENS_RX_LAUDO_IA",
                 "MEDLENS_LAUDO"):
        monkeypatch.setenv(flag, "1")
    import app.llm as llm

    def _falha(*a, **k):
        raise AssertionError("o LLM não pode ser chamado no oneshot")
    for nome in ("ai_available", "ecg_report", "rx_report", "ecg_descricao_fields"):
        if hasattr(llm, nome):
            monkeypatch.setattr(llm, nome, _falha)
    import app.llm.client as cli

    for nome in dir(cli):
        obj = getattr(cli, nome)
        if isinstance(obj, type) and nome.lower().endswith("client"):
            monkeypatch.setattr(obj, "__init__", _falha)
    _bloqueia_rede(monkeypatch)
    r = _post(client, tipo, idade_meses=24)
    assert r.status_code == 200, r.text


def test_oneshot_nao_importa_o_pacote_llm_no_caminho_do_codigo():
    src = Path(oneshot.__file__).read_text(encoding="utf-8") + Path(
        Path(oneshot.__file__).parents[1] / "pediatric.py").read_text(encoding="utf-8")
    import re

    assert not re.search(r"^\s*(from|import)\s+(app\.llm|anthropic|openai|httpx|requests)", src, re.M)


def _carrega_index(monkeypatch):
    # api/index.py atribui os.environ direto: setenv registra o valor atual (ou a ausência) para o teardown restaurar
    for flag in ("MEDLENS_DESCRICAO_IA", "MEDLENS_RX_DESCRICAO_IA", "MEDLENS_RX_IMAGE_AI", "MEDLENS_RX_LAUDO_IA",
                 "MEDLENS_LAUDO", "MEDLENS_RX_MODELS", "MEDLENS_DATA", "MEDLENS_RETENCAO_HORAS"):
        monkeypatch.setenv(flag, os.environ.get(flag, "x"))
    spec = importlib.util.spec_from_file_location("medlens_api_index", BACKEND / "api" / "index.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(BACKEND))
    spec.loader.exec_module(mod)
    return mod


def test_entrypoint_hospedado_forca_os_flags_de_ia_desligados(monkeypatch):
    for flag in ("MEDLENS_DESCRICAO_IA", "MEDLENS_RX_DESCRICAO_IA", "MEDLENS_RX_IMAGE_AI", "MEDLENS_RX_LAUDO_IA",
                 "MEDLENS_LAUDO"):
        monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("MEDLENS_RX_MODELS", "1")
    _carrega_index(monkeypatch)
    for flag in ("MEDLENS_DESCRICAO_IA", "MEDLENS_RX_DESCRICAO_IA", "MEDLENS_RX_IMAGE_AI", "MEDLENS_RX_LAUDO_IA",
                 "MEDLENS_LAUDO", "MEDLENS_RX_MODELS"):
        assert os.environ[flag] == "0", flag


def test_entrypoint_hospedado_expoe_so_oneshot_e_health(monkeypatch):
    mod = _carrega_index(monkeypatch)
    c = TestClient(mod.app)
    assert c.get("/api/health").status_code == 200
    for rota in ("/api/ingest", "/api/studies", "/api/rule-ppv"):
        assert c.request("POST" if rota == "/api/ingest" else "GET", rota, headers=HDR).status_code in (404, 405)
    assert _post(c, "tc", idade_meses=24).status_code == 404
    assert set(mod.app.openapi()["paths"]) == {"/api/health", "/api/oneshot/{tipo}"}


# ------------------------------------------------------------------ PHI em log e em erro
def test_erro_de_analise_nao_vaza_a_excecao_nem_loga_phi(client, monkeypatch, caplog):
    def _boom(tipo, caminho):
        raise RuntimeError("PACIENTE JOAO DA SILVA 123.456.789-00")
    monkeypatch.setattr(oneshot, "_analisar", _boom)
    with caplog.at_level(logging.DEBUG):
        r = _post(client, "ecg", nome="joao_prontuario.png", idade_meses=24)
    assert r.status_code == 500
    assert "joao" not in r.text.lower() and "123.456" not in r.text
    assert "joao" not in caplog.text.lower() and "123.456" not in caplog.text


def test_chamada_bem_sucedida_nao_loga_nome_do_arquivo_nem_conteudo(client, stub_analise, caplog):
    with caplog.at_level(logging.DEBUG):
        _post(client, "rx", nome="maria_cpf999.png", idade_meses=24)
    assert "maria" not in caplog.text.lower() and "cpf999" not in caplog.text.lower()


def test_oneshot_nao_chama_o_usage_log(client, stub_analise, monkeypatch):
    from app import usage_log

    monkeypatch.setattr(usage_log, "log_event", lambda *a, **k: (_ for _ in ()).throw(AssertionError("log")))
    assert _post(client, "ecg", idade_meses=24).status_code == 200


def test_analise_que_levanta_valueerror_do_motor_vira_422_generico(client, monkeypatch):
    def _ve(tipo, caminho):
        raise ValueError("could not detect the ECG grid (px/mm)")
    monkeypatch.setattr(oneshot, "_analisar", _ve)
    r = _post(client, "ecg", idade_meses=24)
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == "imagem_nao_analisavel"
    assert "grid" not in r.text


def test_resultado_que_viola_o_filtro_vira_502_resultado_bloqueado(client, stub_analise, monkeypatch):
    from app import pediatric

    monkeypatch.setattr(pediatric, "AVISO_PEDIATRICO", "O resultado é normal.")
    r = _post(client, "ecg", idade_meses=24)
    assert r.status_code == 502 and r.json()["detail"]["codigo"] == "resultado_bloqueado"


# ------------------------------------------------------------------ motor real (sem stub)
@pytest.fixture(scope="module")
def ecg_sintetico():
    from synth_ecg import render_paper, synth_signal

    leads, fid = synth_signal(hr=120, fs=500, seconds=10, seed=7)
    img = render_paper(leads, 500, px_per_mm=12)
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="PNG")
    return buf.getvalue(), 120


def test_ecg_sintetico_real_devolve_fc_dentro_de_5_bpm(ecg_sintetico, tmp_raiz, monkeypatch):
    png, hr = ecg_sintetico
    c = TestClient(app)
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    r = _post(c, "ecg", nome="ecg.png", conteudo=png, idade_meses=30, sexo="F")
    assert r.status_code == 200, r.text
    j = r.json()
    validar_contrato(j)
    fc = next(m for m in j["medidas"] if m["codigo"] == "fc")
    assert abs(fc["valor"] - hr) <= 5
    assert {m["codigo"] for m in j["medidas"]} >= {"fc", "rr"}
    assert all("estimada a partir de imagem; conferir no traçado" in m["nota"] for m in j["medidas"])
    assert not ({"findings", "laudo"} & set(j))
    assert list(tmp_raiz.iterdir()) == []


def test_rx_sintetico_real_devolve_so_incidencia_regiao_e_qualidade(tmp_raiz, monkeypatch):
    from fixtures_dicom import _chest_phantom

    arr = _chest_phantom(512, 512, "PA").astype(np.float64)
    arr = (255 * (arr - arr.min()) / max(np.ptp(arr), 1)).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")
    r = _post(TestClient(app), "rx", nome="rx.png", conteudo=buf.getvalue(), idade_meses=84)
    assert r.status_code == 200, r.text
    j = r.json()
    validar_contrato(j)
    assert j["medidas"] == [] and j["regiao"] == "indeterminada" and j["incidencia"] == "indeterminada"
    assert "cardiothoracic" not in r.text and "image_png" not in r.text
    assert any("Índice cardiotorácico não exibido" in a for a in j["avisos"])
    assert list(tmp_raiz.iterdir()) == []


# ------------------------------------------------------------------ RX: região/incidência declaradas
def test_rx_saida_traz_o_que_foi_declarado(client, stub_analise):
    r = _post(client, "rx", idade_meses=60, regiao_declarada="torax", incidencia_declarada="perfil")
    assert r.status_code == 200, r.text
    j = r.json()
    validar_contrato(j)
    assert j["regiao"] == "tórax" and j["incidencia"] == "perfil"


def test_rx_sem_declaracao_sai_indeterminada(client, stub_analise):
    j = _post(client, "rx", idade_meses=60).json()
    assert j["regiao"] == "indeterminada" and j["incidencia"] == "indeterminada"


@pytest.mark.parametrize("campo,valor", [("regiao_declarada", "pulmao"), ("regiao_declarada", "Torax"),
                                         ("incidencia_declarada", "lateral"), ("incidencia_declarada", "PA")])
def test_rx_declaracao_invalida_responde_400(client, stub_analise, campo, valor):
    r = _post(client, "rx", idade_meses=60, **{campo: valor})
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == f"{campo}_invalida"


def test_declaracao_vazia_conta_como_ausente(client, stub_analise):
    j = _post(client, "rx", idade_meses=60, regiao_declarada="", incidencia_declarada="").json()
    assert j["regiao"] == "indeterminada"


def test_ecg_ignora_campos_de_declaracao_do_rx(client, stub_analise):
    r = _post(client, "ecg", idade_meses=24, regiao_declarada="torax")
    assert r.status_code == 200 and "regiao" not in r.json()


def test_18_anos_continua_400_com_declaracao_e_sem_ia(client, stub_analise):
    r = _post(client, "rx", idade_meses=216, regiao_declarada="torax", incidencia_declarada="pa")
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "idade_fora_da_faixa"
