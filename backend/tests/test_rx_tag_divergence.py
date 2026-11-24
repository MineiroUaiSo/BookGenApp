"""Regression: the DICOM region tag must never beat the image (chest AP films tagged ABDOMEN were read as abdomen).

Real DICOMs (TCIA public, referenced by path, never versioned; skipped when absent):
  torax/1-5 => CHEST, abdome/1,2,5 => ABDOMEN, torax-tag-errada/3,4 (BodyPartExamined=ABDOMEN but chest AP) => CHEST + warning.
"""
import glob
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.dicom.render import load_dicom, render_to_uint8
from app.rx import seg_model
from app.rx import view as V
from app.rx.analyze import analyze_image
from app.schemas import BodyRegion

ROOT = Path(os.environ.get("MEDLENS_DICOM_EXAMPLES", str(Path.home() / "Downloads" / "dicom-exemplos")))
CHEST = sorted(glob.glob(str(ROOT / "torax" / "*" / "*.dcm")))
ABD = sorted(glob.glob(str(ROOT / "abdome" / "*" / "*.dcm")))
WRONG = sorted(glob.glob(str(ROOT / "torax-tag-errada" / "*" / "*.dcm")))


def _analyze(path):
    if seg_model._xrv() is None:
        pytest.skip("torchxrayvision indisponível")
    ds = load_dicom(path)
    try:
        img = render_to_uint8(ds)
    except RuntimeError as e:
        pytest.skip(f"decoder ausente: {str(e)[:60]}")
    return analyze_image(img, "t", ds, use_model=True)


@pytest.mark.parametrize("path", CHEST)
def test_tag_divergence_chest_tag_chest_image_region_chest(path):
    a = _analyze(path)
    assert a.region == BodyRegion.CHEST and not a.region_conflict and not a.region_uncertain


@pytest.mark.parametrize("path", ABD)
def test_tag_divergence_abdomen_tag_abdomen_image_region_abdomen(path):
    a = _analyze(path)
    assert a.region == BodyRegion.ABDOMEN and not a.region_conflict and not a.region_uncertain


@pytest.mark.parametrize("path", WRONG)
def test_tag_divergence_abdomen_tag_chest_image_corrected_with_warning(path):
    a = _analyze(path)
    assert a.region == BodyRegion.CHEST and a.region_conflict and a.tag_region == BodyRegion.ABDOMEN
    assert "tag DICOM diz ABDOMEN mas a imagem parece tórax" in a.quality["observações"]
    assert a.structures, "chest must be segmented, not skipped as abdomen"


def _fake_model(monkeypatch, kind):
    monkeypatch.setattr(seg_model, "psp_probs", lambda w, m=True: np.zeros((14, 4, 4)))
    monkeypatch.setattr(V, "model_features", lambda p: {})
    monkeypatch.setattr(V, "classify_from_features", lambda f: (kind, "fake"))


def _inputs():
    s = np.random.default_rng(0).random((64, 64)).astype(np.float32)
    return s, SimpleNamespace(BodyPartExamined="ABDOMEN")


def test_tag_divergence_model_chest_frontal_overrides_abdomen_tag(monkeypatch):
    _fake_model(monkeypatch, "chest_frontal")
    s, ds = _inputs()
    r = V.detect_view_region(s, ds, work=s, use_model=True)
    assert r["region"] == BodyRegion.CHEST and r["region_conflict"] and not r["region_uncertain"]


def test_tag_divergence_model_lateral_makes_region_uncertain_and_abstains(monkeypatch):
    _fake_model(monkeypatch, "chest_lateral")
    s, ds = _inputs()
    r = V.detect_view_region(s, ds, work=s, use_model=True)
    assert r["region"] == BodyRegion.ABDOMEN and r["region_uncertain"] and r["kind"] == "other"


def test_tag_divergence_model_nochest_keeps_abdomen_tag(monkeypatch):
    _fake_model(monkeypatch, "nochest")
    s, ds = _inputs()
    r = V.detect_view_region(s, ds, work=s, use_model=True)
    assert r["region"] == BodyRegion.ABDOMEN and not r["region_conflict"] and not r["region_uncertain"]


def test_tag_divergence_forced_region_wins_over_tag(monkeypatch):
    s, ds = _inputs()
    r = V.detect_view_region(s, ds, work=s, use_model=False, forced_region=BodyRegion.PELVIS)
    assert r["region"] == BodyRegion.PELVIS and r["source"] == "usuário" and not r["region_uncertain"]
