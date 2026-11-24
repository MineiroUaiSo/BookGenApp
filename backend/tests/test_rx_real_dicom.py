"""Regression on real public DICOMs (TCIA COVID-19-AR / RICORD / TCGA) — skipped when the folder is absent.

Folder: $MEDLENS_DICOM_EXAMPLES (default ~/Downloads/dicom-exemplos) with torax/*/00000001.dcm, abdome/*/00000001.dcm.
Chest => lungs segmented, numeric cardiothoracic ratio, region chest; abdomen => region abdomen.
Files that need a missing pixel decoder (JPEG Lossless without pylibjpeg) are skipped.
"""
import glob
import os
from pathlib import Path

import pytest

from app.dicom.render import load_dicom, render_to_uint8
from app.rx import seg_model
from app.rx.analyze import analyze_image
from app.schemas import BodyRegion

ROOT = Path(os.environ.get("MEDLENS_DICOM_EXAMPLES", str(Path.home() / "Downloads" / "dicom-exemplos")))
CHEST = sorted(glob.glob(str(ROOT / "torax" / "*" / "*.dcm")))
ABD = sorted(glob.glob(str(ROOT / "abdome" / "*" / "*.dcm")))

pytestmark = pytest.mark.skipif(not (CHEST or ABD), reason="DICOM de exemplo ausentes")


def _load(path):
    ds = load_dicom(path)
    try:
        return ds, render_to_uint8(ds)
    except RuntimeError as e:
        pytest.skip(f"decoder ausente: {str(e)[:60]}")


def _lung_names(a):
    return {s.key for s in a.structures if "lung" in s.key}


@pytest.mark.parametrize("path", CHEST)
@pytest.mark.parametrize("models", [False, True])
def test_chest_segmented_with_ict(path, models):
    if models and seg_model._xrv() is None:
        pytest.skip("torchxrayvision indisponível")
    ds, img = _load(path)
    a = analyze_image(img, "t", ds, use_model=models)
    assert a.region == BodyRegion.CHEST
    assert "indisponível" not in a.quality["segmentação"], a.quality
    assert {"right_lung", "left_lung"} <= _lung_names(a)
    ict = [m for m in a.measurements if m.key == "cardiothoracic_ratio"]
    assert ict and ict[0].value is not None and 0.2 < ict[0].value < 0.9


@pytest.mark.parametrize("path", ABD)
def test_abdomen_region(path):
    ds, img = _load(path)
    a = analyze_image(img, "t", ds, use_model=False)
    assert a.region == BodyRegion.ABDOMEN
