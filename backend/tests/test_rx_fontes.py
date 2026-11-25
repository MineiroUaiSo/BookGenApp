"""Tarefa 3: registro de fontes do laudo RX (esquema, verificadas x pendentes, só verificadas são citáveis)."""
import pytest

from app.rx import fontes as FT


def test_rx_fontes_esquema_completo():
    for f in FT.todas():
        assert f.id and f.titulo and f.entidade and f.direitos, f.id
        assert isinstance(f.verificado, bool)
        assert set(f.secoes) <= set(FT.SECOES), f.id
        if f.verificado:
            assert f.url and f.lido, f.id


def test_rx_fontes_s1_a_s9_verificadas_e_pendencias_nao():
    by = {f.id: f for f in FT.todas()}
    assert all(by[f"S{i}"].verificado for i in range(1, 10))
    pend = [f for f in FT.todas() if not f.verificado]
    assert len(pend) >= 8 and all(f.id.startswith("N") for f in pend)
    assert len(by) == len(FT.todas())


def test_rx_fontes_citar_verificada_ok():
    assert [f.id for f in FT.citar(["S1", "S4"])] == ["S1", "S4"]


@pytest.mark.parametrize("ids", [["N1"], ["S1", "N3"], ["S99"]])
def test_rx_fontes_citar_nao_verificada_falha(ids):
    with pytest.raises(FT.FonteNaoVerificada):
        FT.citar(ids)


def test_rx_fontes_modelo_frozen():
    f = FT.citar(["S1"])[0]
    with pytest.raises(Exception):
        f.titulo = "x"
