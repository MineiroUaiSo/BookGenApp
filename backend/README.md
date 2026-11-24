# MedLens backend (FastAPI)

Decision-support / teaching tool. Not a certified medical device.

## Run
```bash
cd backend
pip install -e '.[dev]'                 # core deps
pip install -e '.[ecg,rx,recon,ai,dicom-compressed]'   # optional features
MEDLENS_DATA=./data uvicorn app.main:app --reload --port 8000
```
Env: `MEDLENS_DATA` (store root, default `./data`), `MEDLENS_CORS` (default `http://localhost:5173`),
`MEDLENS_FRONTEND_DIST` (default `../frontend/dist`, served at `/` when present).

## Tests
`python -m pytest tests/test_core*` (no heavy deps needed; analyzers are stubbed).
Reusable synthetic DICOMs: `from fixtures_dicom import make_dx_dicom, make_ecg_dicom`
(tests dir is on `sys.path` via `conftest.py`). `conftest.install_fake(monkeypatch, "app.rx", ...)` stubs lazy modules.

## Layout
- `app/store.py` disk store (`studies/<id>/study.json`, `instances/<iid>/...`, `artifacts/`)
- `app/dicom/ingest.py` folder/zip ingestion, classification, anonymisation, grouping
- `app/dicom/render.py` `load_dicom`, `render_to_uint8`, `pixel_spacing_mm`, `render_instance`
- `app/api/` routers: health, ingest, studies (+render.png), analysis (ecg, rx, recon3d, model.glb)

Ingest anonymises: names/IDs/birth date are blanked in the stored copy and never in metadata (age/sex kept).
Analyzer modules are imported lazily; missing ones yield HTTP 501.
