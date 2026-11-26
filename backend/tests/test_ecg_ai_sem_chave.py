"""M2-B: sem chave de IA, /ecg/{id}/ai ainda devolve a descrição completa DETERMINÍSTICA."""
import app.ecg.plausibility  # noqa: F401  (carrega o pacote real antes dos stubs de install_fake)
from conftest import install_fake
from test_core import _analysis, _signal, upload
from test_llm import _ecg

_CHAVES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENROUTER_API_KEY")


def _sem_chaves(monkeypatch):
    for k in _CHAVES:
        monkeypatch.delenv(k, raising=False)


def test_endpoint_ai_sem_chave_traz_descricao_deterministica(client, dicom_folder, monkeypatch):
    _sem_chaves(monkeypatch)
    d = upload(client, dicom_folder).json()
    sid = [s for s in d["studies"] if s["series"][0]["modality"] == "ECG"][0]["study_id"]
    install_fake(monkeypatch, "app.ecg.ingest", load_ecg=lambda p: _signal())
    install_fake(monkeypatch, "app.ecg.analysis", analyze_signal=lambda sig, s: _analysis(s))
    assert client.post(f"/api/ecg/{sid}/analyze", json={}).status_code == 200
    r = client.post(f"/api/ecg/{sid}/ai")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["available"] is False and j["limitations"] and "IA indisponível" in j["limitations"][0]
    assert j["descricao_origem"] == "deterministico"
    assert j["descricao_completa"] and "\n" not in j["descricao_completa"]
    assert "regras automáticas" in j["descricao_completa"]


def test_run_ecg_ai_sem_chave_mantem_aviso_e_descricao(monkeypatch):
    _sem_chaves(monkeypatch)
    from app.api.analysis import _run_ecg_ai
    rep = _run_ecg_ai(_ecg(), None)
    assert rep.available is False and rep.description == ""
    assert "IA indisponível" in rep.limitations[0]
    assert rep.descricao_origem == "deterministico" and rep.descricao_completa
