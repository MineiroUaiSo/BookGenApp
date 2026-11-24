"""Orchestrates view detection, segmentation (model -> heuristic fallback), measurements."""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import label

from ..schemas import BodyRegion, RXImageAnalysis, RXMeasurement, RXView, Structure
from . import measure, seg_cxas, seg_heuristic as H, seg_model, view as V
from ._common import autocrop, build_structure, encode_png_b64, normalize_polarity, polarity_margin, to_work

# heuristic masks are unreliable on real films (Dice 0.07-0.24): cap confidence low
HEUR_CONF = {"right_lung": .25, "left_lung": .25, "lung_field": .25, "heart": .2, "spine": .2, "trachea": .15,
             "mediastinum": .15, "aorta": .1, "right_clavicle": .1, "left_clavicle": .1, "ribs": .1,
             "right_diaphragm": .2, "left_diaphragm": .2, "diaphragm": .2, "sternum": .1, "bowel_gas": .2,
             "pelvis_bones": .15, "bones": .15}
MODEL_CONF = 0.75
CXAS_CONF = 0.7   # CXAS (opt-in, MEDLENS_RX_CXAS=1): research model, see docs/benchmarks/trilha_r2_cxas_log.md
# heuristic heart mask is a crude inter-lung gap box: on normal films it gave CTR 0.64-0.87 (model: 0.46-0.52).
# Outside this window the heuristic CTR is not shown as a measurement (downgraded to "não confiável").
HEUR_CTR_RANGE = (0.30, 0.70)   # upper bound just above the largest truthful phantom CTR (0.64); real heuristic films gave up to 0.87
HEUR_WARN = ("segmentação por heurística clássica: BAIXA CONFIABILIDADE (benchmark: Dice ~0,1-0,25 em RX de tórax "
             "reais; medidas como ICT/desvio traqueal não são confiáveis) — não usar para decisão; confirmar visualmente.")


def _as_u8(img) -> np.ndarray:
    a = np.asarray(img)
    if a.ndim == 3:
        a = a[..., :3].mean(axis=2) if a.shape[2] >= 3 else a[..., 0]
    if a.dtype != np.uint8:
        a = a.astype(np.float64)
        # robust stretch: burned-in markers / hot pixels must not squash the contrast of 16-bit data
        lo, hi = (np.percentile(a, [0.5, 99.5]) if a.dtype != np.uint8 else (a.min(), a.max()))
        a = np.clip(a, lo, hi)
        a = ((a - lo) / (hi - lo) * 255.0) if hi > lo else np.zeros_like(a)
        a = a.astype(np.uint8)
    return a


def _model_prefers_inverted(img: np.ndarray) -> bool:
    """True if the chest model finds a more plausible thorax in the inverted image (lungs + heart area)."""
    def score(a):
        c, _ = autocrop(a)
        w, _ = to_work(c)
        pr = seg_model.psp_probs(w)
        if pr is None:
            return None
        f = V.model_features(pr)
        return f["lungs"] + 3.0 * f["heart"]
    s0, s1 = score(img), score((255 - img).astype(np.uint8))
    if s0 is None or s1 is None:
        return polarity_margin(img) > 0.12
    return s1 > s0 + 0.02


def _tag_polarity(ds: Any) -> bool:
    """True if the DICOM header already states the polarity (the loader handled MONOCHROME1)."""
    return ds is not None and getattr(ds, "PhotometricInterpretation", None) in ("MONOCHROME1", "MONOCHROME2")


def _heart_side_check(masks) -> Optional[str]:
    """Patient side convention: image-left = patient right (standard PA/AP display). The cardiac mass normally lies
    towards image-right of the mediastinal midline; if it lies clearly towards image-left, the film may be mirrored
    or dextrocardia/situs inversus, and the D/E labels of lungs/clavicles are NOT confirmed."""
    heart, rl, ll = masks.get("heart"), masks.get("right_lung"), masks.get("left_lung")
    if heart is None or rl is None or ll is None or not (heart.any() and rl.any() and ll.any()):
        return None
    hx = float(np.nonzero(heart)[1].mean())
    mid = 0.5 * (float(np.nonzero(rl)[1].mean()) + float(np.nonzero(ll)[1].mean()))
    span = abs(float(np.nonzero(rl)[1].mean()) - float(np.nonzero(ll)[1].mean()))
    if hx < mid - 0.12 * max(span, 1.0):
        return ("coração projetado à esquerda da imagem: possível imagem espelhada ou dextrocardia — "
                "lateralidade (D/E) não confirmada")
    return None


def _distrust_heuristic_ctr(measurements, ex, quality):
    """Heuristic mode: drop an implausible CTR (and the heart width it came from) instead of presenting it as a measure."""
    ctr = ex.get("ctr")
    if ctr is None or HEUR_CTR_RANGE[0] <= ctr <= HEUR_CTR_RANGE[1]:
        return measurements
    ex.pop("ctr", None)
    quality["ICT"] = (f"não confiável: ICT heurístico {ctr:.2f} fora do intervalo plausível "
                      f"({HEUR_CTR_RANGE[0]:.2f}-{HEUR_CTR_RANGE[1]:.2f}); silhueta cardíaca heurística não é confiável — "
                      "use o modelo de segmentação ou meça manualmente")
    return [m for m in measurements if m.key not in ("cardiothoracic_ratio", "heart_width")]


def _spacing(ds: Any, H_: int, W_: int) -> Optional[tuple[float, float]]:
    if ds is None:
        return None
    for name in ("PixelSpacing", "ImagerPixelSpacing"):
        v = getattr(ds, name, None)
        if v is not None:
            try:
                r, c = float(v[0]), float(v[1])
            except Exception:
                continue
            if r <= 0 or c <= 0:
                continue
            rows, cols = getattr(ds, "Rows", H_), getattr(ds, "Columns", W_)
            return (r * rows / H_, c * cols / W_)
    return None


def _structures(masks, full_shape, scale, spacing, origin, order=None) -> list[Structure]:
    out = []
    keys = order or [k for k in masks if not k.startswith("_")]
    for k in keys:
        m = masks.get(k)
        if m is None or k.startswith("_"):
            continue
        conf = MODEL_CONF if origin == "model" else CXAS_CONF if origin == "cxas" else HEUR_CONF.get(k, 0.3)
        st = build_structure(k, m, full_shape, scale, spacing, conf, origin)
        if st is not None:
            out.append(st)
    return out


# structures each pipeline can actually segment (anything else is "não suportado", never scored/reported as Dice 0).
# PSPNet ChestX-Det has no sternum/ribs class; lateral heuristics have no aorta/clavicle/scapula.
_FRONTAL_HEUR = {"right_lung", "left_lung", "lungs", "heart", "mediastinum", "spine", "trachea", "aorta", "ribs"}
_LATERAL = {"lung_field", "lungs", "heart", "diaphragm", "spine", "sternum", "trachea"}


def supported_structures(mode: str, view_class: str = "frontal") -> set[str]:
    """mode: 'model' | 'heur'; view_class: 'frontal' | 'lateral'. Keys the pipeline is able to produce."""
    if view_class == "lateral":
        return set(_LATERAL) | (set(seg_cxas.CXAS_KEYS) if seg_cxas.enabled() else set())
    extra = set(seg_cxas.CXAS_KEYS) if seg_cxas.enabled() else set()
    if mode == "model":
        return set(seg_model.PSP_KEYS.values()) | {"lungs"} | extra
    return set(_FRONTAL_HEUR) | extra


_ORDER = ["right_lung", "left_lung", "lung_field", "right_hilum", "left_hilum", "heart", "aorta", "mediastinum",
          "trachea", "spine", "right_clavicle", "left_clavicle", "right_scapula", "left_scapula", "ribs", "sternum",
          "diaphragm", "right_diaphragm", "left_diaphragm", "bowel_gas", "pelvis_bones", "bones"]


def analyze_image(img_uint8: np.ndarray, instance_id: str, ds: Any = None, *, use_model: Optional[bool] = None) -> RXImageAnalysis:
    img = _as_u8(img_uint8)
    allow_model = seg_model.models_enabled() if use_model is None else use_model
    inverted = False
    if not _tag_polarity(ds):
        m = polarity_margin(img)
        if m > 0.05 and allow_model:
            inverted = _model_prefers_inverted(img)       # arbitrate with the chest model (rare, +1 PSP pass)
        elif m > 0.12:
            inverted = True
        if inverted:
            img = (255 - img).astype(np.uint8)
    Hh, Ww = img.shape
    spacing = _spacing(ds, Hh, Ww)
    # trim flat borders/letterbox (e.g. a chest film padded with black) so detection and models see the body
    imgc, (cy0, cx0) = autocrop(img)
    work, scale = to_work(imgc)
    s = H.smooth(work)
    info = V.detect_view_region(s, ds, work=work, use_model=allow_model)
    if info.get("rot"):
        # the image was found lying on its side / upside down: work on (and return) the upright image
        img = np.ascontiguousarray(np.rot90(img, info["rot"]))
        Hh, Ww = img.shape
        spacing = spacing[::-1] if (spacing and info["rot"] % 2) else spacing
        imgc, (cy0, cx0) = autocrop(img)
        work, scale = to_work(imgc)
        s = H.smooth(work)
    view, region, kind = info["view"], info["region"], info["kind"]

    structures: list[Structure] = []
    measurements: list[RXMeasurement] = []
    quality: dict[str, str] = {}
    scores: dict[str, float] = {}
    notes = list(info["notes"])
    if inverted:
        notes.append("polaridade invertida detectada (fundo claro) e corrigida")
    # canvas = working-res frame of the FULL image; crop results are pasted into it at (oy, ox)
    ch, cw = max(1, int(round(Hh / scale[0]))), max(1, int(round(Ww / scale[1])))
    oy, ox = int(round(cy0 / scale[0])), int(round(cx0 / scale[1]))
    if (ch, cw) != work.shape:
        cscale = (Hh / ch, Ww / cw)
    else:
        cscale = scale

    def to_canvas(m):
        if m is None or (ch, cw) == m.shape:
            return m
        out = np.zeros((ch, cw), dtype=m.dtype)
        h_, w_ = min(m.shape[0], ch - oy), min(m.shape[1], cw - ox)
        if h_ > 0 and w_ > 0:
            out[oy:oy + h_, ox:ox + w_] = m[:h_, :w_]
        return out

    def canvas_masks(ms):
        return {k: (to_canvas(v) if not k.startswith("_") else v) for k, v in ms.items()}

    scale = cscale
    conv = measure.Conv(scale, spacing)
    full = (Hh, Ww)
    seg_desc = "sem segmentação"

    if kind == "chest_frontal":
        masks = None
        origin = "heuristic"
        if allow_model:
            masks = seg_model.segment_chest_model(work, info.get("prob"))
            if masks is not None:
                origin = "model"
        if masks is None:
            masks = H.segment_chest_frontal(s, info.get("lungs"))
        if masks is None:
            seg_desc = "segmentação indisponível (campos pulmonares não identificados)"
        else:
            seg_desc = ("PSPNet ChestX-Det (torchxrayvision)" if origin == "model"
                        else "heurística clássica (limiar/morfologia/ridge) — baixa confiança")
            if info["source"] == "heurística" or view is None:
                pass
            # AP/PA hint without tag: scapulae over lung fields suggest AP
            if origin == "model" and V.view_from_tags(ds) is None:
                sc = masks.get("left_scapula", np.zeros_like(s, bool)) | masks.get("right_scapula", np.zeros_like(s, bool))
                lungs_u = masks["left_lung"] | masks["right_lung"]
                if sc.sum() > 0 and (sc & lungs_u).sum() / sc.sum() > 0.30:
                    view = RXView.AP
                    notes.append("escápulas projetadas sobre os campos pulmonares: provável incidência AP")
            masks = canvas_masks(masks)
            s_full = to_canvas(s)
            structures = _structures(masks, full, scale, spacing, origin, _ORDER)
            measurements, ex = measure.measure_frontal(masks, conv, view.value)
            if origin == "heuristic":
                measurements = _distrust_heuristic_ctr(measurements, ex, quality)
            quality.update(measure.quality_frontal(s_full, masks, ex))
            side = _heart_side_check(masks)
            if side:
                quality["lateralidade"] = side
            if origin == "heuristic":
                quality["confiabilidade"] = HEUR_WARN
                if not allow_model:
                    quality["confiabilidade"] += " Modelo de segmentação indisponível/desligado."
        if allow_model:
            scores = seg_model.pathology_scores(work)
    elif kind == "chest_lateral":
        hint = seg_model.lung_field_from_probs(info["prob"], s.shape) if info.get("prob") is not None else None
        masks = H.segment_chest_lateral(s, V.posterior_side_from_tags(ds), hint)
        if masks is not None:
            masks = canvas_masks(masks)
            seg_desc = ("campo pulmonar PSPNet + priors anatômicos (perfil) — baixa confiança" if hint is not None
                        else "heurística clássica (perfil) — baixa confiança")
            structures = _structures(masks, full, scale, spacing, "heuristic", _ORDER)
            quality["confiabilidade"] = HEUR_WARN
            post = "direita" if int(masks["_posterior"][0]) == 1 else "esquerda"
            quality["orientação"] = f"coluna à {post} da imagem (estimada)"
    elif kind == "abdomen":
        masks = canvas_masks(H.segment_abdomen(s))
        quality["confiabilidade"] = HEUR_WARN
        seg_desc = "heurística clássica (padrão gasoso/limiar ósseo) — baixa confiança"
        structures = _structures(masks, full, scale, spacing, "heuristic", _ORDER)
        gas = masks.get("bowel_gas")
        if gas is not None and gas.any():
            lab, n = ndi.label(gas)
            dist = ndi.distance_transform_edt(gas)
            k = 0.5 * (conv.kx + conv.ky)
            measurements.append(RXMeasurement(key="bowel_gas_loops", label="Regiões gasosas (alças) detectadas",
                                              value=float(n), unit=""))
            measurements.append(RXMeasurement(key="max_gas_lumen_diameter", label="Maior diâmetro de lúmen gasoso",
                                              value=round(float(2 * dist.max() * k), 1), unit=conv.unit))
    else:
        masks = canvas_masks(H.segment_bones(s))
        quality["confiabilidade"] = HEUR_WARN
        seg_desc = "heurística de limiar (ossos) — baixa confiança"
        structures = _structures(masks, full, scale, spacing, "heuristic", ["bones"])
        for st in structures:
            if region == BodyRegion.PELVIS:
                st.label = "ossos da pelve (limiar)"

    if kind in ("chest_frontal", "chest_lateral") and structures and seg_cxas.enabled():
        cx = seg_cxas.segment(img, "lateral" if kind == "chest_lateral" else "frontal")
        add = seg_cxas.fill_masks(cx, {s.key for s in structures}) if cx else {}
        added = _structures(add, full, (1.0, 1.0), spacing, "cxas") if add else []
        if added:
            structures = structures + added
            notes.append("estruturas adicionais por CXAS (modelo de pesquisa, MIT, não certificado): "
                         + ", ".join(s.key for s in added))

    quality["incidência"] = (f"{view.value} ({'tag DICOM' if V.view_from_tags(ds) else 'estimada'})"
                             if view != RXView.OTHER else "indeterminada")
    quality["segmentação"] = seg_desc
    if notes:
        quality["observações"] = "; ".join(notes)

    return RXImageAnalysis(
        instance_id=instance_id, view=view, region=region, image_png_b64=encode_png_b64(img),
        width=Ww, height=Hh, pixel_spacing_mm=list(spacing) if spacing else None,
        structures=structures, measurements=measurements, model_scores=scores, quality=quality)
