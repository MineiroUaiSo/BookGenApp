"""Tarefa 7: o estudo RX devolve `laudo_rx` (estruturado) e `laudo_rx_markdown` sem PHI."""
import pytest

from app.llm import guard
from app.rx import lexico as LX
from fixtures_dicom import make_dx_dicom


@pytest.fixture(autouse=True)
def _heuristic(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")


def _analisar(client, tmp_path, **kw):
    p = tmp_path / "pa.dcm"
    make_dx_dicom(p, "PA", **kw)
    r = client.post("/api/ingest", files=[("files", ("pa.dcm", p.read_bytes(), "application/dicom"))])
    assert r.status_code == 200, r.text
    sid = r.json()["studies"][0]["study_id"]
    r = client.post(f"/api/rx/{sid}/analyze?ai=false", json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_rx_api_devolve_laudo_estruturado(client, tmp_path):
    a = _analisar(client, tmp_path)
    assert a["laudo_rx"]["versao"] == "rx_laudo/v1" and a["laudo_rx"]["status"] == "rascunho"
    assert [s["id"] for s in a["laudo_rx"]["secoes"]][:3] == ["identificacao_tecnica", "qualidade", "achados"]
    achados = next(s for s in a["laudo_rx"]["secoes"] if s["id"] == "achados")
    assert any(f["texto"].startswith("Dispositivos: não avaliado") for f in achados["frases"])
    assert a["laudo_rx_markdown"].startswith("# Laudo de radiografia de tórax")


def test_rx_api_laudo_sem_phi_e_sem_termo_proibido(client, tmp_path):
    md = _analisar(client, tmp_path)["laudo_rx_markdown"]
    assert guard.scan_text(md) is None
    assert LX.termos_proibidos(md) == []
    assert "Pneumotórax, pneumoperitônio" in md


def test_rx_api_laudo_nao_traz_ids_do_dicom(client, tmp_path):
    a = _analisar(client, tmp_path)
    md = a["laudo_rx_markdown"]
    assert a["study_id"] not in md
    assert all(i["instance_id"] not in md for i in a["images"])
