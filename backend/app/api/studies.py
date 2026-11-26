from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.dicom.render import render_instance, to_png_bytes
from app.schemas import StudyInfo
from app.store import store

router = APIRouter()


@router.get("/studies", response_model=list[StudyInfo])
def list_studies():
    return store.list_studies()


@router.get("/studies/{study_id}", response_model=StudyInfo)
def get_study(study_id: str):
    s = store.get_study(study_id)
    if not s:
        raise HTTPException(404, "study not found")
    return s


@router.delete("/studies/{study_id}", status_code=204)
def delete_study(study_id: str):
    """Apaga o estudo: arquivos originais, instâncias e artefatos (direito de exclusão / minimização)."""
    if not store.delete_study(study_id):
        raise HTTPException(404, "study not found")
    return Response(status_code=204)


@router.get("/instances/{instance_id}/render.png")
def render_png(instance_id: str, wc: Optional[float] = None, ww: Optional[float] = None):
    try:
        arr, _, _ = render_instance(instance_id, wc, ww, gray=False)
    except KeyError:
        raise HTTPException(404, "instance not found")
    except ValueError as e:
        raise HTTPException(415, str(e))
    except RuntimeError as e:
        raise HTTPException(422, str(e))
    return Response(to_png_bytes(arr), media_type="image/png")
