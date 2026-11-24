"""Sieve ("peneira") for captioned plain radiographs coming from open web sources.

A figure is KEPT only if
  (a) caption: describes a plain radiograph (score_caption RX >= 0.35, mentions radiograph / x-ray / film / view,
      and CT / MRI / US / histology terms do not dominate),
  (b) image: looks like ONE greyscale radiograph (low colour saturation, min side >= 400 px) - multi-panel
      montages are split at white/black separators and the "(A) ... (B) ..." sub-captions are assigned to the
      panels, or the figure is dropped,
  (c) not a (near-)duplicate of something already kept.

All scores go to Record.quality; rejected items never reach the manifest, but `SieveStats` counts them per reason.
Structured hints (view, region, arrows, findings -> rx.* labels) are extracted from the caption text.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import Record, dedupe, score_caption

MIN_CAPTION_SCORE = 0.35
MIN_SIDE = 400            # whole figures / single panels (px, shorter side)
MIN_SIDE_PANEL = 300      # panels cut from a montage may be smaller
MAX_MEAN_SAT = 0.10       # mean HSV saturation
MAX_COLOR_FRAC = 0.06     # fraction of strongly coloured pixels (arrows etc. tolerated up to this)

# ------------------------------------------------------------------ caption analysis
_RX_MENTION = re.compile(r"radiograph|radiogram|x-?\s?rays?\b|xray|roentgen|plain film|\bfilms?\b|\bviews?\b|\bcxr\b|\bkub\b", re.I)
_RX_STRONG = re.compile(r"radiograph|radiogram|x-?\s?rays?\b|xray|roentgen|plain film|\bfilms?\b|\bcxr\b|\bkub\b", re.I)
_OTHER = re.compile(
    r"\bct\b|\bcta\b|\bhrct\b|computed tomograph|\bmri?\b|\bmr\b|magnetic resonance|ultrasound|ultrasonograph|sonograph|"
    r"\bus\b scan|\bpet\b|pet-ct|scintigra|spect\b|histolog|histopatholog|photomicrograph|microscop|h&e|hematoxylin|"
    r"haematoxylin|immunohisto|stain(ed|ing)|angiogra|echocardiogra|doppler|endoscop|colonoscop|bronchoscop|"
    r"photograph|gross specimen|intraoperative|ecg|electrocardiogra|cbct|cone[- ]beam|fluorosc|barium|mammogra|dexa\b|"
    r"cephalogram|nuclear|3d reconstruction|volume[- ]render|flow chart|flowchart|schematic|diagram|\bgraph\b|\bchart\b",
    re.I)

VIEW_PATTERNS = [
    ("PA", re.compile(r"\bpa\b|posteroanterior|postero-anterior|posterior-anterior", re.I)),
    ("AP", re.compile(r"\bap\b|anteroposterior|antero-posterior|anterior-posterior", re.I)),
    ("LATERAL", re.compile(r"\blateral (view|projection|chest|radiograph|radiogram|film|x-?ray|image|position|cxr|cr)\b|"
                           r"\b(view|projection|radiograph|film)[,:]? (in )?lateral\b|\bcross[- ]table|\blat(eral)? (cxr|view)|"
                           r"\b(in|on) (the )?lateral\b|\blateral\b[.,;]?\s*$|\blateral and\b|\band lateral\b", re.I)),
    ("DECUBITUS", re.compile(r"decubitus", re.I)),
    ("OBLIQUE", re.compile(r"oblique", re.I)),
]
POSTURE = [("supine", r"supine"), ("erect", r"\berect\b|upright|standing"), ("portable", r"portable|bedside")]

REGION_PATTERNS = [
    ("chest", r"chest|thora(x|cic)|lung|pulmon|cxr|pleura|mediastin|cardio|heart|rib\b|ribs\b|clavic|trache|bronch|diaphragm"),
    ("abdomen", r"abdom|\bkub\b|bowel|intestin|colon|ileus|gastric|stomach|pneumoperiton|kidney|renal|ureter|urinary|bladder"),
    ("spine", r"spine|spinal|vertebra|lumbar|thoracic spine|sacr|scolio|kyph|cervical spine"),
    ("pelvis_hip", r"pelvi|hip\b|hips\b|acetabul|femoral head|sacroiliac"),
    ("skull_head", r"skull|cranial|sinus|mandib|facial|orbit|dental|panoramic|periapical|teeth|tooth|cephalo"),
    ("extremity", r"hand|wrist|finger|thumb|carpal|metacarp|foot|feet|ankle|toe\b|toes\b|tarsal|metatars|knee|femur|femoral|tibia|"
                  r"fibula|humer|elbow|shoulder|forearm|radius|ulna|leg\b|arm\b|patella|calcane|scapula|bone|fracture|limb|digit"),
]

# caption phrase -> label code (codes follow knowledge/rx_signs.yaml; a few extra bone/device codes)
LABEL_PATTERNS = [
    ("rx.pneumothorax", r"pneumothora(x|ces)"),
    ("rx.pleural_effusion", r"pleural effusion|effusion|hydrothorax|costophrenic (angle )?(blunting|obliterat)|blunting of the costophrenic|hemothorax|haemothorax"),
    ("rx.consolidation", r"consolidat|lobar pneumonia|airspace (opacit|disease)|alveolar (opacit|infiltrat)|pneumonia|infiltrat"),
    ("rx.air_bronchogram", r"air[- ]bronchogram"),
    ("rx.atelectasis", r"atelecta|lobar collapse|lung collapse|collapse of the (right|left)"),
    ("rx.cardiomegaly", r"cardiomegal|enlarged (cardiac|heart)|cardiac (enlargement|silhouette (is )?enlarged)|increased cardiothoracic|enlarged cardiac silhouette"),
    ("rx.mediastinal_widening", r"mediastinal widening|widened mediastinum|wide mediastinum|mediastinal (mass|shift)|mediastinal emphysema|pneumomediastinum"),
    ("rx.nodule_mass", r"nodul|\bmass(es)?\b|tumou?r|lesion|cavit|malignan|carcinoma|metasta"),
    ("rx.hilar_enlargement", r"hilar (enlargement|prominence|lymph|mass|adenopath)|hilum|hilar"),
    ("rx.interstitial_pattern", r"interstitial|reticular|reticulonodular|honeycomb|ground[- ]glass|miliary|fibrosis|kerley"),
    ("rx.kerley_lines", r"kerley"),
    ("rx.hyperinflation", r"hyperinflat|hyperlucen|emphysema|flattened diaphragm|barrel chest"),
    ("rx.pneumoperitoneum", r"pneumoperitoneum|free (intraperitoneal )?air|free gas|rigler|football sign|subdiaphragmatic air|air under the (right )?diaphragm"),
    ("rx.bowel_obstruction", r"bowel obstruction|intestinal obstruction|dilated (small )?bowel|air[- ]fluid level|ileus|volvulus|dilated loops|distended (bowel|loops)|small[- ]bowel obstruction|stepladder"),
    ("rx.devices", r"catheter|\bpicc\b|central venous|pacemaker|\bicd\b|endotracheal|tracheostomy|chest tube|drain\b|nasogastric|\bng tube\b|stent|prosthe|implant|\bplate\b|screws?\b|nail\b|\bwire\b|cerclage|foreign body|button battery|coin\b|ingest"),
    ("rx.fracture", r"fractur|break\b|dislocat|subluxat|cortical (disruption|break)|callus|nonunion|non-union|malunion"),
    ("rx.silhouette_sign", r"silhouette sign|loss of the (right|left)? ?(heart|cardiac|hemidiaphragm|diaphragm)|obscur(ed|ation) of the"),
    ("rx.normal", r"\bnormal (chest|radiograph|x-ray|film|study|appearance)|no (acute )?(abnormalit|cardiopulmonary)|unremarkable"),
]
LABEL_PATTERNS = [(c, re.compile(p, re.I)) for c, p in LABEL_PATTERNS]
_NEG_CTX = re.compile(r"\b(no|without|absence of|absent|negative for|free of|resolution of|resolved|ruled out)\b[^.;]{0,40}$", re.I)

_ARROW = re.compile(r"(arrow ?heads?|arrows?|asterisks?|circles?|circled|encircled|dotted line|bracket|star)s?\b", re.I)


def _neg_dominates(text: str) -> tuple[int, int]:
    return len(_RX_STRONG.findall(text)), len(_OTHER.findall(text))


def extract_view(text: str) -> Optional[str]:
    for name in ("DECUBITUS",):  # most specific first
        if dict(VIEW_PATTERNS)[name].search(text):
            return name
    pa = dict(VIEW_PATTERNS)["PA"].search(text)
    lat = dict(VIEW_PATTERNS)["LATERAL"].search(text)
    ap = dict(VIEW_PATTERNS)["AP"].search(text)
    if pa and not lat:
        return "PA"
    if ap and not lat:
        return "AP"
    if lat and not (pa or ap):
        return "LATERAL"
    # first mentioned wins when several
    found = [(m.start(), n) for n, p in VIEW_PATTERNS if (m := p.search(text))]
    return min(found)[1] if found else None


def extract_region(text: str) -> Optional[str]:
    t = text.lower()
    scores = {r: len(re.findall(p, t)) for r, p in REGION_PATTERNS}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return None
    # "chest radiograph/x-ray" explicit wins
    if re.search(r"chest (radiograph|x-?ray|film|xray|radiography)|\bcxr\b", t):
        return "chest"
    if re.search(r"abdomin\w* (radiograph|x-?ray|film|xray)|\bkub\b", t):
        return "abdomen"
    return best


def extract_labels(text: str) -> list[str]:
    """Phrase-level finding codes; mentions preceded by a negation within ~40 chars are skipped."""
    out: list[str] = []
    for code, rx_ in LABEL_PATTERNS:
        for m in rx_.finditer(text):
            ctx = text[max(0, m.start() - 45):m.start()]
            if _NEG_CTX.search(ctx):
                continue
            if code not in out:
                out.append(code)
            break
    # specialised code supersedes generic
    if "rx.kerley_lines" in out and "rx.interstitial_pattern" not in out:
        out.append("rx.interstitial_pattern")
    if "rx.normal" in out and len(out) > 1:
        out.remove("rx.normal")
    return out


def extract_arrows(text: str) -> list[str]:
    """Sentences / clauses that describe arrows, arrowheads, asterisks, circles."""
    res = []
    for sent in re.split(r"(?<=[.;])\s+", text):
        if _ARROW.search(sent):
            res.append(sent.strip()[:240])
    return res


def panel_letters(caption: str) -> list[str]:
    """Distinct panel letters referenced in the caption: '(A)', '(A, B)', '(A and B)', '(A-C)', 'A)'."""
    letters: set[str] = set()
    for m in re.finditer(r"\(([A-Ha-h](?:\s*(?:,|and|&|to|\u2013|\u2014|-)\s*[A-Ha-h])*)\)", caption):
        grp = m.group(1)
        parts = re.split(r"\s*(?:,|and|&)\s*", grp)
        for p in parts:
            rng = re.split(r"\s*(?:to|\u2013|\u2014|-)\s*", p)
            if len(rng) == 2 and len(rng[0]) == 1 and len(rng[1]) == 1:
                letters.update(chr(c).upper() for c in range(ord(rng[0].upper()), ord(rng[1].upper()) + 1))
            else:
                letters.update(x.upper() for x in rng if len(x) == 1)
    return sorted(letters)


def split_subcaptions(caption: str) -> tuple[str, dict[str, str]]:
    """'Chest X-ray. (A) PA view ... (B) lateral ...' -> ('Chest X-ray.', {'A': 'PA view ...', 'B': ...}).
    Accepts (A)/(a)/A./A) markers in ascending order A, B, C ... Needs >= 2 consecutive letters starting at A."""
    pat = re.compile(r"(?:(?<=\s)|^)\(?\b([A-Ha-h])\s?[\).:]\s|(?:(?<=\s)|^)\(([A-Ha-h])\)")
    marks = []
    for m in pat.finditer(caption):
        letter = (m.group(1) or m.group(2)).upper()
        marks.append((m.start(), m.end(), letter))
    # choose ascending run A, B, C...
    seq, nxt = [], "A"
    for s, e, l in marks:
        if l == nxt:
            seq.append((s, e, l))
            nxt = chr(ord(nxt) + 1)
    if len(seq) < 2:
        return caption, {}
    head = caption[:seq[0][0]].strip()
    subs = {}
    for i, (s, e, l) in enumerate(seq):
        end = seq[i + 1][0] if i + 1 < len(seq) else len(caption)
        subs[l] = caption[e:end].strip(" ,;")
    return head, subs


def caption_sieve(caption: str, modality_rx_min: float = MIN_CAPTION_SCORE) -> dict:
    """Return dict(ok, reason, score, ...) for a caption alone."""
    cap = re.sub(r"\s+", " ", caption or "").strip()
    sc = score_caption(cap, "RX")
    rx_n, other_n = _neg_dominates(cap)
    # score_caption's substring negatives ("ct " in "fact ") are noisy: re-add its penalty when our regex disagrees
    raw = sc["caption_score"]
    adj = raw + (0.3 if sc["other_modality_terms"] and other_n == 0 else 0.0)
    adj = round(min(1.0, adj), 3)
    q = {"caption_score": adj, "caption_score_raw": raw, "terms": sc["terms"], "n_words": sc["n_words"],
         "rx_mentions": rx_n, "other_modality_mentions": other_n}
    if not cap:
        return {"ok": False, "reason": "no_caption", "q": q}
    if not _RX_MENTION.search(cap):
        return {"ok": False, "reason": "no_radiograph_word", "q": q}
    if other_n and other_n >= max(1, rx_n):
        return {"ok": False, "reason": "other_modality_dominates", "q": q}
    if adj < modality_rx_min:
        return {"ok": False, "reason": "caption_score_low", "q": q}
    return {"ok": True, "reason": "", "q": q}


def figure_caption_sieve(caption: str) -> dict:
    """Whole-figure caption check. For montages with (A)(B) sub-captions a mixed-modality / short whole caption is
    tolerated here (each sub-caption is judged on its own after the panel split)."""
    cs = caption_sieve(caption)
    if (not cs["ok"] and cs["reason"] in ("other_modality_dominates", "caption_score_low")
            and len(split_subcaptions(re.sub(r"\s+", " ", caption or "").strip())[1]) >= 2 and _RX_MENTION.search(caption)):
        return {"ok": True, "reason": "", "q": cs["q"]}
    return cs


# ------------------------------------------------------------------ image analysis
def _load_gray_and_sat(path_or_img):
    from PIL import Image
    import numpy as np
    im = path_or_img if hasattr(path_or_img, "convert") else Image.open(path_or_img)
    rgb = im.convert("RGB")
    if max(rgb.size) > 1000:  # speed
        s = 1000 / max(rgb.size)
        rgb = rgb.resize((int(rgb.width * s), int(rgb.height * s)))
    a = np.asarray(rgb, dtype=np.float32) / 255.0
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0.05, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    gray = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])
    return gray, sat


def image_stats(path_or_img) -> dict:
    gray, sat = _load_gray_and_sat(path_or_img)
    im0 = path_or_img if hasattr(path_or_img, "size") else None
    if im0 is None:
        from PIL import Image
        im0 = Image.open(path_or_img)
    return {"width": int(im0.size[0]), "height": int(im0.size[1]),
            "mean_sat": round(float(sat.mean()), 4),
            "color_frac": round(float((sat > 0.35).mean()), 4),
            "gray_std": round(float(gray.std()), 4),
            "gray_mean": round(float(gray.mean()), 4)}


def _runs(mask, min_len):
    """(start, end) of True runs at least min_len long."""
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if j - i >= min_len:
                out.append((i, j))
            i = j
        else:
            i += 1
    return out


def _separator_cuts(gray, axis: int, min_seg: int = 200, min_sep: int = 3):
    """Cut positions along `axis` (0 = rows: horizontal separators; 1 = columns). A separator is a run of rows/cols that
    is (almost) uniformly white or black over the whole figure width/height."""
    import numpy as np
    prof_mean = gray.mean(axis=1 - axis)
    prof_std = gray.std(axis=1 - axis)
    white = (prof_mean > 0.93) & (prof_std < 0.06)
    black = (prof_mean < 0.06) & (prof_std < 0.05)
    n = gray.shape[axis]
    cuts = []
    for mask in (white, black):
        for s, e in _runs(mask, min_sep):
            if s <= 2 or e >= n - 2:        # border margins are not separators
                continue
            cuts.append((s, e))
    cuts.sort()
    # segments between cuts
    segs, prev = [], 0
    for s, e in cuts:
        if s - prev >= min_seg:
            segs.append((prev, s))
        prev = e
    if n - prev >= min_seg:
        segs.append((prev, n))
    return segs if len(segs) >= 2 else None


def detect_panels(img, min_seg: int = 200) -> list[tuple[int, int, int, int]]:
    """Return boxes (x0, y0, x1, y1) in img pixel coords (img as given, any size). 1 box -> single panel.
    Recursive guillotine cut along white/black separator lines."""
    import numpy as np
    gray, _ = _load_gray_and_sat(img)
    H, W = gray.shape
    sx, sy = img.size[0] / W, img.size[1] / H

    def rec(x0, y0, x1, y1, depth=0):
        sub = gray[y0:y1, x0:x1]
        if depth > 3 or sub.shape[0] < 2 * min_seg and sub.shape[1] < 2 * min_seg:
            return [(x0, y0, x1, y1)]
        for axis in (1, 0):
            segs = _separator_cuts(sub, axis, min_seg=min(min_seg, max(60, sub.shape[axis] // 6)))
            if segs:
                out = []
                for a, b in segs:
                    box = (x0 + a, y0, x0 + b, y1) if axis == 1 else (x0, y0 + a, x1, y0 + b)
                    out += rec(*box, depth + 1)
                return out
        return [(x0, y0, x1, y1)]

    boxes = rec(0, 0, W, H)
    # trim uniform margins from each box, scale back
    res = []
    for (x0, y0, x1, y1) in boxes:
        res.append((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)))
    return res


def sort_reading_order(boxes):
    """row-major: group by overlapping y ranges, then x."""
    rows: list[list] = []
    for b in sorted(boxes, key=lambda b: (b[1], b[0])):
        for r in rows:
            ry0, ry1 = min(x[1] for x in r), max(x[3] for x in r)
            ov = min(ry1, b[3]) - max(ry0, b[1])
            if ov > 0.5 * min(ry1 - ry0, b[3] - b[1]):
                r.append(b)
                break
        else:
            rows.append([b])
    return [b for r in rows for b in sorted(r, key=lambda x: x[0])]


def image_ok(stats: dict, min_side: int = MIN_SIDE) -> tuple[bool, str]:
    if min(stats["width"], stats["height"]) < min_side:
        return False, "too_small"
    if stats["mean_sat"] > MAX_MEAN_SAT or stats["color_frac"] > MAX_COLOR_FRAC:
        return False, "colour_image"
    if stats["gray_std"] < 0.05:
        return False, "low_contrast_or_blank"
    ar = stats["width"] / stats["height"]
    if ar > 2.6 or ar < 0.38:
        return False, "odd_aspect_ratio"
    return True, ""


# ------------------------------------------------------------------ stats
@dataclass
class SieveStats:
    seen: int = 0
    kept: int = 0
    reasons: Counter = field(default_factory=Counter)

    def reject(self, reason: str):
        self.reasons[reason] += 1

    def as_dict(self):
        return {"seen": self.seen, "kept": self.kept, "rejected": sum(self.reasons.values()),
                "reasons": dict(self.reasons.most_common())}


# ------------------------------------------------------------------ the main entry
@dataclass
class Candidate:
    """What a collector hands to the sieve for one figure."""
    id: str
    caption: str
    image_bytes: bytes
    ext: str                       # source extension without dot
    url: str
    license: str
    attribution: str
    extra: dict = field(default_factory=dict)


def sieve_candidate(c: Candidate, out_dir: Path, source: str, stats: Optional[SieveStats] = None,
                    modality: str = "RX") -> list[Record]:
    """Run caption + image sieve (+panel split). Writes kept images into out_dir/images and returns Records.
    Duplicate removal is a later, corpus-level step (see finalize_dedupe)."""
    import io
    from PIL import Image
    stats = stats or SieveStats()
    stats.seen += 1
    head, subs = split_subcaptions(re.sub(r"\s+", " ", c.caption).strip())
    cs = figure_caption_sieve(c.caption)
    if not cs["ok"]:
        stats.reject("caption:" + cs["reason"])
        return []
    try:
        im = Image.open(io.BytesIO(c.image_bytes))
        im.load()
    except Exception:
        stats.reject("image:unreadable")
        return []
    boxes = sort_reading_order(detect_panels(im))
    n_pan = len(boxes)
    parts: list[tuple[Image.Image, str, str]] = []  # (image, caption, panel_id suffix)
    if n_pan == 1:
        if len(subs) >= 2 or len(panel_letters(c.caption)) >= 2:
            stats.reject("panels:subcaptions_but_single_image")
            return []
        parts.append((im, c.caption, ""))
    else:
        if len(subs) != n_pan:
            stats.reject("panels:montage_unassignable")
            return []
        for (box, letter) in zip(boxes, sorted(subs)):
            parts.append((im.crop(box), f"{head} {subs[letter]}".strip(), f"_{letter}"))
    recs: list[Record] = []
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    for pim, pcap, suf in parts:
        pcs = caption_sieve(pcap)
        if not pcs["ok"]:
            stats.reject("caption:" + pcs["reason"] + ("(panel)" if suf else ""))
            continue
        st = image_stats(pim)
        ok, why = image_ok(st, MIN_SIDE_PANEL if suf else MIN_SIDE)
        if not ok:
            stats.reject("image:" + why + ("(panel)" if suf else ""))
            continue
        rid = c.id + suf
        if suf:
            fn = f"{rid}.png"
            pim.convert("L").save(img_dir / fn)
        else:
            fn = f"{rid}.{c.ext}"
            (img_dir / fn).write_bytes(c.image_bytes)
        cap = re.sub(r"\s+", " ", pcap).strip()
        arrows = extract_arrows(cap)
        r = Record(id=rid, source=source, modality=modality, kind="image", path=f"images/{fn}", url=c.url,
                   license=c.license, attribution=c.attribution, caption=cap,
                   labels=extract_labels(cap), view=extract_view(cap), group=c.extra.get("group"),
                   extra={**c.extra, "region": extract_region(cap), "arrows": arrows,
                          "n_panels_in_figure": n_pan, "full_caption": re.sub(r"\s+", " ", c.caption).strip() if suf else None,
                          "posture": [n for n, p in POSTURE if re.search(p, cap, re.I)]},
                   quality={**pcs["q"], **st, "sieve": "rx_captioned_v1", "panel_split": bool(suf)})
        recs.append(r)
        stats.kept += 1
    return recs


def finalize_dedupe(records: list[Record], root: Path, stats: Optional[SieveStats] = None) -> list[Record]:
    """Corpus-level near-duplicate removal (image phash) + exact duplicate captions with same phash neighbourhood."""
    dedupe(records, root)
    kept = []
    for r in records:
        if r.quality.get("duplicate_of"):
            if stats:
                stats.reject("duplicate_image")
                stats.kept -= 1
            try:
                (root / r.path).unlink()
            except OSError:
                pass
            continue
        kept.append(r)
    return kept


def summarize(records: list[Record]) -> dict:
    lab, reg, view = Counter(), Counter(), Counter()
    for r in records:
        lab.update(r.labels)
        reg[r.extra.get("region") or "unknown"] += 1
        view[r.view or "unknown"] += 1
    return {"n": len(records), "labels": dict(lab.most_common()), "regions": dict(reg.most_common()),
            "views": dict(view.most_common())}
