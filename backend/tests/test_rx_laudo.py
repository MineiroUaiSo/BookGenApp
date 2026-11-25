"""Tarefa 6: laudo determinístico rx_laudo/v1 (propriedades: região sem fato = não avaliado; nada proibido; crítico fixo)."""
import re

import pytest

from app.llm import guard
from app.rx import ficha as FI
from app.rx import fontes as FT
from app.rx import laudo as LA
from app.rx import lexico as LX
from app.schemas import BodyRegion, Finding, RXAnalysis, RXImageAnalysis, RXMeasurement, RXView, Structure

NOMES = {"pleura": "Pleura", "pulmoes": "Pulmões", "mediastino_hilos": "Mediastino e hilos",
         "coracao_vasos": "Coração e vasos", "diafragma": "Diafragma", "ossos_partes_moles": "Ossos e partes moles",
         "dispositivos": "Dispositivos"}


def _img(view=RXView.PA, origin="model", ict=0.46, extra=(), zones=None, probs=None, **kw):
    st = [Structure(key=k, label=k, category="other", color="#fff", origin=origin) for k in ("heart", "right_lung")]
    ms = [RXMeasurement(key="cardiothoracic_ratio", label="ICT", value=ict)] if ict is not None else []
    ms += [RXMeasurement(key=k, label=k, value=v, unit=u) for k, v, u in extra]
    return RXImageAnalysis(instance_id="i1", view=view, region=BodyRegion.CHEST, image_png_b64="", width=8, height=8,
                           structures=st, measurements=ms, model_zones=zones or {}, model_probs=probs or {},
                           quality={"rotação": "possível rotação", "inspiração": "adequada", "penetração": "indeterminada"},
                           **kw)


def _a(img, codes=()):
    return RXAnalysis(study_id="s", images=[img], findings=[Finding(code=c, label=c) for c in codes])


CENARIOS = {
    "pa_modelo": _a(_img()),
    "pa_ict_alto": _a(_img(ict=0.58), ["rx.cardiomegaly"]),
    "pa_sinais_modelo": _a(_img(zones={"Effusion": "sugestivo", "Consolidation": "indeterminado", "Pneumothorax": "sugestivo"},
                                probs={"Effusion": 0.7, "Consolidation": 0.3, "Pneumothorax": 0.9})),
    "pa_outras_medidas": _a(_img(extra=[("mediastinal_width_ratio", 40.0, "%"), ("tracheal_deviation_pct", 6.0, "%"),
                                        ("hemidiaphragm_height_difference_pct", 20.0, "%"),
                                        ("lung_area_ratio_L_R", 0.9, None)]),
                            ["rx.mediastinal_widening", "rx.tracheal_deviation"]),
    "ap": _a(_img(view=RXView.AP, ict=0.55), ["rx.cardiomegaly"]),
    "perfil": _a(_img(view=RXView.LATERAL, ict=None)),
    "heuristica": _a(_img(origin="heuristic", ict=0.64, extra=[("mediastinal_width_ratio", 40.0, "%")])),
    "fora_de_escopo": _a(_img(out_of_scope=True, scope_reason="não é radiografia de tórax adulto")),
}


def _secao(l, id_):
    return next(s for s in l.secoes if s.id == id_)


@pytest.mark.parametrize("nome", CENARIOS)
def test_rx_laudo_toda_regiao_tem_frase_e_sem_fato_diz_nao_avaliado(nome):
    a = CENARIOS[nome]
    l, f = LA.build_laudo(a), FI.build_ficha(a)
    texto = "\n".join(fr.texto for fr in _secao(l, "achados").frases)
    for c in f.cobertura:
        frases = [fr.texto for fr in _secao(l, "achados").frases if fr.texto.startswith(NOMES[c.regiao])]
        assert frases, (nome, c.regiao)
        if not c.avaliada:
            assert any("não avaliado" in t for t in frases), (nome, c.regiao)
    assert texto


@pytest.mark.parametrize("nome", CENARIOS)
def test_rx_laudo_nunca_normal_nem_palavra_proibida(nome):
    md = LA.render_markdown(LA.build_laudo(CENARIOS[nome]))
    assert LX.termos_proibidos(md) == []
    assert not re.search(r"\bnormal", md, re.I)


@pytest.mark.parametrize("nome", CENARIOS)
def test_rx_laudo_bloco_critico_sempre_presente_na_impressao(nome):
    l = LA.build_laudo(CENARIOS[nome])
    assert any("pneumotórax, pneumoperitônio" in fr.texto.lower() and fr.nivel == FI.Nivel.NAO_AVALIADO
               for fr in _secao(l, "impressao").frases)


@pytest.mark.parametrize("nome", CENARIOS)
def test_rx_laudo_frases_respeitam_lexico_fontes_e_fatos(nome):
    a = CENARIOS[nome]
    l, f = LA.build_laudo(a), FI.build_ficha(a)
    ids = {x.id for x in f.fatos}
    for s in l.secoes:
        for fr in s.frases:
            assert LX.problemas(fr.texto, fr.nivel) == [], (nome, fr.texto)
            assert set(fr.fatos) <= ids
            FT.citar(fr.fontes)
            assert fr.secao == s.id


@pytest.mark.parametrize("nome", CENARIOS)
def test_rx_laudo_sem_phi_no_markdown(nome):
    assert guard.scan_text(LA.render_markdown(LA.build_laudo(CENARIOS[nome]))) is None


def test_rx_laudo_ict_pa_baixo_usa_frase_molde():
    t = [fr.texto for fr in _secao(LA.build_laudo(CENARIOS["pa_modelo"]), "achados").frases]
    assert "Índice cardiotorácico medido 0,46 (limite clássico 0,50 em PA)." in t


def test_rx_laudo_ict_pa_alto_sugere_aumento_e_entra_na_impressao():
    l = LA.build_laudo(CENARIOS["pa_ict_alto"])
    imp = " ".join(fr.texto for fr in _secao(l, "impressao").frases)
    assert "sugere aumento da silhueta cardíaca (critério de acurácia limitada; correlacionar)" in imp


def test_rx_laudo_ap_nao_afirma_cardiomegalia():
    md = LA.render_markdown(LA.build_laudo(CENARIOS["ap"]))
    assert "magnifica o coração; não usar para afirmar cardiomegalia" in md
    assert "perfil ou PA" in md


def test_rx_laudo_heuristica_ict_nao_medido():
    md = LA.render_markdown(LA.build_laudo(CENARIOS["heuristica"]))
    assert "Silhueta cardíaca não medida com confiança (segmentação de baixa confiabilidade)." in md
    assert "0,64" not in md


def test_rx_laudo_sinais_do_modelo_ficam_fora_da_impressao():
    l = LA.build_laudo(CENARIOS["pa_sinais_modelo"])
    modelo = " ".join(fr.texto for fr in _secao(l, "sinais_modelo").frases)
    assert "possível derrame pleural" in modelo and "probabilidade calibrada ≈ 0,7" in modelo
    assert "indeterminado para consolidação" in modelo
    assert "pneumotórax" in modelo.lower()
    imp = " ".join(fr.texto for fr in _secao(l, "impressao").frases).lower()
    assert "derrame" not in imp and "consolidação" not in imp
    assert all(fr.nivel in (FI.Nivel.SUGERIDO_MODELO, FI.Nivel.NAO_AVALIADO) for fr in _secao(l, "sinais_modelo").frases)


def test_rx_laudo_pneumotorax_do_modelo_nunca_possivel():
    modelo = " ".join(fr.texto for fr in _secao(LA.build_laudo(CENARIOS["pa_sinais_modelo"]), "sinais_modelo").frases)
    assert "possível pneumotórax" not in modelo.lower()


def test_rx_laudo_secoes_na_ordem_da_spec():
    assert [s.id for s in LA.build_laudo(CENARIOS["pa_modelo"]).secoes] == [
        "identificacao_tecnica", "qualidade", "achados", "sinais_modelo", "impressao", "recomendacoes", "revisao_medica"]


def test_rx_laudo_fora_de_escopo_so_avisa_e_nao_mede():
    md = LA.render_markdown(LA.build_laudo(CENARIOS["fora_de_escopo"]))
    assert "fora do escopo" in md.lower() and "adulto" in md
    assert "Índice cardiotorácico" not in md


def test_rx_laudo_markdown_marca_rascunho_e_nota_de_ia():
    md = LA.render_markdown(LA.build_laudo(CENARIOS["pa_modelo"]))
    assert "rascunho" in md.lower() and "revisão médica" in md.lower() and "decisão final é do médico" in md


def test_rx_laudo_heuristica_nao_repete_frase_de_achado():
    textos = [f.texto for s in LA.build_laudo(CENARIOS["heuristica"]).secoes if s.id == "achados" for f in s.frases]
    assert len(textos) == len(set(textos))
