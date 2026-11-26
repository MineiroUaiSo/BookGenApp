"""Segmentação do perfil por sinal de imagem (D4): fantoma sintético de perfil, sem imagem real nem dado de paciente."""
from __future__ import annotations

import numpy as np
from skimage.filters import gaussian

from app.rx import seg_lateral as L
from app.schemas import Structure

HH, WW = 512, 420


def _phantom(heart: bool = True) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Perfil com a coluna à ESQUERDA: fundo escuro, corpo, campo pulmonar claro (escuro na imagem), abdome denso
    abaixo da cúpula, coluna e esterno brilhantes e (opcional) coração denso no campo."""
    yy, xx = np.mgrid[0:HH, 0:WW]
    s = np.full((HH, WW), 0.03)
    body = (xx > 50) & (xx < 400)
    s[body] = 0.62
    lung = (xx > 135) & (xx < 335) & (yy > 80) & (yy < 360)
    s[lung] = 0.22
    spine = (xx > 85) & (xx < 125) & (yy > 30)
    s[spine] = 0.85
    sternum = (xx > 345) & (xx < 358) & (yy > 100) & (yy < 330)
    s[sternum] = 0.85
    gt = {"lung": lung, "spine": spine, "sternum": sternum}
    if heart:
        h = ((xx - 285) / 45.0) ** 2 + ((yy - 295) / 60.0) ** 2 <= 1.0
        s[h & lung] = 0.32
        gt["heart"] = h & lung
    return gaussian(s, sigma=1.5).astype(np.float32), gt


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    return float((a & b).sum() / max(1, (a | b).sum()))


def test_campo_pulmonar_por_claridade_nao_inclui_abdome():
    s, gt = _phantom()
    r = L.lung_field(s)
    assert r is not None
    lung = r["mask"]
    # o campo claro (incluindo a região do coração, que está dentro dele) e nada abaixo da cúpula
    assert _iou(lung, gt["lung"]) > 0.65
    assert lung[400:].sum() == 0


def test_segmenta_por_sinal_e_marca_so_o_que_e_prior():
    s, gt = _phantom()
    m = L.segment_lateral(s, "left")
    assert m is not None
    assert int(m["_posterior"][0]) == 0
    assert _iou(m["lung_field"], gt["lung"]) > 0.65
    assert _iou(m["heart"], gt["heart"]) > 0.35
    assert "heart" not in m["_estimativa"]           # há sinal de densidade: não é prior
    assert m["diaphragm"].any()


def test_sem_sinal_de_coracao_a_elipse_vira_estimativa():
    s, _ = _phantom(heart=False)
    m = L.segment_lateral(s, "left")
    assert m is not None
    assert "heart" in m and "heart" in m["_estimativa"]


def test_perfil_espelhado_espelha_as_mascaras():
    s, _ = _phantom()
    a = L.segment_lateral(s, "left")
    b = L.segment_lateral(s[:, ::-1].copy(), "right")
    assert a is not None and b is not None
    assert int(b["_posterior"][0]) == 1
    assert _iou(a["lung_field"], b["lung_field"][:, ::-1]) > 0.9
    assert _iou(a["spine"], b["spine"][:, ::-1]) > 0.8


def test_posterior_estimado_pelo_lado_mais_denso():
    s, _ = _phantom()
    r = L.lung_field(s)
    assert L.posterior_by_strip(s, r["mask"]) == "left"
    r2 = L.lung_field(s[:, ::-1].copy())
    assert L.posterior_by_strip(s[:, ::-1].copy(), r2["mask"]) == "right"


def test_imagem_sem_estruturas_devolve_none():
    flat = np.full((256, 256), 0.5, np.float32)
    assert L.segment_lateral(flat, "left") is None


def test_marcar_estimativas_rebaixa_confianca_e_rotula():
    st = Structure(key="spine", label="coluna vertebral", category="bone", color="#eab308",
                   confidence=0.2, origin="heuristic")
    ok = Structure(key="lung_field", label="campos pulmonares", category="lung", color="#60a5fa",
                   confidence=0.25, origin="heuristic")
    L.marcar_estimativas([st, ok], ("spine",))
    assert st.confidence <= L.ESTIMATIVA_CONF
    assert "estimativa" in st.label
    assert ok.confidence == 0.25 and "estimativa" not in ok.label
    L.marcar_estimativas([st], ("spine",))             # idempotente
    assert st.label.count("estimativa") == 1
