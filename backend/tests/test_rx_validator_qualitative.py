"""Tarefa 1 (spec RX-LAUDO-CONFIAVEL §3.1): o caminho RX não pode deixar passar afirmação qualitativa sem lastro.

Sondas (a)-(d): (a) as 6 frases sem fato são REMOVIDAS do texto exibido; (b) escore bruto de pneumotórax não sustenta
a frase (zona nao_sugerido ou INSUFFICIENT_EVIDENCE); (c) cardiomegalia com regra continua aceita; (d) número certo
continua aceito."""
import pytest

from app import llm
from app.rx import claim_check
from app.schemas import (AIReport, BodyRegion, Differential, Finding, RXAnalysis, RXImageAnalysis, RXMeasurement,
                         RXView)

SONDAS = [
    "Consolidação no lobo inferior direito com broncograma aéreo.",
    "Nódulo pulmonar de 12 mm no lobo superior esquerdo.",
    "Sem pneumotórax.",
    "Seios costofrênicos livres.",
    "Pulmões sem opacidades.",
    "Pequeno derrame pleural à direita.",
    "Pneumotórax à esquerda.",
    "Fratura do 6º arco costal direito.",
]


def _summary(*, ict=0.46, probs=None, zones=None, codes=(), origem="modelo", incidencia="PA"):
    medidas = []
    if ict is not None:
        medidas.append({"key": "cardiothoracic_ratio", "label": "ICT", "value": ict, "normal_range": "<= 0,50"})
    return {
        "imagens": [{"incidencia": incidencia, "regiao": "chest", "medidas": medidas,
                     "estruturas_segmentadas": [{"chave": "heart", "rotulo": "Coração", "origem": origem}],
                     "probabilidades_modelo_auxiliar": probs or {},
                     "zonas_modelo_auxiliar": zones or None}],
        "achados_por_regras": [{"code": c, "label": c, "severity": "borderline", "evidence": []} for c in codes],
        "avisos": [],
    }


def _rep(description="", findings=(), differentials=()):
    return AIReport(available=True, description=description, findings=list(findings),
                    differentials=list(differentials))


# ---------------------------------------------------------------- (a)
@pytest.mark.parametrize("frase", SONDAS)
def test_rx_claim_check_frase_sem_fato_some_da_descricao(frase):
    s = _summary(probs={"Pneumothorax": 0.05, "Effusion": 0.02}, zones={"Pneumothorax": "nao_sugerido",
                                                                         "Effusion": "nao_sugerido"})
    desc = f"ICT 0,46 em PA. {frase} Técnica adequada."
    out = claim_check.sanitize_report(_rep(desc), s)
    assert frase not in out.description
    assert "ICT 0,46" in out.description and "Técnica adequada" in out.description
    assert any(frase.rstrip(".") in d for d in out.disagreements_with_measurements)


def test_rx_claim_check_seis_frases_da_sonda_juntas():
    s = _summary()
    out = claim_check.sanitize_report(_rep(" ".join(SONDAS)), s)
    for frase in SONDAS:
        assert frase not in out.description
    assert len(out.disagreements_with_measurements) >= len(SONDAS)


def test_rx_claim_check_remove_de_findings_e_diferenciais():
    s = _summary()
    f_ruim = Finding(code="x.pneumo", label="Pneumotórax à esquerda", severity="critical", evidence=["colapso"])
    f_ok = Finding(code="rx.cardiothoracic_ratio_normal", label="Índice cardiotorácico dentro do limite (≤ 0,50)",
                   severity="normal", evidence=["ICT 0,46"])
    d_ruim = Differential(diagnosis="Pneumonia lobar", rationale="Consolidação no lobo inferior direito.")
    out = claim_check.sanitize_report(_rep("", [f_ruim, f_ok], [d_ruim]), s)
    assert [f.label for f in out.findings] == [f_ok.label]
    assert out.differentials == []
    assert any("Pneumotórax à esquerda" in d for d in out.disagreements_with_measurements)
    assert any("Pneumonia lobar" in d for d in out.disagreements_with_measurements)


# ---------------------------------------------------------------- (b)
def test_rx_claim_check_escore_bruto_alto_com_zona_nao_sugerido_nao_sustenta():
    s = _summary(probs={"Effusion": 0.55}, zones={"Effusion": "nao_sugerido"})
    out = claim_check.sanitize_report(_rep("Derrame pleural à direita."), s)
    assert "Derrame" not in out.description


def test_rx_claim_check_pneumotorax_insuficiente_nunca_sustenta():
    s = _summary(probs={"Pneumothorax": 0.55}, zones={"Pneumothorax": "sugestivo"},
                 codes=("rx.model.pneumothorax",))
    out = claim_check.sanitize_report(_rep("Pneumotórax à esquerda."), s)
    assert "Pneumotórax" not in out.description


def test_rx_claim_check_zona_sugestiva_sustenta_derrame():
    s = _summary(probs={"Effusion": 0.7}, zones={"Effusion": "sugestivo"}, codes=("rx.model.effusion",))
    out = claim_check.sanitize_report(_rep("Possível derrame pleural (escore do modelo)."), s)
    assert "derrame pleural" in out.description
    assert out.disagreements_with_measurements == []


def test_rx_claim_check_zona_indeterminada_nao_sustenta_afirmacao():
    s = _summary(probs={"Effusion": 0.3}, zones={"Effusion": "indeterminado"})
    out = claim_check.sanitize_report(_rep("Derrame pleural bilateral."), s)
    assert "Derrame" not in out.description


def test_rx_claim_check_sem_calibracao_usa_limiar_bruto_exceto_insuficiente():
    s = _summary(probs={"Effusion": 0.9, "Pneumothorax": 0.95})
    out = claim_check.sanitize_report(_rep("Derrame pleural. Pneumotórax."), s)
    assert "Derrame pleural" in out.description
    assert "Pneumotórax" not in out.description


# ---------------------------------------------------------------- (c)(d)
def test_rx_claim_check_cardiomegalia_com_regra_continua_aceita():
    s = _summary(ict=0.58, codes=("rx.cardiomegaly",))
    out = claim_check.sanitize_report(_rep("Cardiomegalia (ICT 0,58)."), s)
    assert "Cardiomegalia" in out.description
    assert out.disagreements_with_measurements == []


def test_rx_claim_check_cardiomegalia_sem_regra_nem_medida_some():
    s = _summary(ict=0.44)
    out = claim_check.sanitize_report(_rep("Cardiomegalia."), s)
    assert "Cardiomegalia" not in out.description


def test_rx_claim_check_numero_certo_continua_aceito():
    s = _summary(ict=0.46)
    out = claim_check.sanitize_report(_rep("ICT 0,46."), s)
    assert out.description == "ICT 0,46."
    assert out.disagreements_with_measurements == []


def test_rx_claim_check_negacao_com_medida_na_faixa_vale():
    s = _summary(ict=0.46)
    out = claim_check.sanitize_report(_rep("Sem cardiomegalia (ICT 0,46)."), s)
    assert "Sem cardiomegalia" in out.description


def test_rx_claim_check_negacao_sem_medida_some():
    s = _summary(ict=None)
    out = claim_check.sanitize_report(_rep("Sem cardiomegalia."), s)
    assert "cardiomegalia" not in out.description


# ---------------------------------------------------------------- abstenção legítima
@pytest.mark.parametrize("frase", [
    "Pneumotórax não avaliado nesta análise.",
    "Não é possível afastar pneumotórax pela análise automática.",
    "O escore do modelo para derrame é indeterminado.",
    "Posição de tubos e cateteres não avaliada.",
])
def test_rx_claim_check_frase_de_nao_avaliado_passa(frase):
    out = claim_check.sanitize_report(_rep(frase), _summary())
    assert out.description == frase


@pytest.mark.parametrize("frase", ["Exame normal.", "Radiografia sem alterações.", "Pulmões limpos.",
                                   "Tórax dentro da normalidade."])
def test_rx_claim_check_normalidade_global_sempre_some(frase):
    out = claim_check.sanitize_report(_rep(frase), _summary())
    assert out.description == ""


def test_rx_claim_check_tamanho_de_lesao_nunca_sustentado():
    s = _summary(probs={"Nodule": 0.9}, zones={"Nodule": "sugestivo"}, codes=("rx.model.nodule",))
    out = claim_check.sanitize_report(_rep("Possível nódulo de 12 mm."), s)
    assert "12 mm" not in out.description


# ---------------------------------------------------------------- ligado em rx_report
def _analysis(zones=None, probs=None, ict=0.46):
    img = RXImageAnalysis(instance_id="i1", view=RXView.PA, region=BodyRegion.CHEST, image_png_b64="", width=64,
                          height=64, measurements=[RXMeasurement(key="cardiothoracic_ratio", label="ICT",
                                                                 value=ict)],
                          model_probs=probs or {}, model_zones=zones or {})
    return RXAnalysis(study_id="s1", images=[img])


def test_rx_report_aplica_claim_check_depois_do_two_stage(monkeypatch):
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    monkeypatch.setenv("MEDLENS_RX_IMAGE_AI", "off")
    bruto = _rep("ICT 0,46. " + " ".join(SONDAS))

    def fake_two_stage(domain, images, context, summary=None, rule_findings=None):
        assert domain == "rx" and images == []
        return bruto

    monkeypatch.setattr(llm, "_two_stage", fake_two_stage)
    out = llm.rx_report(_analysis())
    assert "ICT 0,46" in out.description
    for frase in SONDAS:
        assert frase not in out.description
    assert out.validation.get("claims_rx_removidas", 0) >= len(SONDAS)


def test_rx_report_claim_check_falha_descarta_narrativa(monkeypatch):
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    monkeypatch.setenv("MEDLENS_RX_IMAGE_AI", "off")
    monkeypatch.setattr(llm, "_two_stage", lambda *a, **k: _rep("ICT 0,46."))

    def boom(rep, summary, **kw):
        raise RuntimeError("x")

    monkeypatch.setattr(claim_check, "sanitize_report", boom)
    out = llm.rx_report(_analysis())
    assert out.description == ""
    assert any("barreira de verificação falhou: narrativa descartada" in x for x in out.limitations)


# ---------------------------------------------------------------- R2 / A.2: vazamentos da barreira
SEM_LASTRO_A2 = [
    "Derrame pleural volumoso à direita limitando avaliação do parênquima.",
    "Hipotransparência em base direita.", "Condensação em base pulmonar esquerda.",
    "Hipertransparência difusa bilateral.", "Pneumomediastino.",
    "Cavitação em ápice direito sugestiva de tuberculose.", "Tuberculose pulmonar ativa.", "Abscesso pulmonar.",
    "Bronquiectasias em bases.", "Calcificações pleurais.", "Aneurisma de aorta torácica.",
    "Aorta alongada e ateromatosa.", "Tromboembolismo pulmonar.", "Sinais de insuficiência cardíaca descompensada.",
    "Neoplasia pulmonar provável.", "Metástases pulmonares múltiplas.", "Achados compatíveis com DPOC.",
    "Achados compatíveis com COVID-19.", "Escoliose torácica.", "Radiografia de tórax sem particularidades.",
    "Tórax sem evidências de doença cardiopulmonar aguda.", "Nada digno de nota.",
    "Parênquima pulmonar com transparência conservada.",
    # as 7 que já eram barradas
    "Pneumotórax hipertensivo à direita.", "Consolidação lobar no lobo inferior direito.",
    "Linfonodomegalia hilar bilateral.", "Exame radiográfico sem achados agudos.",
    "Não há derrame pleural, pneumotórax ou consolidação em nenhum dos hemitórax.",
    "Mediastino sem alterações.", "Cardiomegalia.",
]


def test_rx_claim_check_a2_sao_30_sem_lastro():
    assert len(SEM_LASTRO_A2) == 30


@pytest.mark.parametrize("frase", SEM_LASTRO_A2)
def test_rx_claim_check_a2_frase_sem_lastro_e_removida(frase):
    fatos = claim_check.Fatos.de(_summary(probs={"Effusion": 0.1, "Pneumothorax": 0.1},
                                          zones={"Effusion": "nao_sugerido"}))
    assert claim_check.problema_da_frase(frase, fatos) is not None


def test_rx_claim_check_area_cardiaca_normal_com_ict_de_modelo_pa_passa():
    fatos = claim_check.Fatos.de(_summary(ict=0.46))
    assert claim_check.problema_da_frase("Área cardíaca normal.", fatos) is None


def test_rx_claim_check_cardiomegalia_com_ict_heuristico_removida():
    fatos = claim_check.Fatos.de(_summary(ict=0.62, origem="heuristica"))
    assert claim_check.problema_da_frase("Cardiomegalia importante.", fatos) is not None


def test_rx_claim_check_area_cardiaca_normal_com_ict_heuristico_removida():
    fatos = claim_check.Fatos.de(_summary(ict=0.46, origem="heuristica"))
    assert claim_check.problema_da_frase("Área cardíaca normal.", fatos) is not None


def test_rx_claim_check_ict_em_ap_nao_sustenta_cardiomegalia_nem_normal():
    fatos = claim_check.Fatos.de(_summary(ict=0.62, incidencia="AP"))
    assert claim_check.problema_da_frase("Cardiomegalia.", fatos) is not None
    fatos = claim_check.Fatos.de(_summary(ict=0.46, incidencia="AP"))
    assert claim_check.problema_da_frase("Área cardíaca normal.", fatos) is not None


def test_rx_claim_check_ict_sem_info_de_origem_nao_e_lastro():
    s = _summary(ict=0.46)
    s["imagens"][0].pop("estruturas_segmentadas")
    assert claim_check.problema_da_frase("Área cardíaca normal.", claim_check.Fatos.de(s)) is not None


@pytest.mark.parametrize("frase", [
    "Derrame volumoso, não permite avaliar o parênquima.",
    "Derrame pleural extenso à direita limitando a avaliação.",
    "Pneumomediastino impede a avaliação? Limitando avaliação do mediastino.",
])
def test_rx_claim_check_abstencao_nao_libera_achado_afirmado(frase):
    assert claim_check.problema_da_frase(frase, claim_check.Fatos.de(_summary())) is not None


@pytest.mark.parametrize("frase", [
    "Limitando a avaliação, a rotação do paciente.",
    "Avaliação do parênquima limitada pela técnica.",
    "Tuberculose não avaliada nesta análise.",
])
def test_rx_claim_check_abstencao_pura_continua_passando(frase):
    assert claim_check.problema_da_frase(frase, claim_check.Fatos.de(_summary())) is None


def test_rx_claim_check_limite_nao_e_termo_desconhecido():
    f = claim_check.Fatos.de(_summary())
    assert claim_check.problema_da_frase("Índice cardiotorácico dentro do limite de referência.", f) is None
    assert claim_check.problema_da_frase("ICT 0,46 e técnica adequada.", f) is None
