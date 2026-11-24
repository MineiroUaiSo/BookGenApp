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


def detect_view_region(s, ds: Any = None) -> dict:
    """s: smoothed float image at working res. Returns dict(view, region, kind, source, notes, lungs)."""
    notes: list[str] = []
    region = region_from_tags(ds)
    view = view_from_tags(ds)
    lungs = None
    source = "tag" if (region or view) else "heurística"
    kind: Optional[str] = None

    if region in (None, BodyRegion.CHEST) and view != RXView.LATERAL:
        lungs = H.find_lung_pair(s)

    if region is None:
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
            if lungs is not None:
                view, kind = RXView.PA, "chest_frontal"
                notes.append("incidência estimada: frontal (PA assumida)")
            elif H.find_single_dark(s) is not None:
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
    return {"view": view, "region": region, "kind": kind, "source": source, "notes": notes, "lungs": lungs}
