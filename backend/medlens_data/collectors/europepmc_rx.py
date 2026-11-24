"""Europe PMC open-access figures -> captioned plain radiographs ("peneira").

Pipeline per article:  Europe PMC search (OPEN_ACCESS, CC BY / CC0)  ->  fullTextXML (captions, licence, metadata)
  ->  caption pre-sieve  ->  figure image from the PMC Open Access bucket on AWS (s3://pmc-oa-opendata, public, same
  files as PMC, key = <PMCID>.<ver>/<xlink:href>)  ->  image sieve (sieve_rx)  ->  Record.

Why S3 and not europepmc.org/articles/PMCxxx/bin/...: europepmc.org sits behind a Cloudflare challenge for automated
clients (HTTP 403), and ncbi/pmc hosts are not reachable from the sandbox. The AWS Open Data copy is the documented bulk route.

Resumable: every processed article is appended to <source>/_articles.jsonl; rerun continues.

  python -m medlens_data.collectors.europepmc_rx --target 3000 [--max-articles 6000]
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import quote

from .. import PoliteSession, Record, license_ok, read_manifest, source_dir, write_manifest, DATA_ROOT
from ..sieve_rx import (Candidate, SieveStats, figure_caption_sieve, finalize_dedupe, sieve_candidate, summarize)

SOURCE = "europepmc_rx"
EBI = "https://www.ebi.ac.uk/europepmc/webservices/rest"
S3 = "https://pmc-oa-opendata.s3.amazonaws.com"
XLINK = "{http://www.w3.org/1999/xlink}href"

TERMS = ('"chest radiograph" OR "chest x-ray" OR "plain radiograph" OR "abdominal radiograph" OR "lateral radiograph" '
         'OR "chest radiography" OR "plain film" OR "abdominal x-ray" OR "pelvic radiograph" OR "radiograph of the" '
         'OR "radiographs showed" OR "plain x-ray"')
LIC = 'OPEN_ACCESS:y AND (LICENSE:"cc by" OR LICENSE:"cc0")'
QUERIES = [  # case reports first
    f'({TERMS}) AND {LIC} AND PUB_TYPE:"case reports"',
    f'({TERMS}) AND {LIC}',
]


class Hosts:
    """One HTTP session, but a lock per host so threads never exceed the polite rate."""

    def __init__(self, cache_dir: Path, s3_delay: float = 0.25):
        # EBI: 1 s between requests. S3 open-data bucket (built for bulk access, no robots/ToS limit): 0.25 s.
        self.sessions = {"ebi": PoliteSession(delay_s=1.0, cache_dir=cache_dir),
                         "s3": PoliteSession(delay_s=s3_delay, cache_dir=cache_dir)}
        self.locks = {}
        self.g = threading.Lock()

    def get(self, url, **kw):
        from urllib.parse import urlparse
        h = urlparse(url).netloc
        with self.g:
            lk = self.locks.setdefault(h, threading.Lock())
        with lk:
            return self.sessions["s3" if "amazonaws" in h else "ebi"].get(url, **kw)


def search_pmcids(hosts: Hosts, query: str, page_size: int = 500) -> Iterator[str]:
    cursor = "*"
    while True:
        url = (f"{EBI}/search?query={quote(query)}&format=json&resultType=lite&pageSize={page_size}"
               f"&cursorMark={quote(cursor)}&sort=P_PDATE_D%20desc")
        d = json.loads(hosts.get(url, use_cache=True))
        for r in d["resultList"]["result"]:
            if r.get("pmcid"):
                yield r["pmcid"]
        nxt = d.get("nextCursorMark")
        if not nxt or nxt == cursor or not d["resultList"]["result"]:
            return
        cursor = nxt


def _text(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def licence_name(root) -> tuple[str, str]:
    """(short name, url) from <license xlink:href=...>."""
    for lic in root.iter("license"):
        href = lic.get(XLINK) or ""
        if not href:
            for ext in lic.iter("ext-link"):
                href = ext.get(XLINK) or ""
                if href:
                    break
        m = re.search(r"creativecommons\.org/(licenses|publicdomain)/([a-z\-]+)/([\d.]+)", href)
        if m:
            kind, v, ver = m.groups()
            if kind == "publicdomain" or v in ("zero", "mark"):
                return f"CC0 {ver}" if v == "zero" else "Public domain", href
            return f"CC {v.upper()} {ver}", href
        txt = _text(lic).lower()
        if "cc0" in txt or "public domain" in txt:
            return "CC0", href
        m = re.search(r"cc[ -]by(?:[ -](?:nc|nd|sa))*(?:[ -](?:nc|nd|sa))*", txt)
        if m:
            return m.group(0).upper().replace(" ", "-").replace("CC-BY", "CC BY"), href
    return "", ""


def parse_article(xml: str) -> Optional[dict]:
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    lic, lic_url = licence_name(root)
    meta = root.find(".//article-meta")
    title = _text(meta.find(".//article-title")) if meta is not None else ""
    journal = _text(root.find(".//journal-title"))
    year = ""
    for pd in root.iter("pub-date"):
        y = pd.find("year")
        if y is not None and y.text:
            year = y.text
            break
    doi = ""
    for aid in root.iter("article-id"):
        if aid.get("pub-id-type") == "doi":
            doi = (aid.text or "").strip()
    authors = [_text(sn) for sn in root.findall(".//contrib-group/contrib/name/surname")][:3]
    pubtype = root.get("article-type", "")
    figs = []
    for fg in root.iter("fig"):
        gr = fg.find(".//graphic")
        if gr is None or not gr.get(XLINK):
            continue
        cap = fg.find("caption")
        figs.append({"fig_id": fg.get("id") or "", "label": _text(fg.find("label")),
                     "caption": _text(cap), "href": gr.get(XLINK)})
    return {"license": lic, "license_url": lic_url, "title": title, "journal": journal, "year": year,
            "doi": doi, "authors": authors, "article_type": pubtype, "figs": figs}


def s3_keys(hosts: Hosts, pmcid: str) -> tuple[dict[str, str], Optional[str]]:
    """(basename-without-extension -> S3 key for the article's figures, key of the JATS xml)."""
    xml = hosts.get(f"{S3}/?list-type=2&max-keys=200&prefix={pmcid}.", use_cache=False)
    keys = re.findall(r"<Key>([^<]+)</Key>", xml)
    out, xml_key = {}, None
    for k in sorted(keys):  # later versions override earlier
        base = k.split("/", 1)[-1]
        if re.search(r"\.(jpe?g|png|webp|gif|tiff?)$", base, re.I):
            out[re.sub(r"\.[A-Za-z0-9]+$", "", base)] = k
        elif base.endswith(".xml"):
            xml_key = k
    return out, xml_key


def process_article(hosts: Hosts, pmcid: str, out_dir: Path, gstats: SieveStats) -> dict:
    stats = SieveStats()
    res = {"pmcid": pmcid, "records": [], "note": "", "stats": None}
    try:
        _process(hosts, pmcid, out_dir, stats, res)
    finally:
        res["stats"] = {"seen": stats.seen, "reasons": dict(stats.reasons)}
        gstats.seen += stats.seen
        gstats.reasons.update(stats.reasons)
    return res


def _process(hosts, pmcid, out_dir, stats, res):
    keys = None
    try:
        try:   # version .1 is by far the most common: skip the bucket listing unless the article is promising
            xml = hosts.get(f"{S3}/{pmcid}.1/{pmcid}.1.xml", use_cache=True)
        except Exception:
            keys, xml_key = s3_keys(hosts, pmcid)
            xml = hosts.get(f"{S3}/{quote(xml_key)}", use_cache=True) if xml_key else \
                hosts.get(f"{EBI}/{pmcid}/fullTextXML", use_cache=True)
    except Exception as e:
        res["note"] = f"xml_error:{type(e).__name__}"
        return
    art = parse_article(xml)
    if not art:
        res["note"] = "xml_parse_error"
        return
    if not license_ok(art["license"]):
        res["note"] = "licence:" + (art["license"] or "unknown")
        return
    pre = [f for f in art["figs"] if figure_caption_sieve(f["caption"])["ok"]]
    res["n_figs"], res["n_pre"] = len(art["figs"]), len(pre)
    # figures that fail the caption sieve are counted without downloading anything
    for f in art["figs"]:
        if f not in pre:
            stats.seen += 1
            stats.reject("caption:" + figure_caption_sieve(f["caption"])["reason"])
    if not pre:
        return
    if keys is None:
        try:
            keys, _ = s3_keys(hosts, pmcid)
        except Exception as e:
            res["note"] = f"s3_list_error:{type(e).__name__}"
            return
    attrib = (f'{", ".join(art["authors"])} et al. ({art["year"]}) "{art["title"]}". {art["journal"]}. '
              f'doi:{art["doi"]}. {art["license"]}')
    for f in pre:
        base = re.sub(r"\.[A-Za-z0-9]+$", "", f["href"])
        key = keys.get(base) or keys.get(f["href"])
        if not key:
            stats.seen += 1
            stats.reject("image:not_in_bucket")
            continue
        try:
            data = hosts.get(f"{S3}/{quote(key)}", binary=True, use_cache=False)
        except Exception:
            stats.seen += 1
            stats.reject("image:download_error")
            continue
        ext = key.rsplit(".", 1)[-1].lower()
        cand = Candidate(id=f"{pmcid}_{re.sub(r'[^A-Za-z0-9]+', '', f['fig_id'] or base)[-40:]}", caption=f["caption"],
                         image_bytes=data, ext=ext,
                         url=f"https://europepmc.org/article/PMC/{pmcid}#{f['fig_id']}",
                         license=art["license"], attribution=attrib,
                         extra={"pmcid": pmcid, "doi": art["doi"], "fig_label": f["label"], "journal": art["journal"],
                                "year": art["year"], "article_title": art["title"], "license_url": art["license_url"],
                                "article_type": art["article_type"], "group": pmcid, "s3_key": key})
        for r in sieve_candidate(cand, out_dir, SOURCE, stats):
            res["records"].append(json.loads(r.to_json()))



def run(target: int, max_articles: int, workers: int = 3):
    out_dir = source_dir(SOURCE)
    state = out_dir / "_articles.jsonl"
    done: dict[str, dict] = {}
    if state.exists():
        for line in state.open(encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                done[d["pmcid"]] = d
    hosts = Hosts(out_dir / "_cache")
    stats = SieveStats()
    kept = sum(len(d["records"]) for d in done.values())
    lock = threading.Lock()
    seen_ids = set(done)
    print(f"resuming with {len(done)} articles, {kept} figures", flush=True)

    def work(pmcid):
        nonlocal kept
        if kept >= target:
            return
        r = process_article(hosts, pmcid, out_dir, stats)
        with lock:
            kept += len(r["records"])
            with state.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            done[pmcid] = r
            if len(done) % 25 == 0:
                print(f"articles={len(done)} kept_figs={kept} stats={stats.as_dict()['reasons']}", flush=True)

    def ids():
        n = 0
        for q in QUERIES:
            for pm in search_pmcids(hosts, q):
                if pm in seen_ids:
                    continue
                seen_ids.add(pm)
                yield pm
                n += 1
                if n >= max_articles or kept >= target:
                    return

    with ThreadPoolExecutor(workers) as ex:
        batch = []
        for pm in ids():
            batch.append(ex.submit(work, pm))
            if len(batch) >= workers * 4:
                for b in batch:
                    b.result()
                batch = []
        for b in batch:
            b.result()
    finalize(out_dir)


def finalize(out_dir: Path):
    """Rebuild manifest from _articles.jsonl, corpus-level dedupe, write stats."""
    recs, notes = [], {}
    st = SieveStats()
    for line in (out_dir / "_articles.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        if d.get("note"):
            notes[d["note"].split(":")[0] + (":" + d["note"].split(":")[1] if d["note"].startswith("licence") else "")] = \
                notes.get(d["note"], 0) + 1
        for r in d["records"]:
            if (out_dir / r["path"]).exists():
                recs.append(Record(**r))
    st.seen = st.kept = len(recs)
    rej = SieveStats()
    for line in (out_dir / "_articles.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        if d.get("stats"):
            rej.seen += d["stats"]["seen"]
            rej.reasons.update(d["stats"]["reasons"])
    recs = finalize_dedupe(recs, out_dir, st)
    write_manifest(SOURCE, recs)
    summ = summarize(recs)
    allrej = rej.reasons + st.reasons
    summ["dedupe_removed"] = st.reasons.get("duplicate_image", 0)
    summ["figures_seen"] = rej.seen
    summ["rejected_by_reason"] = dict(allrej.most_common())
    summ["rejected_total"] = sum(allrej.values())
    summ["article_notes"] = notes
    (out_dir / "sieve_summary.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False))
    print(json.dumps(summ, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=3000)
    ap.add_argument("--max-articles", type=int, default=6000)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--finalize-only", action="store_true")
    a = ap.parse_args()
    if a.finalize_only:
        finalize(source_dir(SOURCE))
    else:
        run(a.target, a.max_articles, a.workers)
