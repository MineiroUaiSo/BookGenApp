"""Synthetic radiograph phantoms for the RX tests."""
from __future__ import annotations

import numpy as np
from skimage.draw import ellipse, line, polygon
from skimage.filters import gaussian


def _ell(img, cy, cx, ry, rx, val):
    rr, cc = ellipse(cy, cx, ry, rx, shape=img.shape)
    img[rr, cc] = val


def _thick_line(img, p0, p1, w, val):
    for d in range(-w, w + 1):
        rr, cc = line(p0[1] + d, p0[0], p1[1] + d, p1[0])
        ok = (rr >= 0) & (rr < img.shape[0]) & (cc >= 0) & (cc < img.shape[1])
        img[rr[ok], cc[ok]] = val


def _lung(img, cy, cx, ry, rx, base_y, dome, val=0.15, p=3.0):
    """Superellipse lung with a domed (diaphragm) base and a sharp costophrenic corner."""
    yy, xx = np.mgrid[:img.shape[0], :img.shape[1]]
    se = (np.abs((xx - cx) / rx) ** p + np.abs((yy - cy) / ry) ** p) < 1
    u = np.clip((xx - cx) / rx, -1, 1)
    base = base_y - dome * (1 - u ** 2)
    img[se & (yy < base)] = val
    return se & (yy < base)


def pa_phantom(size=512, heart_rx=70, trachea_shift=0, seed=0):
    """Returns (uint8 image, truth dict). Patient right on image left."""
    rng = np.random.default_rng(seed)
    img = np.full((size, size), 0.55, np.float32)
    mR = _lung(img, 235, 175, 150, 78, 385, 32)
    mL = _lung(img, 235, 345, 145, 68, 388, 18)
    # spine (column) then trachea over it
    img[30:490, 256 - 14:256 + 14] = 0.80
    tx = 256 + trachea_shift
    img[40:200, tx - 7:tx + 7] = 0.22
    # clavicles: bright oblique bands over upper lungs
    ov = np.zeros_like(img)
    _thick_line(ov, (230, 150), (110, 112), 3, 0.22)
    _thick_line(ov, (282, 150), (405, 112), 3, 0.22)
    img = img + ov
    # heart, painted over lungs
    hc = (320, 300)
    _ell(img, hc[0], hc[1], 62, heart_rx, 0.72)
    img = gaussian(img, 1.2) + rng.normal(0, 0.004, img.shape).astype(np.float32)
    img = np.clip(img, 0, 1)
    lung_left_edge = 175 - 78
    lung_right_edge = 345 + 68
    truth = {
        "ctr": (2 * heart_rx) / (lung_right_edge - lung_left_edge),
        "heart_width": 2 * heart_rx,
        "thoracic_width": lung_right_edge - lung_left_edge,
        "trachea_dev_px": trachea_shift,
    }
    return (img * 255).astype(np.uint8), truth


def lateral_phantom(size=512, spine_right=True, seed=1):
    rng = np.random.default_rng(seed)
    img = np.full((size, size), 0.55, np.float32)
    _ell(img, 250, 256, 150, 120, 0.15)                 # lung field (overlapping lungs)
    # spine band on posterior side, sternum on anterior side
    if spine_right:
        img[40:480, 395:450] = 0.8
        img[60:330, 105:122] = 0.75
        _ell(img, 340, 190, 60, 55, 0.7)                # heart anterior-inferior
    else:
        img[40:480, 62:117] = 0.8
        img[60:330, 390:407] = 0.75
        _ell(img, 340, 322, 60, 55, 0.7)
    img[30:140, 248:264] = 0.2                           # trachea tube above the field
    img = np.clip(gaussian(img, 1.2) + rng.normal(0, 0.004, img.shape).astype(np.float32), 0, 1)
    return (img * 255).astype(np.uint8)


def abdomen_phantom(size=512, seed=2):
    rng = np.random.default_rng(seed)
    img = np.full((size, size), 0.50, np.float32)
    img[40:470, 256 - 14:256 + 14] = 0.78
    # gas loops (dark)
    _ell(img, 200, 160, 40, 28, 0.10)
    _ell(img, 280, 360, 30, 50, 0.10)
    _ell(img, 340, 200, 22, 22, 0.10)
    # pelvis bones
    _ell(img, 440, 150, 25, 70, 0.85)
    _ell(img, 440, 362, 25, 70, 0.85)
    img = np.clip(gaussian(img, 1.2) + rng.normal(0, 0.004, img.shape).astype(np.float32), 0, 1)
    return (img * 255).astype(np.uint8)
