"""Lote P1: PHI antes de uso real (token de API, exclusão de estudo, retenção, teto do _LAST)."""
import os
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import analysis as api_analysis
from app.schemas import SeriesInfo, StudyInfo
from app.store import store

TOKEN = "segredo-de-teste"
REMOTO = ("203.0.113.9", 4321)


def _app():
    from app.main import app

    return app


def _remoto() -> TestClient:
    return TestClient(_app(), client=REMOTO)


def _make_study(study_id: str, age_hours: float = 0.0) -> str:
    """Estudo mínimo no disco (study.json + instância + artefato), com idade simulada.

    A retenção fica desligada durante a criação para que montar o cenário não apague os outros estudos.
    """
    iid = f"{study_id}-abc123"
    anterior = os.environ.get("MEDLENS_RETENCAO_HORAS")
    os.environ["MEDLENS_RETENCAO_HORAS"] = "1000000"
    try:
        store.save_study(StudyInfo(
            study_id=study_id, created_at="2026-11-25T00:00:00Z",
            series=[SeriesInfo(series_uid="s1", modality="ECG", n_instances=1, instance_ids=[iid])],
        ))
    finally:
        if anterior is None:
            os.environ.pop("MEDLENS_RETENCAO_HORAS", None)
        else:
            os.environ["MEDLENS_RETENCAO_HORAS"] = anterior
    store.save_instance(iid, "ecg.dcm", b"x", {"kind": "dicom"})
    store.put_artifact(study_id, "overlay.png", b"png")
    if age_hours:
        _envelhecer(study_id, age_hours)
    return iid


def _envelhecer(study_id: str, horas: float) -> None:
    t = time.time() - horas * 3600
    root = store.root / "studies" / study_id
    for p in [root, *root.rglob("*")]:
        os.utime(p, (t, t))


def _dir(study_id: str):
    return store.root / "studies" / study_id


# ------------------------------------------------------------------ (1) token / loopback
def test_token_definido_sem_header_da_401(client, monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    assert client.get("/api/studies").status_code == 401


def test_token_definido_errado_da_401(client, monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    r = client.get("/api/studies", headers={"Authorization": "Bearer outro"})
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").lower().startswith("bearer")


def test_token_definido_correto_da_200(client, monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    r = client.get("/api/studies", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


def test_token_definido_cliente_remoto_com_token_passa(monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    r = _remoto().get("/api/studies", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


def test_token_definido_cobre_todas_as_rotas_api(client, monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    assert client.post("/api/ingest", files={"files": ("a.txt", b"x")}).status_code == 401
    assert client.post("/api/ecg/x/analyze").status_code == 401
    assert client.delete("/api/studies/x").status_code == 401
    assert client.get("/api/instances/x-1/render.png").status_code == 401


def test_health_continua_aberto_com_token(client, monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert _remoto().get("/api/health").status_code == 200


def test_preflight_cors_nao_exige_token(client, monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    r = client.options("/api/studies", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization"})
    assert r.status_code == 200


def test_sem_token_cliente_remoto_da_403(monkeypatch):
    monkeypatch.delenv("MEDLENS_API_TOKEN", raising=False)
    assert _remoto().get("/api/studies").status_code == 403


def test_sem_token_string_vazia_equivale_a_nao_definido(monkeypatch):
    monkeypatch.setenv("MEDLENS_API_TOKEN", "")
    assert _remoto().get("/api/studies").status_code == 403


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "testclient"])
def test_sem_token_loopback_funciona_como_antes(monkeypatch, host):
    monkeypatch.delenv("MEDLENS_API_TOKEN", raising=False)
    c = TestClient(_app(), client=(host, 5000))
    assert c.get("/api/studies").status_code == 200


def test_sem_token_health_aberto_para_remoto(monkeypatch):
    monkeypatch.delenv("MEDLENS_API_TOKEN", raising=False)
    assert _remoto().get("/api/health").status_code == 200


def test_fluxo_local_sem_token_ingest_continua(client, monkeypatch, dicom_folder):
    monkeypatch.delenv("MEDLENS_API_TOKEN", raising=False)
    pa = dicom_folder / "CHEST" / "pa.dcm"
    r = client.post("/api/ingest", files={"files": ("pa.dcm", pa.read_bytes())})
    assert r.status_code == 200
    assert r.json()["studies"]


# ------------------------------------------------------------------ (2) DELETE
def test_delete_remove_arquivos_e_artefatos(client):
    iid = _make_study("estudo-del")
    assert _dir("estudo-del").exists()
    r = client.delete("/api/studies/estudo-del")
    assert r.status_code in (200, 204)
    assert not _dir("estudo-del").exists()
    assert client.get("/api/studies/estudo-del").status_code == 404
    with pytest.raises(KeyError):
        store.instance_meta(iid)
    assert store.get_artifact("estudo-del", "overlay.png") is None


def test_delete_so_afeta_o_estudo_pedido(client):
    _make_study("estudo-a")
    _make_study("estudo-b")
    client.delete("/api/studies/estudo-a")
    assert not _dir("estudo-a").exists()
    assert _dir("estudo-b").exists()


def test_delete_inexistente_da_404(client):
    assert client.delete("/api/studies/nao-existe").status_code == 404


def test_delete_id_malicioso_nao_toca_o_disco(client, tmp_path):
    _make_study("estudo-ok")
    r = client.delete("/api/studies/..%2F..%2Fstudies")
    assert r.status_code in (404, 405)
    assert _dir("estudo-ok").exists()


def test_delete_limpa_resultado_em_memoria(client):
    _make_study("estudo-mem")
    api_analysis._remember("ecg", "estudo-mem", object(), b"png")
    api_analysis._remember("rx", "estudo-mem", object())
    client.delete("/api/studies/estudo-mem")
    assert ("ecg", "estudo-mem") not in api_analysis._LAST
    assert ("rx", "estudo-mem") not in api_analysis._LAST


def test_delete_exige_token_quando_definido(client, monkeypatch):
    _make_study("estudo-tok")
    monkeypatch.setenv("MEDLENS_API_TOKEN", TOKEN)
    assert client.delete("/api/studies/estudo-tok").status_code == 401
    assert _dir("estudo-tok").exists()
    r = client.delete("/api/studies/estudo-tok", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code in (200, 204)
    assert not _dir("estudo-tok").exists()


# ------------------------------------------------------------------ (3) retenção
def test_retencao_padrao_24h(monkeypatch):
    monkeypatch.delenv("MEDLENS_RETENCAO_HORAS", raising=False)
    _make_study("velho", age_hours=25)
    _make_study("novo", age_hours=23)
    removidos = store.purge_expired()
    assert removidos == ["velho"]
    assert not _dir("velho").exists()
    assert _dir("novo").exists()


def test_retencao_configuravel_por_env(monkeypatch):
    monkeypatch.setenv("MEDLENS_RETENCAO_HORAS", "2")
    _make_study("tres-horas", age_hours=3)
    _make_study("uma-hora", age_hours=1)
    store.purge_expired()
    assert not _dir("tres-horas").exists()
    assert _dir("uma-hora").exists()


@pytest.mark.parametrize("valor", ["abc", "", "0", "-5"])
def test_retencao_valor_invalido_volta_ao_padrao(monkeypatch, valor):
    monkeypatch.setenv("MEDLENS_RETENCAO_HORAS", valor)
    _make_study("de-30h", age_hours=30)
    _make_study("de-2h", age_hours=2)
    store.purge_expired()
    assert not _dir("de-30h").exists()
    assert _dir("de-2h").exists()


def test_retencao_roda_a_cada_upload(monkeypatch):
    monkeypatch.delenv("MEDLENS_RETENCAO_HORAS", raising=False)
    _make_study("vencido", age_hours=48)
    store.save_study(StudyInfo(study_id="recem-chegado", created_at="2026-11-25T00:00:00Z"))
    assert not _dir("vencido").exists()
    assert _dir("recem-chegado").exists()


def test_retencao_no_upload_nao_apaga_o_estudo_sendo_salvo(monkeypatch):
    monkeypatch.setenv("MEDLENS_RETENCAO_HORAS", "1")
    _make_study("reenvio", age_hours=5)
    store.save_study(StudyInfo(study_id="reenvio", created_at="2026-11-25T00:00:00Z"))
    assert (_dir("reenvio") / "study.json").exists()


def test_retencao_no_ingest_http(client, monkeypatch, dicom_folder):
    monkeypatch.delenv("MEDLENS_RETENCAO_HORAS", raising=False)
    monkeypatch.delenv("MEDLENS_API_TOKEN", raising=False)
    _make_study("vencido-http", age_hours=100)
    pa = dicom_folder / "CHEST" / "pa.dcm"
    r = client.post("/api/ingest", files={"files": ("pa.dcm", pa.read_bytes())})
    assert r.status_code == 200
    assert not _dir("vencido-http").exists()


def test_retencao_na_inicializacao_do_app(monkeypatch):
    from app.main import create_app

    monkeypatch.delenv("MEDLENS_RETENCAO_HORAS", raising=False)
    _make_study("vencido-boot", age_hours=72)
    _make_study("vivo-boot", age_hours=1)
    create_app()
    assert not _dir("vencido-boot").exists()
    assert _dir("vivo-boot").exists()


def test_retencao_limpa_resultado_em_memoria(monkeypatch):
    monkeypatch.delenv("MEDLENS_RETENCAO_HORAS", raising=False)
    _make_study("vencido-mem", age_hours=48)
    api_analysis._remember("ecg", "vencido-mem", object(), b"png")
    store.purge_expired()
    assert ("ecg", "vencido-mem") not in api_analysis._LAST


def test_retencao_sem_pasta_de_estudos_nao_quebra():
    assert store.purge_expired() == []


# ------------------------------------------------------------------ (4) _LAST como LRU
@pytest.fixture
def last_limpo():
    api_analysis._LAST.clear()
    yield api_analysis._LAST
    api_analysis._LAST.clear()


def test_last_tem_teto_padrao_32(last_limpo, monkeypatch):
    monkeypatch.delenv("MEDLENS_LAST_MAX", raising=False)
    for i in range(40):
        api_analysis._remember("ecg", f"s{i}", i)
    assert len(last_limpo) == 32
    assert ("ecg", "s0") not in last_limpo
    assert ("ecg", "s39") in last_limpo


def test_last_descarta_o_menos_recentemente_usado(last_limpo):
    for i in range(32):
        api_analysis._remember("ecg", f"s{i}", i)
    api_analysis._recall("ecg", "s0")              # s0 vira o mais recente
    api_analysis._remember("ecg", "novo", "x")     # estoura: sai s1, não s0
    assert ("ecg", "s0") in last_limpo
    assert ("ecg", "s1") not in last_limpo


def test_last_regravar_mesma_chave_nao_cresce(last_limpo):
    for _ in range(100):
        api_analysis._remember("rx", "mesmo", object())
    assert len(last_limpo) == 1


def test_last_continua_compativel_com_pop(last_limpo):
    api_analysis._remember("ecg", "p", 1)
    api_analysis._LAST.pop(("ecg", "p"), None)
    assert ("ecg", "p") not in api_analysis._LAST


def test_409_em_portugues(last_limpo):
    with pytest.raises(HTTPException) as exc:
        api_analysis._recall("ecg", "sem-analise")
    assert exc.value.status_code == 409
    detalhe = exc.value.detail
    assert "análise" in detalhe.lower()
    assert "analyze first" not in detalhe
