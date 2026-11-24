"""Orchestrates view detection, segmentation (model -> heuristic fallback), measurements."""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import label

from ..schemas import BodyRegion, RXImageAnalysis, RXMeasurement, RXView, Structure
from . import measure, seg_heuristic as H, seg_model, view as V
from ._common import build_structure, encode_png_b64, to_work

HEUR_CONF = {"right_lung": .55, "left_lung": .55, "lung_field": .5, "heart": .45, "spine": .4, "trachea": .35,
             "mediastinum": .3, "aorta": .2, "right_clavicle": .3, "left_clavicle": .3, "ribs": .2,
             "right_diaphragm": .4, "left_diaphragm": .4, "diaphragm": .4, "sternum": .25, "bowel_gas": .4,
             "pelvis_bones": .3, "bones": .3}
MODEL_CONF = 0.75


def _as_u8(img) -> np.ndarray:
    a = np.asarray(img)
    if a.ndim == 3:
        a = a[..., :3].mean(axis=2) if a.shape[2] >= 3 else a[..., 0]
    if a.dtype != np.uint8:
        a = a.astype(np.float64)
        lo, hi = a.min(), a.max()
        a = ((a - lo) / (hi - lo) * 255.0) if hi > lo else np.zeros_like(a)
        a = a.astype(np.uint8)
    return a


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
        conf = MODEL_CONF if origin == "model" else HEUR_CONF.get(k, 0.3)
        st = build_structure(k, m, full_shape, scale, spacing, conf, origin)
        if st is not None:
            out.append(st)
    return out


_ORDER = ["right_lung", "left_lung", "lung_field", "right_hilum", "left_hilum", "heart", "aorta", "mediastinum",
          "trachea", "spine", "right_clavicle", "left_clavicle", "right_scapula", "left_scapula", "ribs", "sternum",
          "diaphragm", "right_diaphragm", "left_diaphragm", "bowel_gas", "pelvis_bones", "bones"]


def analyze_image(img_uint8: np.ndarray, instance_id: str, ds: Any = None, *, use_model: Optional[bool] = None) -> RXImageAnalysis:
    img = _as_u8(img_uint8)
    Hh, Ww = img.shape
    spacing = _spacing(ds, Hh, Ww)
    work, scale = to_work(img)
    s = H.smooth(work)
    info = V.detect_view_region(s, ds)
    view, region, kind = info["view"], info["region"], info["kind"]
    allow_model = seg_model.models_enabled() if use_model is None else use_model

    structures: list[Structure] = []
    measurements: list[RXMeasurement] = []
    quality: dict[str, str] = {}
    scores: dict[str, float] = {}
    notes = list(info["notes"])
    conv = measure.Conv(scale, spacing)
    full = (Hh, Ww)
    seg_desc = "sem segmentação"

    if kind == "chest_frontal":
        masks = None
        origin = "heuristic"
        if allow_model:
            masks = seg_model.segment_chest_model(work)
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
            structures = _structures(masks, full, scale, spacing, origin, _ORDER)
            measurements, ex = measure.measure_frontal(masks, conv, view.value)
            quality.update(measure.quality_frontal(s, masks, ex))
        if allow_model:
            scores = seg_model.pathology_scores(work)
    elif kind == "chest_lateral":
        masks = H.segment_chest_lateral(s, V.posterior_side_from_tags(ds))
        if masks is not None:
            seg_desc = "heurística clássica (perfil) — baixa confiança"
            structures = _structures(masks, full, scale, spacing, "heuristic", _ORDER)
            post = "direita" if int(masks["_posterior"][0]) == 1 else "esquerda"
            quality["orientação"] = f"coluna à {post} da imagem (estimada)"
    elif kind == "abdomen":
        masks = H.segment_abdomen(s)
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
        masks = H.segment_bones(s)
        seg_desc = "heurística de limiar (ossos) — baixa confiança"
        structures = _structures(masks, full, scale, spacing, "heuristic", ["bones"])
        for st in structures:
            if region == BodyRegion.PELVIS:
                st.label = "ossos da pelve (limiar)"

    quality["incidência"] = (f"{view.value} ({'tag DICOM' if V.view_from_tags(ds) else 'estimada'})"
                             if view != RXView.OTHER else "indeterminada")
    quality["segmentação"] = seg_desc
    if notes:
        quality["observações"] = "; ".join(notes)

    return RXImageAnalysis(
        instance_id=instance_id, view=view, region=region, image_png_b64=encode_png_b64(img),
        width=Ww, height=Hh, pixel_spacing_mm=list(spacing) if spacing else None,
        structures=structures, measurements=measurements, model_scores=scores, quality=quality)
