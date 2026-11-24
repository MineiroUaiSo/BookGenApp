"""RX analysis tests on synthetic phantoms (no heavy model required)."""
from __future__ import annotations

import base64
import io
import json
import os
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from app.rx import analyze_image, study_findings
from app.schemas import BodyRegion, RXAnalysis, RXView

from test_rx_phantoms import abdomen_phantom, lateral_phantom, pa_phantom


@pytest.fixture(autouse=True)
def _no_models(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")


def meas(a, key):
    for m in a.measurements:
        if m.key == key:
            return m
    return None


def decode(st):
    return np.array(Image.open(io.BytesIO(base64.b64decode(st.mask_png_b64))))


def keys(a):
    return {s.key for s in a.structures}


def test_pa_structures_and_masks():
    img, _ = pa_phantom()
    a = analyze_image(img, "i1", None)
    assert a.view == RXView.PA and a.region == BodyRegion.CHEST
    assert {"right_lung", "left_lung", "heart", "spine", "trachea", "mediastinum"} <= keys(a)
    assert {"right_clavicle", "left_clavicle"} <= keys(a)
    assert (a.height, a.width) == img.shape
    for s in a.structures:
        m = decode(s)
        assert m.shape == img.shape
        assert set(np.unique(m)) <= {0, 255}
        assert s.origin == "heuristic" and s.confidence <= 0.6
        assert len(s.polygon) >= 3 and len(s.bbox) == 4
        assert s.color.startswith("#")
    rl = next(s for s in a.structures if s.key == "right_lung")
    ll = next(s for s in a.structures if s.key == "left_lung")
    assert rl.bbox[0] < ll.bbox[0]      # patient right on image left
    # image png round-trips
    assert Image.open(io.BytesIO(base64.b64decode(a.image_png_b64))).size == (512, 512)
    assert a.quality["rotação"].startswith("adequada")
    assert set(["rotação", "inspiração", "penetração"]) <= set(a.quality)


@pytest.mark.parametrize("heart_rx", [60, 70, 95])
def test_ctr_close_to_truth(heart_rx):
    img, truth = pa_phantom(heart_rx=heart_rx)
    a = analyze_image(img, "i", None)
    ctr = meas(a, "cardiothoracic_ratio")
    assert ctr is not None and abs(ctr.value - truth["ctr"]) < 0.05
    assert len(ctr.drawing) == 2 and all(len(d) == 4 for d in ctr.drawing)


def test_cardiomegaly_finding_only_when_large():
    big, _ = pa_phantom(heart_rx=100)
    small, _ = pa_phantom(heart_rx=60)
    fb = study_findings([analyze_image(big, "b", None)])
    fs = study_findings([analyze_image(small, "s", None)])
    cb = [f for f in fb if f.code == "rx.cardiomegaly"]
    assert cb and cb[0].severity in ("borderline", "abnormal") and cb[0].references
    assert cb[0].references[0].id == "felson_2025"
    assert not [f for f in fs if f.code == "rx.cardiomegaly"]
    assert any(f.severity == "normal" for f in fs)


def test_ap_tag_softens_cardiomegaly():
    big, _ = pa_phantom(heart_rx=100)
    ds = SimpleNamespace(ViewPosition="AP", BodyPartExamined="CHEST")
    a = analyze_image(big, "b", ds)
    assert a.view == RXView.AP
    f = [f for f in study_findings([a]) if f.code == "rx.cardiomegaly"][0]
    assert f.severity == "borderline" and any("AP" in e for e in f.evidence)


def test_tracheal_deviation():
    img, _ = pa_phantom(trachea_shift=0)
    a0 = analyze_image(img, "a", None)
    img2, _ = pa_phantom(trachea_shift=26)
    a1 = analyze_image(img2, "b", None)
    d0 = meas(a0, "tracheal_deviation").value
    d1 = meas(a1, "tracheal_deviation").value
    assert abs(d0) < 8
    assert 12 < d1 - d0 < 40
    codes = {f.code for f in study_findings([a1])}
    assert "rx.tracheal_deviation" in codes
    assert "rx.tracheal_deviation" not in {f.code for f in study_findings([a0])}


def test_other_measurements_present():
    img, _ = pa_phantom()
    a = analyze_image(img, "i", None)
    for k in ("thoracic_width", "heart_width", "mediastinal_width", "lung_area_ratio_L_R",
              "hemidiaphragm_height_difference", "costophrenic_angle_left", "costophrenic_angle_right"):
        assert meas(a, k) is not None, k
    cp = meas(a, "costophrenic_angle_left").value
    assert 20 < cp < 95            # sharp corner in the phantom
    assert abs(meas(a, "hemidiaphragm_height_difference_pct").value) < 15   # roughly symmetrical domes
    assert meas(a, "cardiothoracic_ratio").unit == ""
    assert meas(a, "thoracic_width").unit == "px"


def test_pixel_spacing_gives_mm():
    img, truth = pa_phantom()
    ds = SimpleNamespace(PixelSpacing=[0.7, 0.7], Rows=512, Columns=512, BodyPartExamined="CHEST", ViewPosition="PA")
    a = analyze_image(img, "i", ds)
    assert a.pixel_spacing_mm == [0.7, 0.7]
    tw = meas(a, "thoracic_width")
    assert tw.unit == "mm" and abs(tw.value - truth["thoracic_width"] * 0.7) < 15
    assert all(s.area_mm2 and s.area_mm2 > 0 for s in a.structures)
    assert a.quality["incidência"].startswith("PA (tag")


def test_lateral_by_tag_and_heuristic():
    img = lateral_phantom(spine_right=True)
    a = analyze_image(img, "l", SimpleNamespace(ViewPosition="LL", BodyPartExamined="CHEST"))
    assert a.view == RXView.LATERAL and a.region == BodyRegion.CHEST
    assert {"lung_field", "heart", "spine"} <= keys(a)
    # purely heuristic
    b = analyze_image(img, "l2", None)
    assert b.view == RXView.LATERAL and b.region == BodyRegion.CHEST
    sp = next(s for s in b.structures if s.key == "spine")
    assert sp.bbox[0] > 256                        # spine on image right
    heart = next(s for s in b.structures if s.key == "heart")
    assert heart.bbox[0] < 256                     # heart anterior (left here)
    c = analyze_image(lateral_phantom(spine_right=False), "l3", None)
    assert next(s for s in c.structures if s.key == "spine").bbox[2] < 256
    assert "trachea" in keys(b)


def test_lateral_orientation_tag():
    img = lateral_phantom(spine_right=True)
    ds = SimpleNamespace(ViewPosition="LL", PatientOrientation=["P", "F"])
    a = analyze_image(img, "l", ds)
    assert "direita" in a.quality["orientação"]


def test_abdomen():
    img = abdomen_phantom()
    a = analyze_image(img, "ab", SimpleNamespace(BodyPartExamined="ABDOMEN"))
    assert a.region == BodyRegion.ABDOMEN
    gas = next(s for s in a.structures if s.key == "bowel_gas")
    assert gas.label == "alças intestinais (gás)"
    assert meas(a, "bowel_gas_loops").value == 3
    assert {"spine", "pelvis_bones"} <= keys(a)
    b = analyze_image(img, "ab2", None)           # heuristic region
    assert b.region == BodyRegion.ABDOMEN


def test_tags_region_and_view():
    img, _ = pa_phantom()
    a = analyze_image(img, "x", SimpleNamespace(BodyPartExamined="HAND", ViewPosition="PA"))
    assert a.region == BodyRegion.EXTREMITY
    assert [s.key for s in a.structures] in ([], ["bones"])
    b = analyze_image(img, "y", SimpleNamespace(SeriesDescription="Tórax PERFIL"))
    assert b.view == RXView.LATERAL


def test_degenerate_images_do_not_crash():
    for im in (np.zeros((200, 150), np.uint8), np.full((64, 64), 255, np.uint8),
               (np.random.default_rng(0).random((300, 300)) * 255).astype(np.uint8)):
        a = analyze_image(im, "z", None)
        json.loads(a.model_dump_json())
        study_findings([a])


def test_json_serializable_full_analysis():
    img, _ = pa_phantom(heart_rx=100)
    lat = lateral_phantom()
    ims = [analyze_image(img, "pa", SimpleNamespace(ViewPosition="PA")),
           analyze_image(lat, "lat", SimpleNamespace(ViewPosition="LL"))]
    fs = study_findings(ims)
    ra = RXAnalysis(study_id="s", images=ims, findings=fs, recon3d_available=True)
    d = json.loads(ra.model_dump_json())
    assert d["images"][0]["structures"][0]["mask_png_b64"]
    assert fs and all(f["origin"] in ("rules", "model") for f in d["findings"])


def test_model_scores_become_model_findings():
    img, _ = pa_phantom()
    a = analyze_image(img, "m", None)
    a.model_scores = {"Effusion": 0.9, "Nodule": 0.2, "Pneumonia": 0.7}
    fs = study_findings([a])
    mf = [f for f in fs if f.origin == "model"]
    assert {f.code for f in mf} == {"rx.model.effusion", "rx.model.pneumonia"}
    assert all("Sugestivo de" in f.label and f.confidence <= 0.6 for f in mf)


def _weights_cached():
    d = os.path.expanduser("~/.torchxrayvision/models_data")
    return os.path.isdir(d) and any(f.startswith("pspnet") for f in os.listdir(d))


@pytest.mark.skipif(not _weights_cached(), reason="torchxrayvision weights not cached")
def test_model_path_runs_or_falls_back(monkeypatch):
    pytest.importorskip("torchxrayvision")
    monkeypatch.setenv("MEDLENS_RX_MODELS", "1")
    img, _ = pa_phantom()
    a = analyze_image(img, "m", SimpleNamespace(ViewPosition="PA", BodyPartExamined="CHEST"), use_model=True)
    assert a.region == BodyRegion.CHEST
    assert a.quality["segmentação"]
    # either the model accepted the phantom or we fell back to heuristics; both are valid outputs
    assert {s.origin for s in a.structures} <= {"model", "heuristic"}
    if a.model_scores:
        assert "Cardiomegaly" in a.model_scores and all(0 <= v <= 1 for v in a.model_scores.values())
    json.loads(a.model_dump_json())


def test_model_branch_with_stubbed_segmentation(monkeypatch):
    """Exercises the 'model' origin path (key mapping, measurements) without needing weights."""
    from app.rx import analyze as an, seg_heuristic as H
    from app.rx._common import to_work
    img, truth = pa_phantom()
    w, _ = to_work(img)
    masks = {k: v for k, v in H.segment_chest_frontal(H.smooth(w)).items() if not k.startswith("_")}
    masks["left_scapula"] = np.zeros_like(masks["heart"])
    monkeypatch.setattr(an.seg_model, "segment_chest_model", lambda work: masks)
    a = analyze_image(img, "m", SimpleNamespace(ViewPosition="PA", BodyPartExamined="CHEST"), use_model=True)
    assert {s.origin for s in a.structures} == {"model"}
    assert "PSPNet" in a.quality["segmentação"]
    assert abs(meas(a, "cardiothoracic_ratio").value - truth["ctr"]) < 0.05
    assert all(s.confidence >= 0.7 for s in a.structures)
