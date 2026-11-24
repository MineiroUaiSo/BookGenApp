"""Grid-based perspective rectification (digitize.perspective)."""
import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from app.ecg.digitize import geometry, perspective  # noqa: E402


def _grid_page(w=1100, h=780, mm=8):
    img = np.full((h, w, 3), 255, np.uint8)
    for k, x in enumerate(range(0, w, mm)):
        col, th = ((235, 120, 120), 2) if k % 5 == 0 else ((250, 205, 205), 1)
        img[:, x:x + th] = col
    for k, y in enumerate(range(0, h, mm)):
        col, th = ((235, 120, 120), 2) if k % 5 == 0 else ((250, 205, 205), 1)
        img[y:y + th, :] = col
    return img


def _warp(img, jitter):
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + np.float32(jitter) * np.float32([w, h])
    m = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, m, (w, h), borderMode=cv2.BORDER_REPLICATE)


def test_recovers_keystone_and_rotation():
    page = _grid_page()
    bent = _warp(page, [[0.02, 0.012], [-0.015, 0.02], [0.012, -0.018], [-0.02, -0.01]])
    H, info = perspective.fit_grid_homography(bent)
    assert H is not None and info["ok"], info
    fixed = perspective.apply_homography(bent, H)
    s_bent = perspective._score_map(*[perspective._prep(bent)[0], np.eye(3)])
    s_fixed = perspective._score_map(*[perspective._prep(fixed)[0], np.eye(3)])
    s_ref = perspective._score_map(*[perspective._prep(page)[0], np.eye(3)])
    assert s_fixed > 1.4 * s_bent
    assert s_fixed > 0.7 * s_ref


def test_rejects_featureless_image():
    flat = np.full((400, 600, 3), 240, np.uint8)
    H, info = perspective.fit_grid_homography(flat)
    assert H is None and not info["ok"]


def test_rectify_reports_homography_info():
    page = _grid_page()
    bent = _warp(page, [[0.015, 0.01], [-0.01, 0.015], [0.01, -0.012], [-0.012, -0.01]])
    _, info = geometry.rectify(bent)
    assert "homography" in info and "homography_reason" in info
