"""Tarefa 5: léxico de incerteza (graus §2.2) e termos proibidos do laudo RX; tabela única."""
import pytest

from app.rx import lexico as L
from app.rx.ficha import Nivel


@pytest.mark.parametrize("texto", ["Exame normal.", "Sem alterações.", "Dentro da normalidade.", "Isso afasta derrame.",
                                   "Descarta pneumotórax.", "Ausência de derrame.", "Seios costofrênicos livres.",
                                   "Diagnóstico de pneumonia.", "O modelo confirma consolidação.",
                                   "Silhueta de aspecto NORMAL."])
def test_rx_lexico_termos_proibidos_sao_detectados(texto):
    assert L.termos_proibidos(texto)


@pytest.mark.parametrize("texto", [
    "Modelo auxiliar: possível derrame pleural (probabilidade calibrada ≈ 0,70); escore de modelo; não confirma nem afasta.",
    "Modelo auxiliar: indeterminado para consolidação; não permite afirmar nem afastar.",
    "Pleura: não avaliado nesta análise automática.",
    "Diafragma: ar livre subdiafragmático não avaliado nesta análise automática.",
    "Índice cardiotorácico medido 0,46, dentro da faixa de referência (limite clássico 0,50 em PA).",
])
def test_rx_lexico_frases_molde_nao_tem_termo_proibido(texto):
    assert L.termos_proibidos(texto) == []


def test_rx_lexico_modelo_nao_gera_sugere_nem_compativel():
    assert L.problemas("O modelo sugere derrame.", Nivel.SUGERIDO_MODELO)
    assert L.problemas("Achado compatível com derrame.", Nivel.SUGERIDO_MODELO)
    assert L.problemas("Modelo auxiliar: possível derrame; não confirma nem afasta.", Nivel.SUGERIDO_MODELO) == []


def test_rx_lexico_regra_pode_sugerir_e_medido_nao():
    assert L.problemas("Sugere aumento da silhueta cardíaca (critério de acurácia limitada).", Nivel.REGRA) == []
    assert L.problemas("Sugere aumento da silhueta cardíaca.", Nivel.MEDIDO)


def test_rx_lexico_compativel_so_para_a_propria_medida():
    assert L.problemas("Medida compatível com a faixa de referência.", Nivel.MEDIDO) == []
    assert L.problemas("Compatível com cardiomegalia.", Nivel.MEDIDO)
    assert L.problemas("Compatível com cardiomegalia.", Nivel.REGRA)


def test_rx_lexico_faixa_de_referencia_exige_fato_medido():
    t = "Valor dentro da faixa de referência."
    assert L.problemas(t, Nivel.MEDIDO) == []
    assert L.problemas(t, Nivel.SUGERIDO_MODELO)
    assert L.problemas(t, Nivel.NAO_AVALIADO)


def test_rx_lexico_nao_avaliado_nao_admite_grau_forte():
    assert L.problemas("Pleura: não avaliado nesta análise automática.", Nivel.NAO_AVALIADO) == []
    assert L.problemas("Sugere derrame.", Nivel.NAO_AVALIADO)
    assert L.problemas("Possível derrame.", Nivel.NAO_AVALIADO)


def test_rx_lexico_qualidade_admite_possivelmente_inadequada():
    assert L.problemas("Inspiração possivelmente inadequada: limita a avaliação.", Nivel.QUALIDADE) == []


def test_rx_lexico_tabela_unica_cobre_todos_os_niveis():
    assert set(L.GRAUS_PERMITIDOS) == set(Nivel)
    assert set(L.GRAUS) == {"sugere", "compativel_com", "possivel", "indeterminado", "nao_avaliado"}
