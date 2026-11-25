"""Laudo v2: saída JSON com citações [F]/[C] de lista fechada, validador generalizado e abstenção.

LLM SIMULADA em todos os testes (nenhuma chamada de rede)."""
import json
import re

import pytest

import laudo_fixtures as F
from app import llm
from app.ecg import features as FT
from app.llm import client as C
from app.llm import laudo as L
from app.llm import validate as V
from test_llm import FakeClient, _ecg, _png


def _ficha(summary=F.CASO1_OK):
    return FT.features_from_summary(summary, sexo="M")


def _f(ficha, chave):
    return ficha.fato_por_chave(chave).id


def _c(ficha, card_id):
    return next(c.id for c in ficha.cartoes if c.card_id == card_id)


def _claim(secao, texto, fatos, criterios):
    return {"secao": secao, "texto": texto, "fatos": list(fatos), "criterios": list(criterios)}


def _resp(*claims):
    return json.dumps({"afirmacoes": list(claims)}, ensure_ascii=False)


def _run(ficha, *claims, raw=None):
    return L.generate_laudo_v2(ficha, lambda s, u: raw if raw is not None else _resp(*claims))


def _sok(ficha, texto="Sokolow-Lyon 60 mm, acima do limiar de 35 mm: critério de voltagem para HVE preenchido."):
    return _claim("complexo_qrs", texto, [_f(ficha, "indice.sokolow_lyon")], [_c(ficha, "lvh.sokolow_lyon")])


def _corn(ficha):
    return _claim("complexo_qrs", "Cornell 58 mm, acima do limite de 28 mm para homens.",
                  [_f(ficha, "indice.cornell_voltagem")], [_c(ficha, "lvh.cornell_voltagem")])


def _fc(ficha, texto="Frequência cardíaca de 68 bpm."):
    return _claim("ritmo_frequencia", texto, [_f(ficha, "globais.heart_rate_bpm")], [_c(ficha, "normal.fc_ritmo")])


# ---------------------------------------------------------------- caminho feliz (caso1 do gabarito)
def test_laudo_v2_caso1_correto_emite_afirmacoes_citadas_com_cobertura_100():
    f = _ficha()
    cmh = _claim("impressao", "Padrão sugestivo de miocardiopatia hipertrófica; correlacionar com ecocardiograma/RM.",
                 [_f(f, "achado.ecg.lvh_voltage"), _f(f, "indice.peguero_lo_presti")], [_c(f, "cmh.voltagem_extrema")])
    lau = _run(f, _fc(f), _sok(f), cmh)
    assert lau.versao == "v2" and lau.abstencao is None and lau.aviso_topo == []
    assert len(lau.citacoes) == 3 and lau.rejeitadas == []
    assert lau.validacao["cobertura_citacao_pct"] == 100
    assert all(c.fatos and c.criterios for c in lau.citacoes)
    assert re.search(r"\[F\d+; C\d+\]", lau.complexo_qrs)
    md = L.render_markdown_v2(lau, f)
    assert "Fontes das citações" in md and "[F" in md and "Rascunho" in md
    assert "Sokolow-Lyon 60 mm" in md


def test_laudo_v2_caso1_errado_abre_com_discordancia_e_rejeita_preexcitacao():
    f = _ficha(F.CASO1_ERRADA)
    hve = _sok(f)
    wpw = _claim("impressao", "Síndrome de pré-excitação (WPW).", [_f(f, "indice.sokolow_lyon")],
                 [_c(f, "lvh.sokolow_lyon")])
    isq = _claim("st_t", "Infra de ST inferior sugestivo de isquemia miocárdica.", [_f(f, "indice.sokolow_lyon")],
                 [_c(f, "lvh.sokolow_lyon")])
    lau = _run(f, hve, wpw, isq, _fc(f))
    assert lau.aviso_topo and "112" in " ".join(lau.aviso_topo)
    assert [c.secao for c in lau.citacoes] == ["complexo_qrs", "ritmo_frequencia"]
    assert len(lau.rejeitadas) == 2 and all("suprimido" in " ".join(r.motivos) for r in lau.rejeitadas)
    emitido = " ".join([lau.complexo_qrs, lau.st_t, *lau.impressao])
    assert not re.search(r"pré-excita|WPW|isquemi", emitido, re.I)
    md = L.render_markdown_v2(lau, f)
    assert md.index("DISCORDÂNCIA") < md.index("## Ritmo")


# ---------------------------------------------------------------- validador
def test_laudo_v2_afirmacao_sem_citacao_e_removida():
    f = _ficha()
    sem_f = _claim("ritmo_frequencia", "Ritmo sinusal.", [], [_c(f, "normal.fc_ritmo")])
    sem_c = _claim("ritmo_frequencia", "Frequência cardíaca de 68 bpm.", [_f(f, "globais.heart_rate_bpm")], [])
    lau = _run(f, _sok(f), _fc(f), sem_f, sem_c)
    assert len(lau.citacoes) == 2 and len(lau.rejeitadas) == 2 and lau.abstencao is None
    motivos = " ".join(m for r in lau.rejeitadas for m in r.motivos)
    assert "sem fatos" in motivos and "sem critérios" in motivos
    assert lau.validacao["cobertura_citacao_pct"] == 100 and lau.validacao["afirmacoes_rejeitadas"] == 2


def test_laudo_v2_identificador_fora_da_lista_e_rejeitado():
    f = _ficha()
    ruim_f = _claim("ritmo_frequencia", "Frequência cardíaca de 68 bpm.", ["F999"], [_c(f, "normal.fc_ritmo")])
    ruim_c = _claim("ritmo_frequencia", "Frequência cardíaca de 68 bpm.", [_f(f, "globais.heart_rate_bpm")], ["C99"])
    inline = _claim("ritmo_frequencia", "Frequência cardíaca de 68 bpm [F77].", [_f(f, "globais.heart_rate_bpm")],
                    [_c(f, "normal.fc_ritmo")])
    lau = _run(f, _sok(f), _fc(f), _corn(f), ruim_f, ruim_c, inline)
    assert len(lau.citacoes) == 3 and len(lau.rejeitadas) == 3
    assert all("fora da lista" in " ".join(r.motivos) for r in lau.rejeitadas)


def test_laudo_v2_numero_que_nao_bate_com_a_ficha_e_rejeitado():
    f = _ficha()
    errado = _fc(f, "Frequência cardíaca de 90 bpm.")
    de_outro_fato = _claim("intervalos", "Intervalo PR de 148 ms.", [_f(f, "globais.heart_rate_bpm")],
                           [_c(f, "normal.fc_ritmo")])
    lau = _run(f, _sok(f), _fc(f), _corn(f), errado, de_outro_fato)
    assert len(lau.citacoes) == 3 and len(lau.rejeitadas) == 2
    assert all("número" in " ".join(r.motivos) for r in lau.rejeitadas)
    assert "90 bpm" not in L.render_markdown_v2(lau, f)


def test_laudo_v2_numero_de_limiar_do_cartao_citado_e_aceito():
    f = _ficha()
    assert len(_run(f, _corn(f)).citacoes) == 1


def test_laudo_v2_criterio_sem_lastro_nos_fatos_citados_e_rejeitado():
    f = _ficha()
    sem_lastro = _claim("ritmo_frequencia", "Frequência cardíaca de 68 bpm.", [_f(f, "globais.heart_rate_bpm")],
                        [_c(f, "cmh.voltagem_extrema")])
    lau = _run(f, _sok(f), _fc(f), sem_lastro)
    assert len(lau.citacoes) == 2 and len(lau.rejeitadas) == 1
    assert "sem lastro" in " ".join(lau.rejeitadas[0].motivos)


def test_laudo_v2_achado_critico_sem_regra_e_rejeitado_mesmo_com_citacao_valida():
    f = _ficha()
    tv = _claim("impressao", "Taquicardia ventricular sustentada.", [_f(f, "globais.heart_rate_bpm")],
                [_c(f, "normal.fc_ritmo")])
    lau = _run(f, _sok(f), _fc(f), tv)
    assert len(lau.rejeitadas) == 1 and "crítico" in " ".join(lau.rejeitadas[0].motivos)
    assert not any("ventricular" in x for x in lau.impressao)


def test_laudo_v2_secao_invalida_e_rejeitada():
    f = _ficha()
    lau = _run(f, _sok(f), _fc(f), {**_fc(f), "secao": "diagnostico_livre"})
    assert len(lau.rejeitadas) == 1 and "seção" in " ".join(lau.rejeitadas[0].motivos)


# ---------------------------------------------------------------- abstenção
def test_laudo_v2_todas_rejeitadas_vira_abstencao_com_motivos_e_sem_texto_clinico():
    f = _ficha()
    lau = _run(f, _claim("impressao", "HVE grave.", [], []), _fc(f, "Frequência de 120 bpm."))
    assert lau.abstencao is not None and lau.abstencao.texto == "Sem laudo automático confiável."
    assert lau.abstencao.motivos and lau.impressao == [] and lau.complexo_qrs == "" and lau.citacoes == []
    md = L.render_markdown_v2(lau, f)
    assert "Sem laudo automático confiável" in md and "HVE grave" not in md and "120 bpm" not in md


def test_laudo_v2_maioria_rejeitada_abstem_em_vez_de_emitir_parcial():
    f = _ficha()
    lau = _run(f, _sok(f), _claim("impressao", "A.", [], []), _claim("impressao", "B.", [], []))
    assert lau.abstencao is not None and lau.citacoes == []


@pytest.mark.parametrize("raw", ["não é json", "[]", json.dumps({"afirmacoes": "x"}), json.dumps({}),
                                 json.dumps({"afirmacoes": []})])
def test_laudo_v2_resposta_malformada_ou_vazia_vira_abstencao(raw):
    lau = _run(_ficha(), raw=raw)
    assert lau.abstencao is not None and lau.abstencao.motivos and lau.citacoes == []


def test_laudo_v2_falha_da_llm_vira_abstencao():
    def boom(s, u):
        raise RuntimeError("rede")
    lau = L.generate_laudo_v2(_ficha(), boom)
    assert lau.abstencao is not None and "falha" in " ".join(lau.abstencao.motivos).lower()


def test_laudo_v2_qualidade_invalida_nao_chama_a_llm():
    f = FT.features_from_summary({"medidas_globais": {}, "medidas_por_derivacao": [], "achados_por_regras": []})
    chamadas = []
    lau = L.generate_laudo_v2(f, lambda s, u: chamadas.append(1) or "{}")
    assert chamadas == [] and lau.abstencao is not None and "sem medidas" in " ".join(lau.abstencao.motivos)


# ---------------------------------------------------------------- esquema e prompt
def test_laudo_v2_esquema_tem_lista_fechada_de_identificadores():
    f = _ficha()
    sch = L.output_schema_v2(f)
    item = sch["properties"]["afirmacoes"]["items"]
    assert sch["additionalProperties"] is False and item["additionalProperties"] is False
    assert item["properties"]["fatos"]["items"]["enum"] == f.fact_ids
    assert item["properties"]["criterios"]["items"]["enum"] == f.card_ids
    assert item["properties"]["fatos"]["minItems"] == 1 and item["properties"]["criterios"]["minItems"] == 1
    assert set(item["required"]) == {"secao", "texto", "fatos", "criterios"}


def test_laudo_v2_prompt_versionado_exige_citacao_e_proibe_imagem_e_calculo():
    p = L.system_prompt_v2()
    assert "ecg_laudo_v2" in p and "lista fechada" in p.lower() and "[F" in p and "[C" in p
    assert "não vê" in p.lower() and "não calcul" in p.lower()


def test_laudo_v2_flag_desligada_por_padrao(monkeypatch):
    monkeypatch.delenv("MEDLENS_LAUDO_V2", raising=False)
    assert L.v2_enabled() is False
    monkeypatch.setenv("MEDLENS_LAUDO_V2", "1")
    assert L.v2_enabled() is True


# ---------------------------------------------------------------- privacidade (LGPD): só texto
def test_laudo_v2_mensagem_ao_provedor_e_so_texto_sem_identificacao():
    s = {**F.CASO1_OK, "paciente": "Maria Souza", "study_id": "ORDER ECG22125996",
         "cabecalho_impresso": {**F.PRINTED, "nome": "Maria Souza"}, "avisos": ["Paciente Maria Souza"]}
    f = _ficha(s)
    visto = {}

    def call(system, user):
        visto.update(system=system, user=user)
        return _resp(_sok(f))

    L.generate_laudo_v2(f, call)
    assert isinstance(visto["system"], str) and isinstance(visto["user"], str)
    blob = visto["system"] + visto["user"]
    for proibido in ("Maria", "Souza", "ORDER", "ECG22125996", "data:image", "base64"):
        assert proibido not in blob
    assert not re.search(r"[A-Za-z0-9+/=]{200,}", blob)
    assert f.narrative() in visto["user"] and f.cards_block() in visto["user"]


@pytest.mark.parametrize("veneno", ["data:image/png;base64,AAAA", "A" * 300, "CPF 123.456.789-09",
                                    "nasc 01/02/1960", "ORDER ECG22125996", "fulano@example.com"])
def test_laudo_v2_guarda_bloqueia_payload_com_imagem_ou_identificacao(veneno):
    with pytest.raises(L.PayloadBloqueado):
        L.assert_text_only("sistema", "usuário " + veneno)


def test_laudo_v2_payload_bloqueado_vira_abstencao_sem_chamar_a_llm(monkeypatch):
    f = _ficha()
    monkeypatch.setattr(L, "user_message_v2", lambda ficha: "ORDER ECG22125996")
    chamadas = []
    lau = L.generate_laudo_v2(f, lambda s, u: chamadas.append(1) or "{}")
    assert chamadas == [] and lau.abstencao is not None


# ---------------------------------------------------------------- integração (ecg_report, cliente falso)
def _setup_v2(monkeypatch, outputs):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("MEDLENS_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("MEDLENS_LAUDO", "1")
    monkeypatch.setenv("MEDLENS_LAUDO_V2", "1")
    fake = FakeClient(outputs)
    monkeypatch.setattr(C, "make_client", lambda: fake)
    return fake


def _blocos(call):
    out = []
    for m in call["messages"]:
        c = m["content"]
        out += [c] if isinstance(c, str) else list(c)
    return out


def test_ecg_report_v2_nao_envia_imagem_e_faz_uma_unica_chamada(monkeypatch):
    f = FT.features_from_analysis(_ecg(), sexo=None)
    resp = _resp(_claim("ritmo_frequencia", "Frequência cardíaca de 72 bpm.", [_f(f, "globais.heart_rate_bpm")],
                        [_c(f, "normal.fc_ritmo")]))
    fake = _setup_v2(monkeypatch, [resp])
    rep = llm.ecg_report(_ecg(), _png())
    assert len(fake.calls) == 1
    for b in _blocos(fake.calls[0]):
        assert isinstance(b, str) or b.get("type") == "text"
    assert "image" not in json.dumps(fake.calls[0]["messages"]) and "base64" not in json.dumps(fake.calls[0])
    assert rep.available and rep.laudo["versao"] == "v2" and rep.laudo["abstencao"] is None
    assert "[F" in rep.laudo_markdown and rep.laudo_curto


def test_ecg_report_v2_resposta_invalida_vira_abstencao_explicita(monkeypatch):
    _setup_v2(monkeypatch, ["lixo"])
    rep = llm.ecg_report(_ecg(), None)
    assert rep.laudo["abstencao"]["texto"] == "Sem laudo automático confiável."
    assert "Sem laudo automático confiável" in rep.laudo_markdown


def test_ecg_report_flag_desligada_mantem_laudo_v1(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("MEDLENS_LAUDO", "0")
    monkeypatch.delenv("MEDLENS_LAUDO_V2", raising=False)
    fake = FakeClient([json.dumps({"description": "d", "findings": [], "differentials": [],
                                   "disagreements_with_measurements": [], "limitations": []})] * 2)
    monkeypatch.setattr(C, "make_client", lambda: fake)
    rep = llm.ecg_report(_ecg(), None)
    assert len(fake.calls) == 2 and rep.laudo is None
