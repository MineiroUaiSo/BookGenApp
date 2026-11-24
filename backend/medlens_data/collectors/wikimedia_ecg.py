"""Wikimedia Commons ECG collector (MediaWiki API, free licences only).

Usage:  python -m medlens_data.collectors.wikimedia_ecg [--max-files N] [--depth 3]
Output: data/datasets/wikimedia_ecg/{images/, manifest.jsonl, rejects.jsonl}
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path

from medlens_data import (USER_AGENT, PoliteSession, Record, dedupe, score_caption, source_dir, write_manifest)

SOURCE = "wikimedia_ecg"
API = "https://commons.wikimedia.org/w/api.php"
ROOTS = ["Category:ECG", "Category:ECG graphs", "Category:ECG entities", "Category:ECG of cardiomyopathies",
         "Category:ECG of pericarditis", "Category:ECG of hyperkalemia", "Category:ECG of hypokalemia",
         "Category:ECG of hypocalcemia", "Category:ECG of bradycardia", "Category:ECG of tachycardias",
         "Category:ECG of pacemakers", "Category:ECG of asystole", "Category:Brugada syndrome",
         "Category:Wellens' syndrome", "Category:Benign early repolarization", "Category:QT interval",
         "Category:Media from CardioNetworks ECGpedia", "Category:Normal ECG graphs",
         "Category:Electrocardiography", "Category:Atrial fibrillation", "Category:Myocardial infarction",
         "Category:Bundle branch block", "Category:Wolff-Parkinson-White syndrome", "Category:Atrial flutter",
         "Category:Ventricular tachycardia", "Category:Long QT syndrome", "Category:Heart block"]
SKIP_CAT = re.compile(r"diagram|schem|cartoon|illustrat|drawing|machine|device|equipment|electrode|lead placement|"
                      r"animation|logo|history|people|art\b|stamps|monitor|defibrillat|pacemaker|software|"
                      r"vectorcardiograph|ecg waves|svg|icons|posters|books|publications|echocardiograph|holter|"
                      r"principle|paper|stamps|videos|performing|stress|catheter|surgery|anatomy|physiology|"
                      r"smartwatch|wearable|veterinar|dog|horse|cat\b|animal", re.I)
BAD_TEXT = re.compile(r"diagram|schematic|cartoon|illustration|drawing|simulat|artist'?s|vector graphic|"
                      r"animation|logo|icon\b|model of|\bmap\b|photograph of (a )?(patient|device|machine)|"
                      r"electrode placement|lead placement|synthetic|generated|mockup", re.I)
FREE_OK = re.compile(r"^(cc0|public domain|pd\b|pd-|no restrictions|cc[- ]by(?![- ]?(nc|nd))|cc[- ]by[- ]sa|"
                     r"gfdl|attribution)", re.I)
KEEP_CAT = re.compile(r"ecg|ekg|electrocardiogra|arrhythm|fibrillation|flutter|block|tachycardia|bradycardia|"
                      r"infarct|brugada|\bqt\b|wpw|wolff|ventricular|atrial|pericarditis|hypertroph|ischa?emi|"
                      r"hyperkal|hypokal|hypocalc|cardiomyopath|syndrome|rhythm|extrasystol|repolari|pacing|paced", re.I)
MIN_W = 1000
MAX_W = 3000

# keyword -> label (checked on lowercased caption + categories)
LABEL_MAP: list[tuple[str, str]] = [
    (r"atrial fibrillation|a-?fib|fibrilação atrial", "ecg.atrial_fibrillation"),
    (r"atrial flutter", "ecg.atrial_flutter"),
    (r"first[- ]degree.{0,12}(av|atrioventricular)|1st[- ]degree.{0,12}(av|block)|av block.{0,6}(1|i)\b|prolonged pr", "ecg.av_block_1"),
    (r"second[- ]degree|mobitz|wenckebach", "ecg.av_block_2"),
    (r"third[- ]degree|complete (heart|av|atrioventricular) block|complete block", "ecg.av_block_3"),
    (r"left bundle[- ]branch block|\blbbb\b", "ecg.lbbb"),
    (r"right bundle[- ]branch block|\brbbb\b", "ecg.rbbb"),
    (r"left anterior (fascicular )?hemiblock|left anterior fascicular", "ecg.lafb"),
    (r"left posterior (fascicular )?hemiblock|left posterior fascicular", "ecg.lpfb"),
    (r"left ventricular hypertrophy|\blvh\b", "ecg.lvh"),
    (r"right ventricular hypertrophy|\brvh\b", "ecg.rvh"),
    (r"left atrial (enlargement|abnormality)", "ecg.lae"),
    (r"right atrial (enlargement|abnormality)|p pulmonale", "ecg.rae"),
    (r"sinus bradycardia", "ecg.sinus_bradycardia"),
    (r"sinus tachycardia", "ecg.sinus_tachycardia"),
    (r"wolff[- ]parkinson|\bwpw\b|pre-?excitation", "ecg.preexcitation"),
    (r"long qt|prolonged qt|qt prolongation", "ecg.long_qt"),
    (r"short qt", "ecg.short_qt"),
    (r"brugada", "ecg.brugada"),
    (r"ventricular tachycardia", "ecg.ventricular_tachycardia"),
    (r"ventricular fibrillation|torsades", "ecg.ventricular_fibrillation"),
    (r"supraventricular tachycardia|\bsvt\b|avnrt", "ecg.svt"),
    (r"premature ventricular|\bpvcs?\b|ventricular extrasystole|ventricular ectopic", "ecg.pvc"),
    (r"premature atrial|\bpacs?\b", "ecg.pac"),
    (r"pericarditis", "ecg.pericarditis"),
    (r"hyperkal(a)?emia", "ecg.hyperkalemia"),
    (r"hypokal(a)?emia", "ecg.hypokalemia"),
    (r"pulmonary embol", "ecg.pulmonary_embolism"),
    (r"paced|pacemaker rhythm", "ecg.paced"),
    (r"stemi|st[- ]elevation|acute myocardial infarction|myocardial infarction|heart attack|infarct", "ecg.st_elevation"),
    (r"st[- ]depression|ischa?emia", "ecg.st_depression"),
    (r"t[- ]wave inversion|inverted t", "ecg.t_inversion"),
    (r"pathologic(al)? q|q[- ]wave", "ecg.pathologic_q"),
    (r"low voltage", "ecg.low_voltage"),
    (r"normal (sinus rhythm|ecg|electrocardiogram)|sinus rhythm", "ecg.sinus_rhythm"),
]


def strip_html(s: str) -> str:
    s = re.sub(r"<(script|style).*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def licence_free(short: str) -> bool:
    return bool(short) and bool(FREE_OK.match(short.strip()))


def extract_labels(text: str) -> list[str]:
    t = (text or "").lower()
    out: list[str] = []
    for pat, lab in LABEL_MAP:
        if re.search(pat, t) and lab not in out:
            out.append(lab)
    # sinus_rhythm label would be wrong when a pathology label is present
    if len(out) > 1 and "ecg.sinus_rhythm" in out and not re.search(r"normal", t):
        out.remove("ecg.sinus_rhythm")
    return out


def record_from_imageinfo(page: dict, local_path: str = "") -> tuple[Record | None, str]:
    """Map one API page (with imageinfo+extmetadata) to a Record; returns (record|None, reject_reason)."""
    ii = (page.get("imageinfo") or [None])[0]
    if not ii:
        return None, "no_imageinfo"
    title = page.get("title", "")
    md = ii.get("extmetadata") or {}
    g = lambda k: (md.get(k) or {}).get("value", "")
    lic = g("LicenseShortName")
    if not licence_free(lic):
        return None, f"licence:{lic or 'none'}"
    mime = ii.get("mime", "")
    if mime not in ("image/jpeg", "image/png"):
        return None, f"mime:{mime}"
    if (ii.get("width") or 0) < MIN_W:
        return None, "too_small"
    cats = [c.strip() for c in g("Categories").split("|") if c.strip()]
    desc = strip_html(g("ImageDescription"))
    if BAD_TEXT.search(title + " " + desc) or any(SKIP_CAT.search(c) for c in cats):
        return None, "diagram_like_text"
    artist = strip_html(g("Artist"))
    caption = desc
    if cats:
        caption = (caption + " [Categories: " + "; ".join(cats) + "]").strip()
    labels = extract_labels(desc + " " + title.replace("_", " ") + " " + " ".join(cats))
    pageid = page.get("pageid")
    rec = Record(
        id=f"wm{pageid}", source=SOURCE, modality="ECG", kind="image", path=local_path,
        url=ii.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
        license=lic + (f" ({g('LicenseUrl')})" if g("LicenseUrl") else ""),
        attribution=(artist or "unknown author") + " / Wikimedia Commons" + (f" - {g('Credit')}" if False else ""),
        caption=caption, labels=labels, view=None, group=None,
        extra={"title": title, "width": ii.get("width"), "height": ii.get("height"), "mime": mime,
               "original_url": ii.get("url"), "categories": cats, "date": g("DateTimeOriginal")},
    )
    rec.quality.update(score_caption(caption, "ECG"))
    return rec, ""


def image_check(path: Path) -> dict:
    """Heuristic: does the raster look like a real ECG tracing (grid colour + thin dark line density)?"""
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGB")
    im.thumbnail((800, 800))
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    sat = (mx - mn)
    grid = ((r > g + 15) & (r >= b) & (mx > 150) & (sat > 20) & (sat < 140)).mean()  # pink/red grid
    dark = (mx < 90).mean()
    w, h = im.size
    # fraction of columns containing dark pixels (a trace spans the width)
    cols = ((mx < 90).any(0)).mean()
    ok = bool((grid > 0.12 and dark > 0.003 and cols > 0.5) or (dark > 0.004 and dark < 0.12 and cols > 0.8 and w / h > 1.2))
    return {"grid_frac": round(float(grid), 3), "dark_frac": round(float(dark), 4), "col_cover": round(float(cols), 3),
            "ecg_like": ok}


class Crawler:
    def __init__(self, out: Path):
        self.out = out
        # The MediaWiki API is governed by the Wikimedia API etiquette (UA, maxlag, rate limits), not by the
        # HTML-crawler robots.txt (which disallows /w/); so robots is not applied to api.php, only to file hosts.
        self.api_ps = PoliteSession(delay_s=1.2, cache_dir=out / "_cache", respect_robots=False)
        self.ps = PoliteSession(delay_s=1.2, cache_dir=out / "_cache")

    def api(self, **params):
        import hashlib
        params.update(action="query", format="json", maxlag=5)
        ck = self.out / "_apicache" / (hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest() + ".json")
        ck.parent.mkdir(exist_ok=True)
        if ck.exists():
            return json.loads(ck.read_text())
        import requests
        if not hasattr(self, "_rs"):
            self._rs = requests.Session()
            self._rs.headers["User-Agent"] = USER_AGENT
            self._last = 0.0
        for attempt in range(300):
            time.sleep(max(0.0, 2.0 - (time.time() - self._last)))
            try:
                r = self._rs.get(API, params=params, timeout=60)
            except Exception as e:
                print(f"  api net error: {str(e)[:80]}", flush=True)
                time.sleep(20)
                continue
            self._last = time.time()
            if r.status_code == 429 or r.status_code >= 500:
                print(f"  http {r.status_code}, wait", flush=True)
                wait = min(60, float(r.headers.get("retry-after", 15)) + 2)
                time.sleep(wait)
                continue
            txt = r.text
            try:
                d = json.loads(txt)
            except Exception:
                time.sleep(20)
                continue
            if d.get("error", {}).get("code") == "maxlag":
                time.sleep(10)
                continue
            ck.write_text(txt)
            return d
        raise RuntimeError("API unavailable")

    def download(self, url: str) -> bytes:
        """File download honouring Retry-After (upload.wikimedia.org throttles shared IPs hard: 600 s)."""
        import requests
        if not hasattr(self, "_ds"):
            self._ds = requests.Session()
            self._ds.headers["User-Agent"] = USER_AGENT
            self._dlast = 0.0
        for attempt in range(30):
            time.sleep(max(0.0, 3.0 - (time.time() - self._dlast)))
            try:
                r = self._ds.get(url, timeout=120)
            except Exception as e:
                print(f"  download net error: {str(e)[:80]}", flush=True)
                time.sleep(30)
                continue
            self._dlast = time.time()
            if r.status_code == 429 or r.status_code >= 500:
                wait = min(900, float(r.headers.get("retry-after", 60)) + 5)
                print(f"  download http {r.status_code}, waiting {wait:.0f}s", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.content
        raise RuntimeError("download throttled")

    def members(self, cat: str, cmtype: str) -> list[dict]:
        res, cont = [], {}
        while True:
            d = self.api(list="categorymembers", cmtitle=cat, cmtype=cmtype, cmlimit="500", **cont)
            res += d.get("query", {}).get("categorymembers", [])
            if "continue" in d:
                cont = {"cmcontinue": d["continue"]["cmcontinue"]}
            else:
                return res

    def walk(self, roots: list[str], depth: int) -> dict[str, int]:
        files: dict[str, int] = {}
        seen = set()
        frontier = [(c, 0) for c in roots]
        while frontier:
            cat, dep = frontier.pop(0)
            if cat in seen:
                continue
            seen.add(cat)
            for m in self.members(cat, "file"):
                files[m["title"]] = m["pageid"]
            if dep < depth:
                for sc in self.members(cat, "subcat"):
                    if not SKIP_CAT.search(sc["title"]) and KEEP_CAT.search(sc["title"]):
                        frontier.append((sc["title"], dep + 1))
            print(f"cat {cat} d{dep}: files={len(files)} queue={len(frontier)}", flush=True)
        (self.out / "categories_seen.json").write_text(json.dumps(sorted(seen), indent=0))
        return files

    def imageinfos(self, titles: list[str]):
        for i in range(0, len(titles), 50):
            chunk = titles[i:i + 50]
            d = self.api(titles="|".join(chunk), prop="imageinfo", iiprop="url|size|mime|extmetadata")
            print(f"  imageinfo chunk {i // 50}", flush=True)
            for p in d.get("query", {}).get("pages", {}).values():
                yield p


def run(max_files: int | None = None, depth: int = 3, metadata_only: bool = False) -> None:
    """Phase 1: walk categories + imageinfo -> manifest (path empty, extra.download='pending').
    Phase 2 (unless metadata_only): download_pending()."""
    out = source_dir(SOURCE)
    (out / "images").mkdir(exist_ok=True)
    cr = Crawler(out)
    files = cr.walk(ROOTS, depth)
    titles = sorted(files)[: max_files or None]
    print(f"{len(titles)} candidate files", flush=True)
    recs: list[Record] = []
    why_count: dict[str, int] = {}
    n = 0
    for page in cr.imageinfos(titles):
        n += 1
        rec, why = record_from_imageinfo(page)
        if rec is None:
            k = why.split(":")[0] if not why.startswith("licence") else "licence"
            why_count[k] = why_count.get(k, 0) + 1
            continue
        rec.extra["download"] = "pending"
        recs.append(rec)
    (out / "reject_counts.json").write_text(json.dumps({"seen": n, "kept_metadata": len(recs), "rejected": why_count}))
    write_manifest(SOURCE, recs)
    print(f"METADATA kept={len(recs)} of {n} rejects={why_count}", flush=True)
    if not metadata_only:
        download_pending()


def download_pending(limit: int | None = None) -> None:
    """Download images for manifest records still pending; image check; dedupe; rewrite manifest.
    Records failing the image check are kept but flagged quality.image_check.ecg_like=False and file removed."""
    from medlens_data import read_manifest
    out = source_dir(SOURCE)
    (out / "images").mkdir(exist_ok=True)
    cr = Crawler(out)
    recs = list(read_manifest(SOURCE))
    done = 0
    for rec in recs:
        if rec.extra.get("download") != "pending":
            continue
        if limit and done >= limit:
            break
        title = rec.extra["title"]
        w = rec.extra.get("width") or 0
        url, big = rec.extra.get("original_url"), False
        try:
            if w > MAX_W:  # huge original: ask for a 3000 px rendition instead
                t = cr.api(titles=title, prop="imageinfo", iiprop="url", iiurlwidth=str(MAX_W))
                tu = (next(iter(t["query"]["pages"].values())).get("imageinfo") or [{}])[0].get("thumburl")
                if tu:
                    big, url = True, tu
            ext = ".png" if url.lower().split("?")[0].endswith(".png") else ".jpg"
            rel = f"images/{rec.id}{ext}"
            (out / rel).write_bytes(cr.download(url))
            chk = image_check(out / rel)
        except Exception as e:
            rec.extra["download"] = f"failed: {str(e)[:80]}"
            continue
        rec.quality["image_check"] = chk
        rec.extra["downloaded_thumb"] = big
        if chk["ecg_like"]:
            rec.path, rec.extra["download"] = rel, "ok"
        else:
            (out / rel).unlink(missing_ok=True)
            rec.extra["download"] = "rejected_image_check"
        done += 1
        if done % 20 == 0:
            print(f"  downloaded {done}", flush=True)
            write_manifest(SOURCE, recs)
    dedupe([r for r in recs if r.path], out)
    write_manifest(SOURCE, recs)
    print(f"DONE downloaded={done}", flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-files", type=int, default=None)
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--metadata-only", action="store_true")
    ap.add_argument("--download-only", action="store_true", help="resume downloads for pending manifest records")
    a = ap.parse_args()
    if a.download_only:
        download_pending()
    else:
        run(a.max_files, a.depth, a.metadata_only)
