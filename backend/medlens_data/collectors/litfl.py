"""LITFL ECG Library collector (CC BY-NC-SA 4.0, https://litfl.com/ecg-library/).

Crawls the library indexes and diagnosis / clinical-case pages, extracts every ECG image with the
text that interprets it, maps to analyzer finding codes and writes manifest.jsonl.

Resumable: per-page results are appended to <source_dir>/pages.jsonl; re-running skips done pages.
Usage:  python -m medlens_data.collectors.litfl [--max-pages N] [--max-gb 2] [--rebuild-only]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from medlens_data import (PoliteSession, Record, dedupe, score_caption, source_dir,
                          write_manifest)

SOURCE = "litfl"
BASE = "https://litfl.com"
LICENSE = "CC BY-NC-SA 4.0"
SEEDS = [
    "https://litfl.com/ecg-library/",
    "https://litfl.com/ecg-library/diagnosis/",
    "https://litfl.com/ecg-library/basics/",
    "https://litfl.com/clinical-cases/ecg-exigency/",
    "https://litfl.com/clinical-cases/cardiovascular-curveball/",
    "https://litfl.com/top-100/ecg/",
    "https://litfl.com/top-100/activate-or-wait/",
]
INDEX_PATHS = {urlparse(u).path for u in SEEDS} | {"/clinical-cases/", "/top-100/"}

# ----------------------------------------------------------------- label rules
# (regex over lower-cased text, label). First element can be a list of labels.
LABEL_RULES: list[tuple[str, list[str]]] = [
    (r"first[- ]degree (heart|av|atrioventricular)? ?block|1st[- ]degree (heart|av)|prolonged pr", ["ecg.av_block_1"]),
    (r"mobitz (type )?(i\b|1\b)|wenckebach", ["ecg.av_block_2", "ecg.av_block_mobitz1"]),
    (r"mobitz (type )?(ii\b|2\b)|hay block", ["ecg.av_block_2", "ecg.av_block_mobitz2", "ecg.av_block_2_mobitz2"]),
    (r"2:1 (av )?block|fixed[- ]ratio", ["ecg.av_block_2", "ecg.av_block_2to1"]),
    (r"second[- ]degree|2nd[- ]degree|high[- ]grade av", ["ecg.av_block_2"]),
    (r"third[- ]degree|3rd[- ]degree|complete heart block|complete av block|av dissociation", ["ecg.av_block_3"]),
    (r"atrial fibrillation|\baf\b|afib", ["ecg.atrial_fibrillation", "ecg.irregular_rhythm"]),
    (r"atrial flutter|flutter waves|sawtooth", ["ecg.atrial_flutter"]),
    (r"left bundle branch block|\blbbb\b", ["ecg.lbbb"]),
    (r"right bundle branch block|\brbbb\b", ["ecg.rbbb"]),
    (r"incomplete left bundle|\bilbbb\b", ["ecg.ilbbb"]),
    (r"incomplete right bundle|\birbbb\b", ["ecg.irbbb"]),
    (r"left anterior fascicular|\blafb\b|left anterior hemiblock", ["ecg.lafb", "ecg.left_axis_deviation"]),
    (r"left posterior fascicular|\blpfb\b|left posterior hemiblock", ["ecg.lpfb", "ecg.right_axis_deviation"]),
    (r"bifascicular|trifascicular", ["ecg.rbbb"]),
    (r"intraventricular conduction|qrs widening|\bivcd\b|nonspecific intraventricular", ["ecg.ivcd"]),
    (r"left axis deviation|\blad\b|left axis", ["ecg.left_axis_deviation", "ecg.axis_deviation"]),
    (r"right axis deviation|\brad\b|right axis", ["ecg.right_axis_deviation", "ecg.axis_deviation"]),
    (r"left ventricular hypertrophy|\blvh\b", ["ecg.lvh"]),
    (r"right ventricular hypertrophy|\brvh\b", ["ecg.rvh"]),
    (r"left atrial (enlargement|abnormality)|p mitrale|\blae\b", ["ecg.lae"]),
    (r"right atrial (enlargement|abnormality)|p pulmonale|\brae\b", ["ecg.rae"]),
    (r"wolff[- ]parkinson|\bwpw\b|pre-?excitation|delta wave", ["ecg.wpw", "ecg.preexcitation"]),
    (r"short pr\b|lown[- ]ganong", ["ecg.short_pr"]),
    (r"long qt|prolonged qt|qt prolongation|torsades", ["ecg.long_qt"]),
    (r"short qt", ["ecg.short_qt"]),
    (r"brugada", ["ecg.brugada"]),
    (r"hyperkal(a)?emi", ["ecg.hyperkalemia"]),
    (r"hypokal(a)?emi", ["ecg.hypokalemia"]),
    (r"pericarditis", ["ecg.pericarditis"]),
    (r"early repolari[sz]ation", ["ecg.early_repolarization"]),
    (r"low (qrs )?voltage|low-voltage", ["ecg.low_voltage"]),
    (r"sinus bradycardia", ["ecg.sinus_bradycardia"]),
    (r"sinus tachycardia", ["ecg.sinus_tachycardia"]),
    (r"normal sinus rhythm|sinus rhythm|normal ecg", ["ecg.sinus_rhythm"]),
    (r"st[- ]elevation|\bstemi\b|myocardial infarction|\bomi\b|injury current", ["ecg.st_elevation_stemi"]),
    (r"st[- ]depression|st segment depression", ["ecg.st_depression"]),
    (r"t[- ]wave inversion|inverted t wave|t wave inversions", ["ecg.t_inversion"]),
    (r"pathological q wave|pathologic q wave|q waves?\b", ["ecg.q_waves"]),
    (r"absent p wave|no p wave|p waves? (are )?absent", ["ecg.no_p_wave"]),
    (r"pacemaker|paced rhythm|pacing", ["ecg.paced"]),
    (r"ventricular tachycardia|\bvt\b", ["ecg.ventricular_tachycardia"]),
    (r"ventricular fibrillation|\bvf\b", ["ecg.ventricular_fibrillation"]),
    (r"supraventricular tachycardia|\bsvt\b|avnrt|avrt", ["ecg.svt"]),
    (r"junctional (escape )?rhythm|junctional tachycardia", ["ecg.junctional_rhythm"]),
    (r"premature ventricular|\bpvcs?\b|ventricular ectopy", ["ecg.pvc"]),
    (r"premature atrial|\bpacs?\b", ["ecg.pac"]),
    (r"hypertrophic cardiomyopathy|\bhcm\b", ["ecg.lvh"]),
    (r"hypercal(c)?aemia", ["ecg.hypercalcemia"]),
    (r"hypocal(c)?aemia", ["ecg.hypocalcemia"]),
    (r"digoxin", ["ecg.digoxin_effect"]),
    (r"dextrocardia", ["ecg.dextrocardia"]),
    (r"limb lead reversal|lead reversal", ["ecg.lead_reversal"]),
    (r"de winter|wellens|sgarbossa", ["ecg.st_elevation_stemi"]),
]
_RULES = [(re.compile(p), labs) for p, labs in LABEL_RULES]


def map_labels(text: str) -> list[str]:
    t = " " + (text or "").lower().replace("‑", "-") + " "
    out: list[str] = []
    for rx, labs in _RULES:
        if rx.search(t):
            for l in labs:
                if l not in out:
                    out.append(l)
    return out


# ----------------------------------------------------------------- HTML parsing
_SIZE_SUFFIX = re.compile(r"-\d{2,4}x\d{2,4}(?=\.[a-zA-Z]{3,4}$)")
_STOP_CLASSES = ("m-a-box", "wp-block-cover", "molongui", "litfl-medmastery", "wp-block-ub-content-toggle")
_NON_ECG_NAME = re.compile(
    r"logo|icon|avatar|gravatar|banner|badge|button|headshot|portrait|flag|favicon|medmastery|"
    r"cxr|x-?ray|radiograph|echo|ultrasound|\bct\b|\bmri\b|photo|cartoon|dissection|anatomy|"
    r"schematic|diagram|infographic|book|cover|thumbnail|author|sponsor|rosc|cath", re.I)
_ECG_NAME = re.compile(r"ecg|ekg|rhythm|strip|lead|block|tachy|brady|stemi|fibrillation|flutter|qrs|st-|t-wave|"
                       r"p-wave|pr-interval|qt|bbb|lvh|wpw|brugada|axis|q-wave", re.I)


@dataclass
class FigureItem:
    image_url: str
    alt: str = ""
    figcaption: str = ""
    heading: str = ""            # nearest preceding h2-h6
    before: str = ""             # paragraphs immediately before the figure (since last figure/heading)
    after: str = ""              # text following the figure up to next figure/heading
    figure_index: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    attachment_id: str = ""


@dataclass
class ParsedPage:
    url: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    answer: str = ""
    figures: list[FigureItem] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    is_index: bool = False


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def best_image_url(img, page_url: str) -> str:
    """Prefer original/full-size file: data-orig-file > <a href> to image > largest srcset > src."""
    cand = img.get("data-orig-file")
    if not cand:
        a = img.find_parent("a")
        if a and a.get("href") and re.search(r"\.(jpe?g|png|gif|webp)(\?|$)", a["href"], re.I):
            cand = a["href"]
    if not cand and img.get("srcset"):
        best, bw = None, -1
        for part in img["srcset"].split(","):
            bits = part.strip().split()
            if not bits:
                continue
            w = int(bits[1][:-1]) if len(bits) > 1 and bits[1].endswith("w") and bits[1][:-1].isdigit() else 0
            if w > bw:
                best, bw = bits[0], w
        cand = best
    if not cand:
        cand = img.get("data-large-file") or img.get("data-src") or img.get("src")
    if not cand:
        return ""
    cand = urljoin(page_url, cand)
    return _SIZE_SUFFIX.sub("", cand.split("?")[0])


def _authors(soup) -> list[str]:
    names = [m.get("content", "").strip() for m in soup.select('meta[name="author"]')]
    names = [n for n in names if n and " and " not in n.replace("\xa0", " ")]
    if not names:
        a = soup.select_one('a[rel="author"]')
        if a:
            names = [_clean(a.get_text())]
    out: list[str] = []
    for n in names:
        if n not in out:
            out.append(n)
    return out


def parse_page(html: str, url: str) -> ParsedPage:
    soup = BeautifulSoup(html, "html.parser")
    pp = ParsedPage(url=url)
    t = soup.title.get_text() if soup.title else ""
    h1 = soup.select_one("h1.entry-title, h1")
    pp.title = _clean(h1.get_text()) if h1 else _clean(t.split("•")[0])
    pp.authors = _authors(soup)
    art = soup.select_one("article")
    classes = art.get("class", []) if art else []
    pp.categories = [c[len("category-"):] for c in classes if c.startswith("category-")]
    pp.tags = [c[len("tag-"):] for c in classes if c.startswith("tag-")]
    content = soup.select_one("article .entry-content") or soup.select_one(".entry-content")
    pp.is_index = urlparse(url).path in INDEX_PATHS
    if content is None:
        return pp

    # links (before stripping) for crawling; keep only litfl.com internal pages
    for a in content.find_all("a", href=True):
        href = urljoin(url, a["href"]).split("#")[0]
        pu = urlparse(href)
        if pu.netloc == "litfl.com" and not re.search(r"\.(jpe?g|png|gif|pdf|webp)$", pu.path, re.I):
            href = href.split("?")[0]
            if href not in pp.links:
                pp.links.append(href)

    # quiz answers: content toggles
    pp.answer = _clean(" ".join(
        d.get_text(" ", strip=True) for d in content.select(".wp-block-ub-content-toggle")))[:6000]

    # walk blocks in document order until author box / cover
    blocks: list[tuple[str, object]] = []   # (kind, node)

    def walk(node):
        for ch in node.children:
            if not getattr(ch, "name", None):
                continue
            cls = " ".join(ch.get("class", []))
            if any(s in cls for s in _STOP_CLASSES):
                if "wp-block-ub-content-toggle" in cls:
                    continue
                blocks.append(("stop", ch))
                continue
            if ch.name == "figure" or (ch.name == "img"):
                blocks.append(("fig", ch))
            elif ch.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                blocks.append(("h", ch))
            elif ch.name in ("p", "ul", "ol", "blockquote", "table"):
                if ch.find("img") and not _clean(ch.get_text()):
                    blocks.append(("fig", ch))
                else:
                    blocks.append(("txt", ch))
            elif ch.name == "div":
                if "spacer" in cls or ch.find("hr"):
                    blocks.append(("sep", ch))
                if ch.find(["figure", "img"]) or ch.find(["p", "ul", "h5", "h6"]):
                    walk(ch)
            else:
                walk(ch)

    walk(content)
    # cut at first stop block
    for i, (k, _) in enumerate(blocks):
        if k == "stop":
            blocks = blocks[:i]
            break

    heading = ""
    pending_before: list[str] = []
    seen_urls: set[str] = set()
    fig_blocks: list[int] = []
    for i, (k, n) in enumerate(blocks):
        if k == "fig":
            fig_blocks.append(i)
    last_fig_idx = -1
    for bi, (k, n) in enumerate(blocks):
        if k == "h":
            heading = _clean(n.get_text())
            pending_before = []
        elif k == "txt":
            pending_before.append(_clean(n.get_text(" ", strip=True)))
        elif k == "sep":
            pass
        elif k == "fig":
            imgs = [n] if n.name == "img" else n.find_all("img")
            fc = n.find("figcaption") if n.name != "img" else None
            fctext = _clean(fc.get_text(" ", strip=True)) if fc else ""
            # text after: until next fig/heading/sep/stop
            after: list[str] = []
            for k2, n2 in blocks[bi + 1:]:
                if k2 in ("fig", "h", "stop"):
                    break
                if k2 == "sep" and after:
                    break
                if k2 == "txt":
                    after.append(_clean(n2.get_text(" ", strip=True)))
            for img in imgs:
                iu = best_image_url(img, url)
                if not iu or iu in seen_urls:
                    continue
                seen_urls.add(iu)
                fi = FigureItem(
                    image_url=iu, alt=_clean(img.get("alt", "")), figcaption=fctext,
                    heading=heading, before=" ".join(pending_before[-2:])[:1500],
                    after=" ".join(after)[:2500], figure_index=len(pp.figures),
                    attachment_id=str(img.get("data-attachment-id", "")))
                m = re.match(r"(\d+),(\d+)$", img.get("data-orig-size", "") or "")
                if m:
                    fi.width, fi.height = int(m.group(1)), int(m.group(2))
                else:
                    try:
                        fi.width = int(img.get("width")) if img.get("width") else None
                        fi.height = int(img.get("height")) if img.get("height") else None
                    except ValueError:
                        pass
                pp.figures.append(fi)
            pending_before = []
    return pp


# ----------------------------------------------------------------- image checks
def ecg_image_check(data: bytes, url: str = "", alt: str = "") -> dict:
    """Heuristic ECG/non-ECG decision from pixels + name. Returns dict with is_ecg and metrics."""
    from PIL import Image
    import numpy as np
    im = Image.open(io.BytesIO(data))
    w, h = im.size
    info = {"width": w, "height": h, "aspect": round(w / max(h, 1), 3)}
    rgb = im.convert("RGB")
    rgb.thumbnail((400, 400))
    a = np.asarray(rgb, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    pink = ((r > 190) & (r - g > 25) & (r - b > 10)).mean()          # pink/red grid
    # thin dark traces vanish when downsampling: min-pool the full-res grey image instead
    gr = np.asarray(im.convert("L"), dtype=np.uint8)
    k = max(1, int(np.ceil(max(gr.shape) / 900)))
    H, W = (gr.shape[0] // k) * k, (gr.shape[1] // k) * k
    mp = gr[:H, :W].reshape(H // k, k, W // k, k).min(axis=(1, 3))
    ink_mask = mp < 205
    ink = float(ink_mask.mean())
    col_cov = float(ink_mask.any(axis=0).mean())
    light = float((mp > 215).mean())
    colourful = float(((a.max(-1) - a.min(-1)) > 70).mean())
    dark = ink
    info.update(pink_frac=round(float(pink), 4), ink_frac=round(ink, 4), col_cov=round(col_cov, 3),
                light_frac=round(light, 4), colourful=round(colourful, 3))
    name = (urlparse(url).path.rsplit("/", 1)[-1] + " " + (alt or ""))
    nonecg_name = bool(_NON_ECG_NAME.search(name)) and not _ECG_NAME.search(name)
    ecg_name = bool(_ECG_NAME.search(name))
    size_ok = w >= 300 and h >= 100 and 1.1 <= w / max(h, 1) <= 8.0
    # grid-like: light background with thin dark trace; low overall dark fraction
    trace_like = 0.002 < ink < 0.35 and col_cov > 0.85 and (light > 0.3 or pink > 0.01) and colourful < 0.25
    score = 0.0
    score += 0.5 if pink > 0.04 else (0.25 if pink > 0.01 else 0.0)
    score += 0.3 if ecg_name else 0.0
    score += 0.45 if trace_like else 0.0
    info["ecg_score"] = round(score, 2)
    info["is_ecg"] = bool(size_ok and not nonecg_name and score >= 0.45)
    if not size_ok:
        info["reject"] = "size/aspect"
    elif nonecg_name:
        info["reject"] = "name"
    elif not info["is_ecg"]:
        info["reject"] = "colour/name"
    return info


# ----------------------------------------------------------------- crawl
class Crawler:
    def __init__(self, max_pages: int = 3000, max_bytes: int = 2 * 1024 ** 3, delay: float = 1.5):
        self.dir = source_dir(SOURCE)
        self.img_dir = self.dir / "images"
        self.img_dir.mkdir(exist_ok=True)
        self.pages_file = self.dir / "pages.jsonl"
        self.sess = PoliteSession(delay_s=delay, cache_dir=self.dir / "_html_cache")
        self.max_pages = max_pages
        self.max_bytes = max_bytes
        self.done: dict[str, dict] = {}
        self.bytes = 0
        self.log = self.dir / "crawl.log"
        if self.pages_file.exists():
            for line in self.pages_file.open(encoding="utf-8"):
                if line.strip():
                    d = json.loads(line)
                    self.done[d["url"]] = d
        self.bytes = sum(f.stat().st_size for f in self.img_dir.glob("*") if f.is_file())

    def _get(self, url: str, binary: bool = False, use_cache: bool = True):
        """PoliteSession.get, but 403/404 are final (no 5x backoff): some URLs are WAF-blocked."""
        key = hashlib.sha1((url + "{}").encode()).hexdigest()
        cp = self.sess.cache / key
        if use_cache and cp.exists():
            return self.sess.get(url, binary=binary)
        if not self.sess.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        host = urlparse(url).netloc
        for attempt in range(3):
            wait = self.sess.delay - (time.time() - self.sess.last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.sess.s.get(url, timeout=60)
            except Exception as e:
                self.sess.last[host] = time.time()
                if attempt == 2:
                    raise RuntimeError(str(e))
                time.sleep(5 * (attempt + 1))
                continue
            self.sess.last[host] = time.time()
            if r.status_code in (403, 404, 410):
                raise RuntimeError(f"HTTP {r.status_code}")
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(15 * (attempt + 1))
                continue
            r.raise_for_status()
            if use_cache:
                cp.write_bytes(r.content)
            return r.content if binary else r.text
        raise RuntimeError("retries exhausted")

    def say(self, msg: str):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)

    @staticmethod
    def relevant(pp: ParsedPage) -> bool:
        """Is the page ECG-related enough to follow its links?"""
        cats = set(pp.categories)
        if pp.is_index:
            return True
        if cats & {"eponym", "eponymictionary", "ccc", "pharmacology", "toxicology", "ultrasound", "echo-library"}:
            return False
        if cats & {"ecg-library", "ecg-diagnosis", "ecg-basics", "clinical-cases", "top-100", "cardiology"}:
            return True
        return "ecg" in urlparse(pp.url).path or "ecg-exigency" in pp.tags

    @staticmethod
    def wanted_link(u: str) -> bool:
        p = urlparse(u).path
        if not p or p == "/":
            return False
        if re.match(r"^/(about|author|category|tag|feed|wp-|cookie|page|search|library|ccc|eponym|echo-library|"
                    r"toxicology|pharm|resus|trauma|medical-blog|lifestyle|education|ecg-library/ecg-references)", p):
            return False
        return True

    last_reject = ""

    def fetch_image(self, fi: FigureItem) -> Optional[tuple[Path, dict]]:
        self.last_reject = ""
        ext = Path(urlparse(fi.image_url).path).suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            return None
        host = urlparse(fi.image_url).netloc
        if not (host == "litfl.com" or host.endswith(".litfl.com")):
            return None          # third-party (ads / other licences)
        fid = hashlib.sha1(fi.image_url.encode()).hexdigest()[:16]
        dest = self.img_dir / f"{fid}{ext}"
        if dest.exists():
            data = dest.read_bytes()
        else:
            if self.bytes >= self.max_bytes:
                raise StopIteration("size cap reached")
            try:
                data = self._get(fi.image_url, binary=True, use_cache=False)
            except Exception as e:
                self.say(f"  image fail {fi.image_url}: {e}")
                self.last_reject = "fetch:" + str(e)[:60]
                return None
            if len(data) > 25 * 1024 * 1024:
                return None
        try:
            chk = ecg_image_check(data, fi.image_url, fi.alt)
        except Exception:
            self.last_reject = "decode"
            return None
        if not chk["is_ecg"]:
            self.last_reject = "check:" + chk.get("reject", "")
            if dest.exists():
                dest.unlink()
            return None
        if not dest.exists():
            dest.write_bytes(data)
            self.bytes += len(data)
        return dest, chk

    def page_records(self, pp: ParsedPage) -> tuple[list[dict], list[dict]]:
        recs, skipped = [], []
        author = " and ".join(pp.authors)
        attribution = f"Life in the Fast Lane (LITFL), {author + ', ' if author else ''}{pp.url}"
        for fi in pp.figures:
            got = self.fetch_image(fi)
            if not got:
                skipped.append({"image_url": fi.image_url, "alt": fi.alt, "reason": self.last_reject})
                continue
            dest, chk = got
            recs.append(build_record(pp, fi, dest.relative_to(self.dir).as_posix(), chk, attribution))
        return recs, skipped

    def run(self):
        queue: list[tuple[str, int]] = [(u, 0) for u in SEEDS]
        queued = {u for u, _ in queue}
        # resume: re-enqueue links from done pages
        for u, d in list(self.done.items()):
            if d.get("follow"):
                for l in d.get("links", []):
                    if l not in queued and self.wanted_link(l):
                        queued.add(l)
                        queue.append((l, d.get("depth", 0) + 1))
        n = 0
        while queue:
            url, depth = queue.pop(0)
            if url in self.done:
                continue
            if len(self.done) >= self.max_pages or self.bytes >= self.max_bytes:
                self.say("cap reached; stopping")
                break
            try:
                html = self._get(url)
            except PermissionError as e:
                self.say(f"skip (robots) {url}")
                self.done[url] = {"url": url, "error": "robots", "records": [], "links": []}
                self._append(self.done[url])
                continue
            except Exception as e:
                self.say(f"page fail {url}: {e}")
                self.done[url] = {"url": url, "error": str(e)[:200], "records": [], "links": []}
                self._append(self.done[url])
                continue
            pp = parse_page(html, url)
            follow = self.relevant(pp) and depth < 3
            try:
                recs, skipped = self.page_records(pp)
            except StopIteration:
                self.say("size cap reached")
                break
            d = {"url": url, "title": pp.title, "depth": depth, "follow": follow, "categories": pp.categories,
                 "links": pp.links if follow else [], "records": recs, "skipped": skipped, "n_figs": len(pp.figures)}
            self.done[url] = d
            self._append(d)
            n += 1
            self.say(f"[{len(self.done)} pages, q={len(queue)}, {self.bytes/1e6:.0f}MB] d{depth} {pp.title[:50]!r} "
                     f"figs={len(pp.figures)} ecg={len(recs)}")
            if follow:
                for l in pp.links:
                    if l not in queued and l not in self.done and self.wanted_link(l):
                        queued.add(l)
                        queue.append((l, depth + 1))

    def _append(self, d: dict):
        with self.pages_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def build_record(pp: ParsedPage, fi: FigureItem, rel_path: str, chk: dict, attribution: str) -> dict:
    slug = urlparse(pp.url).path.strip("/").replace("/", "_")
    rid = f"{slug}-{fi.figure_index:02d}-{hashlib.sha1(fi.image_url.encode()).hexdigest()[:6]}"
    cap_parts = []
    if fi.figcaption:
        cap_parts.append(fi.figcaption)
    if fi.after:
        cap_parts.append(fi.after)
    if not fi.after and fi.before:
        cap_parts.append(fi.before)
    caption = _clean(" ".join(cap_parts))
    if pp.answer:
        caption = _clean(caption + " | Answer: " + pp.answer[:3000])
    # labels: figure-specific text first, then topic (title/heading/tags)
    fig_text = " ".join([fi.figcaption, fi.alt, fi.after, fi.before, fi.heading])
    topic_text = " ".join([pp.title, " ".join(t.replace("-", " ") for t in pp.tags)])
    fig_labels = map_labels(fig_text)
    topic_labels = map_labels(topic_text)
    labels = list(dict.fromkeys(topic_labels + fig_labels))
    return {
        "id": rid, "source": SOURCE, "modality": "ECG", "kind": "image", "path": rel_path, "url": pp.url,
        "license": LICENSE, "attribution": attribution, "caption": caption, "labels": labels,
        "view": None, "group": slug,
        "extra": {"page_title": pp.title, "topic": pp.title, "heading": fi.heading, "figure_index": fi.figure_index,
                  "image_size": [chk["width"], chk["height"]], "image_url": fi.image_url, "alt": fi.alt,
                  "figcaption": fi.figcaption, "categories": pp.categories, "tags": pp.tags,
                  "answer": pp.answer[:3000], "authors": pp.authors, "ecg_check": chk,
                  "label_sources": {"topic": topic_labels, "figure": fig_labels}},
    }


def rebuild_manifest(crawler: Optional[Crawler] = None) -> Path:
    c = crawler or Crawler()
    records: list[Record] = []
    seen_ids: set[str] = set()
    for d in c.done.values():
        for r in d.get("records", []):
            if r["id"] in seen_ids:
                continue
            seen_ids.add(r["id"])
            records.append(Record(**r))
    for r in records:
        text = " ".join([r.caption, r.extra.get("page_title", "")])
        r.quality.update(score_caption(text, "ECG"))
        r.quality["has_label"] = bool(r.labels)
    dedupe(records, c.dir)
    return write_manifest(SOURCE, records)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=3000)
    ap.add_argument("--max-gb", type=float, default=2.0)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--rebuild-only", action="store_true")
    a = ap.parse_args(argv)
    c = Crawler(a.max_pages, int(a.max_gb * 1024 ** 3), a.delay)
    if not a.rebuild_only:
        c.run()
    p = rebuild_manifest(c)
    print("manifest:", p)


if __name__ == "__main__":
    main()
