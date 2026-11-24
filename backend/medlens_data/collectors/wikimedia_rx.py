"""Wikimedia Commons radiographs (free licences only) with the file description as caption, through the same sieve.

MediaWiki API: categorymembers (BFS, depth <= 3 from the seed categories) -> imageinfo/extmetadata (description,
licence, author) -> caption pre-sieve -> download 1280 px rendition from upload.wikimedia.org -> image sieve.

Resumable (<source>/_files.jsonl).   python -m medlens_data.collectors.wikimedia_rx --max-files 3000
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import deque
from pathlib import Path
from urllib.parse import quote

from .. import PoliteSession, Record, license_ok, source_dir, write_manifest
from ..sieve_rx import Candidate, SieveStats, figure_caption_sieve, finalize_dedupe, sieve_candidate, summarize

SOURCE = "wikimedia_rx"
API = "https://commons.wikimedia.org/w/api.php"
SEEDS = ["X-rays of the chest", "Chest radiographs", "X-rays", "Projectional radiography", "Radiographs of fractures",
         "X-rays of fractures", "Radiography", "X-rays of the abdomen", "Abdominal radiographs", "X-rays of the thorax", "Plain radiography",
         "Medical X-rays", "X-ray images of the chest", "Skeletal radiographs", "Radiographs of the hand",
         "Radiographs of the pelvis", "Radiographs of the spine"]
MAX_DEPTH = 3
SKIP_CAT = re.compile(r"crystallograph|astronom|telescope|airport|security|baggage|dental equipment|machines?$|"
                      r"tubes?$|diffraction|synchrotron|spectro|fluorescence|history|portraits?|people|cartoon|"
                      r"drawings?|diagrams?|logos?|paintings?|mammograph|ct scans|mri|ultrasound|animals|dogs|cats|"
                      r"birds|fish|veterinary|horses", re.I)
SESSION = None      # files (upload.wikimedia.org): robots.txt respected
API_SESSION = None  # MediaWiki Action API: documented bot interface (API:Etiquette); robots.txt only covers web crawlers (/w/ is disallowed)


def api(params: dict) -> dict:
    q = "&".join(f"{k}={quote(str(v), safe='|')}" for k, v in params.items())
    return json.loads(API_SESSION.get(f"{API}?{q}&format=json&formatversion=2", use_cache=True))


def walk(seeds, max_files: int):
    """Yield file titles (BFS over subcategories)."""
    seen_cat, seen_file = set(), set()
    dq = deque((f"Category:{s}", 0) for s in seeds)
    while dq:
        cat, d = dq.popleft()
        if cat in seen_cat:
            continue
        seen_cat.add(cat)
        cont = None
        while True:
            p = {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmlimit": 500, "cmtype": "subcat|file"}
            if cont:
                p["cmcontinue"] = cont
            try:
                data = api(p)
            except Exception as e:
                print("category error", cat, e, flush=True)
                break
            for m in data.get("query", {}).get("categorymembers", []):
                if m["ns"] == 14 and d < MAX_DEPTH and not SKIP_CAT.search(m["title"]):
                    dq.append((m["title"], d + 1))
                elif m["ns"] == 6 and m["title"] not in seen_file and re.search(r"\.(jpe?g|png|tiff?)$", m["title"], re.I):
                    seen_file.add(m["title"])
                    yield m["title"], cat
                    if len(seen_file) >= max_files:
                        return
            cont = data.get("continue", {}).get("cmcontinue")
            if not cont:
                break


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def imageinfo(titles: list[str]) -> list[dict]:
    d = api({"action": "query", "titles": "|".join(titles), "prop": "imageinfo",
             "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1280,
             "iiextmetadatafilter": "ImageDescription|LicenseShortName|LicenseUrl|Artist|Credit|ObjectName"})
    out = []
    for p in d.get("query", {}).get("pages", []):
        ii = (p.get("imageinfo") or [None])[0]
        if ii:
            out.append({"title": p["title"], "ii": ii})
    return out


def run(max_files: int):
    global SESSION, API_SESSION
    out_dir = source_dir(SOURCE)
    SESSION = PoliteSession(delay_s=1.2, cache_dir=out_dir / "_cache")
    API_SESSION = PoliteSession(delay_s=1.2, cache_dir=out_dir / "_cache", respect_robots=False)
    state = out_dir / "_files.jsonl"
    done = {}
    if state.exists():
        for line in state.open(encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                done[d["title"]] = d
    print("resuming", len(done), flush=True)
    stats = SieveStats()
    buf: list[tuple[str, str]] = []

    def flush(buf):
        todo = [(t, c) for t, c in buf if t not in done]
        if not todo:
            return
        cats = dict(todo)
        try:
            infos = imageinfo([t for t, _ in todo])
        except Exception as e:
            print("imageinfo error", e, flush=True)
            return
        got = set()
        for it in infos:
            t, ii = it["title"], it["ii"]
            got.add(t)
            res = {"title": t, "records": [], "stats": None}
            st = SieveStats()
            md = {k: v.get("value", "") if isinstance(v, dict) else v for k, v in (ii.get("extmetadata") or {}).items()}
            lic = md.get("LicenseShortName", "")
            desc = strip_html(md.get("ImageDescription", ""))
            st.seen = 1
            if not (license_ok(lic) or lic.lower().startswith("pd")):
                st.reject("licence:not_free")
            elif ii.get("mime") not in ("image/jpeg", "image/png", "image/tiff"):
                st.reject("image:mime")
            elif not figure_caption_sieve(desc)["ok"]:
                st.reject("caption:" + figure_caption_sieve(desc)["reason"])
            else:
                url = ii.get("thumburl") or ii["url"]
                try:
                    data = SESSION.get(url, binary=True, use_cache=False, timeout=90)
                    ext = "jpg" if ii.get("mime") == "image/jpeg" else "png"
                    fid = re.sub(r"[^A-Za-z0-9]+", "_", t[5:])[:80] + f"_{ii.get('width', 0)}"
                    cand = Candidate(id=fid, caption=desc, image_bytes=data, ext=ext,
                                     url=ii.get("descriptionurl") or ii["url"], license=lic,
                                     attribution=f'{strip_html(md.get("Artist", ""))} / {strip_html(md.get("Credit", ""))} / Wikimedia Commons / {lic}'[:500],
                                     extra={"commons_title": t, "license_url": md.get("LicenseUrl", ""), "category": cats.get(t, ""),
                                            "orig_url": ii["url"], "orig_size": [ii.get("width"), ii.get("height")]})
                    for r in sieve_candidate(cand, out_dir, SOURCE, st):
                        res["records"].append(json.loads(r.to_json()))
                except Exception as e:
                    st.reject("image:download_error")
            res["stats"] = {"seen": st.seen, "reasons": dict(st.reasons)}
            done[t] = res
            with state.open("a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
        print(f"files={len(done)} kept={sum(len(d['records']) for d in done.values())}", flush=True)

    for title, cat in walk(SEEDS, max_files):
        if title in done:
            continue
        buf.append((title, cat))
        if len(buf) >= 40:
            flush(buf)
            buf = []
    flush(buf)
    finalize(out_dir)


def finalize(out_dir: Path):
    recs = []
    rej = SieveStats()
    for line in (out_dir / "_files.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        rej.seen += d["stats"]["seen"]
        rej.reasons.update(d["stats"]["reasons"])
        for r in d["records"]:
            if (out_dir / r["path"]).exists():
                recs.append(Record(**r))
    st = SieveStats()
    st.seen = st.kept = len(recs)
    recs = finalize_dedupe(recs, out_dir, st)
    write_manifest(SOURCE, recs)
    allrej = rej.reasons + st.reasons
    summ = summarize(recs)
    summ.update(files_seen=rej.seen, rejected_total=sum(allrej.values()), rejected_by_reason=dict(allrej.most_common()))
    (out_dir / "sieve_summary.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False))
    print(json.dumps(summ, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-files", type=int, default=3000)
    ap.add_argument("--finalize-only", action="store_true")
    a = ap.parse_args()
    if a.finalize_only:
        finalize(source_dir(SOURCE))
    else:
        run(a.max_files)
