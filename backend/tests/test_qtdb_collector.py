"""QTDB collector: header parsing and manifest build on a tiny synthetic record (no network)."""
from __future__ import annotations

import struct

from medlens_data.collectors import physionet_ecg as pe


def _ann(items):
    """items: [(code, absolute_sample)] -> WFDB annotation bytes (no SKIP needed for small gaps)."""
    out, t = b"", 0
    for code, s in items:
        out += struct.pack("<H", (code << 10) | (s - t))
        t = s
    return out + struct.pack("<H", 0)


def test_qtdb_parse_hea_accepts_fs_with_counter_suffix():
    hdr, comments = pe.parse_hea("sel100 2 250/360(0) 225000\nsel100.dat 212 200 12 0 0 0 0 ECG1\n# 69 M\n")
    assert hdr["fs"] == 250.0 and hdr["n_samples"] == 225000 and comments == ["# 69 M"]


def test_qtdb_build_writes_manifest_with_delineation(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "source_dir", lambda name: tmp_path)
    monkeypatch.setattr(pe, "write_manifest", lambda name, recs: (tmp_path / "manifest.jsonl", recs)[0])
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sel100.hea").write_text("sel100 2 250 2000\nsel100.dat 212 200 12 0 0 0 0 ECG1\n# 69 M\n")
    # ( p ) ( N ) ( t )  + u
    (raw / "sel100.q1c").write_bytes(_ann([(39, 100), (24, 110), (40, 120), (39, 150), (1, 160), (40, 170),
                                          (39, 200), (27, 230), (40, 260), (28, 280)]))
    captured = {}
    monkeypatch.setattr(pe, "write_manifest", lambda name, recs: captured.setdefault("recs", recs) and tmp_path)
    pe.build_qtdb()
    rec = captured["recs"][0]
    assert rec.id == "qtdb-sel100" and rec.source == "qtdb"
    assert rec.extra["annotators"] == ["q1c"]
    assert rec.extra["n_waves"]["q1c"] == {"p": 1, "N": 1, "t": 1, "u": 1}
