"""Todo código de achado emitido por rules.py tem >= 1 cartão; cartões carregam e são consistentes."""
import re
from pathlib import Path

from app.knowledge.cards import gatilho_casa, load_cards

RULES = Path(__file__).resolve().parents[1] / "app" / "ecg" / "analysis" / "rules.py"


def _emitted_codes() -> set[str]:
    return set(re.findall(r"[\"'](ecg\.[a-z0-9_]+)[\"']", RULES.read_text(encoding="utf-8")))


def test_cartoes_carregam_e_quantidade_minima():
    cards = load_cards()
    assert len(cards) >= 120
    assert all(c.revisado_por_medico is False for c in cards)


def test_codigos_emitidos_tem_cartao():
    cards = load_cards()
    codes = _emitted_codes()
    assert len(codes) > 30
    sem = sorted(c for c in codes if not any(gatilho_casa(g, c) for k in cards for g in k.gatilhos))
    assert sem == [], f"códigos sem cartão: {sem}"


def test_cartoes_chave_existem():
    ids = {c.id for c in load_cards()}
    assert {"hve.peguero", "hve.cornell_voltagem", "hve.romhilt_escore", "fa.fibrilacao",
            "repol.strain_vs_isquemia", "isquemia.sgarbossa"} <= ids
