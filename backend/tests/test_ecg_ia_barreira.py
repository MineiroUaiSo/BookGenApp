"""Barreira qualitativa do texto de IA do ECG (v1 e laudo v1): falha fechada, frase sem lastro é REMOVIDA."""
import pytest

from app.llm import ecg_claim_check as EC
from app.llm import laudo as L
from app.llm import validate as V
from app.schemas import AIReport, Finding


def _summary(*rules):
    achados = [{"code": c, "label": c, "severity": s, "evidence": []} for c, s in rules]
    return {"medidas_globais": {"heart_rate_bpm": 72, "pr_ms": 160, "qrs_ms": 96, "qt_ms": 400,
                                "qtc_bazett_ms": 430},
            "medidas_por_derivacao": [], "achados_por_regras": achados, "avisos": []}


S_ST_NA = _summary(("ecg.sinus_rhythm", "normal"), ("ecg.st_not_assessable", "borderline"))

# Apêndice A.1 da análise (9 frases; só "Ritmo sinusal" tem lastro)
SEM_LASTRO = [
    "Sem sinais de isquemia aguda.",
    "Ausência de supradesnivelamento de ST.",
    "Não há bloqueio atrioventricular.",
    "Onda T invertida difusa sugestiva de isquemia subendocárdica.",
    "Padrão de Brugada tipo 1 em V1-V2.",
    "Sinais de hipercalemia.",
    "Padrão S1Q3T3 sugestivo de embolia pulmonar.",
    "Eletrocardiograma dentro dos limites da normalidade.",
]
A1_TEXT = "Ritmo sinusal. " + " ".join(SEM_LASTRO)


def _report(text, findings=()):
    return AIReport(description=text, findings=list(findings))


# ------------------------------------------------------------------ v1 (validate_report)
def test_a1_nenhuma_frase_sem_lastro_sobrevive():
    r = V.validate_report(_report(A1_TEXT), S_ST_NA, [])
    for frase in SEM_LASTRO:
        assert frase.rstrip(".") not in r.description, frase
    assert "Ritmo sinusal" in r.description
    assert r.validation["afirmacoes_removidas"] == 8


def test_a1_cada_frase_isolada_e_removida():
    for frase in SEM_LASTRO:
        r = V.validate_report(_report(frase), S_ST_NA, [])
        assert r.description.strip() == "", frase


def test_frase_com_lastro_e_medida_sobrevivem():
    r = V.validate_report(_report("FC 72 bpm. Ritmo sinusal."), S_ST_NA, [])
    assert r.description == "FC 72 bpm. Ritmo sinusal."
    assert r.validation["afirmacoes_removidas"] == 0
    assert not any("sem lastro" in x for x in r.limitations)


def test_limitacao_legivel_com_contagem():
    r = V.validate_report(_report(A1_TEXT), S_ST_NA, [])
    assert "8 frases sem lastro removidas" in r.limitations


def test_limitacao_singular():
    r = V.validate_report(_report("Sem sinais de isquemia aguda."), S_ST_NA, [])
    assert "1 frase sem lastro removida" in r.limitations


def test_normalidade_sem_regra_de_normal_e_removida_mesmo_sem_st_na():
    s = _summary(("ecg.sinus_rhythm", "normal"))
    r = V.validate_report(_report("Ritmo sinusal. Traçado sem alterações."), s, [])
    assert r.description.strip() == "Ritmo sinusal."


def test_normalidade_so_com_regra_normal_e_qualificador():
    s = _summary(("ecg.sinus_rhythm", "normal"), ("ecg.within_normal_limits", "normal"))
    ok = "Pelas regras automáticas, ECG dentro dos limites da normalidade."
    assert V.validate_report(_report(ok), s, []).description == ok
    # sem qualificador: removida
    r = V.validate_report(_report("Eletrocardiograma dentro dos limites da normalidade."), s, [])
    assert r.description.strip() == ""


def test_normalidade_removida_com_st_na_mesmo_com_regra_normal_e_qualificador():
    s = _summary(("ecg.within_normal_limits", "normal"), ("ecg.st_not_assessable", "borderline"))
    r = V.validate_report(_report("Pelas regras automáticas, ECG dentro dos limites da normalidade."), s, [])
    assert r.description.strip() == ""


def test_negacao_qualificada_sobrevive_sem_regra_contraria():
    s = _summary(("ecg.sinus_rhythm", "normal"))
    t = "Nenhuma regra automática detectou bloqueio atrioventricular."
    assert V.validate_report(_report(t), s, []).description == t


def test_negacao_de_st_com_st_na_removida_mesmo_qualificada():
    t = "Nenhuma regra automática detectou isquemia."
    assert V.validate_report(_report(t), S_ST_NA, []).description.strip() == ""


def test_negacao_contra_regra_ativa_removida():
    s = _summary(("ecg.av_block_1", "abnormal"))
    t = "Nenhuma regra automática detectou bloqueio atrioventricular."
    assert V.validate_report(_report(t), s, []).description.strip() == ""


def test_diagnostico_com_regra_correspondente_sobrevive():
    s = _summary(("ecg.av_block_1", "abnormal"), ("ecg.rbbb", "abnormal"))
    t = "Bloqueio atrioventricular de primeiro grau. Bloqueio de ramo direito."
    assert V.validate_report(_report(t), s, []).description == t


def test_diagnostico_sem_regra_removido_e_vizinha_mantida():
    t = "Ritmo sinusal. Bloqueio de ramo esquerdo completo. FC 72 bpm."
    r = V.validate_report(_report(t), _summary(("ecg.sinus_rhythm", "normal")), [])
    assert "ramo esquerdo" not in r.description
    assert "Ritmo sinusal." in r.description and "FC 72 bpm." in r.description


def test_alteracao_de_st_negada_removida():
    r = V.validate_report(_report("Sem alterações agudas do segmento ST."), _summary(), [])
    assert r.description.strip() == ""


def test_achado_ia_critico_sem_regra_e_rebaixado_com_flag():
    f = Finding(code="ia.brugada", label="Padrão de Brugada tipo 1", severity="critical", evidence=[])
    r = V.validate_report(_report("Ritmo sinusal.", [f]), S_ST_NA, [])
    assert len(r.findings) == 1
    assert r.findings[0].severity == "borderline"
    assert V.FLAG_UNSUPPORTED in r.findings[0].validation_flags and V.FLAG_UNSUPPORTED in r.findings[0].label


def test_achado_ia_com_regra_e_mantido():
    s = _summary(("ecg.av_block_1", "abnormal"))
    f = Finding(code="ia.av_block", label="Bloqueio atrioventricular de primeiro grau", severity="abnormal")
    r = V.validate_report(_report("", [f]), s, [])
    assert len(r.findings) == 1


def test_achado_ia_normal_sem_lastro_removido():
    f = Finding(code="ia.normal", label="ECG normal", severity="normal")
    assert V.validate_report(_report("", [f]), S_ST_NA, []).findings == []


def test_evidencia_do_achado_filtrada():
    s = _summary(("ecg.av_block_1", "abnormal"))
    f = Finding(code="ia.x", label="Bloqueio atrioventricular de primeiro grau", severity="abnormal",
                evidence=["PR 160 ms.", "Sem sinais de isquemia."])
    r = V.validate_report(_report("", [f]), s, [])
    assert r.findings[0].evidence == ["PR 160 ms."]


def test_excecao_no_filtro_descarta_narrativa(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("falha simulada")
    monkeypatch.setattr(EC, "filter_text", boom)
    r = V.validate_report(_report("Sem sinais de isquemia aguda."), S_ST_NA, [])
    assert r.description == ""
    assert r.findings == []
    assert "barreira de verificação falhou: narrativa descartada" in r.limitations


# ------------------------------------------------------------------ laudo v1
def _laudo(**kw):
    return L.LaudoECG(**kw)


def test_laudo_v1_frases_sem_lastro_removidas():
    l = _laudo(ritmo_frequencia="Ritmo sinusal, FC 72 bpm.",
               st_t="Sem sinais de isquemia aguda. Ausência de supradesnivelamento de ST.",
               impressao=["Eletrocardiograma dentro dos limites da normalidade.", "Ritmo sinusal."],
               limitrofes=["Padrão de Brugada tipo 1 em V1-V2."])
    out = L.validate_laudo(l, S_ST_NA)
    assert "isquemia" not in out.st_t and "supradesnivelamento" not in out.st_t
    assert out.impressao == ["Ritmo sinusal."]
    assert out.limitrofes == []
    assert "Ritmo sinusal" in out.ritmo_frequencia and "72 bpm" in out.ritmo_frequencia
    assert out.validacao["afirmacoes_removidas"] == 4
    assert any("4 frases sem lastro removidas" in x for x in out.avisos_validacao)


def test_laudo_v1_frase_com_lastro_sobrevive():
    s = _summary(("ecg.sinus_rhythm", "normal"), ("ecg.rbbb", "abnormal"))
    l = _laudo(complexo_qrs="Bloqueio de ramo direito.", impressao=["Bloqueio de ramo direito."])
    out = L.validate_laudo(l, s)
    assert out.complexo_qrs == "Bloqueio de ramo direito."
    assert out.impressao == ["Bloqueio de ramo direito."]


def test_laudo_v1_excecao_descarta_narrativa(monkeypatch):
    monkeypatch.setattr(EC, "filter_text", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    l = _laudo(st_t="Sem sinais de isquemia aguda.", impressao=["Ritmo sinusal."])
    out = L.validate_laudo(l, S_ST_NA)
    assert out.st_t == "" and out.impressao == []
    assert any("barreira de verificação falhou: narrativa descartada" in x for x in out.avisos_validacao)


@pytest.mark.parametrize("texto", ["Sem alterações.", "ECG normal.", "Exame dentro dos limites normais."])
def test_normal_global_variantes_removidas(texto):
    assert EC.sentence_problem(texto, _summary(("ecg.sinus_rhythm", "normal"))) is not None


def test_negacao_de_eixo_nao_e_barrada():
    t = "Sem desvio de eixo do QRS para a esquerda."
    assert V.validate_report(_report(t), _summary(("ecg.sinus_rhythm", "normal")), []).description == t


def test_ritmo_sinusal_com_medida_de_ritmo_sobrevive_sem_regra():
    s = _summary()
    s["medidas_globais"]["rhythm"] = "sinusal regular"
    assert V.validate_report(_report("Ritmo sinusal regular."), s, []).description == "Ritmo sinusal regular."


def test_ritmo_sinusal_sem_regra_nem_medida_removido():
    assert V.validate_report(_report("Ritmo sinusal regular."), _summary(), []).description.strip() == ""


def test_hve_com_indice_de_voltagem_calculado_sobrevive():
    s = _summary()
    s["indices_calculados"] = {"sokolow_lyon_mm": 60.0, "sokolow_lyon_limite_mm": 35}
    t = "Hipertrofia ventricular esquerda por voltagem."
    assert V.validate_report(_report(t), s, []).description == t
    assert V.validate_report(_report(t), _summary(), []).description.strip() == ""


def test_laudo_v1_critico_sem_apoio_vira_aviso_sem_conteudo():
    l = _laudo(impressao=["Taquicardia ventricular sustentada."])
    out = L.validate_laudo(l, _summary(("ecg.sinus_rhythm", "normal")))
    assert "ventricular" not in out.impressao[0]
    assert V.FLAG_UNSUPPORTED in out.impressao[0]
    assert out.validacao["criticos_sem_lastro"] == 1 and out.validacao["afirmacoes_removidas"] == 1
