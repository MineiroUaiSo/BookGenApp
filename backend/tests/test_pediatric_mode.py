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
    cal = {"paper_speed_mm_s": 25.0, "gain_mm_mv": 10.0, "grid_confidence": 0.9,
           "pulse_found": 1.0} if calibration is None else calibration
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


NOTA_IMAGEM = "estimada a partir de imagem; conferir no traçado"


def test_ecg_toda_medida_de_imagem_traz_a_nota_fixa():
    r = aplicar_modo_pediatrico("ecg", _ecg(), 24)
    assert r["medidas"] and all(NOTA_IMAGEM in m["nota"] for m in r["medidas"])
    assert NOTA_BAZETT in _medida(r, "qtc_bazett")["nota"]      # a nota de Bazett continua junto do QTc


@pytest.mark.parametrize("cal", [
    {"paper_speed_mm_s": 25.0, "gain_mm_mv": 10.0, "grid_confidence": 0.9},                     # sem 'pulse_found'
    {"paper_speed_mm_s": 25.0, "gain_mm_mv": 10.0, "grid_confidence": 0.9, "pulse_found": 0.0},  # pulso não achado
])
def test_ecg_calibracao_nao_verificada_derruba_confiabilidade_de_todas_as_medidas(cal):
    r = aplicar_modo_pediatrico("ecg", _ecg(calibration=cal), 24)
    assert r["medidas"] and all(m["confiavel"] is False for m in r["medidas"])
    q = {x["codigo"]: x for x in r["qualidade"]}
    assert q["calibracao"]["nivel"] == "alerta" and "não verificada" in q["calibracao"]["texto"]


@pytest.mark.parametrize("qrs,extremo", [(199.0, False), (200.0, True), (260.0, True)])
def test_ecg_qrs_extremo_vem_sempre_nao_confiavel_com_aviso(qrs, extremo):
    gm = GlobalMeasurements(heart_rate_bpm=100.0, rr_mean_ms=600.0, qrs_ms=qrs, qt_ms=300.0)
    r = aplicar_modo_pediatrico("ecg", _ecg(gm=gm), 24)
    m = _medida(r, "qrs")
    assert m["confiavel"] is (not extremo)
    assert _medida(r, "fc")["confiavel"] is True                 # só a medida extrema é rebaixada
    assert any("valor extremo: pode ser artefato" in a for a in r["avisos"]) is extremo
    assert ("valor extremo: pode ser artefato" in m["nota"].lower()) is extremo
    assert NOTA_IMAGEM in m["nota"] and ". Valor extremo" in m["nota"] or not extremo   # notas separadas por ponto


@pytest.mark.parametrize("eixo,extremo", [(-90.0, False), (-91.0, True), (-120.0, True), (0.0, False),
                                          (180.0, False), (181.0, True)])
def test_ecg_eixo_fora_de_menos90_a_180_e_extremo(eixo, extremo):
    gm = GlobalMeasurements(heart_rate_bpm=100.0, rr_mean_ms=600.0, qrs_axis_deg=eixo)
    r = aplicar_modo_pediatrico("ecg", _ecg(gm=gm), 24)
    assert _medida(r, "eixo_qrs")["confiavel"] is (not extremo)
    assert any("valor extremo: pode ser artefato" in a for a in r["avisos"]) is extremo


def test_ecg_aviso_de_valor_extremo_passa_no_filtro_de_vocabulario():
    gm = GlobalMeasurements(heart_rate_bpm=100.0, rr_mean_ms=600.0, qrs_ms=240.0, qrs_axis_deg=-130.0)
    r = aplicar_modo_pediatrico("ecg", _ecg(gm=gm), 24)
    validar_contrato(r)
    assert not [t for t in textos_filtrados(r) if VETADO.search(t)]


# ------------------------------------------------------------------ RX
def test_rx_pediatrico_sem_ict_sem_medidas_sem_achados():
    r = aplicar_modo_pediatrico("rx", _rx(), 60, **DECL_PA)
    validar_contrato(r)
    assert r["medidas"] == []
    js = json.dumps(r, ensure_ascii=False).lower()
    assert not ({"findings", "laudo", "laudo_rx", "laudo_rx_markdown"} & set(r))
    for proibido in ("cardiothoracic", "0.64", "0,64", "image_png", "findings", "laudo_rx", "cardiomegalia", "derrame",
                     "normal_range", "< 0,50"):
        assert proibido not in js, proibido
    assert any("Índice cardiotorácico não exibido" in a for a in r["avisos"])


DECL_PA = dict(regiao_declarada="torax", incidencia_declarada="pa")
Q_CONFIANTE = {"rotação": "adequada (simétrica; critério: clavículas)"}   # sem a chave 'confiabilidade' = deteção confiante


def test_rx_incidencia_regiao_e_qualidade_tecnica_com_declaracao():
    r = aplicar_modo_pediatrico("rx", _rx(), 60, **DECL_PA)
    assert r["incidencia"] == "PA" and r["regiao"] == "tórax"
    cod = {q["codigo"]: q for q in r["qualidade"]}
    assert cod["declaracao"]["nivel"] == "info"
    assert cod["rotacao"]["nivel"] == "info"
    assert cod["inspiracao"]["nivel"] == "alerta"
    assert cod["exposicao"]["nivel"] == "info"
    assert "texto_queimado" in cod
    assert "Segmentação" not in json.dumps(r, ensure_ascii=False)  # texto livre do motor nunca passa


def test_rx_sem_declaracao_e_indeterminada_mesmo_com_deteccao_de_torax_pa():
    r = aplicar_modo_pediatrico("rx", _rx(), 60)
    assert r["incidencia"] == "indeterminada" and r["regiao"] == "indeterminada"
    cod = {q["codigo"]: q for q in r["qualidade"]}
    assert cod["declaracao"]["nivel"] == "alerta"
    assert not {"rotacao", "inspiracao", "exposicao"} & set(cod)     # qualidade frontal só com PA/AP declarado
    assert "divergencia_regiao" not in cod


def test_rx_perfil_de_torax_detectado_como_abdome_nunca_sai_como_abdome_ok():
    r = aplicar_modo_pediatrico("rx", _rx(view=RXView.OTHER, region=BodyRegion.ABDOMEN, out_of_scope=True), 60)
    js = json.dumps(r, ensure_ascii=False).lower()
    assert r["regiao"] == "indeterminada" and r["incidencia"] == "indeterminada"
    assert "abdome" not in js and "abdomen" not in js
    assert all(q["nivel"] == "alerta" for q in r["qualidade"] if q["codigo"] in ("declaracao", "escopo"))


def test_rx_saida_traz_o_que_o_usuario_declarou_nao_o_detectado():
    r = aplicar_modo_pediatrico("rx", _rx(view=RXView.OTHER, region=BodyRegion.ABDOMEN, out_of_scope=True), 60,
                                regiao_declarada="torax", incidencia_declarada="perfil")
    assert r["regiao"] == "tórax" and r["incidencia"] == "perfil"
    assert "divergencia_regiao" not in {q["codigo"] for q in r["qualidade"]}   # deteção heurística não contradiz


@pytest.mark.parametrize("decl,esperado", [("torax", "tórax"), ("abdome", "abdome"), ("outro", "outro")])
def test_rx_regiao_declarada_aceita_torax_abdome_outro(decl, esperado):
    assert aplicar_modo_pediatrico("rx", _rx(), 60, regiao_declarada=decl)["regiao"] == esperado


@pytest.mark.parametrize("decl,esperado", [("pa", "PA"), ("ap", "AP"), ("perfil", "perfil"), ("outro", "outro")])
def test_rx_incidencia_declarada_aceita_pa_ap_perfil_outro(decl, esperado):
    assert aplicar_modo_pediatrico("rx", _rx(), 60, incidencia_declarada=decl)["incidencia"] == esperado


@pytest.mark.parametrize("campo,valor", [("regiao_declarada", "pulmao"), ("regiao_declarada", "TORAX "),
                                         ("incidencia_declarada", "lateral"), ("incidencia_declarada", "")])
def test_rx_declaracao_invalida_levanta_erro(campo, valor):
    with pytest.raises(ValueError):
        aplicar_modo_pediatrico("rx", _rx(), 60, **{campo: valor})


def test_rx_divergencia_so_com_deteccao_confiante_e_texto_exato():
    r = aplicar_modo_pediatrico("rx", _rx(view=RXView.OTHER, region=BodyRegion.ABDOMEN, quality=Q_CONFIANTE), 60,
                                regiao_declarada="torax", incidencia_declarada="pa")
    div = next(q for q in r["qualidade"] if q["codigo"] == "divergencia_regiao")
    assert div["texto"] == "região detectada diverge da declarada: conferir" and div["nivel"] == "alerta"
    assert r["regiao"] == "tórax"                      # a saída continua sendo a declaração


def test_rx_divergencia_de_incidencia_com_deteccao_confiante():
    r = aplicar_modo_pediatrico("rx", _rx(view=RXView.LATERAL, region=BodyRegion.CHEST, quality=Q_CONFIANTE), 60,
                                regiao_declarada="torax", incidencia_declarada="pa")
    assert "divergencia_incidencia" in {q["codigo"] for q in r["qualidade"]}
    assert "divergencia_regiao" not in {q["codigo"] for q in r["qualidade"]}


def test_rx_sem_divergencia_quando_a_deteccao_confiante_concorda():
    r = aplicar_modo_pediatrico("rx", _rx(view=RXView.AP, region=BodyRegion.CHEST, quality=Q_CONFIANTE), 60,
                                regiao_declarada="torax", incidencia_declarada="pa")   # PA x AP não é contradição
    assert not {"divergencia_regiao", "divergencia_incidencia"} & {q["codigo"] for q in r["qualidade"]}


def test_rx_deteccao_confiante_mas_incerta_ou_fora_de_escopo_nao_conta_como_contradicao():
    r = aplicar_modo_pediatrico("rx", _rx(view=RXView.OTHER, region=BodyRegion.ABDOMEN, quality=Q_CONFIANTE,
                                          region_uncertain=True), 60, regiao_declarada="torax")
    assert "divergencia_regiao" not in {q["codigo"] for q in r["qualidade"]}


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


def test_rx_descricao_menciona_a_declaracao_e_nao_classifica():
    d = aplicar_modo_pediatrico("rx", _rx(), 60, **DECL_PA)["descricao_tecnica"]
    assert "declarada" in d and "PA" in d and "tórax" in d
    assert not VETADO.search(d)
    assert "indeterminad" in aplicar_modo_pediatrico("rx", _rx(), 60)["descricao_tecnica"]


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
