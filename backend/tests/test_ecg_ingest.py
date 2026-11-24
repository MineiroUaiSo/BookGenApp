"""ECG ingestion tests: DICOM waveform, aECG XML, CSV, WFDB, image routing."""
import numpy as np
import pydicom
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.ecg.ingest import load_ecg
from app.ecg.ingest.leads import normalize_lead
from app.schemas import SourceKind
from synth_ecg import LEAD_ORDER, synth_signal

FS = 500


@pytest.fixture(scope="module")
def sig12():
    leads, fid = synth_signal(hr=70, fs=FS, seconds=10, seed=2)
    return leads


def _code(v, scheme, meaning):
    c = pydicom.Dataset()
    c.CodeValue, c.CodingSchemeDesignator, c.CodeMeaning = v, scheme, meaning
    return c


def _group(names, data_mv, fs, unit="uV", sens=1.0, label_style="meaning", bits=16):
    """data_mv: dict name -> mV array. Raw = mV*1000/sens (uV) or mV/sens."""
    n = len(next(iter(data_mv.values())))
    item = pydicom.Dataset()
    item.NumberOfWaveformChannels = len(names)
    item.NumberOfWaveformSamples = n
    item.SamplingFrequency = float(fs)
    chans, cols = [], []
    for nm in names:
        c = pydicom.Dataset()
        meaning = {"meaning": f"Lead {nm}", "mdc": f"MDC_ECG_LEAD_{nm.upper()}"}[label_style]
        c.ChannelSourceSequence = Sequence([_code(f"x-{nm}", "MDC", meaning)])
        c.ChannelSensitivity = sens
        c.ChannelSensitivityUnitsSequence = Sequence([_code(unit, "UCUM", unit)])
        c.ChannelSensitivityCorrectionFactor = 1.0
        c.ChannelBaseline = 0.0
        chans.append(c)
        scale = 1000.0 if unit == "uV" else 1.0
        cols.append(np.round(data_mv[nm] * scale / sens))
    item.ChannelDefinitionSequence = Sequence(chans)
    item.WaveformBitsAllocated = bits
    item.WaveformSampleInterpretation = "SS"
    item.WaveformData = np.stack(cols, 1).astype("<i2").tobytes()
    return item


def _write_dicom(path, groups):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.9.1.1"  # 12-lead ECG
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
    ds.Modality = "ECG"
    ds.StudyInstanceUID, ds.SeriesInstanceUID = generate_uid(), generate_uid()
    ds.WaveformSequence = Sequence(groups)
    ds.save_as(str(path), enforce_file_format=True)
    return path


def test_normalize_lead_variants():
    for raw, exp in [("Lead I", "I"), ("MDC_ECG_LEAD_AVR", "aVR"), ("aVL", "aVL"), ("ECG V3", "V3"),
                     ("II (rhythm)", "II"), ("DIII", "III"), ("Lead aVF", "aVF"), ("V6", "V6")]:
        assert normalize_lead(raw) == exp, raw
    assert normalize_lead("Resp") is None


def test_dicom_12lead_uv(tmp_path, sig12):
    p = _write_dicom(tmp_path / "ecg", [_group(LEAD_ORDER, sig12, FS)])
    s = load_ecg(p)
    assert s.source == SourceKind.DICOM and s.fs == FS
    assert list(s.leads) == LEAD_ORDER
    assert abs(s.duration_s - 10) < 1e-6
    for k in LEAD_ORDER:
        assert np.allclose(s.leads[k], sig12[k], atol=2e-3), k  # 1 uV quantisation


def test_dicom_sensitivity_and_mdc_labels(tmp_path, sig12):
    # 5 uV/LSB, labels in MDC style
    p = _write_dicom(tmp_path / "e.dcm", [_group(LEAD_ORDER, sig12, FS, unit="uV", sens=5.0, label_style="mdc")])
    s = load_ecg(p)
    assert np.allclose(s.leads["V2"], sig12["V2"], atol=6e-3)
    # mV units, 0.01 mV/LSB
    p = _write_dicom(tmp_path / "e2.dcm", [_group(LEAD_ORDER, sig12, FS, unit="mV", sens=0.01)])
    s = load_ecg(p)
    assert np.allclose(s.leads["II"], sig12["II"], atol=6e-3)
    assert 0.8 < max(s.leads["II"]) < 1.6


def test_dicom_derives_limb_leads_and_picks_12lead_group(tmp_path, sig12):
    two = {k: sig12[k] for k in ("I", "II")}
    rhythm = {"II": sig12["II"][::2]}
    g_rhythm = _group(["II"], rhythm, FS // 2)
    g_i_ii = _group(["I", "II", "V1", "V2", "V3", "V4", "V5", "V6"], sig12, FS)
    p = _write_dicom(tmp_path / "d.dcm", [g_rhythm, g_i_ii])
    s = load_ecg(p)
    assert s.fs == FS and set(s.leads) == set(LEAD_ORDER)
    assert np.allclose(s.leads["III"], np.array(s.leads["II"]) - np.array(s.leads["I"]))
    assert np.allclose(s.leads["aVR"], -(np.array(s.leads["I"]) + np.array(s.leads["II"])) / 2)
    assert np.allclose(s.leads["aVL"], np.array(s.leads["I"]) - np.array(s.leads["II"]) / 2)
    assert np.allclose(s.leads["aVF"], np.array(s.leads["II"]) - np.array(s.leads["I"]) / 2)
    # derived leads match the true (Einthoven/Goldberger-built) synthetic ones
    assert np.allclose(s.leads["aVF"], sig12["aVF"], atol=5e-3)


def _aecg_xml(leads, fs, unit="uV", scale=2.0, ns=True):
    inc = 1.0 / fs
    xmlns = (' xmlns="urn:hl7-org:v3"' if ns else "") + ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    seqs = [f'<component><sequence><code code="TIME_ABSOLUTE" codeSystem="2.16.840.1.113883.5.4"/>'
            f'<value xsi:type="GLIST_TS"><head value="20240101120000" unit="s"/>'
            f'<increment value="{inc}" unit="s"/></value></sequence></component>']
    for k, v in leads.items():
        digits = " ".join(str(int(round(x * (1000 if unit == "uV" else 1) / scale))) for x in v)
        seqs.append(f'<component><sequence><code code="MDC_ECG_LEAD_{k.upper()}" codeSystem="2.16.840.1.113883.6.24"/>'
                    f'<value xsi:type="SLIST_PQ"><origin value="0" unit="{unit}"/><scale value="{scale}" unit="{unit}"/>'
                    f'<digits>{digits}</digits></value></sequence></component>')
    return (f'<?xml version="1.0"?><AnnotatedECG{xmlns}><component><series><component><sequenceSet>'
            + "".join(seqs) + "</sequenceSet></component></series></component></AnnotatedECG>")


def test_aecg_xml(tmp_path, sig12):
    sub = {k: sig12[k][:2500] for k in LEAD_ORDER}
    p = tmp_path / "ecg.xml"
    p.write_text(_aecg_xml(sub, FS, "uV", 2.0))
    s = load_ecg(p)
    assert s.source == SourceKind.AECG_XML
    assert abs(s.fs - FS) < 1e-6 and list(s.leads) == LEAD_ORDER
    assert np.allclose(s.leads["V4"], sub["V4"], atol=2e-3)
    p.write_text(_aecg_xml({k: sub[k] for k in ("I", "II")}, FS, "mV", 0.005, ns=False))
    s = load_ecg(p)
    assert "aVF" in s.leads and abs(max(s.leads["II"]) - max(sub["II"])) < 0.01


def test_csv_with_time_ms_and_units(tmp_path, sig12):
    n = 2000
    t = np.arange(n) / FS * 1000
    lines = ["time_ms," + ",".join(f"{k}(uV)" for k in LEAD_ORDER)]
    for i in range(n):
        lines.append(f"{t[i]:.1f}," + ",".join(f"{sig12[k][i] * 1000:.1f}" for k in LEAD_ORDER))
    p = tmp_path / "x.csv"
    p.write_text("\n".join(lines))
    s = load_ecg(p)
    assert s.source == SourceKind.CSV and abs(s.fs - FS) < 1e-6
    assert list(s.leads) == LEAD_ORDER and len(s.leads["I"]) == n
    assert np.allclose(s.leads["II"], sig12["II"][:n], atol=1e-3)


def test_csv_semicolon_headers_without_time(tmp_path, sig12):
    n = 1000
    lines = ["# fs=250", ";".join(["Lead I", "Lead II", "V1"])]
    for i in range(n):
        lines.append(";".join(f"{sig12[k][i]:.4f}".replace(".", ",") for k in ("I", "II", "V1")))
    p = tmp_path / "y.csv"
    p.write_text("\n".join(lines))
    s = load_ecg(p)
    assert s.fs == 250 and {"I", "II", "III", "aVR", "aVL", "aVF", "V1"} == set(s.leads)
    assert np.allclose(s.leads["V1"], sig12["V1"][:n], atol=1e-3)


def test_csv_headerless_12_columns(tmp_path, sig12):
    n = 500
    arr = np.stack([sig12[k][:n] for k in LEAD_ORDER], 1)
    p = tmp_path / "z.txt"
    np.savetxt(p, arr, delimiter="\t", fmt="%.4f")
    s = load_ecg(p)
    assert list(s.leads) == LEAD_ORDER and s.fs == 500


def test_wfdb(tmp_path, sig12):
    wfdb = pytest.importorskip("wfdb")
    n = 2500
    arr = np.stack([sig12[k][:n] for k in LEAD_ORDER], 1)
    wfdb.wrsamp("rec1", fs=FS, units=["mV"] * 12, sig_name=LEAD_ORDER, p_signal=arr, fmt=["16"] * 12,
                write_dir=str(tmp_path))
    for f in (tmp_path / "rec1.hea", tmp_path / "rec1"):
        s = load_ecg(f)
        assert s.source == SourceKind.WFDB and s.fs == FS and list(s.leads) == LEAD_ORDER
        assert np.allclose(s.leads["V5"], sig12["V5"][:n], atol=2e-3)


def test_image_routes_to_digitizer(tmp_path, sig12):
    from PIL import Image
    from synth_ecg import render_paper
    img = render_paper(sig12, FS)
    p = tmp_path / "paper.png"
    Image.fromarray(img).save(p)
    s = load_ecg(p)
    assert s.source == SourceKind.IMAGE and len(s.leads) == 12
    assert abs(s.calibration["px_per_mm"] - 12) / 12 < 0.03


def test_unsupported_garbage_raises(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<a><b/></a>")
    with pytest.raises(ValueError):
        load_ecg(p)
