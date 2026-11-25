"""ECG / RX / 3D routes. Heavy modules are imported lazily inside handlers."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.dicom.render import pixel_spacing_mm, render_instance, to_png_bytes
from app.schemas import (AIReport, BodyRegion, ECGAnalysis, Modality, Recon3DResult, RXAnalysis,
                         RXImageAnalysis, RXView, StudyInfo)
from app.store import store
from app import usage_log
import time

router = APIRouter()


class ECGRequest(BaseModel):
    instance_id: Optional[str] = None
    layout: str = "auto"


class RXRequest(BaseModel):
    instance_ids: Optional[list[str]] = None
    # human-confirmed region per instance id (resolves region_uncertain / a wrong DICOM tag)
    region_overrides: Optional[dict[str, BodyRegion]] = None


class ReconRequest(BaseModel):
    frontal_id: Optional[str] = None
    lateral_id: Optional[str] = None


def _study(study_id: str) -> StudyInfo:
    s = store.get_study(study_id)
    if not s:
        raise HTTPException(404, "study not found")
    return s


def _not_installed(e: ImportError) -> HTTPException:
    return HTTPException(501, f"Required module not installed/implemented: {e}")


def _instances(study: StudyInfo, modalities: set[Modality]) -> list[str]:
    return [i for s in study.series if s.modality in modalities for i in s.instance_ids]


def _check_in_study(study: StudyInfo, ids: list[str]) -> None:
    allowed = {i for s in study.series for i in s.instance_ids}
    for i in ids:
        if i not in allowed:
            raise HTTPException(404, f"instance {i} not in study")


def _ai_unavailable(msg: str) -> AIReport:
    return AIReport(available=False, description="", limitations=[msg])


# Last rules-based result per (kind, study): the AI text is a separate call that reuses it (rules come first).
_LAST: dict[tuple[str, str], tuple[object, Optional[bytes]]] = {}


def _remember(kind: str, study_id: str, result: object, png: Optional[bytes] = None) -> None:
    _LAST[(kind, study_id)] = (result, png)


def _recall(kind: str, study_id: str) -> tuple[object, Optional[bytes]]:
    got = _LAST.get((kind, study_id))
    if got is None:
        raise HTTPException(409, "analyze first: no rules-based result for this study (POST .../analyze)")
    return got


# ------------------------------------------------------------------ ECG
@router.post("/ecg/{study_id}/analyze", response_model=ECGAnalysis)
def ecg_analyze(study_id: str, body: Optional[ECGRequest] = None, ai: bool = False):
    body = body or ECGRequest()
    study = _study(study_id)
    if body.instance_id:
        _check_in_study(study, [body.instance_id])
        iid = body.instance_id
    else:
        cands = _instances(study, {Modality.ECG}) or _instances(study, {Modality.UNKNOWN})
        if not cands:
            raise HTTPException(422, "study has no ECG instance")
        iid = cands[0]
    try:
        meta = store.instance_meta(iid)
    except KeyError:
        raise HTTPException(404, "instance not found")
    png: bytes | None = None
    t0 = time.perf_counter()
    try:
        if meta["kind"] == "image":
            from app.ecg.digitize import digitize_image

            img, _, _ = render_instance(iid, gray=False)
            png = to_png_bytes(img)
            signal = digitize_image(img, body.layout)
        else:
            from app.ecg.ingest import load_ecg

            signal = load_ecg(store.instance_path(iid))
        from app.ecg.analysis import analyze_signal

        t1 = time.perf_counter()
        result = analyze_signal(signal, study_id)
    except ImportError as e:
        raise _not_installed(e)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, str(e))
    t2 = time.perf_counter()
    _remember("ecg", study_id, result, png)
    lat = {"ingest": round((t1 - t0) * 1000), "analysis": round((t2 - t1) * 1000)}
    if ai:
        result = result.model_copy(update={"ai": _run_ecg_ai(result, png)})
        lat["ai"] = round((time.perf_counter() - t2) * 1000)
    usage_log.log_event("analyze", study_id, kind="ecg", latency_ms=lat, quality_flags=_ecg_flags(result),
                        codes=[f.code for f in result.findings], n_findings=len(result.findings),
                        ai_requested=ai, ai_provider=(result.ai.provider if result.ai else None))
    return result


def _ecg_flags(result: ECGAnalysis) -> list[str]:
    flags = [f"noisy_{k.lower()}" for k, q in result.signal.quality.items() if q < 0.5]
    text = " ".join(result.warnings).lower()
    for needle, flag in (("ruí", "noise_warning"), ("st/q não avaliados", "st_q_skipped"),
                         ("delimitação", "delineation_uncertain")):
        if needle in text:
            flags.append(flag)
    return [f for f in flags if usage_log._CODE_RE.match(f)]


def _rx_flags(result: RXAnalysis) -> list[str]:
    flags: list[str] = []
    for im in result.images:
        if im.out_of_scope:
            flags.append("out_of_scope")
        if im.region_uncertain:
            flags.append("region_uncertain")
        if im.external_ai_blocked:
            flags.append("external_ai_blocked")
        if "confiabilidade" in im.quality:
            flags.append("low_reliability")
    return sorted(set(flags))


def _run_ecg_ai(result: ECGAnalysis, png: Optional[bytes]) -> AIReport:
    try:
        from app.llm import ai_available

        if not ai_available():
            return _ai_unavailable("IA indisponível (ANTHROPIC_API_KEY ou OPENROUTER_API_KEY ausente).")
        from app.llm import ecg_report

        return ecg_report(result, png)
    except ImportError as e:
        raise _not_installed(e)


def _run_rx_ai(result: RXAnalysis) -> AIReport:
    try:
        from app.llm import ai_available

        if not ai_available():
            return _ai_unavailable("IA indisponível (ANTHROPIC_API_KEY ou OPENROUTER_API_KEY ausente).")
        from app.llm import rx_report

        return rx_report(result)
    except ImportError as e:
        raise _not_installed(e)


@router.post("/ecg/{study_id}/ai", response_model=AIReport)
def ecg_ai(study_id: str):
    """AI text for the ECG analysed by the last POST /ecg/{id}/analyze (rules are not blocked by this call)."""
    _study(study_id)
    result, png = _recall("ecg", study_id)
    t0 = time.perf_counter()
    rep = _run_ecg_ai(result, png)  # type: ignore[arg-type]
    usage_log.log_event("ai", study_id, kind="ecg", latency_ms={"ai": round((time.perf_counter() - t0) * 1000)},
                        ai_provider=rep.provider)
    return rep


@router.post("/rx/{study_id}/ai", response_model=AIReport)
def rx_ai(study_id: str):
    _study(study_id)
    result, _ = _recall("rx", study_id)
    t0 = time.perf_counter()
    rep = _run_rx_ai(result)  # type: ignore[arg-type]
    usage_log.log_event("ai", study_id, kind="rx", latency_ms={"ai": round((time.perf_counter() - t0) * 1000)},
                        ai_provider=rep.provider)
    return rep


class FeedbackRequest(BaseModel):
    kind: str
    code: str
    verdict: str


@router.post("/feedback/{study_id}")
def feedback(study_id: str, body: FeedbackRequest):
    """Agree/disagree on one finding; stored locally in the PHI-free usage log (code + verdict only)."""
    _study(study_id)
    if body.kind not in ("ecg", "rx") or body.verdict not in ("agree", "disagree") \
            or not usage_log._CODE_RE.match(body.code):
        raise HTTPException(422, "invalid feedback (kind ecg|rx, verdict agree|disagree, code [a-z0-9_.-])")
    usage_log.log_event("feedback", study_id, kind=body.kind, code=body.code, verdict=body.verdict)
    return {"ok": True}


# ------------------------------------------------------------------ RX
def _analyze_images(study: StudyInfo, ids: list[str],
                    overrides: Optional[dict[str, BodyRegion]] = None) -> list[RXImageAnalysis]:
    from app.rx import analyze_image

    out = []
    for iid in ids:
        try:
            arr, ds, _ = render_instance(iid, gray=True)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(422, f"{iid}: {e}")
        ov = (overrides or {}).get(iid)
        res = analyze_image(arr, iid, ds, region_override=ov) if ov else analyze_image(arr, iid, ds)
        if res.pixel_spacing_mm is None and ds is not None:
            ps = pixel_spacing_mm(ds)
            if ps:
                res.pixel_spacing_mm = list(ps)
        out.append(res)
    return out


def _pick_rx_ids(study: StudyInfo, ids: Optional[list[str]]) -> list[str]:
    if ids:
        _check_in_study(study, ids)
        return ids
    ids = _instances(study, {Modality.RX}) or _instances(study, {Modality.UNKNOWN})
    if not ids:
        raise HTTPException(422, "study has no RX instance")
    return ids


def _has_biplane(images: list[RXImageAnalysis]) -> bool:
    views = {i.view for i in images}
    return RXView.LATERAL in views and bool(views & {RXView.PA, RXView.AP})


@router.post("/rx/{study_id}/analyze", response_model=RXAnalysis)
def rx_analyze(study_id: str, body: Optional[RXRequest] = None, ai: bool = False):
    study = _study(study_id)
    ids = _pick_rx_ids(study, body.instance_ids if body else None)
    t0 = time.perf_counter()
    try:
        images = _analyze_images(study, ids, body.region_overrides if body else None)
        from app.rx import study_findings

        findings = study_findings(images)
    except ImportError as e:
        raise _not_installed(e)
    result = RXAnalysis(study_id=study_id, images=images, findings=findings,
                        recon3d_available=_has_biplane(images))
    for im in images:
        if im.region_uncertain:
            result.warnings.append(f"{im.instance_id}: região incerta (tag DICOM x imagem); achados suspensos até "
                                   "confirmar a região")
        elif im.out_of_scope:
            result.warnings.append(f"{im.instance_id}: FORA DE ESCOPO — {im.scope_reason}")
        elif im.region_conflict:
            result.warnings.append(f"{im.instance_id}: tag DICOM diz {im.tag_region.value if im.tag_region else '?'} "
                                   f"mas a imagem parece {im.region.value}; região corrigida pela imagem")
    t1 = time.perf_counter()
    _remember("rx", study_id, result)
    lat = {"analysis": round((t1 - t0) * 1000)}
    if ai:
        result = result.model_copy(update={"ai": _run_rx_ai(result)})
        lat["ai"] = round((time.perf_counter() - t1) * 1000)
    usage_log.log_event("analyze", study_id, kind="rx", latency_ms=lat, quality_flags=_rx_flags(result),
                        codes=[f.code for f in result.findings], n_findings=len(result.findings),
                        ai_requested=ai, ai_provider=(result.ai.provider if result.ai else None),
                        out_of_scope=any(i.out_of_scope for i in result.images))
    return result


@router.post("/rx/{study_id}/recon3d", response_model=Recon3DResult)
def rx_recon3d(study_id: str, body: Optional[ReconRequest] = None):
    body = body or ReconRequest()
    study = _study(study_id)
    try:
        if body.frontal_id and body.lateral_id:
            _check_in_study(study, [body.frontal_id, body.lateral_id])
            f, l = _analyze_images(study, [body.frontal_id, body.lateral_id])
        else:
            images = _analyze_images(study, _pick_rx_ids(study, None))
            fr = [i for i in images if i.view in (RXView.PA, RXView.AP)]
            lat = [i for i in images if i.view == RXView.LATERAL]
            if body.frontal_id:
                fr = [i for i in fr if i.instance_id == body.frontal_id]
            if body.lateral_id:
                lat = [i for i in lat if i.instance_id == body.lateral_id]
            if not fr or not lat:
                raise HTTPException(422, "need a frontal (PA/AP) and a lateral image")
            fr.sort(key=lambda i: i.view != RXView.PA)  # prefer PA
            f, l = fr[0], lat[0]
        from app.recon3d import reconstruct

        glb, meshes, method = reconstruct(f, l)
    except ImportError as e:
        raise _not_installed(e)
    store.put_artifact(study_id, "model.glb", glb)
    return Recon3DResult(study_id=study_id, gltf_url=f"/api/recon3d/{study_id}/model.glb",
                         meshes=meshes, method=method)


@router.get("/recon3d/{study_id}/model.glb")
def model_glb(study_id: str):
    p = store.get_artifact(study_id, "model.glb")
    if not p:
        raise HTTPException(404, "no 3D model for this study; POST /rx/{study}/recon3d first")
    return FileResponse(p, media_type="model/gltf-binary", filename="model.glb")
