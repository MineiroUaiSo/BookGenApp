"""Descrição completa do ECG em parágrafo único: base determinística + redação opcional por IA verificada.

LLM SIMULADA em todos os testes (nenhuma chamada de rede)."""
import json
import re

import pytest

from app import llm
from app.llm import descricao_ecg as D
from app.llm import ecg_claim_check as EC
from app.llm import laudo as L
from app.schemas import AIReport

# ------------------------------------------------------------------ fabricas de resumo (valores sintéticos)
LEADS_OK = [
    {"lead": "II", "p_duration_ms": 100, "r_amplitude_mv": 1.2, "t_amplitude_mv": 0.3, "st_j_mv": 0.0,
     "q_amplitude_mv": -0.05},
    {"lead": "V1", "s_amplitude_mv": -0.9, "r_amplitude_mv": 0.2, "st_j_mv": 0.0},
    {"lead": "V5", "r_amplitude_mv": 1.6, "st_j_mv": 0.0},
]


def _f(code, label, sev, ev=()):
    return {"code": code, "label": label, "severity": sev, "evidence": list(ev)}


def _sum(g, rules=(), leads=LEADS_OK, **extra):
    s = {"fonte": "image", "fs_hz": 500, "duracao_s": 10, "calibracao": {"gain_mm_mv": 10, "paper_speed_mm_s": 25},
         "medidas_globais": g, "medidas_por_derivacao": list(leads), "achados_por_regras": list(rules),
         "avisos": [], "qualidade_por_derivacao": {}}
    s.update(extra)
    return L.prepare_summary(s, sexo="M")


NORMAL_G = {"heart_rate_bpm": 72, "rr_mean_ms": 833, "rr_sd_ms": 20, "pr_ms": 160, "qrs_ms": 92, "qt_ms": 380,
            "qtc_bazett_ms": 416, "qtc_fridericia_ms": 410, "p_axis_deg": 45, "qrs_axis_deg": 50, "t_axis_deg": 40,
            "p_duration_ms": 100, "rhythm": "sinusal regular", "precordial_transition": "V3"}
R_SINUS = _f("ecg.sinus_rhythm", "Ritmo sinusal regular", "normal", ["FC 72 bpm"])
R_NORMAL = _f("ecg.within_normal_limits",
              "Nenhuma regra automática disparou; isso não exclui IAM, BAV ou outras alterações.", "normal",
              ["nenhuma regra de anormalidade foi acionada"])

S_NORMAL = _sum(NORMAL_G, [R_SINUS, R_NORMAL])
S_FA = _sum({"heart_rate_bpm": 118, "rr_mean_ms": 508, "rr_sd_ms": 180, "qrs_ms": 88, "qt_ms": 320,
             "qtc_bazett_ms": 440, "qrs_axis_deg": 20, "rhythm": "irregularmente irregular"},
            [_f("ecg.atrial_fibrillation", "Fibrilação atrial", "abnormal", ["RR irregularmente irregular"])])
S_QRS_LARGO = _sum({**NORMAL_G, "qrs_ms": 115, "qtc_bazett_ms": 430},
                   [R_SINUS, _f("ecg.qrs_borderline", "QRS limítrofe (110-119 ms)", "borderline",
                                ["QRS 115 ms (zona limítrofe 110-119 ms)",
                                 "critérios de BRD/BRE não preenchidos; sem distúrbio de condução definido"]),
                    R_NORMAL])
S_ST_NA = _sum({**NORMAL_G, "qrs_ms": 140},
               [R_SINUS, _f("ecg.st_not_assessable",
                            "ST não interpretável pelas regras; aplicar Sgarbossa/Smith manualmente", "borderline",
                            ["QRS largo (140 ms) sem critério de bloqueio definido"])])
S_VAZIO = _sum({}, [], leads=[])
S_SEM_NORMAL = _sum(NORMAL_G, [R_SINUS])
S_ST_DEP = _sum(NORMAL_G, [R_SINUS, _f("ecg.st_depression_inferior",
                                       "Infradesnivelamento do segmento ST (inferior: D2, D3, aVF)", "abnormal",
                                       ["ST em J+60: D2 -1.5 mm, D3 -1.2 mm, aVF -1.4 mm"])])

TODOS = {"normal": S_NORMAL, "fa": S_FA, "qrs_largo": S_QRS_LARGO, "st_na": S_ST_NA, "vazio": S_VAZIO,
         "sem_normal": S_SEM_NORMAL, "st_dep": S_ST_DEP}


def _frases(texto):
    return [p for p in re.split(r"(?<=[.!?])\s+", texto) if p.strip()]


def _det(s):
    return D.montar_deterministico(s)


# ------------------------------------------------------------------ parágrafo único e lastro
@pytest.mark.parametrize("nome", list(TODOS))
def test_paragrafo_unico_sem_quebra_de_linha(nome):
    t = _det(TODOS[nome])
    assert t and "\n" not in t and "\r" not in t and "  " not in t


@pytest.mark.parametrize("nome", list(TODOS))
def test_toda_frase_passa_na_barreira_qualitativa(nome):
    s = TODOS[nome]
    for fr in _frases(_det(s)):
        assert EC.sentence_problem(fr, s) is None, (nome, fr)


@pytest.mark.parametrize("nome", list(TODOS))
def test_sem_dado_pessoal(nome):
    from app.llm.guard import scan_text
    assert scan_text(_det(TODOS[nome])) is None


def test_cobre_todos_os_topicos_pedidos():
    t = _det(S_NORMAL).lower()
    for termo in ["ritmo", "frequência cardíaca", "72 bpm", "regular", "onda p", "intervalo pr", "160 ms", "eixo",
                  "qrs", "92 ms", "voltagem", "onda q", "r nas precordiais", "segmento st", "onda t", "qt",
                  "qtc", "416 ms", "sobrecarga", "bloqueio", "digitaliza", "limita", "impressão"]:
        assert termo in t, termo


# ------------------------------------------------------------------ casos clínicos
def test_fa_descreve_ritmo_fc_e_abstem_pr():
    t = _det(S_FA).lower()
    assert "fibrilação atrial" in t and "118 bpm" in t and "irregular" in t
    assert "intervalo pr não avaliado" in t
    assert "dentro dos limites" not in t
    assert t.rstrip(".").split(".")[-1].strip().startswith("impressão")


def test_qrs_largo_sem_bre_diz_limitrofe_e_nao_afirma_bloqueio():
    t = _det(S_QRS_LARGO)
    assert "limítrofe" in t and "115 ms" in t
    for fr in _frases(t):
        if re.search(r"bloqueio de ramo", fr, re.I):
            assert re.search(r"n[ãa]o|sem", fr, re.I) and "regras automáticas" in fr, fr


def test_st_nao_avaliavel_nao_nega_isquemia_nem_diz_normal():
    t = _det(S_ST_NA)
    low = t.lower()
    assert "st e a onda t não foram avaliados" in low or "st e a onda t não puderam" in low
    assert "isquemia" not in low and "infarto" not in low and "iam" not in re.findall(r"\b\w+\b", low)
    assert "dentro dos limites" not in low and "normal" not in re.sub(r"normalidade", "", low).replace("anormal", "")
    assert "alterações de st" not in low


def test_normal_por_regras_diz_regras_automaticas_e_nao_exclui():
    t = _det(S_NORMAL)
    imp = _frases(t)[-1]
    assert "dentro dos limites" in imp and "regras automáticas" in imp and "não exclui" in imp


def test_sem_achado_de_normalidade_nunca_afirma_normal():
    t = _det(S_SEM_NORMAL).lower()
    assert "dentro dos limites" not in t and "ecg normal" not in t


def test_st_com_achado_cita_derivacoes():
    t = _det(S_ST_DEP)
    assert "D2, D3, aVF" in t and "-1.5 mm" in t
    assert "dentro dos limites" not in t.lower()


def test_medidas_ausentes_sao_abstencao_explicita():
    t = _det(S_VAZIO).lower()
    assert "não avaliado" in t
    assert not re.search(r"\d+\s*(bpm|ms|graus)", t)
    assert "dentro dos limites" not in t and "bloqueio" not in t.replace("sem regra automática", "")
    for fr in _frases(_det(S_VAZIO)):
        assert EC.sentence_problem(fr, S_VAZIO) is None, fr


def test_divergencia_de_digitalizacao_suprime_pr_e_diz_limitacao():
    s = _sum({**NORMAL_G, "pr_ms": 160}, [R_SINUS, R_NORMAL], cabecalho_impresso={"pr_ms": 260})
    t = _det(s).lower()
    assert "diverge" in t and "260 ms" in t
    assert "dentro dos limites" not in t
    assert "intervalo pr de 160" not in t


def test_nao_inventa_numero():
    s = S_QRS_LARGO
    assert L.unverified_numbers(_det(s), s) == []


# ------------------------------------------------------------------ redação por IA verificada
def _call(texto):
    return lambda sistema, user: json.dumps({"descricao": texto}, ensure_ascii=False)


def test_ia_usa_so_fatos_estruturados_sem_cabecalho():
    visto = {}

    def call(sistema, user):
        visto["user"] = user
        return json.dumps({"descricao": "Ritmo sinusal regular a 72 bpm, pelas regras automáticas."})
    s = _sum(NORMAL_G, [R_SINUS, R_NORMAL], cabecalho_impresso={"pr_ms": 160, "nome": "FULANO"})
    D.compor_descricao(s, call)
    assert "FULANO" not in visto["user"] and "cabecalho_impresso" not in visto["user"]
    assert "ecg.within_normal_limits" in visto["user"]


def test_ia_texto_valido_e_marcado_ia():
    texto = ("O ritmo é sinusal regular, com frequência cardíaca de 72 bpm, e o intervalo PR mede 160 ms. "
             "Pelas regras automáticas, o traçado está dentro dos limites da normalidade, o que não exclui "
             "IAM nem BAV nem outras alterações.")
    d = D.compor_descricao(S_NORMAL, _call(texto))
    assert d.origem == "ia" and d.removidas == 0
    assert d.texto.startswith(texto)
    assert _frases(d.texto)[-1].lower().startswith("impressão")   # sem impressão da IA: entra a determinística verificada
    assert "\n" not in d.texto


def test_ia_com_impressao_propria_nao_duplica():
    texto = ("O ritmo é sinusal regular, com frequência cardíaca de 72 bpm. "
             "Impressão: pelas regras automáticas, o traçado está dentro dos limites da normalidade, o que não exclui "
             "IAM nem BAV nem outras alterações.")
    d = D.compor_descricao(S_NORMAL, _call(texto))
    assert d.texto == texto and d.texto.lower().count("impressão") == 1


def test_ia_impressao_sem_lastro_removida_e_substituida_pela_deterministica():
    texto = "Ritmo sinusal regular, com frequência cardíaca de 72 bpm. Impressão: sem sinais de isquemia aguda."
    d = D.compor_descricao(S_SEM_NORMAL, _call(texto))
    assert d.removidas == 1
    assert "isquemia" not in d.texto.lower()
    assert _frases(d.texto)[-1].lower().startswith("impressão")


def test_ia_inventa_sem_isquemia_sem_regra_frase_removida():
    texto = ("Ritmo sinusal regular, com frequência cardíaca de 72 bpm. Sem sinais de isquemia aguda. "
             "Não há bloqueio atrioventricular.")
    d = D.compor_descricao(S_SEM_NORMAL, _call(texto))
    assert d.origem == "ia" and d.removidas == 2
    assert "isquemia" not in d.texto.lower() and "bloqueio" not in d.texto.lower()
    assert "72 bpm" in d.texto


def test_ia_afirma_normal_com_st_nao_avaliavel_removida():
    d = D.compor_descricao(S_ST_NA, _call("Ritmo sinusal regular. ECG normal, dentro dos limites da normalidade."))
    assert d.removidas == 1 and "normal" not in d.texto.lower().replace("normalidade", "")


def test_ia_numero_fora_das_medidas_removido():
    d = D.compor_descricao(S_NORMAL, _call("A frequência é de 72 bpm. O QRS mede 187 ms."))
    assert d.removidas == 1 and "187" not in d.texto and "72 bpm" in d.texto


def test_ia_quebras_de_linha_viram_paragrafo_unico():
    d = D.compor_descricao(S_NORMAL, _call("**Ritmo**\n\n- sinusal regular\n- 72 bpm\n\r\nPR 160 ms."))
    assert d.origem == "ia" and "\n" not in d.texto and "*" not in d.texto and "- " not in d.texto


@pytest.mark.parametrize("erro", [RuntimeError("falhou"), llm.client.LLMRefusal("recusou"),
                                  llm.client.LLMTruncated("estourou"), llm.client.PayloadBloqueado("CPF")])
def test_ia_falha_cai_no_deterministico(erro):
    def call(s, u):
        raise erro
    d = D.compor_descricao(S_NORMAL, call)
    assert d.origem == "deterministico" and d.texto == _det(S_NORMAL)


@pytest.mark.parametrize("bruto", ["não é json", json.dumps({"outro": 1}), json.dumps({"descricao": ""}),
                                   json.dumps({"descricao": "   "})])
def test_ia_saida_invalida_cai_no_deterministico(bruto):
    d = D.compor_descricao(S_NORMAL, lambda s, u: bruto)
    assert d.origem == "deterministico"


def test_ia_com_dado_pessoal_cai_no_deterministico():
    d = D.compor_descricao(S_NORMAL, _call("Paciente CPF 529.982.247-25 com ritmo sinusal."))
    assert d.origem == "deterministico" and "529" not in d.texto


def test_ia_tudo_removido_cai_no_deterministico():
    d = D.compor_descricao(S_SEM_NORMAL, _call("Sem sinais de isquemia aguda."))
    assert d.origem == "deterministico"


def test_sem_ia_disponivel_usa_deterministico():
    d = D.compor_descricao(S_NORMAL, None)
    assert d.origem == "deterministico" and d.texto == _det(S_NORMAL) and d.removidas == 0


def test_excecao_na_barreira_descarta_com_limitacao(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("barreira quebrou")
    monkeypatch.setattr(EC, "sentence_problem", boom)
    d = D.compor_descricao(S_NORMAL, _call("Ritmo sinusal."))
    assert d.texto == "" and d.origem == "" and "barreira de verificação falhou" in " ".join(d.limitacoes)


# ------------------------------------------------------------------ ligação no relatório
def test_campos_aditivos_no_aireport():
    r = AIReport()
    assert r.descricao_completa == "" and r.descricao_origem == "" and r.descricao_validacao == 0


def test_ecg_report_sem_ia_traz_descricao_deterministica(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    from test_llm import _ecg
    rep = llm.ecg_report(_ecg(), None)
    assert rep.available is False
    assert rep.descricao_origem == "deterministico" and rep.descricao_completa and "\n" not in rep.descricao_completa
    assert "regras automáticas" in rep.descricao_completa


def test_ecg_descricao_fields_com_ia_injetada():
    from test_llm import _ecg
    campos = llm.ecg_descricao_fields(_ecg(), call=_call("O intervalo PR mede 210 ms. Sem sinais de isquemia."))
    assert campos["descricao_origem"] == "ia" and campos["descricao_validacao"] == 1
    assert campos["descricao_completa"].startswith("O intervalo PR mede 210 ms")
