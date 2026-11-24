"""Image normalisation: RGB conversion, paper quadrilateral -> perspective rectification, deskew."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

try:  # opencv is optional
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


def to_rgb_uint8(img: np.ndarray) -> np.ndarray:
    a = np.asarray(img)
    if a.dtype != np.uint8:
        a = a.astype(np.float64)
        mx = a.max() if a.size else 1.0
        a = np.clip(a * (255.0 / mx if mx <= 1.0 + 1e-9 else 1.0), 0, 255).astype(np.uint8)
    if a.ndim == 2:
        a = np.stack([a] * 3, -1)
    elif a.shape[2] == 1:
        a = np.repeat(a, 3, 2)
    elif a.shape[2] == 4:
        a = a[..., :3]
    return np.ascontiguousarray(a)


def _resize(a: np.ndarray, scale: float) -> np.ndarray:
    if cv2 is not None:
        return cv2.resize(a, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    zoom = (scale, scale) + (1,) * (a.ndim - 2)
    return ndi.zoom(a.astype(np.float32), zoom, order=1).astype(a.dtype)


def limit_size(rgb: np.ndarray, max_dim: int = 5000) -> np.ndarray:
    m = max(rgb.shape[:2])
    return rgb if m <= max_dim else _resize(rgb, max_dim / m)


def _otsu(v: np.ndarray) -> float:
    hist, edges = np.histogram(v, bins=128)
    p = hist / max(hist.sum(), 1)
    w = np.cumsum(p)
    mu = np.cumsum(p * (edges[:-1] + edges[1:]) / 2)
    mt = mu[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        sb = (mt * w - mu) ** 2 / (w * (1 - w))
    return float(edges[int(np.nanargmax(sb)) + 1])


def _order_quad(pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, np.float32).reshape(-1, 2)
    s, d = pts.sum(1), pts[:, 0] - pts[:, 1]
    return np.float32([pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]])


def _quad_ok(q: np.ndarray, w: int, h: int) -> bool:
    """A usable paper quad: 4 distinct corners, convex-ish area >= 35% of the frame, no collapsed side."""
    x, y = q[:, 0], q[:, 1]
    area = 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
    sides = np.linalg.norm(q - np.roll(q, -1, axis=0), axis=1)
    return bool(area >= 0.35 * w * h and sides.min() >= 0.25 * min(w, h))


def find_paper_quad(rgb: np.ndarray):
    """Return ordered quad (TL,TR,BR,BL) in full-res pixels, or None if the paper fills the frame."""
    h, w = rgb.shape[:2]
    sc = 900.0 / max(h, w)
    small = _resize(rgb, sc) if sc < 1 else rgb
    gray = small.astype(np.float32).mean(2)
    gray = ndi.gaussian_filter(gray, 2)
    thr = _otsu(gray[::2, ::2].ravel())
    mask = gray > thr
    # pink/red printed grid marks paper even in a shadowed corner whose brightness matches a light table
    diff = ndi.gaussian_filter(small[..., 0].astype(np.float32) - small[..., 1].astype(np.float32), 6)
    hi = float(np.percentile(diff, 95))
    if hi > 6.0:
        mask = mask | (diff > 0.4 * hi)
    if mask.mean() > 0.94 or mask.mean() < 0.2:
        return None
    mask = ndi.binary_closing(mask, iterations=3)
    mask = ndi.binary_fill_holes(mask)
    lab, n = ndi.label(mask)
    if n == 0:
        return None
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    k = int(np.argmax(sizes)) + 1
    comp = lab == k
    if comp.mean() < 0.2:
        return None
    quad = None
    if cv2 is not None:
        cs, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea)
        hull = cv2.convexHull(c)
        peri = cv2.arcLength(hull, True)
        for eps in (0.01, 0.02, 0.03, 0.05, 0.08):
            ap = cv2.approxPolyDP(hull, eps * peri, True)
            if len(ap) == 4:
                quad = ap.reshape(4, 2)
                break
        if quad is None:
            quad = cv2.boxPoints(cv2.minAreaRect(hull))
    if quad is None:  # extremal points fallback
        ys, xs = np.nonzero(comp)
        s, d = xs + ys, xs - ys
        quad = np.array([[xs[s.argmin()], ys[s.argmin()]], [xs[d.argmax()], ys[d.argmax()]],
                         [xs[s.argmax()], ys[s.argmax()]], [xs[d.argmin()], ys[d.argmin()]]], np.float32)
    q = _order_quad(quad) / (sc if sc < 1 else 1.0)
    if not _quad_ok(q, w, h):  # degenerate corners (paper cut by the frame): try the min-area box, else leave unrectified
        if cv2 is None:
            return None
        q = _order_quad(cv2.boxPoints(cv2.minAreaRect(hull))) / (sc if sc < 1 else 1.0)
        if not _quad_ok(q, w, h):
            return None
    # paper fills the frame (axis-aligned quad hugging the image borders) -> nothing to rectify
    tol = 0.03
    if (q[:, 0].min() < tol * w and q[:, 1].min() < tol * h and q[:, 0].max() > (1 - tol) * w
            and q[:, 1].max() > (1 - tol) * h
            and abs(q[0, 1] - q[1, 1]) < 0.01 * h and abs(q[0, 0] - q[3, 0]) < 0.01 * w):
        return None
    return q


def warp_quad(rgb: np.ndarray, quad: np.ndarray, inset: float = 0.006) -> np.ndarray:
    tl, tr, br, bl = quad
    W = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    H = int(round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))))
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    if cv2 is not None:
        M = cv2.getPerspectiveTransform(np.float32(quad), dst)
        out = cv2.warpPerspective(rgb, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    else:
        from skimage.transform import ProjectiveTransform, warp
        tf = ProjectiveTransform()
        tf.estimate(dst, np.float32(quad))
        out = warp(rgb, tf, output_shape=(H, W), order=1, mode="edge", preserve_range=True).astype(np.uint8)
    ix, iy = int(inset * W), int(inset * H)  # crop the dark paper rim without rescaling
    out = np.ascontiguousarray(out[iy:H - iy, ix:W - ix])
    if out.shape[0] > out.shape[1]:
        out = np.ascontiguousarray(np.rot90(out))
    return out


def grid_darkness(rgb: np.ndarray) -> np.ndarray:
    """Cheap darkness map (green channel is weakest for red/pink grids and trace alike)."""
    g = rgb[..., 1].astype(np.float32)
    bg = ndi.gaussian_filter(ndi.maximum_filter(g[::4, ::4], size=9), 3)
    bg = np.maximum(ndi.zoom(bg, 4, order=1)[: g.shape[0], : g.shape[1]], 1)
    if bg.shape != g.shape:
        bg = np.pad(bg, ((0, g.shape[0] - bg.shape[0]), (0, g.shape[1] - bg.shape[1])), mode="edge")
    return np.clip(1 - g / bg, 0, 0.5)


def estimate_skew_deg(rgb: np.ndarray, max_deg: float = 6.0) -> float:
    d = grid_darkness(rgb)
    sc = 1100.0 / max(d.shape)
    if sc < 1:
        d = ndi.zoom(d, sc, order=1)
    d = d - ndi.gaussian_filter(d, 25)
    crop = 0.12
    hh, ww = d.shape

    def score(a):
        r = ndi.rotate(d, a, reshape=False, order=1, mode="nearest")
        r = r[int(hh * crop):int(hh * (1 - crop)), int(ww * crop):int(ww * (1 - crop))]
        return float(r.sum(0).var() + r.sum(1).var())

    angles = np.arange(-max_deg, max_deg + 1e-6, 0.5)
    best = angles[int(np.argmax([score(a) for a in angles]))]
    fine = np.arange(best - 0.5, best + 0.5001, 0.1)
    return float(fine[int(np.argmax([score(a) for a in fine]))])


def rotate_image(rgb: np.ndarray, deg: float) -> np.ndarray:
    if abs(deg) < 0.12:
        return rgb
    if cv2 is not None:
        h, w = rgb.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
        return cv2.warpAffine(rgb, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return ndi.rotate(rgb, deg, axes=(1, 0), reshape=False, order=1, mode="nearest")


def rectify(rgb: np.ndarray):
    """Returns (rectified rgb, info dict)."""
    info = {"quad": None, "skew_deg": 0.0}
    quad = find_paper_quad(rgb)
    if quad is not None:
        rgb = warp_quad(rgb, quad)
        info["quad"] = quad.tolist()
    ang = estimate_skew_deg(rgb)
    info["skew_deg"] = ang
    # estimate_skew rotates the *content* by `ang` to align; apply same convention
    rgb = rotate_image(rgb, ang)
    return rgb, info
