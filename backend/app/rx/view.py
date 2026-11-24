"""View (PA/AP/lateral) and body-region detection: DICOM tags first, image heuristics second."""
from __future__ import annotations

import re
from typing import Any, Optional

from ..schemas import BodyRegion, RXView
from . import seg_heuristic as H

_REGION_WORDS = [
    (BodyRegion.CHEST, r"chest|thorax|torax|tórax|lung|pulm|torac|\btx\b|cardi"),
    (BodyRegion.ABDOMEN, r"abd|abdo|kub|barriga"),
    (BodyRegion.PELVIS, r"pelv|bacia|hip\b|quadril"),
    (BodyRegion.SPINE, r"spine|coluna|cspine|lspine|tspine|lombar|cervical|dorsal|sacr"),
    (BodyRegion.SKULL, r"skull|head|cranio|crânio|face|sinus"),
    (BodyRegion.EXTREMITY, r"hand|foot|knee|leg|arm|elbow|wrist|ankle|shoulder|femur|tibia|humer|"
                           r"extrem|mao|mão|pe\b|pé|joelho|cotovelo|punho|tornozelo|ombro|braco|braço|perna"),
]


def _tag(ds: Any, name: str) -> str:
    if ds is None:
        return ""
    v = getattr(ds, name, None)
    if v is None:
        return ""
    if isinstance(v, (list, tuple)) or v.__class__.__name__ == "MultiValue":
        return "\\".join(str(x) for x in v)
    return str(v)


def region_from_tags(ds: Any) -> Optional[BodyRegion]:
    text = " ".join(_tag(ds, n) for n in ("BodyPartExamined", "SeriesDescription", "ProtocolName",
                                          "StudyDescription")).lower()
    if not text.strip():
        return None
    for reg, pat in _REGION_WORDS:
        if re.search(pat, text):
            return reg
    return None


def view_from_tags(ds: Any) -> Optional[RXView]:
    vp = _tag(ds, "ViewPosition").strip().upper()
    if vp in ("PA",):
        return RXView.PA
    if vp in ("AP",):
        return RXView.AP
    if vp in ("LL", "RL", "LAT", "LATERAL", "LEFT LATERAL", "RIGHT LATERAL"):
        return RXView.LATERAL
    text = " ".join(_tag(ds, n) for n in ("SeriesDescription", "ProtocolName", "StudyDescription")).lower()
    if re.search(r"\b(lat|lateral|perfil|ll|rl)\b", text):
        return RXView.LATERAL
    if re.search(r"\bpa\b", text):
        return RXView.PA
    if re.search(r"\bap\b|portable|portátil|portatil|supine|leito|\bap/", text):
        return RXView.AP
    return None


def posterior_side_from_tags(ds: Any) -> Optional[str]:
    """Image side of the spine for lateral films, from PatientOrientation (row, col)."""
    po = _tag(ds, "PatientOrientation").split("\\")
    if po and po[0] in ("A", "P"):
        return "right" if po[0] == "P" else "left"
    return None


# ---------------------------------------------------------------------------------------------- model-based
# Thresholds tuned on JSRT + Montgomery + PAX-Ray++ (dev); Shenzhen + manually labelled IU images = test.
FRONTAL_HEART_MIN = 0.015      # heart mask fraction of the (cropped) image
FRONTAL_LUNGS_MIN = 0.08       # left+right lung mask fraction
LATERAL_LUNG_MIN = 0.05
LATERAL_MAXPROB_MIN = 0.90
LATERAL_SPINE_MAX = 0.01


def model_features(prob) -> dict:
    """Anatomical plausibility features from the PSPNet probabilities (14, h, w)."""
    import numpy as np
    from . import seg_model as M
    ix = {n: i for i, n in enumerate(M.PSP_TARGETS)}
    m = prob > 0.5
    L, R, Hm = m[ix["Left Lung"]], m[ix["Right Lung"]], m[ix["Heart"]]
    lungs = L | R
    f = {"left": float(L.mean()), "right": float(R.mean()), "heart": float(Hm.mean()),
         "lungs": float(lungs.mean()), "spine": float(m[ix["Spine"]].mean()),
         "maxprob": float(max(prob[ix["Left Lung"]].max(), prob[ix["Right Lung"]].max()))}
    h, w = lungs.shape
    f["heart_cy"] = f["heart_cx"] = f["lung_cx_gap"] = float("nan")
    if lungs.any() and Hm.any():
        yl = np.nonzero(lungs.any(axis=1))[0]
        f["heart_cy"] = float((np.nonzero(Hm)[0].mean() - yl[0]) / max(yl[-1] - yl[0], 1))   # 0 top .. 1 bottom of lungs
        f["heart_cx"] = float(np.nonzero(Hm)[1].mean() / w)
    if L.any() and R.any():
        f["lung_cx_gap"] = float(abs(np.nonzero(L)[1].mean() - np.nonzero(R)[1].mean()) / w)
    return f


def classify_from_features(f: dict) -> tuple[str, str]:
    """-> (kind, why); kind in chest_frontal, chest_lateral, nochest."""
    if f["heart"] >= FRONTAL_HEART_MIN and f["lungs"] >= FRONTAL_LUNGS_MIN:
        return "chest_frontal", "PSPNet: dois campos pulmonares + silhueta cardíaca"
    # PSPNet never draws a spine on a lateral film but does on frontal/abdomen films: that separates a lateral
    # chest from an abdomen on which it hallucinates lung bases
    if (f["lungs"] >= LATERAL_LUNG_MIN and f["maxprob"] >= LATERAL_MAXPROB_MIN and f["heart"] < FRONTAL_HEART_MIN
            and f["spine"] < LATERAL_SPINE_MAX):
        return "chest_lateral", "PSPNet: campo pulmonar único sem silhueta cardíaca frontal (perfil)"
    return "nochest", "PSPNet: sem estrutura torácica plausível"


def _upright(f: dict) -> bool:
    """Frontal chest with the heart in the lower half of the lung field."""
    cy = f.get("heart_cy")
    return cy is not None and cy == cy and cy >= 0.30


def estimate_rotation(work, f: dict, kind: str, prob_fn) -> tuple[int, Optional[dict], Optional[object]]:
    """Try np.rot90 k in {1,3} for landscape non-chest images and k=2 for upside-down frontals.
    Returns (k, features, prob) of the best orientation (k=0 = leave as is). Costs extra PSP passes only for
    images that look wrong."""
    import numpy as np
    h, w = work.shape
    cands: list[int] = []
    if kind == "chest_frontal" and not _upright(f):
        cands = [2]
    elif kind == "nochest" and w > 1.15 * h:
        cands = [1, 3]
    best = (0, None, None)
    for k in cands:
        pr = prob_fn(np.ascontiguousarray(np.rot90(work, k)))
        if pr is None:
            continue
        fk = model_features(pr)
        kk, _ = classify_from_features(fk)
        if kk == "chest_frontal" and _upright(fk) and fk["lungs"] >= f["lungs"] - 0.02:
            best = (k, fk, pr)
            break
    return best


def detect_view_region(s, ds: Any = None, work=None, use_model: bool = False, allow_rotate: bool = True) -> dict:
    """s: smoothed float image at working res (autocropped); work: unsmoothed float image.
    Returns dict(view, region, kind, source, notes, lungs, prob, feats, rot).
    Order: DICOM tags -> PSPNet anatomical plausibility (when models are on) -> image heuristics."""
    from . import seg_model as M
    notes: list[str] = []
    region = region_from_tags(ds)
    view = view_from_tags(ds)
    lungs = None
    prob = None
    feats = None
    rot = 0
    source = "tag" if (region or view) else "heurística"
    kind: Optional[str] = None
    model_kind: Optional[str] = None

    if use_model and work is not None and region in (None, BodyRegion.CHEST):
        prob = M.psp_probs(work)
        if prob is not None:
            feats = model_features(prob)
            model_kind, why = classify_from_features(feats)
            if allow_rotate and region is None and (model_kind == "nochest" or (model_kind == "chest_frontal" and not _upright(feats))):
                k, f2, p2 = estimate_rotation(work, feats, model_kind, M.psp_probs)
                if k:
                    rot, feats, prob = k, f2, p2
                    model_kind, why = classify_from_features(feats)
                    notes.append(f"imagem rotacionada (np.rot90 k={k}) para posição ortostática")
            if region is None:
                source = "modelo"
                notes.append(f"região estimada pela imagem: {why}")
                if model_kind == "chest_frontal":
                    region, kind = BodyRegion.CHEST, "chest_frontal"
                    if view is None:
                        view = RXView.PA
                        notes.append("incidência estimada: frontal (PA assumida; AP não distinguível sem tag)")
                elif model_kind == "chest_lateral":
                    region, kind = BodyRegion.CHEST, "chest_lateral"
                    if view is None:
                        view = RXView.LATERAL

    if prob is None and region in (None, BodyRegion.CHEST) and view != RXView.LATERAL:
        lungs = H.find_lung_pair(s)

    if region is None:
        if use_model and prob is not None:
            # model says: not a chest. Use the heuristics only to tell abdomen / extremity / other.
            hk, why = H.classify_region_heuristic(s)
            if hk in ("chest_frontal", "chest_lateral"):
                hk, why = "other", "indeterminado (modelo torácico não encontrou tórax)"
            kind = hk
            notes.append(f"região estimada pela imagem: {why}")
        else:
            kind, why = H.classify_region_heuristic(s)
            notes.append(f"região estimada pela imagem: {why}")
        region = {"chest_frontal": BodyRegion.CHEST, "chest_lateral": BodyRegion.CHEST,
                  "abdomen": BodyRegion.ABDOMEN, "extremity": BodyRegion.EXTREMITY}.get(kind, BodyRegion.OTHER)
        if kind == "chest_frontal" and view is None:
            view = RXView.PA
            notes.append("incidência estimada: frontal (PA assumida; AP não distinguível sem tag)")
        if kind == "chest_lateral" and view is None:
            view = RXView.LATERAL
    if region == BodyRegion.CHEST:
        if view is None:
            if model_kind == "chest_frontal" or (model_kind is None and lungs is not None):
                view, kind = RXView.PA, "chest_frontal"
                notes.append("incidência estimada: frontal (PA assumida)")
            elif model_kind == "chest_lateral" or (model_kind is None and H.find_single_dark(s) is not None):
                view, kind = RXView.LATERAL, "chest_lateral"
                notes.append("incidência estimada: perfil (campo pulmonar único)")
            else:
                view, kind = RXView.OTHER, "other"
        elif view == RXView.LATERAL:
            kind = "chest_lateral"
        else:
            kind = "chest_frontal"
    else:
        view = view or RXView.OTHER
        kind = kind or {BodyRegion.ABDOMEN: "abdomen"}.get(region, "other")
        if kind in ("chest_frontal", "chest_lateral"):
            kind = "other"
    return {"view": view, "region": region, "kind": kind, "source": source, "notes": notes, "lungs": lungs,
            "prob": prob, "feats": feats, "rot": rot}
