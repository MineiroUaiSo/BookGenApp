"""M1: o ramo lateral usa seg_lateral só para campo pulmonar e diafragma; o resto continua como no ramo legado."""
from __future__ import annotations

import numpy as np

from app.rx import seg_heuristic as H, seg_lateral as L
from app.rx.analyze import analyze_image
from tests.test_rx_seg_lateral import _phantom


def _legacy(s, posterior, monkeypatch):
    with monkeypatch.context() as mp:
        mp.setattr(L, "segment_lateral", lambda *a, **k: None)
        return H.segment_chest_lateral(s, posterior)


def test_pulmao_e_diafragma_vem_do_sinal(monkeypatch):
    s, _ = _phantom()
    sig = L.segment_lateral(s, "left")
    out = H.segment_chest_lateral(s, "left")
    assert out is not None and sig is not None
    assert np.array_equal(out["lung_field"], sig["lung_field"])
    assert np.array_equal(out["diaphragm"], sig["diaphragm"])


def test_coracao_coluna_esterno_traqueia_iguais_ao_ramo_legado(monkeypatch):
    s, _ = _phantom()
    leg = _legacy(s, "left", monkeypatch)
    out = H.segment_chest_lateral(s, "left")
    assert leg is not None and out is not None
    for k in ("heart", "spine", "sternum", "trachea"):
        assert (k in out) == (k in leg)
        if k in leg:
            assert np.array_equal(out[k], leg[k]), k
    assert int(out["_posterior"][0]) == int(leg["_posterior"][0])


def test_sem_campo_claro_cai_no_ramo_legado(monkeypatch):
    s, _ = _phantom()
    leg = _legacy(s, "left", monkeypatch)
    monkeypatch.setattr(L, "segment_lateral", lambda *a, **k: None)
    out = H.segment_chest_lateral(s, "left")
    assert np.array_equal(out["lung_field"], leg["lung_field"])
    assert np.array_equal(out["diaphragm"], leg["diaphragm"])


def test_priors_geometricos_vem_marcados_como_estimativa():
    s, _ = _phantom()
    out = H.segment_chest_lateral(s, "left")
    assert "spine" in out["_estimativa"] and "sternum" in out["_estimativa"]
    assert "lung_field" not in out["_estimativa"] and "diaphragm" not in out["_estimativa"]


def test_analyze_rotula_estimativas_no_perfil():
    s, _ = _phantom()
    img = (np.clip(s, 0, 1) * 255).astype(np.uint8)
    a = analyze_image(img, "m1-fantoma")
    marcadas = {st.key for st in a.structures if "estimativa" in st.label}
    if a.view.value == "LATERAL":
        assert {"spine", "sternum"} <= marcadas
        assert not ({"lung_field", "diaphragm"} & marcadas)
