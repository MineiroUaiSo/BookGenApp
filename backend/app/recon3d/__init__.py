"""Reconstrução 3D aproximada de tórax a partir de PA/AP + perfil (visual hull + priors)."""
from __future__ import annotations

import base64
import io
from typing import Optional

import numpy as np
import trimesh
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure

from app.schemas import Recon3DMesh, RXImageAnalysis, Structure

VOXEL_MM = 2.0
MAX_VOX = 160
DEFAULT_THORAX_HEIGHT_MM = 260.0   # sem pixel spacing: altura pulmonar assumida
MAGNIFICATION = 1.0                # PA ~1.1 poderia ser aplicado aqui (divide mm/px)

# prior de profundidade AP (fração da largura local) e centro z (fração da profundidade torácica)
_DEPTH_PRIOR = {"lung": (1.6, 0.5), "heart_vessels": (0.8, 0.6), "airway": (1.0, 0.45),
                "bone": (1.0, 0.5), "mediastinum": (0.9, 0.5), "diaphragm": (1.4, 0.5)}
_DEFAULT_PRIOR = (0.7, 0.5)
_SUPER_N = {"lung": 2.3}
_ALPHA = {"lung": 0.35, "mediastinum": 0.4, "diaphragm": 0.5}


def _decode(st: Structure, w: int, h: int) -> Optional[np.ndarray]:
    if not st.mask_png_b64:
        return None
    try:
        im = Image.open(io.BytesIO(base64.b64decode(st.mask_png_b64))).convert("L")
    except Exception:
        return None
    if im.size != (w, h):
        im = im.resize((w, h), Image.NEAREST)
    m = np.asarray(im) > 127
    return m if m.any() else None


def _masks(a: RXImageAnalysis) -> dict[str, tuple[Structure, np.ndarray]]:
    out = {}
    for s in a.structures:
        m = _decode(s, a.width, a.height)
        if m is not None:
            out[s.key] = (s, m)
    return out


def _is_lung(k: str) -> bool:
    return "lung" in k


def _rows_extent(ms) -> Optional[tuple[float, float]]:
    ys = [np.where(m.any(1))[0] for m in ms]
    ys = [y for y in ys if y.size]
    if not ys:
        return None
    return float(min(y.min() for y in ys)), float(max(y.max() for y in ys))


def _lat_lookup(key, lat):
    if key in lat:
        return lat[key]
    if _is_lung(key):
        ms = [v for k, v in lat.items() if _is_lung(k)]
        if ms:
            m = np.any([x[1] for x in ms], axis=0)
            return ms[0][0], m
    return None


def _superellipse(u, v, n):
    return (np.abs(u) ** n + np.abs(v) ** n) <= 1.0


def reconstruct(frontal: RXImageAnalysis, lateral: RXImageAnalysis):
    F = _masks(frontal)
    L = _masks(lateral)
    if not F and not L:
        raise ValueError("Sem máscaras de estruturas nas duas incidências.")
    if not L:
        raise ValueError("Incidência lateral sem máscaras de estruturas.")
    if not F:
        raise ValueError("Incidência frontal sem máscaras de estruturas.")

    # ---- escala frontal (mm/px)
    fr_lung = [m for k, (s, m) in F.items() if _is_lung(k)] or [m for _, m in F.values()]
    la_lung = [m for k, (s, m) in L.items() if _is_lung(k)] or [m for _, m in L.values()]
    fext = _rows_extent(fr_lung)
    lext = _rows_extent(la_lung)
    ps = frontal.pixel_spacing_mm
    if ps and len(ps) >= 2 and ps[0] > 0:
        s_f_y, s_f_x = float(ps[0]) / MAGNIFICATION, float(ps[1]) / MAGNIFICATION
        scale_src = "pixel spacing do DICOM"
    else:
        s_f_y = DEFAULT_THORAX_HEIGHT_MM / max(fext[1] - fext[0] + 1, 1)
        s_f_x = s_f_y
        scale_src = f"altura torácica assumida de {DEFAULT_THORAX_HEIGHT_MM:.0f} mm"

    # ---- registro vertical lateral -> frontal: row_l = a*row_f + b
    if fext and lext and (fext[1] - fext[0]) > 5 and (lext[1] - lext[0]) > 5:
        a = (lext[1] - lext[0]) / (fext[1] - fext[0])
        b = lext[0] - a * fext[0]
        reg = "ápice e base pulmonares"
    else:
        a = lateral.height / frontal.height
        b = 0.0
        reg = "altura total da imagem"
    s_l = s_f_y / a  # mm por pixel do perfil

    # ---- lado posterior (coluna vertebral)
    lat_cols = np.concatenate([np.where(m.any(0))[0] for _, m in L.values()])
    cmin, cmax = lat_cols.min(), lat_cols.max()
    post_right = None
    if "spine" in L:
        cs = np.where(L["spine"][1].any(0))[0].mean()
        post_right = cs > (cmin + cmax) / 2
    elif "heart" in L:
        ch = np.where(L["heart"][1].any(0))[0].mean()
        post_right = ch < (cmin + cmax) / 2   # coração anterior
    else:
        post_right = False
    sgn = -1.0 if post_right else 1.0           # z cresce em direção anterior
    post_col = float(cmax if post_right else cmin)
    depth_mm = (cmax - cmin + 1) * s_l

    # ---- grade
    allm = np.any([m for _, m in F.values()], axis=0)
    ys, xs = np.where(allm)
    r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
    cmid = (c0 + c1) / 2.0
    vox = VOXEL_MM
    marg = 6
    ny0, ny1 = (r0 * s_f_y), (r1 + 1) * s_f_y
    nx = (c1 - c0 + 1) * s_f_x
    vox = max(vox, max(ny1 - ny0, nx, depth_mm) / (MAX_VOX - 2 * marg))
    NY = int(np.ceil((ny1 - ny0) / vox)) + 2 * marg
    NX = int(np.ceil(nx / vox)) + 2 * marg
    NZ = int(np.ceil(depth_mm / vox)) + 2 * marg
    ymm = ny0 + (np.arange(NY) - marg + 0.5) * vox     # mm do topo da imagem
    xmm = (np.arange(NX) - marg + 0.5) * vox - nx / 2  # relativo ao meio
    zmm = (np.arange(NZ) - marg + 0.5) * vox           # 0 = posterior
    rowf = ymm / s_f_y - 0.5
    colf = cmid + xmm / s_f_x - 0.5
    rowl = a * rowf + b
    coll = post_col + sgn * (zmm / s_l)

    def samp(m, rows, cols):
        rr, cc = np.meshgrid(rows, cols, indexing="ij")
        return ndi.map_coordinates(m.astype(np.float32), [rr, cc], order=1, cval=0) > 0.5

    keys = list(F.keys())
    for k in L:
        if k not in keys and not _is_lung(k):
            keys.append(k)

    occ: dict[str, np.ndarray] = {}
    info: dict[str, tuple[str, str, bool]] = {}
    single: list[str] = []
    for k in keys:
        fs = F.get(k)
        ls = _lat_lookup(k, L)
        st = (fs or ls)[0]
        cat = st.category
        Fg = samp(fs[1], rowf, colf) if fs else None          # [y,x]
        Lg = samp(ls[1], rowl, coll) if ls else None          # [y,z]
        if Fg is None:
            # só no perfil: largura prior (fração da profundidade) centrada
            Fg = np.zeros((NY, NX), bool)
            if k == "spine":
                half = int(max(2, 0.12 * depth_mm / vox / 2 + 1))
            elif k == "sternum":  # adult sternal body ~25-35 mm wide
                half = int(max(2, 15.0 / vox))
            else:
                half = int(0.15 * depth_mm / vox)
            Fg[:, NX // 2 - half: NX // 2 + half + 1] = Lg.any(1)[:, None]
        if Fg is not None and not Fg.any():
            continue
        n = _SUPER_N.get(cat, 2.0)
        vol = np.zeros((NY, NX, NZ), np.float32)
        zz = np.arange(NZ)
        xx = np.arange(NX)
        for iy in range(NY):
            fx = Fg[iy]
            if not fx.any():
                continue
            xi = np.where(fx)[0]
            xa, xb = xi.min(), xi.max()
            hx = (xb - xa + 1) / 2.0
            cx = (xa + xb) / 2.0
            if Lg is not None:
                lz = Lg[iy]
                if not lz.any():
                    continue
                zi = np.where(lz)[0]
                za, zb = zi.min(), zi.max()
                hz = (zb - za + 1) / 2.0
                cz = (za + zb) / 2.0
            else:
                fac, zc = _DEPTH_PRIOR.get(cat, _DEFAULT_PRIOR)
                hz = max(hx * fac, 2.0)
                cz = zc * (NZ - 2 * marg) + marg
                if k == "spine":
                    cz = hz + marg
                cz = min(max(cz, hz + 1), NZ - hz - 1)
            sl = _superellipse((xx[:, None] - cx) / hx, (zz[None, :] - cz) / hz, n)
            vol[iy] = sl * fx[:, None]
        if vol.any():
            occ[k] = vol
            both = fs is not None and ls is not None
            info[k] = (st.label, st.color, both)
            if not both:
                single.append(k)

    # ---- priors: concavidade medial (coração/mediastino removem pulmões)
    carve = np.zeros((NY, NX, NZ), bool)
    for k in ("heart", "mediastinum"):
        if k in occ:
            carve |= occ[k] > 0.5
    if carve.any():
        carve = ndi.binary_dilation(carve, iterations=1)
        for k in occ:
            if _is_lung(k):
                occ[k][carve] = 0

    # ---- malhas
    cy, cx_, cz_ = NY * vox / 2, NX * vox / 2, NZ * vox / 2
    scene = trimesh.Scene()
    out: list[Recon3DMesh] = []
    for k, vol in occ.items():
        label, color, both = info[k]
        lab = label + ("" if both else " (estimativa, 1 incidência)")
        v = np.pad(ndi.gaussian_filter(vol, 0.8), 2)
        if v.max() < 0.5:
            continue
        try:
            verts, faces, _, _ = measure.marching_cubes(v, 0.5, spacing=(vox, vox, vox))
        except Exception:
            continue
        verts = verts - 2 * vox
        # (y,x,z) -> (x,y,z), y para cima, centrado
        pts = np.column_stack([verts[:, 1] - cx_, -(verts[:, 0] - cy), verts[:, 2] - cz_])
        faces = faces[:, ::-1]  # inversão de y muda a orientação
        mesh = trimesh.Trimesh(pts, faces, process=True)
        try:
            trimesh.smoothing.filter_taubin(mesh, iterations=8)
        except Exception:
            pass
        try:
            if len(mesh.faces) > 40000:
                mesh = mesh.simplify_quadric_decimation(face_count=30000)
        except Exception:
            pass
        mesh.fix_normals()
        vol_ml = abs(float(mesh.volume)) / 1000.0 if mesh.is_volume else float((vol > 0.5).sum() * vox ** 3 / 1000.0)
        rgb = _hex(color)
        alpha = _ALPHA.get(_cat_of(k, F, L), 1.0)
        mat = trimesh.visual.material.PBRMaterial(
            baseColorFactor=[rgb[0], rgb[1], rgb[2], int(255 * alpha)],
            metallicFactor=0.0, roughnessFactor=0.6,
            alphaMode="BLEND" if alpha < 1 else "OPAQUE", doubleSided=True)
        mesh.visual = trimesh.visual.TextureVisuals(material=mat)
        scene.add_geometry(mesh, node_name=k, geom_name=k)
        out.append(Recon3DMesh(key=k, label=lab, color=color, volume_ml=round(vol_ml, 1)))

    if not out:
        raise ValueError("Nenhuma estrutura pôde ser reconstruída.")
    glb = scene.export(file_type="glb")
    method = _method_text(scale_src, reg, single, vox)
    return glb, out, method


def _cat_of(k, F, L):
    s = (F.get(k) or L.get(k) or (None,))[0]
    return s.category if s else "other"


def _hex(c: str):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    except Exception:
        return [200, 200, 200]


def _method_text(scale_src, reg, single, vox):
    t = ("Reconstrução aproximada por envoltória visual (visual hull): cada estrutura segmentada na "
         "incidência frontal (PA/AP) é extrudada ao longo do eixo antero-posterior e interseccionada "
         "com a silhueta da incidência lateral extrudada ao longo do eixo látero-lateral. "
         f"O registro vertical entre as incidências usa {reg}; a escala em mm vem de {scale_src}. "
         "Para evitar formas em caixa, cada corte craniocaudal é substituído por uma elipse (ou "
         "superelipse, nos pulmões) inscrita nos limites da envoltória; coração e mediastino escavam a "
         "face medial dos pulmões. A superfície é gerada por marching cubes sobre ocupação suavizada "
         f"(voxel de {vox:.1f} mm) e suavizada por Taubin. ")
    if single:
        t += ("Estruturas visíveis em uma única incidência (" + ", ".join(single) + ") usam uma profundidade "
              "AP presumida a partir da largura local e têm confiança menor. ")
    t += ("Limitações: forma e volumes são estimativas; não há informação de densidade; assimetrias "
          "entre os lados não vistas no perfil são perdidas (o perfil não separa pulmão direito e "
          "esquerdo); magnificação e rotação do paciente não são corrigidas. Não equivale a tomografia.")
    return t
