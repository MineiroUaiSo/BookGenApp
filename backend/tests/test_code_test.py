"""CODE-test (final external test) loader + guard. The analyser is NEVER run here and no metric is computed."""
from __future__ import annotations

import numpy as np
import pytest

from bench import code_test as ct
from bench import splits


def _have_data() -> bool:
    r = ct.root()
    return (r / "ecg_tracings.hdf5").exists() and (r / "annotations" / "gold_standard.csv").exists()


needs_data = pytest.mark.skipif(not _have_data(), reason="datasets/code_test not downloaded")


@needs_data
def test_code_test_smoke_two_tracings_shape_and_unit():
    x = ct.load_tracings()
    assert x.shape == (827, 4096, 12)
    for i in (0, 1):
        y = ct.trim_padding(x[i])
        assert 2000 < len(y) <= 4096 and y.shape[1] == 12          # 7-10 s at 400 Hz after removing the zero padding
        sig = ct.to_signal(x[i])
        assert sig.fs == 400.0 and list(sig.leads) == ct.DATASET_LEADS
        assert abs(sig.duration_s - len(y) / 400.0) < 1e-6
        v = np.abs(np.asarray(sig.leads["II"]))
        assert 0.3 < np.percentile(v, 99.5) < 8.0                  # millivolts (an R wave of ~1-3 mV), not volts/microvolts
    lab = ct.load_labels()
    assert lab.shape == (827, 6) and set(np.unique(lab)) <= {0, 1}
    assert len(ct.load_attributes()) == 827


def test_trim_padding_removes_zero_rows_on_both_sides():
    x = np.zeros((10, 12))
    x[3:7] = 1.0
    assert ct.trim_padding(x).shape == (4, 12)
    assert ct.trim_padding(np.zeros((5, 12))).shape == (5, 12)


def test_label_mapping_covers_all_labels_with_known_predicates():
    from bench import ecg_bench as eb
    assert set(ct.LABEL_TO_PRED) == set(ct.LABELS)
    assert all(v in eb.PRED for v in ct.LABEL_TO_PRED.values())


def test_guard_requires_flag(tmp_path):
    with pytest.raises(ct.FinalTestGuardError):
        ct.guard_run(False, tmp_path)
    assert not ct.marker_path(tmp_path).exists()


def test_guard_writes_marker_and_refuses_second_run(tmp_path):
    m = ct.guard_run(True, tmp_path, head="abc")
    assert m == tmp_path / "code_test.RUN" and m.exists()
    with pytest.raises(ct.FinalTestGuardError):
        ct.guard_run(True, tmp_path)


def test_run_final_refused_without_flag_never_touches_analyser(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "_task", lambda i: (_ for _ in ()).throw(AssertionError("analyser must not run")))
    with pytest.raises(ct.FinalTestGuardError):
        ct.run_final(False, 1, tmp_path)
    ct.guard_run(True, tmp_path)
    with pytest.raises(ct.FinalTestGuardError):     # marker already there -> refuses before any analysis
        ct.run_final(True, 1, tmp_path)


def test_evaluate_runs_on_synthetic_results():
    gold = np.array([[1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]])
    res = [{"id": ct.rid(0), "ok": True, "codes": ["ecg.av_block_1"]}, {"id": ct.rid(1), "ok": True, "codes": []},
           {"id": ct.rid(2), "ok": True, "codes": []}, {"id": ct.rid(3), "ok": True, "codes": ["ecg.av_block_1"]}]
    t = ct.evaluate(res, gold)
    assert "1dAVb" in t and "50,0%" in t


def test_code_test_ids_are_test_split_and_flagged_as_leak():
    assert splits.split_of("code_test", "codetest-0001") == "test"
    assert splits.test_ids_in('{"tuned_on": ["codetest-0042"]}') == [("code_test", "codetest-0042")]
