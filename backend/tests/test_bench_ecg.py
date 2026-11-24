"""Tests for bench.ecg_bench on tiny synthetic fixtures (no external datasets needed)."""
import json
from pathlib import Path

import numpy as np
import pytest

wfdb = pytest.importorskip("wfdb")

from synth_ecg import synth_signal  # noqa: E402

from bench import ecg_bench as eb  # noqa: E402
from bench.report import pct, table, wilson, write_markdown  # noqa: E402


def _make_ludb(tmp_path, rid="1", src="ludb"):
    leads, fid = synth_signal(hr=70, fs=500, seconds=10.0, seed=1)
    names = ["i", "ii", "iii", "avr", "avl", "avf", "v1", "v2", "v3", "v4", "v5", "v6"]
    sig = np.stack([leads[k] for k in ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]], axis=1)
    d = tmp_path / src / "data"
    d.mkdir(parents=True, exist_ok=True)
    wfdb.wrsamp(rid, fs=500, units=["mV"] * 12, sig_name=names, p_signal=sig, fmt=["16"] * 12, write_dir=str(d))
    fs = 500
    syms, smp = [], []
    for i in range(len(fid["r_peaks_s"])):
        if i == 0 or i == len(fid["r_peaks_s"]) - 1:
            continue  # LUDB leaves the borders unannotated
        pon, poff = fid["p_on_s"][i], fid["p_off_s"][i]
        qon, qoff, rt = fid["qrs_on_s"][i], fid["qrs_off_s"][i], fid["r_peaks_s"][i]
        tend = fid["t_end_s"][i]
        for (a, b, c, ch) in ((pon, (pon + poff) / 2, poff, "p"), (qon, rt, qoff, "N"), (tend - 0.17, tend - 0.085, tend, "t")):
            syms += ["(", ch, ")"]
            smp += [int(a * fs), int(b * fs), int(c * fs)]
    for ext in names:  # wfdb refuses to *write* extensions with digits (real LUDB has .v1), so rename
        wfdb.wrann(rid, "zz", np.array(smp), np.array(syms), write_dir=str(d))
        (d / f"{rid}.zz").rename(d / f"{rid}.{ext}")
    return fid, d


def test_report_helpers(tmp_path):
    lo, hi = wilson(8, 10)
    assert 0.4 < lo < 0.5 and 0.9 < hi < 1.0
    assert pct(1, 4) == "25.0% (1/4)"
    t = table([[1, "a|b"]], ["x", "y"])
    assert t.splitlines()[1] == "|---|---|" and "a\\|b" in t
    p = write_markdown(tmp_path / "r.md", "T", [("S", "body")])
    assert "# T" in p.read_text() and "## S" in p.read_text()


def test_ludb_gold_parse_and_task(tmp_path, monkeypatch):
    fid, d = _make_ludb(tmp_path)
    gold, fs = eb.ludb_gold(str(d / "1"))
    assert fs == 500 and set(gold) == set(eb.LUDB_EXT)
    assert len(gold["II"]) == len(fid["r_peaks_s"]) - 2
    assert gold["II"][0]["p"] is not None and gold["II"][0]["t"] is not None
    monkeypatch.setattr(eb, "DATA_ROOT", tmp_path)
    res = eb._worker(("ludb", {"id": "1", "path": "data/1.hea", "source": "ludb"}))
    assert res["ok"], res.get("tb")
    data = res["data"]
    cnt = data["leads"]["II"]["cnt"]
    assert cnt["qrs_tp"] >= 0.9 * cnt["gold_qrs"]
    errs = data["leads"]["II"]["err"]
    assert abs(np.median(errs["qrs_on"])) < 25 and abs(np.median(errs["qrs_off"])) < 40
    assert data["gold_global"]["qrs"] == pytest.approx(90, abs=6)
    # report from cache runs end-to-end
    body, head = eb.report_ludb({"1": res})
    assert "QRS onset" in body and head["N"] == 1


def test_worker_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "DATA_ROOT", tmp_path)
    res = eb._worker(("ludb", {"id": "x", "path": "missing.hea", "source": "ludb"}))
    assert res["ok"] is False and "error" in res


def test_scp_mapping():
    assert eb.parse_scp({"extra": {"scp_codes": "{'NORM': 100.0, 'SR': 0.0}"}}) == {"NORM": 100.0, "SR": 0.0}
    g = eb.gold_classes({"CRBBB": 100.0, "LAFB": 100.0, "ISCAL": 20.0, "IMI": 80.0, "AFLT": 100.0})
    assert {"RBBB_complete", "RBBB_any", "LAFB", "MI_any", "MI_inferior", "AF_AFL"} <= g
    assert "STTC" not in g and "AF" not in g  # ISCAL likelihood 20 < 50
    c = {"ecg.pathologic_q_inferior", "ecg.rbbb"}
    assert eb.PRED["MI_inferior"](c) and eb.PRED["RBBB_any"](c) and not eb.PRED["LBBB_any"](c)


def test_ptbxl_task_and_report(tmp_path, monkeypatch):
    fid, d = _make_ludb(tmp_path, "00001_hr", "ptbxl")
    monkeypatch.setattr(eb, "DATA_ROOT", tmp_path)
    rec = {"id": "00001", "source": "ptbxl", "path": "data/00001_hr", "extra": {"scp_codes": {"NORM": 100.0, "SR": 0.0}, "heart_axis": "MID"}}
    res = eb._worker(("ptbxl", rec))
    assert res["ok"], res.get("tb")
    body, head = eb.report_ptbxl({"00001": res})
    assert "Per-class performance" in body and head["_N"] == 1


def test_caption_classes():
    cls, unc = eb.caption_classes({"labels": ["ecg.av_block_1"], "caption": "Atrial fibrillation with RBBB. No evidence of Wolff-Parkinson-White."})
    assert {"AV1", "AF", "RBBB_any"} <= cls and "WPW" not in cls
    cls, _ = eb.caption_classes({"caption": "Normal sinus rhythm ECG", "labels": []})
    assert cls == {"NORM"}
    _, unc = eb.caption_classes({"caption": "Atrial flutter 2:1", "labels": []})
    assert unc


def test_compare_to_truth_alignment():
    from app.schemas import ECGSignal, SourceKind
    leads, _ = synth_signal(hr=70, fs=500, seconds=10.0, seed=2)
    true = ECGSignal(fs=500, leads={k: v.tolist() for k, v in leads.items()}, duration_s=10, source=SourceKind.WFDB)
    shifted = {k: (0.9 * np.roll(v, 50))[:2500].tolist() for k, v in leads.items()}
    dig = ECGSignal(fs=500, leads=shifted, duration_s=5, source=SourceKind.IMAGE)
    out = eb.compare_to_truth(dig, true)
    assert out["II"]["r"] > 0.95 and abs(out["II"]["lag_ms"]) in range(0, 400) and 1.0 < out["II"]["gain"] < 1.3


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "OUT_ROOT", tmp_path / "bench")
    (tmp_path / "bench").mkdir()
    eb.cache_path("ludb").write_text(json.dumps({"id": "a", "ok": True}) + "\nbad line\n")
    assert list(eb.load_cache("ludb")) == ["a"]
