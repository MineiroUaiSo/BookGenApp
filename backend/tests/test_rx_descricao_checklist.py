"""M1: o parágrafo determinístico da descrição completa segue o checklist de docs/MODELOS-DESCRICAO-COMPLETA.md (RX, 3.1)
e o prompt da IA carrega a ordem, os conectivos e as armadilhas do mesmo documento."""
import re

import pytest

from app.rx import descricao_ia as DI
from app.rx import laudo as LA
from test_rx_laudo_descricao import CRITICO, TODOS, _desc

# item do checklist -> trecho que prova que o item foi dito (medido ou como abstenção escrita)
ITENS = {
    "tecnica": ("radiografia de tórax em", "imagem fora do escopo"),
    "qualidade": ("qualidade técnica",),
    "pulmoes": ("pulmões",),
    "pleura": ("pleura",),
    "mediastino": ("mediastino",),
    "hilos": ("hilos",),
    "traqueia": ("traqueia",),
    "coracao_ict": ("silhueta cardíaca",),
    "vasos": ("vasos",),
    "diafragma": ("diafragma",),
    "seios": ("seios costofrênicos",),
    "ossos": ("ósseo",),
    "partes_moles": ("partes moles",),
    "dispositivos": ("dispositivos",),
    "limitacoes": ("não foram avaliados nesta análise automática",),
    "impressao": ("em síntese",),
}


@pytest.mark.parametrize("nome", TODOS)
def test_paragrafo_cobre_todos_os_itens_do_checklist_e_fecha_com_a_frase_critica(nome):
    d = _desc(nome)
    baixo = d.lower()
    for item, trechos in ITENS.items():
        assert any(t in baixo for t in trechos), (nome, item)
    assert d.endswith(CRITICO)
    assert d.count(CRITICO) == 1


def test_itens_na_ordem_do_checklist():
    d = _desc("pa_medidas_sem_regra")
    ordem = ["Radiografia de tórax em", "qualidade técnica", "Nos pulmões,", "No mediastino,",
             "Na região do coração e vasos,", "No diafragma,", "Não foram avaliados nesta análise automática",
             "Em síntese,", CRITICO]
    pos = [d.index(t) for t in ordem]
    assert pos == sorted(pos), dict(zip(ordem, pos))


@pytest.mark.parametrize("nome", TODOS)
def test_nao_usa_nao_e_possivel_em_frase_de_medida_ou_abstencao(nome):
    d = _desc(nome)
    assert not re.search(r"n[aã]o (é|foi|e) poss[ií]vel", d, re.IGNORECASE)


def test_ict_abre_com_a_regiao_do_coracao_e_vasos():
    for nome in ("pa_modelo", "pa_ict_alto", "ap", "heuristica"):
        assert "Na região do coração e vasos," in _desc(nome), nome


def test_numero_de_imagens_em_palavras():
    assert "uma imagem" in _desc("pa_modelo")
    assert "duas imagens" in _desc("pa_perfil")


def test_qualidade_nao_repete_o_mesmo_item_entre_imagens():
    d = _desc("pa_perfil")
    assert d.count("a rotação é possivelmente inadequada") == 1
    assert d.count("a penetração é indeterminada") == 1


def test_sintese_sem_criterio_descreve_o_alcance_e_remete_ao_medico():
    d = _desc("pa_modelo")
    assert "o que descreve o alcance da análise e não o estado do exame" in d
    assert "dependem da leitura do médico" in d
    assert "permanecem sem análise" not in d


def test_prompt_da_ia_segue_o_documento():
    s = DI.SISTEMA
    # ordem do checklist 3.1 (pleura e pulmões antes de mediastino; coração; diafragma; ossos; dispositivos; limitações; impressão)
    ordem = ["técnica e qualidade", "pleura e pulmões", "mediastino", "coração", "diafragma", "ossos", "dispositivos",
             "limitações", "impressão"]
    pos = [s.index(t) for t in ordem]
    assert pos == sorted(pos), dict(zip(ordem, pos))
    # armadilha 5.2: nunca "não é possível"; usar abstenção correta
    assert "não é possível" in s and "não há como afirmar" in s and "não avaliado" in s
    # conectivos do banco de frases (3.3)
    for c in ("na região de", "enquanto", "o que limita a avaliação de"):
        assert c in s
    # armadilhas de construção (5.3)
    assert "não calcule" in s and "conduta" in s and "descritor visual" in s
