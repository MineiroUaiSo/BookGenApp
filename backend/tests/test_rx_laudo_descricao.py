"""L1: `descricao_completa` do rx_laudo/v1: parágrafo único determinístico, só com o que já está nas seções do laudo."""
import pytest

from app.llm import guard
from app.rx import ficha as FI
from app.rx import laudo as LA
from app.rx import lexico as LX
from app.schemas import RXView
from test_rx_laudo import CENARIOS, _a, _img

CRITICO = "Pneumotórax, pneumoperitônio e posição de tubos/cateteres NÃO são avaliados por esta análise: revisar a imagem."

# palavra que prova que a região foi dita (avaliada ou "não avaliado")
REGIOES = {"pleura": "pleura", "pulmoes": "pulmões", "mediastino": "mediastino", "hilos": "hilos",
           "traqueia": "traqueia", "coracao": "silhueta cardíaca", "vasos": "vasos", "diafragma": "diafragma",
           "seios": "seios costofrênicos", "ossos": "ósseo", "partes_moles": "partes moles",
           "dispositivos": "dispositivos"}

TODOS = dict(CENARIOS)
TODOS["pa_perfil"] = RXAnalysisPAPerfil = _a(_img())
TODOS["pa_perfil"].images.append(_img(view=RXView.LATERAL, ict=None))
TODOS["regiao_incerta"] = _a(_img(region_uncertain=True))


def _desc(nome):
    return LA.build_laudo(TODOS[nome]).descricao_completa


@pytest.mark.parametrize("nome", TODOS)
def test_descricao_paragrafo_unico_e_nao_vazio(nome):
    d = _desc(nome)
    assert d and "\n" not in d and "\r" not in d and d == d.strip()


@pytest.mark.parametrize("nome", TODOS)
def test_descricao_cobre_toda_regiao_e_mantem_o_critico(nome):
    d = _desc(nome)
    baixo = d.lower()
    for chave, palavra in REGIOES.items():
        assert palavra in baixo, (nome, chave)
    assert CRITICO in d
    assert d.endswith(CRITICO)


@pytest.mark.parametrize("nome", TODOS)
def test_descricao_nunca_normal_livre_afasta(nome):
    d = _desc(nome)
    assert LX.termos_proibidos(d) == []
    assert "normal" not in d.lower()


@pytest.mark.parametrize("nome", TODOS)
def test_descricao_sem_phi(nome):
    assert guard.scan_text(_desc(nome)) is None


@pytest.mark.parametrize("nome", TODOS)
def test_descricao_cada_oracao_passa_o_validador(nome):
    a = TODOS[nome]
    laudo = LA.build_laudo(a)
    ficha = FI.build_ficha(a)
    for texto, fatos in LA.oracoes_descricao(laudo, ficha):
        assert LA.problemas_oracao(texto, fatos, ficha) == [], texto
    assert " ".join(t for t, _ in LA.oracoes_descricao(laudo, ficha)) == laudo.descricao_completa


def test_descricao_so_pa():
    d = _desc("pa_modelo")
    assert "incidência PA" in d and "perfil" not in d
    assert "0,46" in d and "com incerteza" in d and "não exclui aumento da silhueta cardíaca" in d
    assert "rotação é possivelmente inadequada" in d


def test_descricao_pa_mais_perfil():
    d = _desc("pa_perfil")
    assert "PA e perfil" in d
    assert "perfil" in d and "sem medidas automáticas" in d


def test_descricao_perfil_so_nao_mede_nada():
    d = _desc("perfil")
    assert "perfil" in d and "0," not in d.split("Quanto à qualidade")[0]
    assert "não foram avaliados" in d.lower()


def test_descricao_ict_modelo_baixo_incerteza():
    d = _desc("pa_modelo")
    assert "índice cardiotorácico foi medido em 0,46, com incerteza (±0,05; pode estar subestimado)" in d
    assert "não exclui aumento da silhueta cardíaca" in d


def test_descricao_ict_alto_sugere_e_vai_para_a_impressao():
    d = _desc("pa_ict_alto")
    assert "0,58" in d and "sugere aumento da silhueta cardíaca" in d
    assert "Em síntese" in d and "acima de 0,50" in d


def test_descricao_ict_ap_nao_afirma_cardiomegalia():
    d = _desc("ap")
    assert "não deve ser usado para afirmar cardiomegalia" in d and "magnifica" in d


def test_descricao_ict_heuristico_nao_aparece_como_medida():
    d = _desc("heuristica")
    assert "0,64" not in d
    assert "silhueta cardíaca não foi medida com confiança" in d


def test_descricao_regiao_incerta_ou_fora_de_escopo():
    for nome in ("regiao_incerta", "fora_de_escopo"):
        d = _desc(nome)
        assert "fora do escopo" in d.lower()
        assert "Índice cardiotorácico" not in d and "índice cardiotorácico foi medido" not in d


def test_descricao_outras_medidas_com_limiar_local():
    d = _desc("pa_outras_medidas")
    assert "largura do mediastino foi medida em 40% da largura torácica" in d
    assert "desvio traqueal foi medido em +6,0% da largura torácica" in d
    assert "limiar local" in d


def test_descricao_sinais_do_modelo_nao_viram_achado():
    d = _desc("pa_sinais_modelo").lower()
    assert "caixa separada" in d and "não confirma nem afasta" in d
    assert "derrame" not in d and "consolidação" not in d and "pneumotórax" in d   # só no CRÍTICO


def test_descricao_ressalva_nao_repetida():
    d = _desc("pa_modelo")
    assert d.count("nesta análise automática") <= 2


def test_markdown_inclui_descricao_no_fim():
    l = LA.build_laudo(CENARIOS["pa_modelo"])
    md = LA.render_markdown(l)
    assert md.rstrip().endswith(l.descricao_completa)
    assert "## Descrição completa" in md
