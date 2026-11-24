from typing import List, Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.dicom.ingest import ingest_files
from app.schemas import IngestResponse
from app.store import store

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    files: List[UploadFile] = File(...),
    relative_paths: Optional[List[str]] = Form(None),
):
    items = []
    for i, f in enumerate(files):
        name = f.filename or f"file{i}"
        if relative_paths and i < len(relative_paths) and relative_paths[i]:
            name = relative_paths[i]
        items.append((name, await f.read()))
    return ingest_files(items, store)
