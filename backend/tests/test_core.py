import io
import zipfile

import numpy as np
import pydicom
from PIL import Image

from conftest import install_fake
from fixtures_dicom import make_dx_dicom, make_ecg_dicom
from app.dicom.render import load_dicom, pixel_spacing_mm, render_to_uint8
from app.schemas import (ECGAnalysis, ECGSignal, GlobalMeasurements, Recon3DMesh, RXImageAnalysis,
                         RXView, BodyRegion, SourceKind, Finding)


def upload(client, root, extra=None):
    files, paths = [], []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            files.append(("files", (p.name, p.read_bytes())))
            paths.append(str(p.relative_to(root.parent)))
    for n, b in extra or []:
        files.append(("files", (n, b)))
        paths.append(n)
    return client.post("/api/ingest", files=files, data={"relative_paths": paths})


def png_bytes(color=False):
    a = (np.random.rand(40, 60, 3) * 255).astype("uint8") if color else (np.random.rand(40, 60) * 255).astype("uint8")
    b = io.BytesIO()
    Image.fromarray(a).save(b, "PNG")
    return b.getvalue()


# ------------------------------------------------------------- render
def test_render_windowing_and_mono1(tmp_path):
    p2 = make_dx_dicom(tmp_path / "a.dcm", "PA")
    p1 = make_dx_dicom(tmp_path / "b.dcm", "PA", monochrome1=True)
    a = render_to_uint8(load_dicom(p2))
    b = render_to_uint8(load_dicom(p1))
    assert a.dtype == np.uint8 and a.shape == (128, 128)
    assert np.array_equal(b, 255 - a)
    c = render_to_uint8(load_dicom(p2), wc=500, ww=200)
    assert c.shape == a.shape and not np.array_equal(a, c)


def test_auto_window_and_rescale(tmp_path):
    p = make_dx_dicom(tmp_path / "a.dcm", with_window=False, rescale=(1.0, -1024.0))
    img = render_to_uint8(load_dicom(p))
    assert img.min() < 20 and img.max() > 235  # percentile stretch


def test_pixel_spacing_fallback(tmp_path):
    ds = load_dicom(make_dx_dicom(tmp_path / "a.dcm", imager_spacing_only=True, pixel_spacing=(0.14, 0.15)))
    assert pixel_spacing_mm(ds) == (0.14, 0.15)
    ds2 = load_dicom(make_dx_dicom(tmp_path / "b.dcm"))
    assert pixel_spacing_mm(ds2) == (0.2, 0.2)


# ------------------------------------------------------------- ingest
def test_ingest_folder_groups_and_classifies(client, dicom_folder):
    r = upload(client, dicom_folder)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["studies"]) == 3  # PA+LL study, mono1 study, ECG study
    assert any("readme.txt" in s for s in data["skipped_files"])
    rx = [s for s in data["studies"] if s["series"][0]["modality"] == "RX"]
    ecg = [s for s in data["studies"] if s["series"][0]["modality"] == "ECG"]
    assert len(rx) == 2 and len(ecg) == 1
    biplane = max(rx, key=lambda s: sum(x["n_instances"] for x in s["series"]))
    assert sum(x["n_instances"] for x in biplane["series"]) == 2
    assert {x["view_position"] for x in biplane["series"]} == {"PA", "LL"}
    assert biplane["patient_age"] == "045Y" and biplane["patient_sex"] == "F"
    # anonymised
    assert "Doe" not in r.text and "SECRET" not in r.text
    assert (client.get("/api/studies").json().__len__()) == 3
    assert client.get(f"/api/studies/{biplane['study_id']}").status_code == 200
    assert client.get("/api/studies/nope").status_code == 404


def test_stored_original_anonymised(client, dicom_folder):
    from app.store import store

    r = upload(client, dicom_folder).json()
    iid = r["studies"][0]["series"][0]["instance_ids"][0]
    ds = pydicom.dcmread(store.instance_path(iid))
    assert str(ds.PatientName) == "" and str(ds.PatientID) == ""


def test_reingest_is_idempotent(client, dicom_folder):
    upload(client, dicom_folder)
    r = upload(client, dicom_folder).json()
    assert len(client.get("/api/studies").json()) == 3
    assert all(s["n_instances"] == 1 for st in r["studies"] for s in st["series"] if st["series"][0]["modality"] == "ECG")


def test_ingest_zip_and_images_and_other(client, dicom_folder, tmp_path):
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        for p in dicom_folder.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(dicom_folder.parent))
    csv = b"I,II\n0.1,0.2\n0.3,0.4\n"
    xml = b"<AnnotatedECG/>"
    r = client.post("/api/ingest", files=[
        ("files", ("exam.zip", zb.getvalue())),
        ("files", ("photo.png", png_bytes(True))),
        ("files", ("photo2.jpg", png_bytes())),  # PNG bytes with jpg name: PIL sniffs content
        ("files", ("trace.csv", csv)),
        ("files", ("ecg.xml", xml)),
        ("files", ("rec1.hea", b"rec1 1 250 10\nrec1.dat 16 200 16 0 0 0 0 I\n")),
        ("files", ("rec1.dat", b"\x00" * 20)),
        ("files", ("orphan.dat", b"\x00" * 20)),
        ("files", ("junk.bin", b"hello")),
        ("files", ("broken.png", b"notapng")),
    ])
    d = r.json()
    mods = sorted(s["series"][0]["modality"] for s in d["studies"])
    assert mods.count("RX") == 2 and mods.count("UNKNOWN") == 2
    assert mods.count("ECG") == 4  # dicom ecg, csv, xml, wfdb
    assert sorted(d["skipped_files"]) == ["broken.png", "exam.zip/exam/readme.txt", "junk.bin", "orphan.dat"]
    from app.store import store

    wf = [s for s in d["studies"] if s["series"][0]["description"] == "rec1.hea"][0]
    p = store.instance_path(wf["series"][0]["instance_ids"][0])
    assert (p.parent / "rec1.dat").exists()


def test_dicomdir_ignored(client, tmp_path):
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.1.3.10"
    meta.MediaStorageSOPInstanceUID = "1.2.3"
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset("DICOMDIR", {}, file_meta=meta, preamble=b"\0" * 128)
    ds.save_as(str(tmp_path / "DICOMDIR"), enforce_file_format=True)
    r = client.post("/api/ingest", files=[("files", ("DICOMDIR", (tmp_path / "DICOMDIR").read_bytes()))])
    assert r.status_code == 200 and r.json()["studies"] == []


def test_mammography_flagged(client, tmp_path):
    p = make_dx_dicom(tmp_path / "mg.dcm", modality="MG", body_part="BREAST")
    r = client.post("/api/ingest", files=[("files", ("mg.dcm", p.read_bytes()))]).json()
    assert r["studies"][0]["series"][0]["modality"] == "UNKNOWN"
    assert any("mammography" in w for w in r["warnings"])


# ------------------------------------------------------------- render endpoint
def test_render_endpoint(client, dicom_folder):
    d = upload(client, dicom_folder).json()
    iid = [s for st in d["studies"] for s in st["series"] if s["modality"] == "RX"][0]["instance_ids"][0]
    r = client.get(f"/api/instances/{iid}/render.png?wc=2000&ww=1000")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(r.content)).size == (128, 128)
    assert client.get("/api/instances/zzz-1/render.png").status_code == 404
    ecg = [s for st in d["studies"] for s in st["series"] if s["modality"] == "ECG"][0]["instance_ids"][0]
    assert client.get(f"/api/instances/{ecg}/render.png").status_code == 415


def test_health(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and "ai_available" in h and isinstance(h["models"], dict)


def test_cors(client):
    r = client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                               "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


# ------------------------------------------------------------- analysis wiring
def _signal():
    return ECGSignal(fs=500, leads={"I": [0.0] * 10}, duration_s=0.02, source=SourceKind.DICOM)


def _analysis(study_id):
    return ECGAnalysis(study_id=study_id, signal=_signal(), global_measurements=GlobalMeasurements(heart_rate_bpm=60))


def test_ecg_analyze_dicom_and_ai(client, dicom_folder, monkeypatch):
    d = upload(client, dicom_folder).json()
    st = [s for s in d["studies"] if s["series"][0]["modality"] == "ECG"][0]
    seen = {}
    install_fake(monkeypatch, "app.ecg.ingest", load_ecg=lambda p: (seen.setdefault("p", str(p)), _signal())[1])
    install_fake(monkeypatch, "app.ecg.analysis", analyze_signal=lambda sig, sid: _analysis(sid))
    r = client.post(f"/api/ecg/{st['study_id']}/analyze", json={})
    assert r.status_code == 200, r.text
    assert r.json()["global_measurements"]["heart_rate_bpm"] == 60 and r.json()["ai"] is None
    load_dicom(seen["p"])  # a real file path

    install_fake(monkeypatch, "app.llm", ai_available=lambda: False)
    r = client.post(f"/api/ecg/{st['study_id']}/analyze?ai=true", json={})
    assert r.json()["ai"]["available"] is False
    from app.schemas import AIReport
    install_fake(monkeypatch, "app.llm", ai_available=lambda: True,
                 ecg_report=lambda a, png: AIReport(description="ok"))
    r = client.post(f"/api/ecg/{st['study_id']}/analyze?ai=true")
    assert r.json()["ai"]["description"] == "ok"


def test_ecg_analyze_image_uses_digitizer(client, monkeypatch):
    d = client.post("/api/ingest", files=[("files", ("ecg.png", png_bytes(True)))]).json()
    st = d["studies"][0]
    got = {}

    def dig(img, layout):
        got["shape"], got["layout"] = img.shape, layout
        return _signal()

    install_fake(monkeypatch, "app.ecg.digitize", digitize_image=dig)
    install_fake(monkeypatch, "app.ecg.analysis", analyze_signal=lambda s, sid: _analysis(sid))
    r = client.post(f"/api/ecg/{st['study_id']}/analyze", json={"layout": "6x2"})
    assert r.status_code == 200 and got == {"shape": (40, 60, 3), "layout": "6x2"}


def test_501_when_module_missing(client, dicom_folder, monkeypatch):
    import sys
    d = upload(client, dicom_folder).json()
    st = [s for s in d["studies"] if s["series"][0]["modality"] == "ECG"][0]
    for m in ("app.ecg", "app.ecg.ingest", "app.ecg.analysis"):
        monkeypatch.setitem(sys.modules, m, None)  # forces ImportError
    r = client.post(f"/api/ecg/{st['study_id']}/analyze", json={})
    assert r.status_code == 501


def _fake_rx(monkeypatch):
    def analyze_image(img, iid, ds):
        view = RXView.LATERAL if ds is not None and ds.ViewPosition == "LL" else RXView.PA
        return RXImageAnalysis(instance_id=iid, view=view, region=BodyRegion.CHEST,
                               image_png_b64="", width=img.shape[1], height=img.shape[0])

    install_fake(monkeypatch, "app.rx", analyze_image=analyze_image,
                 study_findings=lambda imgs: [Finding(code="x", label="y", severity="normal")])


def test_rx_analyze_and_recon(client, dicom_folder, monkeypatch):
    d = upload(client, dicom_folder).json()
    st = [s for s in d["studies"] if len(s["series"]) == 2][0]
    _fake_rx(monkeypatch)
    r = client.post(f"/api/rx/{st['study_id']}/analyze", json={})
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["images"]) == 2 and j["recon3d_available"] is True and j["findings"][0]["code"] == "x"
    assert j["images"][0]["pixel_spacing_mm"] == [0.2, 0.2]

    one = st["series"][0]["instance_ids"][0]
    j = client.post(f"/api/rx/{st['study_id']}/analyze", json={"instance_ids": [one]}).json()
    assert len(j["images"]) == 1 and j["recon3d_available"] is False
    assert client.post(f"/api/rx/{st['study_id']}/analyze", json={"instance_ids": ["bad-1"]}).status_code == 404

    assert client.get(f"/api/recon3d/{st['study_id']}/model.glb").status_code == 404
    calls = {}

    def reconstruct(f, l):
        calls["v"] = (f.view, l.view)
        return b"glTF\x02\x00\x00\x00", [Recon3DMesh(key="heart", label="Coracao", color="#f00")], "visual hull"

    install_fake(monkeypatch, "app.recon3d", reconstruct=reconstruct)
    r = client.post(f"/api/rx/{st['study_id']}/recon3d")
    assert r.status_code == 200, r.text
    assert calls["v"] == (RXView.PA, RXView.LATERAL)
    assert r.json()["gltf_url"] == f"/api/recon3d/{st['study_id']}/model.glb"
    g = client.get(r.json()["gltf_url"])
    assert g.status_code == 200 and g.content.startswith(b"glTF")
    assert g.headers["content-type"] == "model/gltf-binary"


def test_recon_needs_two_views(client, dicom_folder, monkeypatch):
    d = upload(client, dicom_folder).json()
    mono = [s for s in d["studies"] if len(s["series"]) == 1 and s["series"][0]["modality"] == "RX"][0]
    _fake_rx(monkeypatch)
    install_fake(monkeypatch, "app.recon3d", reconstruct=lambda f, l: (b"", [], ""))
    assert client.post(f"/api/rx/{mono['study_id']}/recon3d").status_code == 422
