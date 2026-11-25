"""Tarefa 4: ficha rx_ficha/v1 (fatos F com origem/nível + cobertura por região)."""
import pytest

from app.rx import ficha as FI
from app.rx import fontes as FT
from app.schemas import BodyRegion, RXAnalysis, RXImageAnalysis, RXMeasurement, RXView, Structure


def _st(key, origin):
    return Structure(key=key, label=key, category="other", color="#fff", origin=origin)


def _img(view=RXView.PA, origin="model", ict=0.46, extra=(), quality=None, zones=None, probs=None, scores=None,
         **kw):
    ms = []
    if ict is not None:
        ms.append(RXMeasurement(key="cardiothoracic_ratio", label="ICT", value=ict))
    ms.extend(RXMeasurement(key=k, label=k, value=v, unit=u) for k, v, u in extra)
    return RXImageAnalysis(instance_id="i1", view=view, region=BodyRegion.CHEST, image_png_b64="", width=8, height=8,
                           structures=[_st("heart", origin), _st("right_lung", origin)], measurements=ms,
                           quality=quality or {"rotação": "adequada", "inspiração": "adequada (≈9 arcos)",
                                               "penetração": "adequada"},
                           model_zones=zones or {}, model_probs=probs or {}, model_scores=scores or {}, **kw)


def _fi(img, findings=()):
    return FI.build_ficha(RXAnalysis(study_id="s", images=[img], findings=list(findings)))


def _fato(f, chave):
    return next((x for x in f.fatos if x.chave == chave), None)


def _cob(f, regiao):
    return next(c for c in f.cobertura if c.regiao == regiao)


def test_rx_ficha_versao_e_regioes_completas():
    f = _fi(_img())
    assert f.versao == "rx_ficha/v1"
    assert [c.regiao for c in f.cobertura] == list(FI.REGIOES)


def test_rx_ficha_ict_modelo_pa_medido_e_cobertura_avaliada():
    f = _fi(_img(ict=0.46))
    ict = _fato(f, "ict")
    assert (ict.nivel, ict.origem, ict.valor, ict.regiao) == (FI.Nivel.MEDIDO, "modelo", 0.46, "coracao_vasos")
    assert _cob(f, "coracao_vasos").avaliada is True


def test_rx_ficha_ict_acima_de_050_em_pa_e_regra():
    assert _fato(_fi(_img(ict=0.58)), "ict").nivel == FI.Nivel.REGRA


def test_rx_ficha_ict_heuristica_nao_avaliado():
    f = _fi(_img(origin="heuristic", ict=0.64))
    ict = _fato(f, "ict")
    assert ict.nivel == FI.Nivel.NAO_AVALIADO and ict.valor is None
    assert _cob(f, "coracao_vasos").avaliada is False


def test_rx_ficha_ap_leva_ressalva_de_magnificacao():
    ict = _fato(_fi(_img(view=RXView.AP, ict=0.55)), "ict")
    assert any("magnifica" in r for r in ict.ressalvas)
    assert ict.nivel == FI.Nivel.REGRA


def test_rx_ficha_sem_dispositivos_nao_avaliado():
    f = _fi(_img())
    d = _fato(f, "dispositivos")
    assert d.nivel == FI.Nivel.NAO_AVALIADO and d.valor is None
    assert _cob(f, "dispositivos").avaliada is False
    for r in ("pleura", "ossos_partes_moles"):
        assert _cob(f, r).avaliada is False


def test_rx_ficha_modelo_nao_sugerido_nao_vira_fato_e_indeterminado_vira():
    f = _fi(_img(zones={"Effusion": "nao_sugerido", "Consolidation": "indeterminado", "Atelectasis": "sugestivo"},
                 probs={"Effusion": 0.01, "Consolidation": 0.3, "Atelectasis": 0.7}))
    assert _fato(f, "modelo.effusion") is None
    assert _fato(f, "modelo.consolidation").zona == "indeterminado"
    a = _fato(f, "modelo.atelectasis")
    assert (a.nivel, a.regiao, a.valor) == (FI.Nivel.SUGERIDO_MODELO, "pulmoes", 0.7)
    assert _cob(f, "pulmoes").sinal_modelo is True and _cob(f, "pulmoes").avaliada is False


def test_rx_ficha_pneumotorax_nunca_sugestivo():
    f = _fi(_img(zones={"Pneumothorax": "sugestivo"}, probs={"Pneumothorax": 0.9}))
    p = _fato(f, "modelo.pneumothorax")
    assert p.zona == "indeterminado" and any("insuficiente" in r for r in p.ressalvas)


def test_rx_ficha_mediastino_regra_vem_das_regras_e_heuristica_some():
    from app.schemas import Finding
    reg = Finding(code="rx.mediastinal_widening", label="x", severity="abnormal")
    f = _fi(_img(extra=[("mediastinal_width_ratio", 40.0, "%")]), [reg])
    m = _fato(f, "mediastino_largura_pct")
    assert (m.nivel, m.regiao) == (FI.Nivel.REGRA, "mediastino_hilos")
    assert not m.fontes            # limiar local sem fonte primária (N7)
    h = _fi(_img(origin="heuristic", extra=[("mediastinal_width_ratio", 40.0, "%")]))
    assert _fato(h, "mediastino_largura_pct").nivel == FI.Nivel.NAO_AVALIADO


def test_rx_ficha_qualidade_vira_fatos_com_fonte_verificada():
    f = _fi(_img(quality={"rotação": "possível rotação", "inspiração": "possivelmente insuficiente", "penetração": "indeterminada"}))
    assert _fato(f, "rotacao").valor == "possivelmente_inadequada"
    assert _fato(f, "inspiracao").valor == "possivelmente_inadequada"
    assert _fato(f, "penetracao").valor == "indeterminada"
    assert all(x.nivel == FI.Nivel.QUALIDADE for x in f.fatos if x.chave in ("rotacao", "inspiracao", "penetracao"))


def test_rx_ficha_perfil_e_fora_de_escopo_sem_medidas():
    lat = _fi(_img(view=RXView.LATERAL, ict=None))
    assert all(not c.avaliada for c in lat.cobertura) and lat.fora_de_escopo is False
    fe = _fi(_img(out_of_scope=True, scope_reason="não é RX de tórax adulto"))
    assert fe.fora_de_escopo is True and "adulto" in fe.motivo_fora_de_escopo
    assert _fato(fe, "ict") is None


def test_rx_ficha_ids_estaveis_por_ordem_e_modelos_frozen():
    a, b = _fi(_img()), _fi(_img())
    assert a == b
    assert [x.id for x in a.fatos] == [f"F{i}" for i in range(1, len(a.fatos) + 1)]
    with pytest.raises(Exception):
        a.fatos[0].valor = 1
    with pytest.raises(Exception):
        a.versao = "x"


def test_rx_ficha_fontes_todas_verificadas():
    f = _fi(_img(ict=0.58, zones={"Effusion": "sugestivo"}, probs={"Effusion": 0.7}))
    FT.citar([s for x in f.fatos for s in x.fontes])
