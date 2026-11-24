import pytest
from pydantic import ValidationError

from app.knowledge.cards import Cartao, gatilho_casa, parse_cards, validate_cards

BASE = {
    "id": "lvh.peguero", "versao": 1, "nome_pt": "Peguero", "criterio": "Soma do S mais profundo com S em V4.",
    "limiares": {"homem_mm": 28}, "medidas": ["indices.peguero_mm"], "gatilhos": ["ecg.lvh"],
    "fonte": {"ref": "sbc_laudos_2022", "local": "seção HVE"},
}


def test_cartao_valido_defaults():
    c = Cartao(**BASE)
    assert c.revisado_por_medico is False and c.fonte.tipo == "paráfrase" and c.familia == "lvh"


@pytest.mark.parametrize("patch", [{"id": "SemPonto"}, {"gatilhos": ["foo.bar"]}, {"extra": 1}, {"versao": 0},
                                   {"fonte": {"ref": "x", "local": "y", "tipo": "cópia"}}])
def test_cartao_invalido(patch):
    with pytest.raises(ValidationError):
        Cartao(**{**BASE, **patch})


def test_validate_cards_detecta_problemas():
    a = Cartao(**{**BASE, "nao_confundir": ["x.y"]})
    erros = validate_cards([a, a], refs={"sbc_laudos_2022"})
    assert any("duplicado" in e for e in erros) and any("nao_confundir" in e for e in erros)
    assert validate_cards([Cartao(**BASE)], refs=set())[0].endswith("sbc_laudos_2022")


def test_parse_exige_chave():
    with pytest.raises(ValueError):
        parse_cards({}, "x")


def test_gatilho_casa():
    assert gatilho_casa("ecg.lvh", "ecg.lvh")
    assert gatilho_casa("ecg.st_elevation_*", "ecg.st_elevation_anterior")
    assert gatilho_casa("ecg.st_elevation_*", "ecg.st_elevation_")
    assert not gatilho_casa("ecg.lvh", "ecg.lvh_voltage")
