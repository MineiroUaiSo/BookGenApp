"""Mask conversion for the rx_masks collector on synthetic data (no network)."""
import numpy as np
from PIL import Image

from medlens_data.collectors import rx_masks as rm

PFS = """;
; Array sets
;

{
  [Label=right lung fixed]
  [LineDisplay=0]
  { 10, 10 },
  { 40, 10 }
},

{
  [Label=right lung]
  [LineMode=ClosedContour]
  { 10, 10 },
  { 40, 10 },
  { 40, 80 },
  { 10, 80 }
},

{
  [Label=left lung]
  [LineMode=ClosedContour]
  { 60, 10 },
  { 90, 10 },
  { 90, 80 },
  { 60, 80 }
}
"""


def test_parse_pfs_and_polygon_mask():
    shapes = rm.parse_pfs(PFS)
    assert set(shapes) == {"right lung", "left lung"}  # 'fixed' landmark set skipped
    m = rm.polygon_mask(shapes["right lung"], (100, 100))
    assert m[40, 25] and not m[40, 75] and not m[5, 25]
    assert 0.9 * 31 * 71 < m.sum() < 1.1 * 31 * 71
    # contours defined in 1024 space, image at 256 -> scale 0.25
    m4 = rm.polygon_mask([(0, 0), (512, 0), (512, 512), (0, 512)], (256, 256), 0.25)
    assert m4[:128, :128].all() and not m4[:, 130:].any()


def test_binarize_handles_antialiased_and_01():
    a = np.array([[0, 3, 200, 255]], dtype=np.uint8)
    assert rm.binarize(a).tolist() == [[False, False, True, True]]
    assert rm.binarize(np.array([[0, 1]], dtype=np.uint8)).tolist() == [[False, True]]


def test_split_left_right_patient_side():
    m = np.zeros((50, 100), bool)
    m[10:40, 10:35] = True   # image-left blob  -> patient RIGHT
    m[10:40, 65:90] = True   # image-right blob -> patient LEFT
    a, b = rm.split_left_right(m)
    assert rm.centroid_x(a) < 50 < rm.centroid_x(b)
    assert a.sum() == b.sum() == 30 * 25
    # touching blobs are cut at the bounding-box midline
    t = np.zeros((20, 100), bool)
    t[5:15, 10:90] = True
    a, b = rm.split_left_right(t)
    assert a.any() and b.any() and not (a & b).any() and (a | b).sum() == t.sum()


def test_rle_roundtrip_uncompressed():
    m = np.zeros((6, 8), bool)
    m[1:4, 2:5] = True
    flat = m.T.reshape(-1)  # column-major
    counts, run, val = [], 0, False
    for v in flat:
        if bool(v) == val:
            run += 1
        else:
            counts.append(run); run, val = 1, bool(v)
    counts.append(run)
    assert (rm.rle_decode(counts, (6, 8)) == m).all()


def test_dice_and_save_mask(tmp_path):
    a = np.zeros((10, 10), bool); a[:5] = True
    b = np.zeros((10, 10), bool); b[:5, :5] = True
    assert rm.dice(a, a) == 1.0 and abs(rm.dice(a, b) - 2 * 25 / 75) < 1e-9
    rm.save_mask(a, tmp_path / "x" / "m.png")
    back = np.asarray(Image.open(tmp_path / "x" / "m.png"))
    assert set(np.unique(back)) == {0, 255} and (back > 0).tolist() == a.tolist()
