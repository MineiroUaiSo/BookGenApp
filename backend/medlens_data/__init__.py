"""Shared infrastructure for MedLens dataset collection and benchmarks.

Every collector writes items under  $MEDLENS_DATASETS (default <repo>/data/datasets)/<source>/
and ONE manifest  <source>/manifest.jsonl  of `Record` lines. Data never goes into git.

Rules for collectors (see docs/DATASETS.md):
  * only sources whose licence allows our use (record it per item); respect robots.txt / ToS;
  * polite HTTP: identify ourselves, >= 1 s between requests per host, cache, retry with backoff;
  * keep provenance: url, licence, attribution, retrieved_at;
  * run the sieve (score_caption / dedupe) and store the score, don't silently drop.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get("MEDLENS_DATASETS", REPO / "data" / "datasets"))
USER_AGENT = "MedLens-research/0.1 (non-commercial medical education research; polite crawler)"

# licences we accept (lower-case substrings)
OK_LICENSES = ("cc0", "public domain", "cc by", "cc-by", "odc-by", "odbl", "pddl", "physionet",
               "open data commons", "us government work", "mit", "apache")


@dataclass
class Record:
    id: str                         # unique within source
    source: str                     # e.g. "litfl", "ludb", "ptbxl", "iu_xray", "europepmc"
    modality: str                   # "ECG" | "RX"
    kind: str                       # "image" | "signal" | "dicom"
    path: str                       # relative to DATA_ROOT/<source>/ (main file)
    url: str                        # page or file the item came from
    license: str
    attribution: str = ""
    caption: str = ""               # original legend / report / interpretation (verbatim, for eval only)
    labels: list[str] = field(default_factory=list)       # normalised tags e.g. ["ecg.av_block_1", "rx.cardiomegaly"]
    view: Optional[str] = None      # RX: PA / AP / LATERAL ; ECG: layout "3x4+1" etc.
    group: Optional[str] = None     # items that belong together (PA + lateral of same study, same patient)
    extra: dict = field(default_factory=dict)            # source-specific (fs, annotations path, scp codes...)
    quality: dict = field(default_factory=dict)          # sieve scores
    retrieved_at: str = ""

    def to_json(self) -> str:
        d = asdict(self)
        d["retrieved_at"] = d["retrieved_at"] or datetime.now(timezone.utc).isoformat()
        return json.dumps(d, ensure_ascii=False)


def source_dir(source: str) -> Path:
    p = DATA_ROOT / source
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_manifest(source: str, records: Iterable[Record]) -> Path:
    p = source_dir(source) / "manifest.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(r.to_json() + "\n")
    return p


def read_manifest(source: str) -> Iterator[Record]:
    p = DATA_ROOT / source / "manifest.jsonl"
    if not p.exists():
        return iter(())
    def gen():
        for line in p.open(encoding="utf-8"):
            if line.strip():
                yield Record(**json.loads(line))
    return gen()


def license_ok(lic: str) -> bool:
    l = (lic or "").lower()
    return any(k in l for k in OK_LICENSES)


# ------------------------------------------------------------------ polite HTTP
class PoliteSession:
    """requests wrapper: UA, per-host delay, robots.txt, disk cache, retries with backoff."""

    def __init__(self, delay_s: float = 1.0, cache_dir: Optional[Path] = None, respect_robots: bool = True):
        import requests
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.delay = delay_s
        self.last: dict[str, float] = {}
        self.robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self.cache = cache_dir or (DATA_ROOT / "_http_cache")
        self.cache.mkdir(parents=True, exist_ok=True)
        self.respect_robots = respect_robots

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        u = urlparse(url)
        host = f"{u.scheme}://{u.netloc}"
        if host not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.s.get(host + "/robots.txt", timeout=20)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
                self.robots[host] = rp
            except Exception:
                self.robots[host] = None
        rp = self.robots[host]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, binary: bool = False, use_cache: bool = True, timeout: int = 60, **kw):
        key = hashlib.sha1((url + json.dumps(kw.get("params", {}), sort_keys=True)).encode()).hexdigest()
        cp = self.cache / key
        if use_cache and cp.exists():
            data = cp.read_bytes()
            return data if binary else data.decode("utf-8", "replace")
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        host = urlparse(url).netloc
        wait = self.delay - (time.time() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        err = None
        for attempt in range(5):
            try:
                r = self.s.get(url, timeout=timeout, **kw)
                self.last[host] = time.time()
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(min(60, 2 ** attempt * 2))
                    continue
                r.raise_for_status()
                if use_cache:
                    cp.write_bytes(r.content)
                return r.content if binary else r.text
            except Exception as e:  # network errors
                err = e
                time.sleep(min(60, 2 ** attempt))
        raise RuntimeError(f"GET failed {url}: {err}")


# ------------------------------------------------------------------ sieve
_ECG_TERMS = ("rhythm", "rate", "axis", "pr ", "pr interval", "qrs", "qt", "st elevation", "st depression",
              "t wave", "p wave", "block", "fibrillation", "flutter", "tachycardia", "bradycardia",
              "hypertrophy", "infarct", "ischaemi", "ischemi", "bundle", "lbbb", "rbbb", "brugada", "wpw",
              "ritmo", "eixo", "bloqueio", "sobrecarga", "supradesnivel", "infradesnivel", "onda")
_RX_TERMS = ("lung", "lobe", "opacit", "consolidat", "effusion", "pneumothorax", "cardiomegal", "heart",
             "mediastin", "hilar", "hilum", "diaphragm", "costophrenic", "rib", "clavicle", "trachea",
             "nodule", "mass", "atelecta", "interstitial", "kerley", "bowel", "air-fluid", "pneumoperitoneum",
             "fracture", "radiograph", "x-ray", "pa view", "lateral", "silhouette", "pulmão", "derrame")
_NEG = ("ct ", "computed tomography", "mri", "magnetic resonance", "ultrasound", "sonograph", "pet",
        "histolog", "photomicrograph", "microscop", "angiogra", "echocardiog")


def score_caption(text: str, modality: str) -> dict:
    """0..1 heuristic quality of a legend/report for evaluation use + modality-mismatch flags."""
    t = " " + (text or "").lower() + " "
    terms = _ECG_TERMS if modality == "ECG" else _RX_TERMS
    hits = sorted({w.strip() for w in terms if w in t})
    neg = sorted({w.strip() for w in _NEG if w in t})
    n_words = len(t.split())
    length = min(1.0, n_words / 40.0)
    richness = min(1.0, len(hits) / 6.0)
    score = round(0.4 * length + 0.6 * richness - (0.3 if neg and modality == "RX" else 0.0), 3)
    return {"caption_score": max(0.0, score), "terms": hits, "other_modality_terms": neg, "n_words": n_words}


def image_phash(path: Path) -> str:
    """256-bit difference-hash (16x16 dHash) for near-duplicate detection (no extra deps).
    (An 8x8 average hash was too coarse: most chest radiographs collided.)"""
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("L").resize((17, 16))
    a = np.asarray(im, dtype=float)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return "".join("1" if b else "0" for b in bits)


def dedupe(records: list[Record], root: Path, max_hamming: int = 10) -> list[Record]:
    """Mark near-duplicate images (quality['duplicate_of']) instead of deleting them."""
    seen: list[tuple[str, str]] = []
    for r in records:
        if r.kind != "image":
            continue
        try:
            h = image_phash(root / r.path)
        except Exception:
            continue
        r.quality["phash"] = h
        for oid, oh in seen:
            if sum(a != b for a, b in zip(h, oh)) <= max_hamming:
                r.quality["duplicate_of"] = oid
                break
        else:
            seen.append((r.id, h))
    return records
