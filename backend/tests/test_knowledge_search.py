from app.knowledge import select_relevant
from app.knowledge.search import format_cards, search_cards, select_cards


def _ids(cards):
    return [c.id for c in cards]


def test_select_cards_hve_strain_traz_lvh_e_strain_vs_isquemia():
    ids = _ids(select_cards(["ecg.lvh", "ecg.secondary_repolarization"], ["indices.peguero_mm"]))
    assert any(i.startswith("lvh.") for i in ids)
    assert "lvh.peguero" in ids and "repol.strain_vs_isquemia" in ids


def test_select_cards_fa_traz_cartoes_af():
    ids = _ids(select_cards(["ecg.atrial_fibrillation", "ecg.irregular_rhythm"]))
    assert "af.fibrilacao" in ids and any(i.startswith("af.") for i in ids)


def test_select_cards_limite_e_ordem_deterministica():
    a = _ids(select_cards(["ecg.lvh", "ecg.lbbb", "ecg.st_elevation_anterior"], ["qrs_ms"], ["strain"]))
    b = _ids(select_cards(["ecg.st_elevation_anterior", "ecg.lbbb", "ecg.lvh"], ["qrs_ms"], ["strain"]))
    assert a == b and len(a) <= 20 and len(set(a)) == len(a)
    assert len(select_cards(["ecg.lvh"], limite=3)) == 3


def test_select_cards_inclui_nao_confundir():
    ids = _ids(select_cards(["ecg.lbbb"]))
    assert "isquemia.sgarbossa" in ids or "conducao.bre_strauss" in ids


def test_select_cards_entrada_vazia():
    assert select_cards() == []


def test_busca_livre_peguero_acha_lvh_peguero():
    assert _ids(search_cards("Peguero"))[0] == "lvh.peguero"
    assert "lvh.peguero" in _ids(search_cards("Peguéro S4 mulheres 23 mm"))


def test_busca_sem_termos_ou_sem_resultado():
    assert search_cards("  ") == [] and search_cards("xyzzyqq") == []


def test_format_cards_compacto():
    txt = format_cards(select_cards(["ecg.lvh"], limite=2))
    assert txt.count("\n") == 1 and "Fonte:" in txt


def test_api_antiga_continua():
    assert select_relevant("ecg", ["ecg.lvh"], ["qrs_ms"])
