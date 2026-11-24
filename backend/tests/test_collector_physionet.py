"""Offline tests for the PhysioNet ECG collector (tiny synthetic fixtures, no network / wfdb)."""
import struct

from medlens_data.collectors import physionet_ecg as pe

CODES = {"(": 39, ")": 40, "p": 24, "N": 1, "t": 27}


def _encode(samples, symbols):
    """WFDB annotation encoder (small-interval + SKIP form) for fixtures."""
    out, prev = b"", 0
    for s, sym in zip(samples, symbols):
        dt = s - prev
        prev = s
        if dt > 1023:
            out += struct.pack("<H", 59 << 10) + struct.pack("<hH", dt >> 16, dt & 0xFFFF)
            dt = 0
        out += struct.pack("<H", (CODES[sym] << 10) | dt)
    return out + b"\x00\x00"


SAMPLES = [100, 110, 120, 200, 215, 230, 400, 450, 500, 1900, 1910, 1920, 2000, 2010]
SYMS = ["(", "p", ")", "(", "N", ")", "(", "t", ")", "(", "p", ")", "(", "N"]  # last QRS is truncated


def test_annotation_roundtrip_and_delineation():
    s, sym = pe.read_wfdb_annotation(_encode(SAMPLES, SYMS))
    assert s == SAMPLES and sym == SYMS
    d = pe.delineation_from_annotation(s, sym)
    assert d == {"p": [[100, 110, 120], [1900, 1910, 1920]], "N": [[200, 215, 230]], "t": [[400, 450, 500]]}


def test_ludb_header_labels():
    comments = ["#<age>: 51", "#<sex>: F", "#<diagnoses>:", "#Rhythm: Sinus bradycardia.",
                "#Electric axis of the heart: left axis deviation. ", "#Conduction abnormalities: I degree AV block.",
                "#Conduction abnormalities: Incomplete right bundle branch block.", "#Left ventricular hypertrophy. "]
    labels, raw = pe.ludb_labels_from_header(comments)
    assert {"ecg.sinus_bradycardia", "ecg.left_axis_deviation", "ecg.av_block_1", "ecg.irbbb", "ecg.lvh"} <= set(labels)
    assert "ecg.rbbb" not in labels and raw["age"] == "51"


def test_ptbxl_labels():
    stmts = {"CRBBB": {"diagnostic": "1.0", "diagnostic_class": "CD"}, "SR": {"diagnostic": "", "diagnostic_class": ""},
             "LVH": {"diagnostic": "1.0", "diagnostic_class": "HYP"}}
    labels, supers = pe.ptbxl_labels({"CRBBB": 100.0, "SR": 0.0, "LVH": 15.0}, stmts)
    assert "ecg.rbbb" in labels and "ecg.sinus_rhythm" in labels and "ecg.lvh" not in labels
    assert supers == ["ecg.super_CD"]
