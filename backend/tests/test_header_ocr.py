"""K2: printed-header reader (deterministic digit template matching) on the redacted real case."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

CASE1 = Path(__file__).parent / "data" / "caso1_ecg.jpg"


def _norm_and_scale():
    from app.ecg.digitize import geometry, grid
    rgb = geometry.limit_size(geometry.to_rgb_uint8(np.array(Image.open(CASE1).convert("RGB"))))
    rgb, _ = geometry.rectify(rgb)
    norm = grid.normalise(rgb)
    gr = grid.detect_grid(norm, grid.trace_mask(norm))
    return norm, gr["px_per_mm_x"], gr["px_per_mm_y"]


@pytest.mark.skipif(not CASE1.exists(), reason="caso1 image missing")
def test_header_values_read_from_real_print():
    from app.ecg.digitize import header_ocr
    pv = header_ocr.read_header(*_norm_and_scale())
    assert pv is not None
    assert pv.qrs_ms == 112
    assert (pv.qt_ms, pv.qtc_ms) == (438, 482)
    assert (pv.p_axis, pv.r_axis, pv.t_axis) == (49, 20, 171)
    # the PR line is cut by the page edge: it must stay unread rather than be guessed
    assert pv.pr_ms is None
    assert "QRS 112 ms" in pv.text()


def test_header_absent_returns_none():
    from app.ecg.digitize import header_ocr
    blank = np.ones((300, 400, 3), np.float32)
    assert header_ocr.read_header(blank, 4.0, 4.0) is None


def test_printed_values_calibration_keys():
    from app.ecg.digitize.header_ocr import PrintedValues
    cal = PrintedValues(qrs_ms=112.0, qt_ms=438.0, qtc_ms=482.0).as_calibration()
    assert cal == {"printed.qrs_ms": 112.0, "printed.qt_ms": 438.0, "printed.qtc_ms": 482.0}
