"""End-to-end tests across real modules (no fakes): API ingest -> analyzers -> recon3d."""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from fixtures_dicom import make_ecg_dicom
from synth_ecg import render_paper, synth_signal
from test_rx_phantoms import lateral_phantom, pa_phantom



@pytest.fixture(autouse=True)
def _heuristic_rx_only(monkeypatch):
    """Deterministic heuristic path, scoped to this module (no env leakage into the session)."""
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")


def _png(arr: np.ndarray) -> bytes:
    if arr.dtype != np.uint8:
        arr = np.clip(arr * 255 if arr.max() <= 1.0 else arr, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _ingest(client, files):
    r = client.post("/api/ingest", files=[("files", f) for f in files])
    assert r.status_code == 200, r.text
    return r.json()


def test_ecg_dicom_end_to_end(client, tmp_path):
    p = tmp_path / "ecg.dcm"
    make_ecg_dicom(p, bpm=75)
    study = _ingest(client, [("ecg.dcm", p.read_bytes(), "application/dicom")])["studies"][0]
    r = client.post(f"/api/ecg/{study['study_id']}/analyze?ai=false", json={})
    assert r.status_code == 200, r.text
    a = r.json()
    gm = a["global_measurements"]
    assert gm["heart_rate_bpm"] == pytest.approx(75, abs=4)
    assert a["waves"] and a["conduction"] and len(a["lead_measurements"]) == 12


def test_ecg_photo_end_to_end(client):
    leads, fid = synth_signal(hr=70, seed=3)
    img = render_paper(leads, 500, layout="3x4+1", photo_effects=True)
    if isinstance(img, tuple):
        img = img[0]
    study = _ingest(client, [("ecg.jpg", _png(img), "image/png")])["studies"][0]
    r = client.post(f"/api/ecg/{study['study_id']}/analyze?ai=false", json={"layout": "auto"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["signal"]["source"] == "image"
    assert a["global_measurements"]["heart_rate_bpm"] == pytest.approx(70, abs=5)
    assert a["global_measurements"]["qrs_ms"] is not None


def test_rx_pa_lateral_recon3d_end_to_end(client):
    pa, lat = pa_phantom(), lateral_phantom()
    pa = pa[0] if isinstance(pa, tuple) else pa
    lat = lat[0] if isinstance(lat, tuple) else lat
    res = _ingest(client, [("pa.png", _png(pa), "image/png")])
    res2 = _ingest(client, [("perfil.png", _png(lat), "image/png")])
    sid = res["studies"][0]["study_id"]
    r = client.post(f"/api/rx/{sid}/analyze?ai=false", json={})
    assert r.status_code == 200, r.text
    a = r.json()
    keys = {s["key"] for s in a["images"][0]["structures"]}
    assert {"heart"} <= keys and any("lung" in k for k in keys)
    assert any(m["key"] == "cardiothoracic_ratio" for m in a["images"][0]["measurements"])

    # recon3d directly through the modules (images were ingested as separate studies)
    from app.rx import analyze_image
    from app.recon3d import reconstruct
    f = analyze_image(np.asarray(Image.open(io.BytesIO(_png(pa))).convert("L")), "pa", None)
    l_ = analyze_image(np.asarray(Image.open(io.BytesIO(_png(lat))).convert("L")), "lat", None)
    assert l_.view.value == "LATERAL", l_.view
    glb, meshes, method = reconstruct(f, l_)
    assert glb[:4] == b"glTF" and len(meshes) >= 3 and method
    assert res2["studies"]


def test_images_uploaded_together_form_one_study_and_recon3d(client):
    pa, lat = pa_phantom(), lateral_phantom()
    pa = pa[0] if isinstance(pa, tuple) else pa
    lat = lat[0] if isinstance(lat, tuple) else lat
    res = _ingest(client, [("pa.png", _png(pa), "image/png"), ("perfil.png", _png(lat), "image/png")])
    assert len(res["studies"]) == 1 and len(res["studies"][0]["series"]) == 2
    sid = res["studies"][0]["study_id"]
    a = client.post(f"/api/rx/{sid}/analyze?ai=false", json={}).json()
    assert {i["view"] for i in a["images"]} >= {"LATERAL"} and a["recon3d_available"]
    r = client.post(f"/api/rx/{sid}/recon3d", json={})
    assert r.status_code == 200, r.text
    glb = client.get(r.json()["gltf_url"])
    assert glb.status_code == 200 and glb.content[:4] == b"glTF"
