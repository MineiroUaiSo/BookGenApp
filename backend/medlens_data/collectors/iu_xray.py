"""Indiana University Chest X-ray collection (Demner-Fushman et al. 2016) via Open-i bulk files.

Source files (NLM Open-i, no robots.txt restrictions, licence CC BY-NC-ND 4.0 per each report XML):
  https://openi.nlm.nih.gov/imgs/collections/NLMCXR_reports.tgz   (3,955 XML reports)
  https://openi.nlm.nih.gov/imgs/collections/NLMCXR_png.tgz       (~7.4k PNGs, ~1.3 GB)

Output: data/datasets/iu_xray/{images/*.png, reports/*.xml, manifest.jsonl}
One Record per image; group = report id (PA + LATERAL of one study share it).

Run:  python -m medlens_data.collectors.iu_xray [--skip-download]
      python -m medlens_data.collectors.iu_xray --hf abdulhaseeb1308/IU-Xray   (public HF mirror; Open-i robots.txt is Disallow: /)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tarfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional

from medlens_data import PoliteSession, Record, dedupe, score_caption, source_dir, write_manifest

SOURCE = "iu_xray"
BASE = "https://openi.nlm.nih.gov/imgs/collections/"
FILES = ("NLMCXR_reports.tgz", "NLMCXR_png.tgz")
DEFAULT_LICENSE = "CC BY-NC-ND 4.0"
ATTRIBUTION = ("Demner-Fushman D, et al. Preparing a collection of radiology examinations for distribution "
               "and retrieval. J Am Med Inform Assoc 2016;23(2):304-310. Indiana University / NLM Open-i.")

# (regex on lower-cased MeSH "major" term, label code) - first-match-per-rule, several rules may fire
_RULES: list[tuple[str, str]] = [
    (r"^normal$", "rx.normal"),
    (r"cardiomegaly|cardiac shadow/enlarged|heart/enlarged", "rx.cardiomegaly"),
    (r"pleural effusion", "rx.pleural_effusion"),
    (r"costophrenic angle.*(blunt|obliterat)", "rx.costophrenic_blunting"),
    (r"pneumothorax", "rx.pneumothorax"),
    (r"consolidation|pneumonia|airspace disease", "rx.consolidation"),
    (r"atelectasis", "rx.atelectasis"),
    (r"(^|/)(pulmonary )?nodule|solitary pulmonary|(^|/)mass\b|neoplasm", "rx.nodule"),
    (r"^opacity|infiltrate|density/lung", "rx.opacity"),
    (r"mediastin\w*/(widen|enlarg)|mediastinum/(widen|enlarg)|widened mediastinum", "rx.mediastinal_widening"),
    (r"hyperdistention|hyperinflat|emphysema|pulmonary disease, chronic obstructive", "rx.hyperinflation"),
    (r"hypoinflation", "rx.hypoinflation"),
    (r"catheter|implanted medical device|medical device|surgical instruments|pacemaker|drainage tube|"
     r"tube|stent|prosthesis|sutures|defibrillator|sternotomy|port", "rx.device"),
    (r"pulmonary congestion|pulmonary edema|edema", "rx.pulmonary_congestion"),
    (r"diaphragm.*elevat|diaphragmatic eventration", "rx.hemidiaphragm_elevation"),
    (r"calcified granuloma|granulomatous disease|granuloma", "rx.granuloma"),
    (r"cicatrix|scar", "rx.scarring"),
    (r"hernia, hiatal", "rx.hiatal_hernia"),
    (r"aorta.*tortuous|aorta, thoracic/tortuous|atherosclerosis/aorta|calcinosis/aorta", "rx.aortic_tortuosity_calcification"),
    (r"fracture", "rx.fracture"),
    (r"scoliosis|kyphosis|spondylosis|osteophyte|spine/degenerative|vertebrae/degenerative", "rx.spine_changes"),
    (r"technical quality of image unsatisfactory", "rx.technical_limitation"),
]
_RULES_C = [(re.compile(p), c) for p, c in _RULES]


def map_labels(majors: Iterable[str]) -> list[str]:
    out: list[str] = []
    for m in majors:
        t = m.lower().strip()
        for rx, code in _RULES_C:
            if rx.search(t) and code not in out:
                out.append(code)
    return out


def _text(el: Optional[ET.Element]) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def _guess_view(caption: str, idx: int, n: int) -> tuple[Optional[str], str]:
    """View is not an XML field. Use the image caption when it is unambiguous, else the file order
    (IM-xxxx-1001 frontal, IM-xxxx-2001 lateral is the dataset's convention) when exactly 2 images."""
    c = " " + caption.lower() + " "
    lat = "lateral" in c
    fr = bool(re.search(r"\b(pa|frontal|ap|anteroposterior|posteroanterior)\b", c))
    if lat and not fr:
        return "LATERAL", "caption"
    if fr and not lat:
        return "PA", "caption"
    if n == 2:
        return ("PA", "file_order") if idx == 0 else ("LATERAL", "file_order")
    return None, "unknown"


def parse_report(xml_bytes: bytes | str, image_exists=None) -> list[Record]:
    """Report XML -> one Record per parentImage. `image_exists(name)->bool` optionally filters."""
    root = ET.fromstring(xml_bytes)
    rid = root.find("uId").get("id") if root.find("uId") is not None else ""
    abstract = {a.get("Label", "").upper(): _text(a) for a in root.iter("AbstractText")}
    findings, impression = abstract.get("FINDINGS", ""), abstract.get("IMPRESSION", "")
    caption = " ".join(x for x in (findings, impression) if x)
    majors = [_text(m) for m in root.findall("./MeSH/major") if _text(m)]
    automatic = [_text(m) for m in root.findall("./MeSH/automatic") if _text(m)]
    lic_url = _text(root.find("licenseURL"))
    lic = DEFAULT_LICENSE if "by-nc-nd" in lic_url or not lic_url else lic_url
    labels = map_labels(majors)
    quality = score_caption(caption, "RX")
    imgs = root.findall("parentImage")
    recs: list[Record] = []
    for i, im in enumerate(imgs):
        iid = im.get("id", "")
        name = f"{iid}.png"
        if image_exists is not None and not image_exists(name):
            continue
        cap_img = _text(im.find("caption"))
        view, vsrc = _guess_view(cap_img, i, len(imgs))
        recs.append(Record(
            id=iid, source=SOURCE, modality="RX", kind="image", path=f"images/{name}",
            url=f"https://openi.nlm.nih.gov/detailedresult?img={iid}&req=4",
            license=lic, attribution=ATTRIBUTION, caption=caption, labels=list(labels), view=view, group=rid,
            extra={"mesh_major": majors, "mesh_automatic": automatic, "indication": abstract.get("INDICATION", ""),
                   "comparison": abstract.get("COMPARISON", ""), "findings": findings, "impression": impression,
                   "image_caption": cap_img, "view_source": vsrc, "report_file": f"reports/{rid.replace('CXR','')}.xml",
                   "problems": [m.split("/")[0] for m in majors]},
            quality=dict(quality)))
    return recs


def download(d: Path) -> None:
    sess = PoliteSession(delay_s=1.0)
    for fn in FILES:
        dest = d / "raw" / fn
        dest.parent.mkdir(exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0 and (d / "raw" / (fn + ".ok")).exists():
            continue
        url = BASE + fn
        assert sess.allowed(url), url
        with sess.s.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for ch in r.iter_content(1 << 20):
                    f.write(ch)
        (d / "raw" / (fn + ".ok")).write_text("ok")


def _safe_extract(tgz: Path, out: Path, suffix: str) -> int:
    n = 0
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tgz) as t:
        for m in t:
            if not m.isfile() or not m.name.lower().endswith(suffix):
                continue
            f = t.extractfile(m)
            (out / Path(m.name).name).write_bytes(f.read())
            n += 1
    return n


def run(skip_download: bool = False) -> Path:
    d = source_dir(SOURCE)
    if not skip_download:
        download(d)
    if not any((d / "reports").glob("*.xml")) if (d / "reports").exists() else True:
        _safe_extract(d / "raw" / FILES[0], d / "reports", ".xml")
    if not any((d / "images").glob("*.png")) if (d / "images").exists() else True:
        _safe_extract(d / "raw" / FILES[1], d / "images", ".png")
    have = {p.name for p in (d / "images").glob("*.png")}
    recs: list[Record] = []
    for x in sorted((d / "reports").glob("*.xml"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
        recs.extend(parse_report(x.read_bytes(), image_exists=have.__contains__))
    dedupe(recs, d)
    return write_manifest(SOURCE, recs)


# ------------------------------------------------------------------ Hugging Face mirror (--hf)
# Mirror layout (abdulhaseeb1308/IU-Xray): image.zip with iu_xray/image/<CXR..._IM-....>/<k>.png and
# {train,val,test}.jsonl rows {"response": report text (findings/impression), "images": [".../<study>/0.png", ...]}.
# There is no MeSH: labels come from a negation-aware text heuristic over the report (label_source says so).
_NEG = re.compile(r"\b(no|without|negative for|free of|clear of|not)\b|\bresolved\b|\bnormal\b")
_TEXT_RULES = [(re.compile(p), c) for p, c in [
    (r"cardiomegaly|enlarged heart|heart (is )?enlarged", "rx.cardiomegaly"), (r"pleural effusion", "rx.pleural_effusion"),
    (r"pneumothorax", "rx.pneumothorax"), (r"consolidation|pneumonia|airspace disease", "rx.consolidation"),
    (r"atelecta", "rx.atelectasis"), (r"nodule|mass\b", "rx.nodule"), (r"opacit|infiltrate", "rx.opacity"),
    (r"hyperinflat|emphysema|copd", "rx.hyperinflation"), (r"edema|congestion", "rx.pulmonary_congestion"),
    (r"catheter|pacemaker|tube\b|stent|sternotomy|defibrillator", "rx.device"), (r"granuloma", "rx.granuloma"),
    (r"fracture", "rx.fracture"), (r"scoliosis|kyphosis|spondylosis|osteophyte", "rx.spine_changes"),
    (r"hernia", "rx.hiatal_hernia"),
]]


def text_labels(report: str) -> list[str]:
    """Labels from report sentences that contain no negation/normality word (conservative, documented heuristic)."""
    out: list[str] = []
    for sent in re.split(r"[.;]\s*", report.lower()):
        if not sent or _NEG.search(sent):
            continue
        for rx, code in _TEXT_RULES:
            if rx.search(sent) and code not in out:
                out.append(code)
    if not out and re.search(r"no acute|no active|normal|within normal", report.lower()):
        out.append("rx.normal")
    return out


def run_hf(repo_id: str) -> Path:
    d = source_dir(SOURCE)
    raw = d / "raw_hf"
    raw.mkdir(exist_ok=True)
    base = f"https://huggingface.co/datasets/{repo_id}/resolve/main/"
    for fn in ("image.zip", "train.jsonl", "val.jsonl", "test.jsonl"):
        rc = subprocess.call(["curl", "-sS", "-L", "-C", "-", "--retry", "5", "-A", "MedLens-research/0.1",
                              "-o", str(raw / fn), base + fn])
        if rc != 0:
            raise RuntimeError(f"download failed: {fn} (curl rc={rc})")
    (d / "images").mkdir(exist_ok=True)
    zf = zipfile.ZipFile(raw / "image.zip")
    members = {n: n for n in zf.namelist() if n.lower().endswith(".png")}
    recs: list[Record] = []
    seen: set[str] = set()
    for part in ("train", "val", "test"):
        for line in (raw / f"{part}.jsonl").open(encoding="utf-8"):
            row = json.loads(line)
            report = row.get("response", "")
            labels = text_labels(report)
            quality = score_caption(report, "RX")
            imgs = row["images"]
            for i, ip in enumerate(imgs):
                parts = Path(ip).parts
                study, k = parts[-2], Path(ip).stem
                iid = f"{study}-{k}"
                src_name = next((n for n in members if n.endswith(f"{study}/{k}.png")), None)
                if iid in seen or src_name is None:
                    continue
                seen.add(iid)
                (d / "images" / f"{iid}.png").write_bytes(zf.read(src_name))
                view = ("PA", "file_order") if (len(imgs) == 2 and i == 0) else (("LATERAL", "file_order") if len(imgs) == 2 else (None, "unknown"))
                recs.append(Record(
                    id=iid, source=SOURCE, modality="RX", kind="image", path=f"images/{iid}.png",
                    url=f"https://huggingface.co/datasets/{repo_id}", license=DEFAULT_LICENSE, attribution=ATTRIBUTION,
                    caption=report, labels=list(labels), view=view[0], group=study,
                    extra={"findings": report, "view_source": view[1], "label_source": "text_heuristic (no MeSH in HF mirror)",
                           "hf_repo": repo_id, "hf_split_original": part, "split": "dev"},
                    quality=dict(quality)))
    dedupe(recs, d)
    return write_manifest(SOURCE, recs)


if __name__ == "__main__":
    if "--hf" in sys.argv:
        print(run_hf(sys.argv[sys.argv.index("--hf") + 1]))
    else:
        print(run("--skip-download" in sys.argv))
