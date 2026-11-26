import base64
import io
import time

import numpy as np
import pytest
import trimesh
from scipy import ndimage as ndi
from PIL import Image

from app.recon3d import reconstruct
from app.schemas import BodyRegion, RXImageAnalysis, RXView, Structure

MM = 1.0  # mm por pixel (frontal e lateral)
W = H = 300
# elipsoides: (cx, cy, cz, rx, ry, rz)  x esq-dir, y cranio-caudal (linhas), z antero-posterior
ELL = {
    "left_lung": (+55, 150, 120, 45, 100, 90, "lung", "#88aaff"),
    "right_lung": (-55, 150, 120, 45, 100, 90, "lung", "#88aaff"),
    "heart": (+15, 190, 140, 45, 45, 40, "heart_vessels", "#ff4444"),
    "spine": (0, 150, 40, 15, 110, 15, "bone", "#eeeeee"),
}
TRACHEA = (0, 100, 90, 9, 50, 9)  # cilindro vertical


def _grid():
    return np.mgrid[0:H, 0:W]


def _enc(m):
    b = io.BytesIO()
    Image.fromarray((m * 255).astype(np.uint8)).save(b, "PNG")
    return base64.b64encode(b.getvalue()).decode()


def _proj_ell(e, axis):
    cx, cy, cz, rx, ry, rz = e[:6]
    r, c = _grid()
    if axis == "f":   # linhas=y, colunas=x
        return (((c - 150 - cx) / rx) ** 2 + ((r - cy) / ry) ** 2) <= 1
    return (((c - cz) / rz) ** 2 + ((r - cy) / ry) ** 2) <= 1  # lateral: colunas=z


def _build():
    fs, ls, vols = [], [], {}
    for k, e in ELL.items():
        cat, col = e[6], e[7]
        fs.append(Structure(key=k, label=k, category=cat, color=col, mask_png_b64=_enc(_proj_ell(e, "f"))))
        ls.append(Structure(key=k, label=k, category=cat, color=col, mask_png_b64=_enc(_proj_ell(e, "l"))))
        vols[k] = 4 / 3 * np.pi * e[3] * e[4] * e[5] / 1000
    # traqueia
    _, cy, cz, rx, hy, rz = TRACHEA
    r, c = _grid()
    fm = (np.abs(c - 150) <= rx) & (np.abs(r - cy) <= hy)
    lm = (np.abs(c - cz) <= rz) & (np.abs(r - cy) <= hy)
    fs.append(Structure(key="trachea", label="trachea", category="airway", color="#ffffff", mask_png_b64=_enc(fm)))
    ls.append(Structure(key="trachea", label="trachea", category="airway", color="#ffffff", mask_png_b64=_enc(lm)))
    vols["trachea"] = np.pi * rx * rz * 2 * hy / 1000
    img = _enc(np.zeros((H, W)))
    mk = lambda v, s: RXImageAnalysis(instance_id=v, view=RXView.PA if v == "f" else RXView.LATERAL,
                                      region=BodyRegion.CHEST, image_png_b64=img, width=W, height=H,
                                      pixel_spacing_mm=[MM, MM], structures=s)
    return mk("f", fs), mk("l", ls), vols


def test_reconstruct_synthetic():
    f, l, vols = _build()
    t = time.time()
    glb, meshes, method = reconstruct(f, l)
    dt = time.time() - t
    assert dt < 20
    sc = trimesh.load(io.BytesIO(glb), file_type="glb")
    names = set(sc.geometry.keys()) | set(sc.graph.nodes_geometry)
    got = {m.key: m.volume_ml for m in meshes}
    for k, v in vols.items():
        assert k in got, k
        assert any(k in n for n in names), k
        err = (got[k] - v) / v
        print(f"{k}: true {v:.0f} ml, got {got[k]:.0f} ml, err {err:+.1%}")
        assert abs(err) < 0.35, (k, err)
    assert "visual hull" in method and "Limitações" in method


def test_single_view_structure_flagged():
    f, l, _ = _build()
    l.structures = [s for s in l.structures if s.key != "heart"]
    glb, meshes, method = reconstruct(f, l)
    heart = [m for m in meshes if m.key == "heart"]
    assert heart and "1 incidência" in heart[0].label


def _label(s):
    return {"left_lung": "pulmão esquerdo", "right_lung": "pulmão direito", "heart": "coração",
            "spine": "coluna", "trachea": "traqueia"}[s]


def _pt(a):
    for s in a.structures:
        s.label = _label(s.key)
    return a


def test_lateral_so_pulmoes_monta_o_que_existe_e_rotula_ausentes():
    f, l, _ = _build()
    _pt(f)
    # perfil heurístico parcial: só campo pulmonar (coração/coluna/traqueia falharam)
    l.structures = [s for s in l.structures if "lung" in s.key]
    glb, meshes, method = reconstruct(f, l)
    got = {m.key: m for m in meshes}
    assert {"left_lung", "right_lung", "heart", "spine", "trachea"} <= set(got)
    for k in ("heart", "spine", "trachea"):
        assert "ausente no perfil" in got[k].label, got[k].label
        assert "1 incidência" in got[k].label
    for k in ("left_lung", "right_lung"):
        assert "estimativa" not in got[k].label
    assert "Estruturas ausentes no perfil: coração, coluna, traqueia." in method
    assert "orientação anteroposterior assumida" in method.lower()  # sem coluna/coração no perfil: assumida, não medida


def test_estrutura_estimada_nao_e_opaca_como_se_fosse_medida():
    f, l, _ = _build()
    l.structures = [s for s in l.structures if "lung" in s.key]
    glb, _, _ = reconstruct(f, l)
    sc = trimesh.load(io.BytesIO(glb), file_type="glb")
    heart = [g for n, g in sc.geometry.items() if "heart" in n][0]
    assert heart.visual.material.baseColorFactor[3] < 255
    lung = [g for n, g in sc.geometry.items() if "left_lung" in n][0]
    assert lung.visual.material.baseColorFactor[3] < 255  # pulmão já era translúcido


def test_orientacao_do_perfil_vem_do_quality_quando_ha_so_pulmao():
    f, l, _ = _build()
    l.structures = [s for s in l.structures if "lung" in s.key]
    l.quality = {"orientação": "coluna à direita da imagem (estimada)"}
    _, _, method = reconstruct(f, l)
    assert "assumida" not in method.split("Orientação", 1)[1].split(".")[0]
    assert "Orientação anteroposterior do perfil: coluna à direita da imagem" in method


def test_perfil_sem_mascaras_da_mensagem_util_e_422():
    from fastapi import HTTPException

    f, l, _ = _build()
    l.structures = []
    with pytest.raises(ValueError) as ei:
        reconstruct(f, l)
    msg = str(ei.value)
    assert "perfil" in msg and "PA" in msg and "incidência" in msg
    assert isinstance(ei.value, HTTPException) and ei.value.status_code == 422


def test_frontal_sem_mascaras_pede_pa():
    f, l, _ = _build()
    f.structures = []
    with pytest.raises(ValueError) as ei:
        reconstruct(f, l)
    assert "PA" in str(ei.value) and "incidência" in str(ei.value)


def test_sem_nenhuma_mascara_nas_duas():
    f, l, _ = _build()
    f.structures, l.structures = [], []
    with pytest.raises(ValueError) as ei:
        reconstruct(f, l)
    assert "nenhuma" in str(ei.value).lower()


def test_estrutura_segmentada_mas_nao_reconstruida_e_declarada():
    """Máscara real fina demais para o voxel some do 3D: o método deve dizer, não omitir em silêncio."""
    f, l, _ = _build()
    _pt(f)
    thin = np.zeros((H, W))
    thin[60:140, 150] = 1                      # traqueia de 1 px de largura (< voxel de 2 mm)
    for s in f.structures:
        if s.key == "trachea":
            s.mask_png_b64 = _enc(thin)
    _, meshes, method = reconstruct(f, l)
    assert "trachea" not in {m.key for m in meshes}
    assert "Estruturas segmentadas que não puderam ser reconstruídas: traqueia." in method


def _tex(glb):
    import json
    import struct

    n = struct.unpack("<I", glb[12:16])[0]
    return json.loads(glb[20:20 + n])["scenes"][0]["extras"]["medlens_texture"]


def _mask_of(a, key):
    from app.recon3d import _decode

    s = [x for x in a.structures if x.key == key][0]
    return _decode(s, a.width, a.height)


def test_textura_expoe_projecao_pa_e_perfil_que_cai_dentro_das_mascaras():
    """Vértices das malhas, projetados pelos coeficientes exportados, caem sobre pixels da máscara de origem."""
    f, l, _ = _build()
    glb, meshes, _ = reconstruct(f, l)
    tex = _tex(glb)
    assert tex["frontal"]["w"] == W and tex["lateral"]["w"] == W
    assert tex["frontal"]["png_b64"] and tex["lateral"]["png_b64"]
    sc = trimesh.load(io.BytesIO(glb), file_type="glb")
    for key in ("left_lung", "heart", "spine"):
        g = [g for n, g in sc.geometry.items() if key in n][0]
        v = np.asarray(g.vertices)
        fm, lm = _mask_of(f, key), _mask_of(l, key)
        fx, fy = tex["frontal"], tex["lateral"]
        cf = fx["col"][0] + fx["col"][1] * v[:, 0]
        rf = fx["row"][0] + fx["row"][1] * v[:, 1]
        cl = fy["col"][0] + fy["col"][1] * v[:, 2]
        rl = fy["row"][0] + fy["row"][1] * v[:, 1]

        def inside(m, r, c):
            m = ndi.binary_dilation(m, iterations=2)  # a malha suavizada pode passar ~1-2 px do contorno
            ri, ci = np.round(r).astype(int), np.round(c).astype(int)
            ok = (ri >= 0) & (ri < H) & (ci >= 0) & (ci < W)
            hit = np.zeros(len(r), bool)
            hit[ok] = m[ri[ok], ci[ok]]
            return hit.mean()

        assert inside(fm, rf, cf) > 0.9, (key, "frontal")
        assert inside(lm, rl, cl) > 0.9, (key, "lateral")


def test_textura_so_pa_quando_nao_ha_perfil_com_imagem():
    f, l, _ = _build()
    l.image_png_b64 = ""
    glb, _, method = reconstruct(f, l)
    tex = _tex(glb)
    assert "lateral" not in tex and "frontal" in tex
    assert "imagem real só da PA" in method
