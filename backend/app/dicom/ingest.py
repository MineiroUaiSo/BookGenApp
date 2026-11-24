"""Folder / archive ingestion: detect, classify, anonymise, group, store."""
from __future__ import annotations

import hashlib
import io
import posixpath
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

import pydicom
from PIL import Image

from app import config
from app.dicom import render as _render  # noqa: F401  (registers HEIC opener if available)
from app.schemas import IngestResponse, Modality, SeriesInfo, StudyInfo
from app.store import Store

ECG_SOP_CLASSES = {
    "1.2.840.10008.5.1.4.1.1.9.1.1",  # 12-lead ECG
    "1.2.840.10008.5.1.4.1.1.9.1.2",  # general ECG
    "1.2.840.10008.5.1.4.1.1.9.1.3",  # ambulatory ECG
}
RX_MODALITIES = {"CR", "DX", "RG"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".heic", ".heif", ".webp"}
PATIENT_TAGS = [
    "PatientName", "PatientID", "PatientBirthDate", "OtherPatientIDs", "OtherPatientNames",
    "PatientAddress", "PatientTelephoneNumbers", "ReferringPhysicianName", "InstitutionName",
    "AccessionNumber",
]


def _h(*parts: str, n: int = 12) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:n]


def is_dicom_bytes(data: bytes) -> bool:
    return len(data) > 132 and data[128:132] == b"DICM"


def _try_read_dicom(data: bytes):
    """Return a Dataset for DICOM files (preamble or forced read), else None."""
    force = not is_dicom_bytes(data)
    try:
        ds = pydicom.dcmread(io.BytesIO(data), force=True)
    except Exception:
        return None
    if force:
        # forced reads of random bytes yield garbage; require real DICOM-ish content
        if "SOPClassUID" not in ds and "StudyInstanceUID" not in ds and "Modality" not in ds:
            return None
        if "PixelData" not in ds and "WaveformSequence" not in ds and "Modality" not in ds:
            return None
    return ds


def classify_dicom(ds) -> tuple[Modality, str | None]:
    sop = str(ds.get("SOPClassUID", "") or getattr(getattr(ds, "file_meta", None), "MediaStorageSOPClassUID", ""))
    mod = str(ds.get("Modality", "") or "").upper()
    if sop in ECG_SOP_CLASSES or mod == "ECG":
        return Modality.ECG, mod or "ECG"
    if mod in RX_MODALITIES:
        return Modality.RX, mod
    return Modality.UNKNOWN, mod or None


def _anonymise(ds) -> bytes | None:
    try:
        for t in PATIENT_TAGS:
            if t in ds:
                ds.data_element(t).value = ""
        buf = io.BytesIO()
        ds.save_as(buf, enforce_file_format=True)
        return buf.getvalue()
    except Exception:
        return None


def _expand(items: list[tuple[str, bytes]], warnings: list[str], depth: int = 0):
    """Expand zip archives (recursively, bounded)."""
    out: list[tuple[str, bytes]] = []
    budget = [config.MAX_ZIP_BYTES, config.MAX_ZIP_FILES]
    for name, data in items:
        if data[:4] == b"PK\x03\x04" and depth < 3 and (
            name.lower().endswith(".zip") or not is_dicom_bytes(data)
        ):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    inner = []
                    for zi in zf.infolist():
                        if zi.is_dir() or "__MACOSX" in zi.filename or zi.filename.endswith(".DS_Store"):
                            continue
                        budget[0] -= zi.file_size
                        budget[1] -= 1
                        if budget[0] < 0 or budget[1] < 0:
                            warnings.append(f"{name}: archive too large, truncated")
                            break
                        base = posixpath.normpath(zi.filename).lstrip("/")
                        if base.startswith(".."):
                            continue
                        inner.append((f"{name}/{base}", zf.read(zi)))
                    out.extend(_expand(inner, warnings, depth + 1))
                continue
            except zipfile.BadZipFile:
                pass
        out.append((name, data))
    return out


def ingest_files(items: list[tuple[str, bytes]], store: Store, group_images: bool = True) -> IngestResponse:
    """items: [(relative_path, bytes)]. Stores originals and returns affected studies.

    group_images: images (prints/photos) sent in the same request become ONE study with one
    series per image, so e.g. a PA + lateral pair can be analysed together (and reconstructed in 3D).
    """
    warnings: list[str] = []
    skipped: list[str] = []
    items = _expand([(n.replace("\\", "/"), d) for n, d in items], warnings)
    img_digests = sorted(hashlib.sha1(d).hexdigest() for n, d in items
                         if posixpath.splitext(n.lower())[1] in IMAGE_EXT)
    group_sid = _h("imgset", *img_digests) if group_images and len(img_digests) > 1 else None
    now = datetime.now(timezone.utc).isoformat()

    studies: dict[str, StudyInfo] = {}

    def get_study(sid: str, uid: str | None) -> StudyInfo:
        if sid not in studies:
            studies[sid] = store.get_study(sid) or StudyInfo(study_id=sid, study_uid=uid, created_at=now)
        return studies[sid]

    def add(study: StudyInfo, series_uid: str, modality: Modality, iid: str, **kw):
        ser = next((s for s in study.series if s.series_uid == series_uid), None)
        if ser is None:
            ser = SeriesInfo(series_uid=series_uid, modality=modality, **kw)
            study.series.append(ser)
        if iid not in ser.instance_ids:
            ser.instance_ids.append(iid)
            ser.n_instances = len(ser.instance_ids)

    wfdb_headers: dict[tuple[str, str], str] = {}
    pending_other: list[tuple[str, bytes]] = []
    consumed: set[str] = set()

    for name, data in items:
        low = name.lower()
        base = posixpath.basename(low)
        ext = posixpath.splitext(base)[1]
        if base in ("dicomdir",):
            warnings.append(f"{name}: DICOMDIR index ignored (files are read directly)")
            continue
        if ext in IMAGE_EXT:
            if _store_image(name, data, store, get_study, add, group_sid):
                continue
            skipped.append(name)
            continue
        ds = _try_read_dicom(data) if ext not in (".xml", ".csv", ".hea", ".txt") else None
        if ds is not None:
            if not _store_dicom(name, data, ds, store, get_study, add, warnings):
                skipped.append(name)
            continue
        if ext == ".hea":
            wfdb_headers[(posixpath.dirname(low), posixpath.splitext(base)[0])] = name
            pending_other.append((name, data))
            continue
        if ext in (".xml", ".csv"):
            kind = "aecg_xml" if ext == ".xml" else "csv"
            sid = _h(data.hex()[:0], hashlib.sha1(data).hexdigest())
            iid = f"{sid}-{_h(name, hashlib.sha1(data).hexdigest(), n=10)}"
            store.save_instance(iid, posixpath.basename(name), data,
                                {"kind": kind, "source_name": name, "modality": "ECG"})
            st = get_study(sid, None)
            add(st, f"ecg-{iid}", Modality.ECG, iid, description=posixpath.basename(name))
            continue
        pending_other.append((name, data))

    # WFDB: attach siblings with the same stem to the .hea
    for name, data in pending_other:
        low = name.lower()
        base = posixpath.basename(low)
        stem, ext = posixpath.splitext(base)
        d = posixpath.dirname(low)
        if ext == ".hea":
            sid = _h("wfdb", hashlib.sha1(data).hexdigest(), d, stem)
            iid = f"{sid}-{_h(name, n=10)}"
            store.save_instance(iid, posixpath.basename(name), data,
                                {"kind": "wfdb", "source_name": name, "modality": "ECG"})
            for n2, d2 in pending_other:
                l2 = n2.lower()
                b2 = posixpath.basename(l2)
                if n2 != name and posixpath.dirname(l2) == d and posixpath.splitext(b2)[0] == stem:
                    store.add_instance_file(iid, posixpath.basename(n2), d2)
                    consumed.add(n2)
            st = get_study(sid, None)
            add(st, f"ecg-{iid}", Modality.ECG, iid, description=posixpath.basename(name))
            consumed.add(name)
    for name, _ in pending_other:
        if name not in consumed:
            skipped.append(name)

    for st in studies.values():
        store.save_study(st)
    return IngestResponse(studies=list(studies.values()), skipped_files=skipped, warnings=warnings)


def _store_image(name, data, store, get_study, add, group_sid=None) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception:
        return False
    digest = hashlib.sha1(data).hexdigest()
    sid = group_sid or _h("img", digest)
    iid = f"{sid}-{_h(name, digest, n=10)}"
    store.save_instance(iid, posixpath.basename(name), data,
                        {"kind": "image", "source_name": name, "modality": "UNKNOWN"})
    st = get_study(sid, None)
    add(st, f"img-{iid}", Modality.UNKNOWN, iid, description=posixpath.basename(name))
    return True


def _store_dicom(name, data, ds, store, get_study, add, warnings) -> bool:
    if "PixelData" not in ds and "WaveformSequence" not in ds:
        warnings.append(f"{name}: DICOM without pixel/waveform data ignored")
        return False
    modality, dmod = classify_dicom(ds)
    if dmod == "MG":
        warnings.append(f"{name}: mammography is not supported (kept as UNKNOWN)")
    study_uid = str(ds.get("StudyInstanceUID", "") or "") or None
    sop_uid = str(ds.get("SOPInstanceUID", "") or "") or hashlib.sha1(data).hexdigest()
    sid = _h("study", study_uid) if study_uid else _h("nostudy", hashlib.sha1(data).hexdigest())
    series_uid = str(ds.get("SeriesInstanceUID", "") or "") or f"noseries-{sid}"
    iid = f"{sid}-{_h(sop_uid, n=10)}"
    st = get_study(sid, study_uid)
    if st.patient_age is None and ds.get("PatientAge"):
        st.patient_age = str(ds.PatientAge)
    if st.patient_sex is None and ds.get("PatientSex"):
        st.patient_sex = str(ds.PatientSex)
    view = ds.get("ViewPosition")
    sop = str(ds.get("SOPClassUID", ""))
    store.save_instance(
        iid,
        posixpath.basename(name) + ("" if name.lower().endswith(".dcm") else ".dcm"),
        _anonymise(ds) or data,
        {"kind": "dicom", "source_name": name, "modality": modality.value, "sop_class": sop},
    )
    add(
        st, series_uid, modality, iid,
        dicom_modality=dmod,
        description=str(ds.get("SeriesDescription", "") or "") or None,
        view_position=str(view) if view else None,
        body_part=str(ds.get("BodyPartExamined", "") or "") or None,
    )
    return True
