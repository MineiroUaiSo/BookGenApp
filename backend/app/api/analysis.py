"""ECG / RX / 3D routes. Heavy modules are imported lazily inside handlers."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.dicom.render import pixel_spacing_mm, render_instance, to_png_bytes
from app.schemas import (AIReport, ECGAnalysis, Modality, Recon3DResult, RXAnalysis,
                         RXImageAnalysis, RXView, StudyInfo)
from app.store import store

router = APIRouter()


class ECGRequest(BaseModel):
    instance_id: Optional[str] = None
    layout: str = "auto"


class RXRequest(BaseModel):
    instance_ids: Optional[list[str]] = None


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

        result = analyze_signal(signal, study_id)
    except ImportError as e:
        raise _not_installed(e)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, str(e))
    if ai:
        try:
            from app.llm import ai_available

            if ai_available():
                from app.llm import ecg_report

                result.ai = ecg_report(result, png)
            else:
                result.ai = _ai_unavailable("IA indisponível (ANTHROPIC_API_KEY ausente).")
        except ImportError as e:
            raise _not_installed(e)
    return result


# ------------------------------------------------------------------ RX
def _analyze_images(study: StudyInfo, ids: list[str]) -> list[RXImageAnalysis]:
    from app.rx import analyze_image

    out = []
    for iid in ids:
        try:
            arr, ds, _ = render_instance(iid, gray=True)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(422, f"{iid}: {e}")
        res = analyze_image(arr, iid, ds)
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
    try:
        images = _analyze_images(study, ids)
        from app.rx import study_findings

        findings = study_findings(images)
    except ImportError as e:
        raise _not_installed(e)
    result = RXAnalysis(study_id=study_id, images=images, findings=findings,
                        recon3d_available=_has_biplane(images))
    if ai:
        try:
            from app.llm import ai_available

            if ai_available():
                from app.llm import rx_report

                result.ai = rx_report(result)
            else:
                result.ai = _ai_unavailable("IA indisponível (ANTHROPIC_API_KEY ausente).")
        except ImportError as e:
            raise _not_installed(e)
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
