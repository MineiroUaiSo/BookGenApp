"""Rules-based pt-BR findings from measurements (+ auxiliary model scores)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ..schemas import BodyRegion, Finding, Reference, RXImageAnalysis, RXMeasurement, RXView
from . import calibration as CAL

REF_FELSON = Reference(id="felson_2025", source="Felson's Principles of Chest Roentgenology — silhueta cardiomediastinal, diafragma e pleura",
                       note="critérios clássicos de tamanho cardíaco (ICT) e contornos")
REF_FLEISCHNER = Reference(id="fleischner_glossary", source="Fleischner Society — Glossary of Terms for Thoracic Imaging (atualização)",
                           note="terminologia padronizada de sinais torácicos")
REF_SQUIRE = Reference(id="squire", source="Squire's Fundamentals of Radiology — radiografia de tórax e abdome",
                       note="abordagem sistemática e sinais básicos")
REF_TXRV = Reference(id="xrv_cohen_2022", source="Cohen JP et al. TorchXRayVision: a library of chest X-ray datasets and models (MIDL 2022)",
                     note="escore auxiliar de modelo; não é laudo")

PATHO_PT = {
    "Atelectasis": "atelectasia", "Consolidation": "consolidação", "Infiltration": "opacidade",
    "Pneumothorax": "pneumotórax", "Edema": "edema pulmonar", "Emphysema": "enfisema",
    "Fibrosis": "fibrose", "Effusion": "derrame pleural", "Pneumonia": "pneumonia",
    "Pleural_Thickening": "espessamento pleural", "Cardiomegaly": "cardiomegalia", "Nodule": "nódulo pulmonar",
    "Mass": "massa", "Hernia": "hérnia (hiatal/diafragmática)", "Lung Lesion": "lesão pulmonar",
    "Fracture": "fratura", "Lung Opacity": "opacidade pulmonar", "Enlarged Cardiomediastinum": "alargamento cardiomediastinal",
}
MODEL_THRESHOLD = 0.65  # fallback when a pathology has no tuned threshold
_THRESHOLDS_PATH = Path(os.environ.get("MEDLENS_RX_THRESHOLDS", Path(__file__).resolve().parents[2] / "bench" / "tuning" / "rx_thresholds.json"))
_TUNING: Optional[dict] = None


def _tuning() -> dict:
    """Versioned per-pathology thresholds (bench/tune_rx_thresholds.py, fixed on dev). Missing/invalid file -> defaults."""
    global _TUNING
    if _TUNING is None:
        try:
            _TUNING = json.loads(_THRESHOLDS_PATH.read_text(encoding="utf-8"))
        except Exception:
            _TUNING = {}
    return _TUNING


def model_threshold(pathology: str) -> float:
    t = _tuning()
    try:
        return float(t.get("thresholds", {}).get(pathology, t.get("default", MODEL_THRESHOLD)))
    except (TypeError, ValueError):
        return MODEL_THRESHOLD


def costophrenic_demoted() -> bool:
    """True when the geometric costophrenic-angle rule was validated with low sensitivity (R5): evidence is downgraded."""
    return bool(_tuning().get("costophrenic_rule", {}).get("demoted", False))


def _m(img: RXImageAnalysis, key: str) -> Optional[RXMeasurement]:
    for m in img.measurements:
        if m.key == key and m.value is not None:
            return m
    return None


def _val(img, key):
    m = _m(img, key)
    return None if m is None else float(m.value)


def _origin_conf(img: RXImageAnalysis, key: str, base_model: float, base_heur: float) -> float:
    for s in img.structures:
        if s.key == key:
            return base_model if s.origin == "model" else base_heur
    return base_heur


def _ict_from_model(img: RXImageAnalysis) -> bool:
    """True se a segmentacao do coracao veio de modelo (mesmo criterio de ficha._origem_img). Heuristica: sem achado de ICT."""
    for s in img.structures:
        if s.key == "heart":
            return s.origin in ("model", "cxas")
    if img.structures:
        return img.structures[0].origin in ("model", "cxas")
    return False


def _fmt_unit(m: RXMeasurement) -> str:
    return f"{m.value:g} {m.unit}".strip() if m.unit else f"{m.value:g}"


def _frontal_findings(img: RXImageAnalysis, tag: str) -> list[Finding]:
    out: list[Finding] = []
    ap = img.view == RXView.AP
    vname = img.view.value

    ctr = _m(img, "cardiothoracic_ratio")
    if ctr is not None and _ict_from_model(img):   # ICT de segmentacao heuristica nao vira achado (R7)
        v = float(ctr.value)
        c = _origin_conf(img, "heart", 0.7, 0.45)
        ev = [f"índice cardiotorácico = {v:.2f} (incidência {vname}{tag})",
              "ICT de modelo com incerteza de ±0,05; a máscara do coração pode estar subestimada"]
        if v > 0.50:
            if ap:
                out.append(Finding(code="rx.cardiomegaly", label="Aumento da silhueta cardíaca (ICT > 0,50) — incidência AP magnifica o coração",
                                   severity="borderline", evidence=ev + ["em AP o ICT é superestimado; confirmar em PA/perfil"],
                                   references=[REF_FELSON, REF_SQUIRE], confidence=c * 0.8))
            else:
                out.append(Finding(code="rx.cardiomegaly", label="Sugere aumento da silhueta cardíaca (ICT > 0,50 em PA)",
                                   severity="abnormal" if v >= 0.55 else "borderline",
                                   evidence=ev, references=[REF_FELSON, REF_SQUIRE], confidence=c))
        # ICT <= 0,50 de modelo NAO vira achado "normal": a medida tem incerteza (±0,05) e tende a subestimar; ela segue
        # na ficha/laudo com a ressalva, sem afirmar coracao normal nem excluir cardiomegalia (H1).

    mw, mr = _m(img, "mediastinal_width"), _val(img, "mediastinal_width_ratio")
    if mr is not None:
        wide = mr > 30.0
        if mw is not None and mw.unit == "mm":
            wide = mw.value > 80.0 or mr > 36.0
        if wide:
            ev = [f"largura mediastinal no nível do botão aórtico = {_fmt_unit(mw)} ({mr:.0f}% da largura torácica)"]
            if ap:
                ev.append("em AP/decúbito o mediastino parece mais largo")
            out.append(Finding(code="rx.mediastinal_widening", label="Alargamento mediastinal",
                               severity="borderline" if ap else "abnormal", evidence=ev,
                               references=[REF_FELSON, REF_FLEISCHNER], confidence=_origin_conf(img, "mediastinum", 0.6, 0.35)))

    td = _val(img, "tracheal_deviation_pct")
    tdm = _m(img, "tracheal_deviation")
    if td is not None and abs(td) > 3.0:
        side = "esquerda" if td > 0 else "direita"
        sev = "abnormal" if abs(td) > 5.0 else "borderline"
        out.append(Finding(code="rx.tracheal_deviation", label=f"Desvio traqueal para a {side} do paciente",
                           severity=sev, evidence=[f"desvio = {_fmt_unit(tdm)} ({td:+.1f}% da largura torácica) em relação à coluna",
                                                   "avaliar tração (atelectasia/fibrose) ou empurrão (pneumotórax hipertensivo, massa, derrame volumoso); rotação do paciente pode simular"],
                           references=[REF_FELSON, REF_SQUIRE], confidence=_origin_conf(img, "trachea", 0.6, 0.3)))

    for side, nome in (("right", "direito"), ("left", "esquerdo")):
        a = _val(img, f"costophrenic_angle_{side}")
        if a is not None and a >= 95:
            base_conf = 0.3 if img.structures and img.structures[0].origin == "heuristic" else 0.45
            ev = [f"ângulo costofrênico estimado = {a:.0f}° (agudo é normal)",
                  "estimativa a partir da máscara pulmonar; sugere derrame/espessamento pleural — confirmar visualmente (perfil ou decúbito)"]
            if costophrenic_demoted():
                ev.append("regra geométrica com baixa sensibilidade validada (IU); o escore do modelo para derrame é o sinal principal")
            out.append(Finding(code=f"rx.costophrenic_blunting_{side}", label=f"Possível velamento/embotamento do seio costofrênico {nome}",
                               severity="borderline", evidence=ev,
                               references=[REF_FELSON, REF_FLEISCHNER], confidence=min(base_conf, 0.15) if costophrenic_demoted() else base_conf))

    d = _val(img, "hemidiaphragm_height_difference_pct")
    dmm = _m(img, "hemidiaphragm_height_difference")
    if d is not None:
        if d < -5.0:
            out.append(Finding(code="rx.hemidiaphragm_elevation_left", label="Elevação da hemicúpula esquerda (acima da direita)",
                               severity="borderline", evidence=[f"diferença D−E = {_fmt_unit(dmm)} ({d:+.1f}% da altura pulmonar); normalmente a direita é mais alta"],
                               references=[REF_FELSON, REF_SQUIRE], confidence=0.4))
        elif d > 14.0:
            out.append(Finding(code="rx.hemidiaphragm_elevation_right", label="Elevação acentuada da hemicúpula direita",
                               severity="borderline", evidence=[f"diferença D−E = {_fmt_unit(dmm)} ({d:+.1f}% da altura pulmonar)",
                                                                "considerar paralisia frênica, atelectasia basal, derrame subpulmonar, processo subfrênico"],
                               references=[REF_FELSON, REF_SQUIRE], confidence=0.4))

    ar = _val(img, "lung_area_ratio_L_R")
    if ar is not None and (ar < 0.55 or ar > 1.3):
        lado = "esquerdo" if ar < 0.55 else "direito"
        out.append(Finding(code="rx.lung_volume_asymmetry", label=f"Assimetria de volume pulmonar (hemitórax {lado} menor/mais radiotransparente em área)",
                           severity="borderline", evidence=[f"razão de área E/D = {ar:.2f} (esperado ≈ 0,7–1,1)",
                                                            "correlacionar com perda de volume (atelectasia), derrame, pneumotórax ou rotação"],
                           references=[REF_FELSON, REF_FLEISCHNER], confidence=0.35))

    rot, ins = img.quality.get("rotação", ""), img.quality.get("inspiração", "")
    issues = [t for t in (rot if rot.startswith("possível") else "", ins if ins.startswith("possivelmente") else "") if t]
    if issues:
        out.append(Finding(code="rx.technique_limitations", label="Limitações técnicas que afetam as medidas",
                           severity="borderline", evidence=issues, references=[REF_SQUIRE], confidence=0.4))

    # model scores (auxiliary)
    out.extend(_model_findings(img))
    return out


def _model_findings(img: RXImageAnalysis) -> list[Finding]:
    """Model-score findings. With a calibration curve: zones 'sugestivo' / 'indeterminado' on the calibrated probability
    ('não sugerido' emits nothing). Without one: legacy raw score >= per-pathology threshold (unchanged behaviour)."""
    out: list[Finding] = []
    cands = []
    for k, v in img.model_scores.items():
        if k not in PATHO_PT:
            continue
        z = CAL.zone(k, v)
        if z is None:
            if v >= model_threshold(k):
                cands.append((k, v, CAL.ZONE_SUGGESTIVE, None))
        elif z != CAL.ZONE_NOT_SUGGESTED:
            cands.append((k, v, z, CAL.calibrated_probability(k, v)))
    for k, v, z, p in sorted(cands, key=lambda c: -c[1])[:5]:
        slug = k.lower().replace(" ", "_")
        thin = k in CAL.INSUFFICIENT_EVIDENCE
        note = ["evidência insuficiente para este achado no desenvolvimento (poucos positivos): nunca afastar nem confirmar só por este escore"] if thin else []
        if p is None:
            out.append(Finding(code=f"rx.model.{slug}", label=f"Sugestivo de {PATHO_PT[k]} (escore do modelo)",
                               severity="borderline",
                               evidence=[f"DenseNet121 (torchxrayvision, 'all') escore = {v:.2f}; sinal auxiliar não calibrado, nunca laudo"] + note,
                               references=[REF_TXRV], confidence=round(min(0.6, v * 0.6), 2), origin="model"))
        elif z == CAL.ZONE_SUGGESTIVE:
            out.append(Finding(code=f"rx.model.{slug}", label=f"Sugestivo de {PATHO_PT[k]} (probabilidade calibrada ≈ {p:.0%})",
                               severity="borderline",
                               evidence=[f"DenseNet121 (torchxrayvision, 'all'): escore {v:.2f} -> probabilidade calibrada ≈ {p:.0%} (curva isotônica ajustada em dev IU, otimista); sinal auxiliar, nunca laudo"] + note,
                               references=[REF_TXRV], confidence=round(min(0.6, p), 2), origin="model"))
        else:
            out.append(Finding(code=f"rx.model_indeterminate.{slug}",
                               label=f"Indeterminado para {PATHO_PT[k]} (probabilidade calibrada ≈ {p:.0%}); o escore não permite sugerir nem afastar o achado",
                               severity="borderline",
                               evidence=[f"DenseNet121 (torchxrayvision, 'all'): escore {v:.2f} na faixa intermediária entre sensibilidade ≈ 95% e especificidade ≈ 90% em dev; correlacionar clinicamente"] + note,
                               references=[REF_TXRV], confidence=round(min(0.3, p), 2), origin="model"))
    return out


def _abdomen_findings(img: RXImageAnalysis) -> list[Finding]:
    out = []
    d = _m(img, "max_gas_lumen_diameter")
    if d is not None and d.unit == "mm" and d.value >= 60:
        out.append(Finding(code="rx.bowel_gas_distension", label="Possível distensão de alça com gás (≥ 60 mm) - medida/sugestivo, não validado",
                           severity="borderline",
                           evidence=[f"maior lúmen gasoso = {d.value:g} mm (delgado > 30 mm, cólon > 60 mm, ceco > 90 mm costumam ser os limites); a origem da alça não é identificada automaticamente"],
                           references=[REF_SQUIRE], confidence=0.25))
    return out


def study_findings(images: list[RXImageAnalysis]) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    multi = len(images) > 1
    for i, img in enumerate(images):
        tag = f", imagem {i + 1}" if multi else ""
        if img.region_uncertain or (img.out_of_scope and img.region == BodyRegion.CHEST):
            fs = []                                  # ambiguous region: abstain until a human confirms it
        elif img.region == BodyRegion.CHEST and img.view in (RXView.PA, RXView.AP):
            fs = _frontal_findings(img, tag)
        elif img.region == BodyRegion.ABDOMEN:
            fs = _abdomen_findings(img)
        else:
            fs = []
        for f in fs:
            if f.code in seen:
                # keep the more severe duplicate's evidence by appending
                prev = next(p for p in findings if p.code == f.code)
                prev.evidence = prev.evidence + [e for e in f.evidence if e not in prev.evidence]
                continue
            seen.add(f.code)
            findings.append(f)
    order = {"critical": 0, "abnormal": 1, "borderline": 2, "normal": 3}
    findings.sort(key=lambda f: order[f.severity])
    return findings
