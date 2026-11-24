"""Regression: paper quad touching the frame must never come back degenerate (-> 'no ECG trace found')."""
import cv2
import numpy as np

from app.ecg.digitize import geometry


def _photo(poly):
    img = np.full((600, 800, 3), 110, np.uint8)
    cv2.fillConvexPoly(img, np.array(poly, np.int32), (235, 230, 232))
    return img


def test_find_paper_quad_clipped_corner_returns_none_or_valid_quad():
    # paper rotated so two corners fall outside the frame (triangle-like visible region)
    img = _photo([(0, 560), (790, 5), (790, 420), (0, 599)])
    q = geometry.find_paper_quad(img)
    assert q is None or geometry._quad_ok(np.asarray(q, np.float32), 800, 600)


def test_find_paper_quad_normal_tilted_sheet_is_kept():
    img = _photo([(60, 80), (740, 40), (770, 540), (30, 570)])
    q = geometry.find_paper_quad(img)
    assert q is not None and geometry._quad_ok(np.asarray(q, np.float32), 800, 600)


def test_quad_ok_rejects_duplicate_corners():
    q = np.float32([[20, 580], [780, 10], [780, 500], [20, 580]])
    assert not geometry._quad_ok(q, 800, 600)
