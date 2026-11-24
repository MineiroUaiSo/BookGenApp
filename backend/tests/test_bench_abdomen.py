import numpy as np
import pytest

from bench import abdomen_bench as ab


def _vol():
    v = np.full((40, 30, 50), -1000.0, np.float32)   # ar
    v[5:35, 5:25, 5:45] = 40.0                      # corpo
    v[10:30, 12:18, 20:25] = 700.0                  # "coluna"
    return v


def test_drr_shape_range_and_bone_brighter():
    d = ab.drr_ap(_vol(), axis=1)
    assert d.shape == (40, 50) and d.min() >= 0.0 and d.max() <= 1.0
    assert d[20, 22] > d[20, 40] > d[0, 0]


def test_project_mask_matches_shape():
    m = np.zeros((40, 30, 50), bool)
    m[10:30, 12:18, 20:25] = True
    p = ab.project_mask(m, axis=1)
    assert p.shape == (40, 50) and p[20, 22] and not p[0, 0]


def test_dice_values():
    a = np.zeros((10, 10), bool)
    a[:5] = True
    assert ab.dice(a, a) == 1.0
    assert ab.dice(a, ~a) == 0.0
    assert ab.dice(np.zeros((3, 3)), np.zeros((3, 3))) == 1.0
    assert ab.dice_by_structure({"x": a}, {"x": a, "y": a}) == {"x": 1.0}


def test_expected_regions(tmp_path):
    assert ab.expected_regions(tmp_path / "abdome" / "1" / "a.dcm", tmp_path) == {"abdomen", "pelvis"}
    assert ab.expected_regions(tmp_path / "torax" / "a.dcm", tmp_path) == {"chest"}
    assert ab.expected_regions(tmp_path / "outro" / "a.dcm", tmp_path) is None


def test_gas_csv_and_metrics(tmp_path):
    c = tmp_path / "a.csv"
    c.write_text("image,diameter_mm\nx.dcm,70\ny.dcm,40\n")
    assert [r["diameter_mm"] for r in ab.read_gas_csv(c)] == [70.0, 40.0]
    m = ab.gas_metrics([70, 40, 65], [60.0, 50.0, None])
    assert m["n"] == 2 and m["mae_mm"] == pytest.approx(10.0) and m["bias_mm"] == pytest.approx(0.0)
    assert m["sens_60mm"].startswith("100")


def test_gas_csv_invalid(tmp_path):
    c = tmp_path / "b.csv"
    c.write_text("foo,bar\n1,2\n")
    with pytest.raises(ValueError):
        ab.read_gas_csv(c)
    c.write_text("image,diameter_mm\nx,abc\n")
    with pytest.raises(ValueError):
        ab.read_gas_csv(c)
