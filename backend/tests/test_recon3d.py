import base64
import io
import time

import numpy as np
import trimesh
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
