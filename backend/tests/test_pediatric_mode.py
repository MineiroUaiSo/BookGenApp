"""P1b: filtro pediátrico (app/pediatric.py). Análises fixture, sem imagem, sem rede."""
import json
import random

import pytest

from app import pediatric
from app.pediatric import aplicar_modo_pediatrico, checar_vocabulario
from app.schemas import (BodyRegion, ECGAnalysis, ECGSignal, Finding, GlobalMeasurements, RXAnalysis,
                         RXImageAnalysis, RXMeasurement, RXView, SourceKind)
from pediatric_schema import VETADO, textos_filtrados, validar_contrato

LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
CODIGOS_ECG = {"fc", "rr", "pr", "qrs", "qt", "qtc_bazett", "eixo_qrs"}
NOTA_BAZETT = "Bazett superestima o QTc com FC alta, comum em lactentes; compare QT e RR"


def _ecg(gm=None, quality=0.9, calibration=None, warnings=None, findings=None, n_leads=12) -> ECGAnalysis:
    gm = gm if gm is not None else GlobalMeasurements(
        heart_rate_bpm=128.0, rr_mean_ms=469.0, pr_ms=110.0, qrs_ms=70.0, qt_ms=290.0, qtc_bazett_ms=423.0,
        qrs_axis_deg=75.0, rhythm="Ritmo sinusal", qtc_fridericia_ms=400.0, sokolow_lyon_mv=3.2,
        p_axis_deg=50.0, t_axis_deg=40.0, cornell_mv=1.0)
    cal = {"paper_speed_mm_s": 25.0, "gain_mm_mv": 10.0, "grid_confidence": 0.9} if calibration is None else calibration
    leads = {k: [0.0] * 10 for k in LEADS[:n_leads]}
    sig = ECGSignal(fs=500, leads=leads, duration_s=10, source=SourceKind.IMAGE,
                    quality={k: quality for k in leads}, calibration=cal)
    fnd = findings if findings is not None else [
        Finding(code="ecg.hve", label="Hipertrofia ventricular esquerda", severity="abnormal"),
        Finding(code="ecg.qt_longo", label="QT prolongado", severity="critical")]
    return ECGAnalysis(study_id="s1", signal=sig, global_measurements=gm, findings=fnd,
                       warnings=warnings or [])


def _rx(view=RXView.PA, region=BodyRegion.CHEST, quality=None,
        burned="BurnedInAnnotation=ausente; sem texto detectado", **kw) -> RXAnalysis:
    q = quality if quality is not None else {
        "rotação": "adequada (simétrica; critério: clavículas)",
        "inspiração": "possivelmente insuficiente (≈7 arcos posteriores estimados; <9)",
        "penetração": "adequada (coluna discernível atrás do coração; contraste 0.03)",
        "texto queimado": "BurnedInAnnotation=ausente; sem texto detectado",
        "confiabilidade": "Segmentação heurística de baixa confiança"}
    im = RXImageAnalysis(
        instance_id="i1", view=view, region=region, image_png_b64="QUJD", width=100, height=100, quality=q,
        measurements=[RXMeasurement(key="cardiothoracic_ratio", label="ICT", value=0.64, unit="",
                                    normal_range="< 0,50")],
        burned_text=burned, **kw)
    return RXAnalysis(study_id="s1", images=[im],
                      findings=[Finding(code="rx.cardiomegalia", label="Cardiomegalia", severity="abnormal"),
                                Finding(code="rx.derrame", label="Derrame pleural", severity="abnormal")],
                      laudo_rx={"conclusao": "Cardiomegalia"}, laudo_rx_markdown="# Laudo: cardiomegalia")


def _medida(r, codigo):
    return next((m for m in r["medidas"] if m["codigo"] == codigo), None)


# ------------------------------------------------------------------ ECG
def test_ecg_pediatrico_devolve_so_medidas_da_whitelist():
    r = aplicar_modo_pediatrico("ecg", _ecg(), 24)
    validar_contrato(r)
    assert {m["codigo"] for m in r["medidas"]} == CODIGOS_ECG
    assert r["tipo"] == "ecg" and r["modo"] == "pediatrico" and r["idade_meses"] == 24
    fc = _medida(r, "fc")
    assert fc["valor"] == pytest.approx(128, abs=0.5) and fc["unidade"] == "bpm"
    assert _medida(r, "qtc_bazett")["valor"] == pytest.approx(423, abs=0.5)
    assert _medida(r, "eixo_qrs")["unidade"] == "graus"


def test_ecg_pediatrico_nao_vaza_achados_nem_laudo_nem_indices_adultos():
    r = aplicar_modo_pediatrico("ecg", _ecg(), 36)
    js = json.dumps(r, ensure_ascii=False).lower()
    for proibido in ("findings", "classificacao", "diagnostico", "hipertrofia", "prolongado",
                     "ecg.hve", "ecg.qt_longo", "sokolow", "cornell", "fridericia", "ritmo sinusal", "severity",
                     "abnormal"):
        assert proibido not in js, proibido
    assert "indices" not in r and "findings" not in r


def test_ecg_qtc_sempre_vem_com_a_nota_de_bazett():
    r = aplicar_modo_pediatrico("ecg", _ecg(), 3)
    assert NOTA_BAZETT in _medida(r, "qtc_bazett")["nota"]


def test_ecg_sem_qtc_nao_inventa_medida():
    gm = GlobalMeasurements(heart_rate_bpm=100.0, rr_mean_ms=600.0)
    r = aplicar_modo_pediatrico("ecg", _ecg(gm=gm), 60)
    assert {m["codigo"] for m in r["medidas"]} == {"fc", "rr"}
    validar_contrato(r)


def test_ecg_descricao_segue_o_template_deterministico():
    r = aplicar_modo_pediatrico("ecg", _ecg(), 24)
    d = r["descricao_tecnica"]
    assert d.startswith("ECG digitalizado de imagem.")
    for trecho in ("FC 128 bpm", "PR 110 ms", "QRS 70 ms", "QT 290 ms", "QTc (Bazett) 423 ms", "eixo do QRS +75°",
                   "12 de 12 derivações legíveis", "10 mm/mV"):
        assert trecho in d, trecho
    assert aplicar_modo_pediatrico("ecg", _ecg(), 24)["descricao_tecnica"] == d  # determinística


def test_ecg_qualidade_baixa_marca_medidas_como_nao_confiaveis():
    r = aplicar_modo_pediatrico("ecg", _ecg(quality=0.3), 12)
    assert r["medidas"] and all(m["confiavel"] is False for m in r["medidas"])
    assert any(q["nivel"] == "alerta" for q in r["qualidade"])


def test_ecg_grade_pouco_confiavel_reprova_confiabilidade():
    cal = {"paper_speed_mm_s": 25.0, "gain_mm_mv": 10.0, "grid_confidence": 0.1}
    r = aplicar_modo_pediatrico("ecg", _ecg(calibration=cal), 12)
    assert all(m["confiavel"] is False for m in r["medidas"])


def test_ecg_boa_qualidade_marca_medidas_como_confiaveis():
    r = aplicar_modo_pediatrico("ecg", _ecg(), 12)
    assert all(m["confiavel"] is True for m in r["medidas"])


def test_ecg_foto_distorcida_so_fc_e_rr_e_nao_confiaveis():
    cal = {"paper_speed_mm_s": 25.0, "gain_mm_mv": 10.0, "grid_confidence": 0.9, "rhythm_only": 1.0}
    gm = GlobalMeasurements(heart_rate_bpm=90.0, rr_mean_ms=667.0, pr_ms=150.0, qrs_ms=80.0)
    r = aplicar_modo_pediatrico("ecg", _ecg(gm=gm, calibration=cal), 12)
    assert {m["codigo"] for m in r["medidas"]} == {"fc", "rr"}
    assert all(m["confiavel"] is False for m in r["medidas"])
    validar_contrato(r)


def test_ecg_ruido_elevado_so_derruba_a_confianca_dos_intervalos():
    r = aplicar_modo_pediatrico("ecg", _ecg(warnings=["Ruído elevado (sigma 80 µV): delimitação imprecisa."]), 12)
    assert _medida(r, "fc")["confiavel"] is True
    for c in ("pr", "qrs", "qt", "qtc_bazett", "eixo_qrs"):
        assert _medida(r, c)["confiavel"] is False
    assert any(q["codigo"] == "ruido" for q in r["qualidade"])


def test_ecg_sem_nenhuma_medida_avisa_em_vez_de_inventar():
    r = aplicar_modo_pediatrico("ecg", _ecg(gm=GlobalMeasurements()), 12)
    assert r["medidas"] == []
    assert any(q["nivel"] == "alerta" for q in r["qualidade"])
    validar_contrato(r)


def test_ecg_avisos_trazem_o_aviso_fixo_pediatrico_e_a_referencia():
    r = aplicar_modo_pediatrico("ecg", _ecg(), 12)
    assert r["avisos"][0].startswith("Apoio técnico, não é laudo.")
    assert "não classifica o exame" in r["avisos"][0]
    assert any("Rijnbeek" in a and "11286528" in a for a in r["avisos"])


# ------------------------------------------------------------------ RX
def test_rx_pediatrico_sem_ict_sem_medidas_sem_achados():
    r = aplicar_modo_pediatrico("rx", _rx(), 60)
    validar_contrato(r)
    assert r["medidas"] == []
    js = json.dumps(r, ensure_ascii=False).lower()
    assert not ({"findings", "laudo", "laudo_rx", "laudo_rx_markdown"} & set(r))
    for proibido in ("cardiothoracic", "0.64", "0,64", "image_png", "findings", "laudo_rx", "cardiomegalia", "derrame",
                     "normal_range", "< 0,50"):
        assert proibido not in js, proibido
    assert any("Índice cardiotorácico não exibido" in a for a in r["avisos"])


def test_rx_incidencia_regiao_e_qualidade_tecnica():
    r = aplicar_modo_pediatrico("rx", _rx(), 60)
    assert r["incidencia"] == "PA" and r["regiao"] == "tórax"
    cod = {q["codigo"]: q for q in r["qualidade"]}
    assert cod["rotacao"]["nivel"] == "info"
    assert cod["inspiracao"]["nivel"] == "alerta"
    assert cod["exposicao"]["nivel"] == "info"
    assert "texto_queimado" in cod
    assert "Segmentação" not in json.dumps(r, ensure_ascii=False)  # texto livre do motor nunca passa


def test_rx_texto_queimado_nao_mascarado_e_alerta():
    b = "BurnedInAnnotation=YES; texto detectado em 2 região(ões) (3.0% do quadro); NÃO mascarado com segurança"
    r = aplicar_modo_pediatrico("rx", _rx(burned=b), 60)
    assert next(x for x in r["qualidade"] if x["codigo"] == "texto_queimado")["nivel"] == "alerta"


def test_rx_regiao_incerta_e_fora_de_escopo_geram_alerta_sem_texto_adulto():
    r = aplicar_modo_pediatrico("rx", _rx(region_uncertain=True, out_of_scope=True,
                                          scope_reason="não é radiografia de tórax de adulto"), 60)
    cods = {q["codigo"]: q for q in r["qualidade"]}
    assert cods["regiao_incerta"]["nivel"] == "alerta" and cods["escopo"]["nivel"] == "alerta"
    assert "adulto" not in " ".join(q["texto"] for q in r["qualidade"]).lower()
    assert r["incidencia"] == "indeterminada" and r["regiao"] == "indeterminada"  # nunca afirma sob dúvida


def test_rx_incidencia_outra_fica_indeterminada():
    r = aplicar_modo_pediatrico("rx", _rx(view=RXView.OTHER, region=BodyRegion.OTHER), 60)
    assert r["incidencia"] == "indeterminada" and r["regiao"] == "outra"


def test_rx_descricao_menciona_incidencia_e_nao_classifica():
    d = aplicar_modo_pediatrico("rx", _rx(), 60)["descricao_tecnica"]
    assert "PA" in d and "tórax" in d
    assert not VETADO.search(d)


# ------------------------------------------------------------------ idade e vocabulário
def test_idade_ausente_continua_pediatrico_e_avisa():
    r = aplicar_modo_pediatrico("ecg", _ecg(), None)
    validar_contrato(r)
    assert r["idade_meses"] is None and r["modo"] == "pediatrico"
    assert any("Idade não informada" in a for a in r["avisos"])


@pytest.mark.parametrize("idade", [0, 1, 215])
def test_idade_nos_limites_da_faixa_pediatrica_e_aceita(idade):
    assert aplicar_modo_pediatrico("rx", _rx(), idade)["idade_meses"] == idade


@pytest.mark.parametrize("idade", [-1, 216, 400])
def test_idade_fora_da_faixa_pediatrica_levanta_erro(idade):
    with pytest.raises(ValueError):
        aplicar_modo_pediatrico("ecg", _ecg(), idade)


def test_tipo_desconhecido_levanta_erro():
    with pytest.raises(ValueError):
        aplicar_modo_pediatrico("tc", _ecg(), 12)  # type: ignore[arg-type]


@pytest.mark.parametrize("texto", ["ECG normal", "QT prolongado", "sinais de hipertrofia", "Cardiomegalia",
                                   "bloqueio de ramo", "Derrame", "infarto", "pneumonia", "tempo curto"])
def test_filtro_de_vocabulario_barra_termos_vetados(texto):
    with pytest.raises(ValueError):
        checar_vocabulario([texto])


def test_filtro_de_vocabulario_deixa_passar_texto_tecnico():
    checar_vocabulario(["FC 128 bpm; PR 110 ms", "Rotação adequada", "possível rotação do tórax"])


def test_template_que_produzisse_termo_vetado_levanta_valueerror(monkeypatch):
    monkeypatch.setattr(pediatric, "AVISO_PEDIATRICO", "Apoio técnico. O resultado é normal.")
    with pytest.raises(ValueError):
        aplicar_modo_pediatrico("ecg", _ecg(), 12)


def test_cinquenta_combinacoes_aleatorias_de_medidas_sem_termo_vetado():
    rng = random.Random(20261126)
    for _ in range(50):
        gm = GlobalMeasurements(**{
            k: (round(rng.uniform(lo, hi), 1) if rng.random() > 0.2 else None)
            for k, (lo, hi) in {"heart_rate_bpm": (40, 260), "rr_mean_ms": (230, 1500), "pr_ms": (60, 260),
                                "qrs_ms": (40, 200), "qt_ms": (150, 600), "qtc_bazett_ms": (250, 700),
                                "qrs_axis_deg": (-180, 180)}.items()})
        a = _ecg(gm=gm, quality=rng.choice([0.2, 0.6, 0.95]),
                 warnings=rng.choice([[], ["Ruído elevado (sigma 60 µV)"]]),
                 calibration=rng.choice([None, {"gain_mm_mv": 5.0, "paper_speed_mm_s": 50.0, "grid_confidence": 0.2}]))
        r = aplicar_modo_pediatrico("ecg", a, rng.randint(0, 215))
        validar_contrato(r)
        for t in textos_filtrados(r):
            assert not VETADO.search(t), t
        if _medida(r, "qtc_bazett"):
            assert NOTA_BAZETT in _medida(r, "qtc_bazett")["nota"]
        assert not ({"findings", "laudo"} & set(r))


def test_versao_motor_usa_commit_curto_do_ambiente(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "abcdef1234567890")
    assert aplicar_modo_pediatrico("rx", _rx(), 12)["versao_motor"] == "abcdef1"
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA")
    monkeypatch.delenv("MEDLENS_VERSION", raising=False)
    assert aplicar_modo_pediatrico("rx", _rx(), 12)["versao_motor"]  # nunca vazio
