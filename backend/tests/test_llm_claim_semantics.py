"""Laudo v2: lastro SEMÂNTICO das afirmações (o achado/medida do texto tem de casar com o do fato [F] citado).

Regressão da auditoria: afirmação falsa com identificadores válidos (ids existentes) era aceita. Sem rede."""
import copy

import pytest

import laudo_fixtures as F
from app.ecg import features as FT
from app.llm import validate as V


def _ficha(summary=F.CASO1_OK):
    return FT.features_from_summary(summary, sexo="M")


def _cid(ficha, card_id):
    return next(c.id for c in ficha.cartoes if c.card_id == card_id)


def _claim(secao, texto, fatos, criterios):
    return {"secao": secao, "texto": texto, "fatos": list(fatos), "criterios": list(criterios)}


def _com_achado(code, label, severity="abnormal"):
    s = copy.deepcopy(F.CASO1_OK)
    s["achados_por_regras"] = s["achados_por_regras"] + [
        {"code": code, "label": label, "severity": severity, "evidence": ["QRS 150 ms"]}]
    return s


def _nao_meta_ids(ficha):
    return [f.id for f in ficha.fatos if f.tipo != "meta"]


def _nao_generico_ids(ficha):
    return [c.id for c in ficha.cartoes if c.card_id not in V.GENERIC_CARD_IDS]


FALSAS = [
    "Eletrocardiograma dentro dos limites da normalidade.",
    "ECG normal.",
    "Traçado sem alterações.",
    "Não há sobrecarga ventricular esquerda.",
    "Bloqueio de ramo esquerdo completo.",
    "Sobrecarga atrial direita.",
    "Não há supradesnivelamento de ST nem isquemia.",
    "Sem sinais de sobrecarga atrial esquerda.",
    "Infarto agudo do miocárdio anterior.",
    "Bloqueio atrioventricular de primeiro grau.",
]


# ---------------------------------------------------------------- caso do probe: F26 + C1
@pytest.mark.parametrize("texto", FALSAS)
def test_claim_falsa_com_ids_validos_do_probe_e_rejeitada(texto):
    f = _ficha()
    c = _claim("impressao", texto, [f.fato_por_chave("indice.cornell_voltagem").id], [_cid(f, "lvh.cornell_voltagem")])
    assert V.claim_issues(c, f), texto


@pytest.mark.parametrize("texto", FALSAS)
def test_claim_falsa_citando_todos_os_fatos_e_cartoes_nao_meta_e_rejeitada(texto):
    f = _ficha()
    c = _claim("impressao", texto, _nao_meta_ids(f), _nao_generico_ids(f))
    assert V.claim_issues(c, f), texto


# ---------------------------------------------------------------- (a) código do achado tem de coincidir
def test_claim_achado_com_fato_de_outro_codigo_e_rejeitada():
    f = _ficha(_com_achado("ecg.lbbb", "Bloqueio de ramo esquerdo"))
    cartao = _cid(f, "conducao.bre_completo")
    errada = _claim("complexo_qrs", "Bloqueio de ramo esquerdo.", [f.fato_por_chave("indice.cornell_voltagem").id],
                    [cartao])
    certa = _claim("complexo_qrs", "Bloqueio de ramo esquerdo.", [f.fato_por_chave("achado.ecg.lbbb").id], [cartao])
    assert any("mesmo achado" in m for m in V.claim_issues(errada, f))
    assert not [m for m in V.claim_issues(certa, f) if "mesmo achado" in m]


def test_claim_achado_presente_na_ficha_mas_nao_citado_e_rejeitada():
    f = _ficha()
    c = _claim("impressao", "Sobrecarga atrial esquerda.", [f.fato_por_chave("globais.heart_rate_bpm").id],
               [_cid(f, "normal.fc_ritmo")])
    assert any("mesmo achado" in m for m in V.claim_issues(c, f))


def test_claim_achado_com_fato_correto_e_aceita():
    f = _ficha()
    c = _claim("impressao", "Sobrecarga atrial esquerda (limítrofe).",
               [f.fato_por_chave("achado.ecg.left_atrial_enlargement").id, f.fato_por_chave("achado.ecg.lvh_voltage").id],
               [_cid(f, "lvh.sbc_interpretacao")])
    assert V.claim_issues(c, f) == []


def test_claim_medida_com_chave_de_outro_fato_e_rejeitada():
    f = _ficha()
    c = _claim("intervalos", "Intervalo PR normal.", [f.fato_por_chave("globais.heart_rate_bpm").id],
               [_cid(f, "normal.fc_ritmo")])
    assert any("mesmo achado" in m or "medida" in m for m in V.claim_issues(c, f))


def test_claim_medida_com_fato_da_mesma_chave_e_aceita():
    f = _ficha()
    c = _claim("intervalos", "Intervalo PR de 148 ms.", [f.fato_por_chave("globais.pr_ms").id],
               [_cid(f, "normal.p_pr")])
    assert V.claim_issues(c, f) == []


def test_claim_indice_que_nao_preenche_nao_sustenta_afirmacao_de_preenchimento():
    f = _ficha()
    c = _claim("complexo_qrs", "Peguero-Lo Presti preenche o critério de HVE.",
               [f.fato_por_chave("indice.peguero_lo_presti").id], [_cid(f, "lvh.peguero")])
    assert V.claim_issues(c, f)


def test_claim_bre_aceita_quando_ha_regra_lbbb_citada():
    f = _ficha(_com_achado("ecg.lbbb", "Bloqueio de ramo esquerdo"))
    cartao = _cid(f, "conducao.bre_completo")
    c = _claim("complexo_qrs", "Bloqueio de ramo esquerdo.", [f.fato_por_chave("achado.ecg.lbbb").id], [cartao])
    assert V.claim_issues(c, f) == []


# ---------------------------------------------------------------- (b) normal / negação com regra ativa
def test_claim_normal_rejeitada_quando_ha_regra_anormal_ativa_mesmo_citando_o_fato_da_regra():
    f = _ficha()
    c = _claim("impressao", "Eletrocardiograma dentro dos limites da normalidade.",
               [f.fato_por_chave("achado.ecg.lvh_voltage").id], [_cid(f, "lvh.sokolow_lyon")])
    assert any("normal" in m.lower() for m in V.claim_issues(c, f))


def test_claim_negacao_de_achado_com_regra_ativa_e_rejeitada():
    f = _ficha()
    c = _claim("impressao", "Não há sobrecarga ventricular esquerda.",
               [f.fato_por_chave("achado.ecg.lvh_voltage").id], [_cid(f, "lvh.sokolow_lyon")])
    assert any("contradiz" in m for m in V.claim_issues(c, f))


def test_claim_negacao_sem_qualificador_nao_vale_mesmo_sem_regra():
    f = _ficha()
    c = _claim("st_t", "Não há supradesnivelamento de ST.", [f.fato_por_chave("derivacao.V5").id],
               [_cid(f, "lvh.sokolow_lyon")])
    assert any("não exclui" in m for m in V.claim_issues(c, f))


def test_claim_negacao_qualificada_pelas_regras_automaticas_e_aceita():
    f = _ficha()
    c = _claim("st_t", "Nenhuma regra automática de supradesnivelamento de ST disparou.",
               [f.fato_por_chave("derivacao.V5").id], [_cid(f, "lvh.sokolow_lyon")])
    assert not [m for m in V.claim_issues(c, f) if "não exclui" in m or "contradiz" in m]


def test_claim_normal_aceita_so_com_regra_normal_citada_e_qualificada_pelas_regras():
    s = copy.deepcopy(F.CASO1_OK)
    s["achados_por_regras"] = [{"code": "ecg.within_normal_limits", "label": "x", "severity": "normal",
                                "evidence": ["nenhuma regra de anormalidade foi acionada"]}]
    f = _ficha(s)
    fato = f.fato_por_chave("achado.ecg.within_normal_limits").id
    cartao = _cid(f, "normal.fc_ritmo")
    sem_qual = _claim("impressao", "Eletrocardiograma normal.", [fato], [cartao])
    com_qual = _claim("impressao", "Nenhuma regra automática disparou; eletrocardiograma sem alterações pelas regras.",
                      [fato], [cartao])
    assert V.claim_issues(sem_qual, f)
    assert V.claim_issues(com_qual, f) == []


def test_claim_normal_sem_fato_da_regra_normal_e_rejeitada_mesmo_sem_regra_anormal():
    s = copy.deepcopy(F.CASO1_OK)
    s["achados_por_regras"] = []
    f = _ficha(s)
    c = _claim("impressao", "Eletrocardiograma dentro dos limites da normalidade pelas regras automáticas.",
               [f.fato_por_chave("globais.heart_rate_bpm").id], [_cid(f, "normal.fc_ritmo")])
    assert V.claim_issues(c, f)


def test_claim_negacao_em_categoria_suprimida_nao_escapa_como_hedge():
    f = _ficha(F.CASO1_ERRADA)
    c = _claim("st_t", "Não há isquemia nem infra de ST.", [f.fato_por_chave("indice.sokolow_lyon").id],
               [_cid(f, "lvh.sokolow_lyon")])
    assert any("suprimido" in m for m in V.claim_issues(c, f))


# ---------------------------------------------------------------- (c) meta e cartão genérico não bastam
def test_claim_so_com_fato_meta_fora_de_qualidade_tecnica_e_rejeitada():
    f = _ficha()
    meta = f.fato_por_chave("aquisicao").id
    c = _claim("impressao", "Traçado digitalizado em 500 Hz.", [meta], [_cid(f, "lvh.sokolow_lyon")])
    assert any("meta" in m for m in V.claim_issues(c, f))


def test_claim_so_com_cartao_generico_fora_de_qualidade_tecnica_e_rejeitada():
    f = _ficha()
    c = _claim("impressao", "Frequência cardíaca de 68 bpm.", [f.fato_por_chave("globais.heart_rate_bpm").id],
               [_cid(f, "normal.convencoes_medida")])
    assert any("genérico" in m or "sem lastro" in m for m in V.claim_issues(c, f))


def test_claim_qualidade_tecnica_continua_valida_com_meta_e_cartao_generico():
    f = _ficha()
    c = _claim("qualidade_tecnica", "Traçado digitalizado a 500 Hz, 10 derivações com medidas.",
               [f.fato_por_chave("aquisicao").id], [_cid(f, "normal.convencoes_medida")])
    assert V.claim_issues(c, f) == []


def test_claim_qualidade_tecnica_nao_sustenta_diagnostico_com_fato_meta():
    f = _ficha()
    c = _claim("qualidade_tecnica", "Bloqueio de ramo esquerdo.", [f.fato_por_chave("aquisicao").id],
               [_cid(f, "normal.convencoes_medida")])
    assert V.claim_issues(c, f)


def test_claim_fato_nao_avaliavel_nao_sustenta_afirmacao_da_medida():
    f = _ficha(F.CASO1_ERRADA)
    nao_av = next(x for x in f.fatos if x.nao_avaliavel and x.chave == "globais.qrs_ms")
    c = _claim("intervalos", "Duração do QRS alargada.", [nao_av.id], [_cid(f, "lvh.sokolow_lyon")])
    assert V.claim_issues(c, f)


# ---------------------------------------------------------------- (d) o que já funcionava segue valendo
def test_claim_id_inexistente_e_numero_inventado_continuam_rejeitados():
    f = _ficha()
    fc, cartao = f.fato_por_chave("globais.heart_rate_bpm").id, _cid(f, "normal.fc_ritmo")
    assert any("fora da lista" in m for m in V.claim_issues(_claim("ritmo_frequencia", "FC 68 bpm.", ["F999"], [cartao]), f))
    assert any("número" in m for m in V.claim_issues(_claim("ritmo_frequencia", "FC 90 bpm.", [fc], [cartao]), f))


def test_claim_lista_de_afirmacoes_validas_do_caso1_segue_aceita():
    f = _ficha()
    ok = [
        _claim("ritmo_frequencia", "Frequência cardíaca de 68 bpm.", [f.fato_por_chave("globais.heart_rate_bpm").id],
               [_cid(f, "normal.fc_ritmo")]),
        _claim("complexo_qrs", "Sokolow-Lyon 60 mm, acima do limiar de 35 mm: critério de voltagem para HVE preenchido.",
               [f.fato_por_chave("indice.sokolow_lyon").id], [_cid(f, "lvh.sokolow_lyon")]),
        _claim("impressao", "Padrão sugestivo de miocardiopatia hipertrófica; correlacionar com ecocardiograma/RM.",
               [f.fato_por_chave("achado.ecg.lvh_voltage").id, f.fato_por_chave("indice.peguero_lo_presti").id],
               [_cid(f, "cmh.voltagem_extrema")]),
    ]
    assert [V.claim_issues(c, f) for c in ok] == [[], [], []]


# ---------------------------------------------------------------- T1: janela de negação para em vírgula/"com"/"observa"
def _msgs(f, texto, fatos, cartao_id):
    return V.claim_issues(_claim("impressao", texto, fatos, [cartao_id]), f)


def test_negacao_nao_atravessa_virgula_e_hemibloqueio_afirmado_nao_vira_negado():
    f = _ficha(_com_achado("ecg.lafb", "Hemibloqueio anterior esquerdo"))
    fatos = [f.fato_por_chave("achado.ecg.lafb").id]
    texto = "Ritmo sinusal sem evidência de BAV, com hemibloqueio anterior esquerdo."
    msgs = _msgs(f, texto, fatos, _cid(f, "bloqueio.bdas"))
    assert not [m for m in msgs if "hemibloqueio" in m], msgs
    assert any("bloqueio atrioventricular" in m for m in msgs)       # a negação de BAV segue sem qualificador


def test_negacao_para_em_observa_se_e_brd_afirmado_nao_vira_negado():
    f = _ficha(_com_achado("ecg.rbbb", "Bloqueio de ramo direito"))
    fatos = [f.fato_por_chave("achado.ecg.rbbb").id]
    msgs = _msgs(f, "Sem pré-excitação, observa-se BRD.", fatos, _cid(f, "lvh.cornell_voltagem"))
    assert not [m for m in msgs if "bloqueio de ramo direito" in m], msgs


@pytest.mark.parametrize("texto", ["Sem sinais de BRD mas com BAV.", "Não há BRD porém há BAV."])
def test_negacao_ainda_vale_antes_de_mas_e_porem(texto):
    f = _ficha(_com_achado("ecg.rbbb", "Bloqueio de ramo direito"))
    msgs = _msgs(f, texto, [f.fato_por_chave("achado.ecg.lvh_voltage").id], _cid(f, "lvh.sokolow_lyon"))
    assert any("bloqueio de ramo direito" in m and "contradiz" in m for m in msgs), msgs


@pytest.mark.parametrize("texto", ["Sem HVE mas com BRD.", "Não há HVE porém há BRD.", "Sem sinais de BAV, com BRD.",
                                   "Sem BAV nota-se BRD."])
def test_negacao_corta_em_mas_porem_com_nota_se(texto):
    f = _ficha(_com_achado("ecg.rbbb", "Bloqueio de ramo direito"))
    msgs = _msgs(f, texto, [f.fato_por_chave("achado.ecg.rbbb").id], _cid(f, "lvh.cornell_voltagem"))
    assert not [m for m in msgs if "bloqueio de ramo direito" in m], (texto, msgs)


def test_nao_ha_continua_negado_e_nao_se_observa_tambem():
    f = _ficha(_com_achado("ecg.rbbb", "Bloqueio de ramo direito"))
    fatos = [f.fato_por_chave("achado.ecg.rbbb").id]
    for texto in ("Não há BRD.", "Não se observa BRD.", "Sem sinais de BRD."):
        msgs = _msgs(f, texto, fatos, _cid(f, "lvh.cornell_voltagem"))
        assert any("contradiz" in m for m in msgs), (texto, msgs)


# ---------------------------------------------------------------- T2: Sgarbossa/Smith só como recomendação, nunca como resultado
def _ficha_st_nao_avaliavel():
    return _ficha(_com_achado("ecg.st_not_assessable", "ST não avaliável", "borderline"))


@pytest.mark.parametrize("texto", [
    "Critérios de Sgarbossa ausentes.", "Sgarbossa negativo.", "Sgarbossa positivo.", "Critérios de Smith presentes.",
    "Escore de Sgarbossa 3 pontos.", "Sgarbossa não preenchido.", "Sgarbossa modificado: nenhum critério preenchido.",
])
def test_sgarbossa_com_resultado_e_rejeitado(texto):
    f = _ficha_st_nao_avaliavel()
    fid = f.fato_por_chave("achado.ecg.st_not_assessable").id
    msgs = V.claim_issues(_claim("st_t", texto + f" [{fid}]", [fid], [_cid(f, "isquemia.sgarbossa")]), f)
    assert any("Sgarbossa" in m for m in msgs), (texto, msgs)


@pytest.mark.parametrize("texto", ["Considerar critérios de Sgarbossa/Smith.",
                                   "ST não avaliável de forma confiável; considerar critérios de Sgarbossa/Smith."])
def test_sgarbossa_como_recomendacao_e_aceito(texto):
    f = _ficha_st_nao_avaliavel()
    fid = f.fato_por_chave("achado.ecg.st_not_assessable").id
    c = _claim("recomendacao", texto + f" [{fid}]", [fid], [_cid(f, "isquemia.sgarbossa")])
    assert V.claim_issues(c, f) == []


# ---------------------------------------------------------------- T3: "preenche" só vale no trecho que nomeia o índice/critério
def _msgs_preenche(texto):
    f = _ficha()
    fid = f.fato_por_chave("indice.peguero_lo_presti").id           # índice que NÃO preenche
    c = _claim("complexo_qrs", texto, [fid], [_cid(f, "lvh.peguero")])
    return [m for m in V.claim_issues(c, f) if "preenche" in m]


def test_preenche_de_outro_trecho_nao_contamina_indice_negado():
    assert _msgs_preenche("Peguero-Lo Presti 14 mm não preenche; deflexão positiva em V5.") == []


def test_indice_que_nao_preenche_afirmado_como_preenchido_continua_rejeitado():
    assert _msgs_preenche("Peguero-Lo Presti preenche o critério de HVE.")
    assert _msgs_preenche("Voltagem normal em V5; Peguero-Lo Presti preenche o critério.")
