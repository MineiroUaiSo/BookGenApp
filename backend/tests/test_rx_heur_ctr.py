"""Heuristic-mode CTR outside the plausible window is downgraded to 'não confiável', not reported as a measurement."""
from app.rx.analyze import HEUR_CTR_RANGE, _distrust_heuristic_ctr
from app.schemas import RXMeasurement


def _ms():
    return [RXMeasurement(key="thoracic_width", label="x", value=300.0, unit="mm"),
            RXMeasurement(key="cardiothoracic_ratio", label="ICT", value=0.8, unit=""),
            RXMeasurement(key="heart_width", label="h", value=240.0, unit="mm")]


def test_heuristic_ctr_implausible_is_dropped_with_note():
    q, ex = {}, {"ctr": 0.8}
    out = _distrust_heuristic_ctr(_ms(), ex, q)
    assert [m.key for m in out] == ["thoracic_width"]
    assert "não confiável" in q["ICT"] and "ctr" not in ex


def test_heuristic_ctr_plausible_is_kept():
    mid = sum(HEUR_CTR_RANGE) / 2
    q, ex = {}, {"ctr": mid}
    assert len(_distrust_heuristic_ctr(_ms(), ex, q)) == 3 and "ICT" not in q


def test_heuristic_without_ctr_untouched():
    q = {}
    assert len(_distrust_heuristic_ctr(_ms()[:1], {}, q)) == 1 and not q
