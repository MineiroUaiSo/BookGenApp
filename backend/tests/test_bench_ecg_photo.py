"""Unit tests of the ECG photo bench (synthetic signals; no dataset needed)."""
import re

import numpy as np
import pytest

from bench import ecg_photo_bench as pb
from synth_ecg import synth_signal


@pytest.fixture(scope="module")
def truth():
    leads, _ = synth_signal(hr=72, fs=500, seconds=10, seed=5)
    return {k: np.asarray(v) for k, v in leads.items()}


def test_stratum_of():
    assert pb.stratum_of({"NORM": 100.0, "SR": 0.0}) == "NORM"
    assert pb.stratum_of({"CRBBB": 100.0, "SR": 0.0}) == "BRD"
    assert pb.stratum_of({"CLBBB": 100.0}) == "BRE"
    assert pb.stratum_of({"WPW": 100.0}) == "WPW"
    assert pb.stratum_of({"IMI": 80.0, "NORM": 0.0}) == "IAM"
    assert pb.stratum_of({"NORM": 100.0, "LVH": 100.0}) is None


def _recs():
    out = []
    for i in range(60):
        scp = [{"NORM": 100}, {"CRBBB": 100}, {"CLBBB": 100}, {"IMI": 100}][i % 4]
        out.append({"id": f"r{i}", "path": f"p{i}", "extra": {"strat_fold": (i % 10) + 1, "scp_codes": str(scp)}})
    out.append({"id": "w1", "path": "w", "extra": {"strat_fold": 3, "scp_codes": "{'WPW': 100}"}})
    return out


def test_select_only_dev_folds_and_stratified():
    sel = pb.select_records(_recs(), 20, seed=1)
    assert len(sel) == 20
    assert all(int((r["extra"]["strat_fold"])) <= 8 for r in sel)
    assert {r["_stratum"] for r in sel} == set(pb.STRATA)
    assert sel == pb.select_records(_recs(), 20, seed=1)  # deterministic


def test_render_and_degrade_deterministic(truth):
    page = pb.render_ecg_page(truth, px_per_mm=5, seed=1)
    assert page.dtype == np.uint8 and page.shape[2] == 3 and page.shape[1] > page.shape[0]
    a = pb.degrade(page, "hard", seed=2)
    b = pb.degrade(page, "hard", seed=2)
    assert np.array_equal(a, b) and not np.array_equal(a, pb.degrade(page, "hard", seed=3))


def test_classify_exception_points_into_app():
    from app.ecg.digitize import digitize_image
    try:
        digitize_image(np.full((200, 300, 3), 255, np.uint8))
    except Exception as e:
        c = pb.classify_exception(e)
        assert c["type"] and re.fullmatch(r"\w+\.py:\d+", c["where"])
    else:
        pytest.skip("blank image did not raise")


def test_task_end_to_end_clean(truth, tmp_path):
    job = {"id": "syn", "stratum": "NORM", "profile": "clean", "seed": 1, "truth": {k: v.tolist() for k, v in truth.items()},
           "img": str(tmp_path / "syn.jpg"), "ppm": 8.0}
    r = pb._task(job)
    assert r["ok"], r
    assert (tmp_path / "syn.jpg").exists()
    assert r["n_leads"] >= 12
    assert np.median(list(r["corr"].values())) > 0.8
    s = pb.summarize([r])
    assert s["n"] == 1 and "median_corr_overall" in s
    assert "Exceptions by cause" in pb.render_report(s, "t")


def test_summarize_counts_causes():
    rs = [{"id": "a", "stratum": "NORM", "profile": "hard", "ok": False,
           "exc": {"type": "ValueError", "msg": "no ECG trace found", "where": "__init__.py:N"}},
          {"id": "b", "stratum": "NORM", "profile": "hard", "ok": True, "grid_conf": 0.9, "n_beats": 10, "corr": {"II": 0.95}}]
    s = pb.summarize(rs)
    assert s["usable"] == 1 and s["exceptions"] == 1 and s["causes"][0][1] == 1


def test_worker_cap(monkeypatch, tmp_path):
    seen = {}

    class Ex:
        def __init__(self, n):
            seen["n"] = n

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def map(self, fn, it, chunksize=1):
            return []

    monkeypatch.setattr(pb, "ProcessPoolExecutor", Ex)
    pb.run([{"id": "x"}, {"id": "y"}], tmp_path, workers=16, force=True)
    assert seen["n"] == 3
