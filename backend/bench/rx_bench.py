"""RX benchmark: segmentation vs GT masks, IU X-ray view/findings/3D, captioned web images.

    python -m bench.rx_bench [--source masks|iu|captioned|all] [--limit N] [--workers K]
                             [--models on|off|both] [--max-side 1024] [--report-only]

Results are cached (append-only JSONL, one row per item+mode) in data/bench/rx/<kind>.jsonl, so reruns only
process what is new. The markdown report (docs/benchmarks/rx.md) is always rebuilt from the cache.
Images are down-scaled to --max-side (GT masks resized by nearest neighbour) to keep CPU time bounded.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import random
import re
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

import numpy as np

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

MASK_SOURCES = ["jsrt_masks", "montgomery", "shenzhen", "rx_masks_other"]
IU_SOURCES = ["iu_xray"]
CAP_SOURCES = ["europepmc_rx", "wikimedia_rx"]
KIND_SOURCES = {"seg": MASK_SOURCES, "iu": IU_SOURCES, "cap": CAP_SOURCES}
SOURCE_ARG = {"masks": ["seg"], "iu": ["iu"], "captioned": ["cap"], "all": ["seg", "iu", "cap"]}
MODES = {"on": "model", "off": "heur"}


def data_root() -> Path:
    from medlens_data import DATA_ROOT
    return Path(DATA_ROOT)


def cache_dir() -> Path:
    d = Path(os.environ.get("MEDLENS_BENCH_DIR", data_root().parent / "bench" / "rx"))
    d.mkdir(parents=True, exist_ok=True)
    return d


# ======================================================================================= metrics
def dice_iou(pred: np.ndarray, gt: np.ndarray) -> tuple[float, float]:
    p, g = pred.astype(bool), gt.astype(bool)
    inter = float((p & g).sum())
    sp, sg = float(p.sum()), float(g.sum())
    if sp + sg == 0:
        return 1.0, 1.0
    union = sp + sg - inter
    return 2 * inter / (sp + sg), (inter / union if union else 1.0)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def auc_score(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y).astype(bool)
    s = np.asarray(s, dtype=float)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s))
    ss = s[order]
    i = 0
    while i < len(ss):  # average ranks for ties
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def auc_ci(y, s, n_boot: int = 500, seed: int = 0) -> tuple[float, float, float]:
    y = np.asarray(y).astype(bool)
    s = np.asarray(s, dtype=float)
    a = auc_score(y, s)
    if math.isnan(a):
        return a, a, a
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        v = auc_score(y[idx], s[idx])
        if not math.isnan(v):
            vals.append(v)
    if not vals:
        return a, float("nan"), float("nan")
    return a, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def binary_stats(y: list[bool], p: list[bool]) -> dict:
    y = np.asarray(y, bool)
    p = np.asarray(p, bool)
    tp, fn = int((y & p).sum()), int((y & ~p).sum())
    tn, fp = int((~y & ~p).sum()), int((~y & p).sum())
    return {"tp": tp, "fn": fn, "tn": tn, "fp": fp, "n": len(y),
            "sens": (tp, tp + fn), "spec": (tn, tn + fp), "ppv": (tp, tp + fp)}


# ======================================================================================= GT masks
_IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif")


def norm_struct(name: str) -> Optional[str]:
    """Map a free-form mask name/key to one of our structure keys (patient-side convention)."""
    n = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    toks = set(n.split("_"))
    side = "left" if ("left" in toks or "l" in toks or "esq" in toks) else \
           "right" if ("right" in toks or "r" in toks or "dir" in toks) else None
    if "heart" in n or "cardiac" in n:
        return "heart"
    if "clav" in n:
        return f"{side}_clavicle" if side else None
    if "scap" in n:
        return f"{side}_scapula" if side else None
    for k in ("spine", "trachea", "aorta", "mediastinum", "hilum"):
        if k in n:
            return k if k not in ("hilum",) or not side else f"{side}_hilum"
    if "lung" in n or "mask" in n or "seg" in n:
        return f"{side}_lung" if side else "lungs"
    return None


def gt_paths(rec) -> dict[str, str]:
    """Find GT mask files in a Record.extra (flexible: {'masks': {name: path}}, 'mask_left', 'lung_mask', ...)."""
    out: dict[str, str] = {}
    ex = rec.extra or {}

    def add(name, val):
        if isinstance(val, dict):
            for k2, v2 in val.items():
                add(f"{name}_{k2}" if name not in ("masks", "mask", "gt", "gt_masks", "annotations") else str(k2), v2)
            return
        if isinstance(val, (list, tuple)):
            for v2 in val:
                if isinstance(v2, dict):
                    add(name, v2)
            return
        if isinstance(val, str) and val.lower().endswith(_IMG_EXT):
            key = norm_struct(name)
            if key is None:
                key = norm_struct(Path(val).stem)
            if key:
                out[key] = val

    for k, v in ex.items():
        if "mask" in k.lower() or k.lower() in ("gt", "annotations", "segmentation"):
            add(k, v)
    return out


def load_gray(path: Path, max_side: int = 1024) -> np.ndarray:
    from PIL import Image
    im = Image.open(path)
    if im.mode in ("I;16", "I;16B", "I", "F"):
        a = np.asarray(im).astype(np.float64)
        lo, hi = np.percentile(a, [0.5, 99.5])
        a = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1) * 255
        im = Image.fromarray(a.astype(np.uint8))
    else:
        im = im.convert("L")
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((max(1, round(im.size[0] * s)), max(1, round(im.size[1] * s))), Image.LANCZOS)
    return np.asarray(im, dtype=np.uint8)


def load_mask(path: Path, shape: tuple[int, int]) -> np.ndarray:
    from PIL import Image
    im = Image.open(path)
    if im.mode == "P":
        im = im.convert("L")
    elif im.mode not in ("L", "1"):
        im = im.convert("L") if im.mode != "I;16" else Image.fromarray((np.asarray(im) > 0).astype(np.uint8) * 255)
    if im.size != (shape[1], shape[0]):
        im = im.resize((shape[1], shape[0]), Image.NEAREST)
    return np.asarray(im) > 0


def decontour(img: np.ndarray, gts: dict[str, np.ndarray], width: int = 2) -> np.ndarray:
    """Remove contour lines burned into some SCR/JSRT JPEGs: pixels in a thin band around every GT mask
    boundary are replaced by the nearest pixel outside the band (then lightly smoothed inside the band)."""
    from scipy import ndimage as ndi
    bd = np.zeros(img.shape, bool)
    for g in gts.values():
        bd |= g ^ ndi.binary_erosion(g)
    band = ndi.binary_dilation(bd, iterations=width)
    idx = ndi.distance_transform_edt(band, return_distances=False, return_indices=True)
    filled = img[tuple(idx)]
    sm = ndi.uniform_filter(filled.astype(np.float32), 3)
    out = img.copy()
    out[band] = sm[band].astype(np.uint8)
    return out


def decode_struct_mask(st, shape) -> Optional[np.ndarray]:
    import base64
    import io
    from PIL import Image
    if not st.mask_png_b64:
        return None
    im = Image.open(io.BytesIO(base64.b64decode(st.mask_png_b64))).convert("L")
    if im.size != (shape[1], shape[0]):
        im = im.resize((shape[1], shape[0]), Image.NEAREST)
    return np.asarray(im) > 127


def width_of(m: np.ndarray) -> float:
    cols = np.where(m.any(axis=0))[0]
    return float(cols.max() - cols.min() + 1) if len(cols) else float("nan")


def ctr_from_masks(heart: Optional[np.ndarray], lungs: Optional[np.ndarray]) -> Optional[float]:
    if heart is None or lungs is None or not heart.any() or not lungs.any():
        return None
    return width_of(heart) / width_of(lungs)


# ======================================================================================= caption hints
_REGION_KW = [
    ("chest", r"\b(chest|thora(x|cic)|lung|pulmon|pleur|cardiac|heart|cardiomegal|pneumo|mediastin|hil(ar|um)|rib)\w*"),
    ("abdomen", r"\b(abdom|bowel|ileus|obstruction|colon|pneumoperitoneum|kub)\w*"),
    ("pelvis", r"\b(pelvi|hip|sacr|femoral head)\w*"),
    ("spine", r"\b(spine|spinal|vertebr|scolio|lumbar|cervical|thoracic spine)\w*"),
    ("skull", r"\b(skull|cranial|sinus|mandib)\w*"),
    ("extremity", r"\b(hand|wrist|finger|forearm|elbow|humer|shoulder|knee|ankle|foot|tibia|fibula|femur|leg|radius|ulna)\w*"),
]
_LAT_RE = re.compile(r"\b(lateral|lat\.?\s*view|left lateral|right lateral)\b", re.I)
_FRONT_RE = re.compile(r"\b(pa|ap|frontal|posteroanterior|anteroposterior|postero-anterior|antero-posterior)\b(?=[\s,.;:)\-]|$)", re.I)

TARGETS = ["cardiomegaly", "effusion", "pneumothorax", "consolidation", "atelectasis", "diaphragm", "normal"]
_TARGET_PATTERNS = {
    "cardiomegaly": r"cardiomegal|enlarged (cardiac|heart)|cardiac enlargement|enlarged cardiomediastin",
    "effusion": r"effusion|pleural fluid|costophrenic.*(blunt|obliterat)",
    "pneumothorax": r"pneumothora",
    "consolidation": r"consolidat|pneumonia|airspace (disease|opacit)|lobar",
    "atelectasis": r"atelecta|volume loss",
    "diaphragm": r"hemidiaphragm|diaphragm.*elevat|eventration",
    "normal": r"\bnormal\b",
}


def caption_hints(text: str, view: Optional[str] = None) -> dict:
    t = (text or "")
    regs = []
    for name, pat in _REGION_KW:
        if re.search(pat, t, re.I):
            regs.append(name)
    out = {"regions": regs, "region": regs[0] if len(regs) == 1 else (("chest" if "chest" in regs and len(regs) <= 2 and not (set(regs) - {"chest", "spine"}) else None)),
           "view": None}
    lat = bool(_LAT_RE.search(t))
    fr = bool(_FRONT_RE.search(t))
    if view:
        v = view.upper()
        out["view"] = "lateral" if v.startswith("LAT") or v in ("LL", "RL") else "frontal" if v in ("PA", "AP", "FRONTAL") else None
    elif lat and not fr:
        out["view"] = "lateral"
    elif fr and not lat:
        out["view"] = "frontal"
    return out


def text_labels(rec) -> set[str]:
    """Canonical target labels from Record.labels (preferred) plus negation-aware caption/report matching."""
    out: set[str] = set()
    labs = [l.lower() for l in (rec.labels or [])]
    for l in labs:
        if re.search(r"(^|[._])(no|not|neg|without|absent)[._ ]", l):
            continue
        for tgt, pat in _TARGET_PATTERNS.items():
            if re.search(pat, l.replace("_", " ")):
                out.add(tgt)
    if "normal" in out and len(out - {"normal"}) > 0:
        out.discard("normal")
    return out


def caption_labels(text: str) -> set[str]:
    """Weak labels from free text: sentence-level negation filter."""
    out: set[str] = set()
    for sent in re.split(r"[.;\n]", (text or "").lower()):
        neg = re.search(r"\b(no|without|negative for|absence of|not|free of|resolved)\b", sent)
        for tgt, pat in _TARGET_PATTERNS.items():
            if tgt == "normal":
                continue
            if re.search(pat, sent) and not neg:
                out.add(tgt)
    return out


def view_class(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    v = v.upper()
    if v in ("PA", "AP", "FRONTAL", "FRONT") or v.startswith("FRONT"):
        return "frontal"
    if v.startswith("LAT") or v in ("LL", "RL"):
        return "lateral"
    return None


# ======================================================================================= workers
def _init_worker():
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:
        pass
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


def _fake_ds(view: Optional[str] = "PA"):
    """Stand-in for DICOM tags (what a real DICOM would carry): chest + view position."""
    import types
    return types.SimpleNamespace(BodyPartExamined="CHEST", ViewPosition=view or "PA")


def _analyze(img, iid, mode, ds=None):
    from app.rx import analyze_image
    t0 = time.perf_counter()
    a = analyze_image(img, iid, ds, use_model=(mode == "model"))
    return a, time.perf_counter() - t0


def _meas(a, key):
    for m in a.measurements:
        if m.key == key:
            return m.value
    return None


def _img_summary(a, dt) -> dict:
    return {"view": a.view.value, "region": a.region.value, "t": round(dt, 3),
            "ctr": _meas(a, "cardiothoracic_ratio"), "scores": a.model_scores,
            "seg_origin": sorted({s.origin for s in a.structures}),
            "n_struct": len(a.structures), "quality": a.quality.get("segmentação", "")}


def run_seg(task: dict) -> dict:
    out = {"key": task["key"], "kind": "seg", "source": task["source"], "id": task["id"], "mode": task["mode"]}
    try:
        root = Path(task["root"])
        img = load_gray(root / task["path"], task["max_side"])
        shape = img.shape
        gts = {k: load_mask(root / p, shape) for k, p in task["gt"].items()}
        if task.get("decontour"):
            img = decontour(img, gts)
        # untagged run (what a PNG/JPG upload gets): only region/view detection is scored from it
        a0, _ = _analyze(img, task["id"], "heur")
        out["auto_view"], out["auto_region"] = a0.view.value, a0.region.value
        gv = view_class(task.get("view"))
        a, dt = _analyze(img, task["id"], task["mode"], _fake_ds("LATERAL" if gv == "lateral" else "PA"))
        pred = {}
        for st in a.structures:
            m = decode_struct_mask(st, shape)
            if m is not None:
                pred[st.key] = m
        if "left_lung" in pred or "right_lung" in pred:
            pred["lungs"] = pred.get("left_lung", np.zeros(shape, bool)) | pred.get("right_lung", np.zeros(shape, bool))
        if "lungs" not in gts and "left_lung" in gts and "right_lung" in gts:
            gts["lungs"] = gts["left_lung"] | gts["right_lung"]
        res = {}
        for k, g in gts.items():
            p = pred.get(k)
            if p is None:
                res[k] = {"dice": 0.0, "iou": 0.0, "missing": True}
            else:
                d, i = dice_iou(p, g)
                res[k] = {"dice": d, "iou": i, "missing": False}
                sw = {"left_lung": "right_lung", "right_lung": "left_lung", "left_clavicle": "right_clavicle",
                      "right_clavicle": "left_clavicle"}.get(k)
                if sw and sw in pred:
                    res[k]["dice_swapped"] = dice_iou(pred[sw], g)[0]
        out["metrics"] = res
        gh, gl = gts.get("heart"), gts.get("lungs")
        out["ctr_gt"] = ctr_from_masks(gh, gl)
        out["ctr_ours"] = _meas(a, "cardiothoracic_ratio")
        out["ctr_from_pred_masks"] = ctr_from_masks(pred.get("heart"), pred.get("lungs"))
        out.update(_img_summary(a, dt))
        out["ok"] = True
    except Exception as e:
        out.update(ok=False, error=f"{type(e).__name__}: {e}", tb=traceback.format_exc(limit=3))
    return out


def run_iu(task: dict) -> dict:
    """task['items'] = [{id,path,view,labels}] of one study group."""
    out = {"key": task["key"], "kind": "iu", "source": task["source"], "id": task["id"], "mode": task["mode"],
           "gt_labels": task["gt_labels"], "gt_raw": task.get("gt_raw", [])}
    try:
        from app.rx import study_findings
        root = Path(task["root"])
        analyses, imgs = [], []
        for it in task["items"]:
            try:
                img = load_gray(root / it["path"], task["max_side"])
                a, dt = _analyze(img, it["id"], task["mode"])
                analyses.append(a)
                s = _img_summary(a, dt)
                s.update(id=it["id"], gt_view=it["view"], vsrc=it.get("vsrc"))
                imgs.append(s)
            except Exception as e:
                imgs.append({"id": it["id"], "gt_view": it["view"], "error": f"{type(e).__name__}: {e}"})
        out["images"] = imgs
        if analyses:
            fs = study_findings(analyses)
            out["findings"] = [{"code": f.code, "severity": f.severity, "origin": f.origin} for f in fs]
        else:
            out["findings"] = []
        # 3D reconstruction when we have a frontal + lateral pair (by our own classification of the pair)
        fr = [a for a in analyses if a.view.value in ("PA", "AP")]
        la = [a for a in analyses if a.view.value == "LATERAL"]
        gt_f = [a for a, i in zip(analyses, [x for x in imgs if "error" not in x]) if view_class(i["gt_view"]) == "frontal"]
        gt_l = [a for a, i in zip(analyses, [x for x in imgs if "error" not in x]) if view_class(i["gt_view"]) == "lateral"]
        if gt_f and gt_l:
            from app.recon3d import reconstruct
            out["recon"] = {"attempted": True}
            t0 = time.perf_counter()
            try:
                glb, meshes, method = reconstruct(gt_f[0], gt_l[0])
                out["recon"].update(ok=bool(glb), t=round(time.perf_counter() - t0, 2), n_meshes=len(meshes),
                                    glb_kb=round(len(glb) / 1024, 1), ours_pair=bool(fr and la))
            except Exception as e:
                out["recon"].update(ok=False, t=round(time.perf_counter() - t0, 2), error=f"{type(e).__name__}: {e}")
        out["ok"] = True
    except Exception as e:
        out.update(ok=False, error=f"{type(e).__name__}: {e}", tb=traceback.format_exc(limit=3))
    return out


def run_cap(task: dict) -> dict:
    out = {"key": task["key"], "kind": "cap", "source": task["source"], "id": task["id"], "mode": task["mode"],
           "hints": task["hints"], "gt_labels": task["gt_labels"]}
    try:
        from app.rx import study_findings
        root = Path(task["root"])
        img = load_gray(root / task["path"], task["max_side"])
        a, dt = _analyze(img, task["id"], task["mode"])
        out.update(_img_summary(a, dt))
        out["shape"] = list(img.shape)
        out["findings"] = [{"code": f.code, "severity": f.severity, "origin": f.origin} for f in study_findings([a])]
        out["ok"] = True
    except Exception as e:
        out.update(ok=False, error=f"{type(e).__name__}: {e}", tb=traceback.format_exc(limit=3))
    return out


RUNNERS = {"seg": run_seg, "iu": run_iu, "cap": run_cap}


def _dispatch(task: dict) -> dict:
    return RUNNERS[task["kind"]](task)


# ======================================================================================= task building
def build_tasks(kind: str, modes: list[str], limit: Optional[int], max_side: int, seed: int = 0) -> list[dict]:
    from medlens_data import read_manifest
    tasks: list[dict] = []
    for src in KIND_SOURCES[kind]:
        root = data_root() / src
        recs = [r for r in read_manifest(src) if r.modality == "RX" or kind == "seg"]
        recs = [r for r in recs if r.kind in ("image", "dicom") and (root / r.path).exists()]
        if kind == "seg":
            recs = [r for r in recs if gt_paths(r)]
        if kind == "cap":
            recs = [r for r in recs if not (r.quality or {}).get("duplicate_of")]
        if kind == "iu":
            groups: dict[str, list] = defaultdict(list)
            for r in recs:
                groups[r.group or r.id].append(r)
            gl = sorted(groups.items())
            random.Random(seed).shuffle(gl)
            if limit:
                gl = gl[:limit]
            for g, rs in gl:
                labs: set[str] = set()
                for r in rs:
                    labs |= text_labels(r)
                evaluable = any(r.labels or r.caption for r in rs)
                for mode in modes:
                    tasks.append({"kind": "iu", "source": src, "root": str(root), "id": g, "mode": mode,
                                  "key": f"iu:{src}:{g}:{mode}", "max_side": max_side,
                                  "gt_labels": sorted(labs) if evaluable else None,
                                  "gt_raw": sorted({l for r in rs for l in (r.labels or [])}),
                                  "items": [{"id": r.id, "path": r.path, "view": r.view,
                                             "vsrc": (r.extra or {}).get("view_source")} for r in rs]})
            continue
        rs = sorted(recs, key=lambda r: r.id)
        random.Random(seed).shuffle(rs)
        if limit:
            rs = rs[:limit]
        for r in rs:
            for mode in modes:
                t = {"kind": kind, "source": src, "root": str(root), "id": r.id, "path": r.path, "mode": mode,
                     "key": f"{kind}:{src}:{r.id}:{mode}", "max_side": max_side}
                if kind == "seg":
                    t["gt"] = gt_paths(r)
                    t["view"] = r.view
                    # SCR-derived JPEGs (Zenodo 7056076) carry the GT contours burned into the image
                    t["decontour"] = "scr" in json.dumps(r.extra.get("mask_source", "")).lower() or "7056076" in (r.url or "")
                else:
                    txt = r.caption or ""
                    t["hints"] = caption_hints(txt, r.view)
                    labs = text_labels(r) | caption_labels(txt)
                    t["gt_labels"] = sorted(labs)
                tasks.append(t)
    return tasks


def load_cache(kind: str) -> dict[str, dict]:
    p = cache_dir() / f"{kind}.jsonl"
    out = {}
    if p.exists():
        for line in p.open(encoding="utf-8"):
            if line.strip():
                try:
                    d = json.loads(line)
                    out[d["key"]] = d
                except Exception:
                    pass
    return out


def run_kind(kind: str, modes: list[str], limit, workers: int, max_side: int) -> int:
    tasks = build_tasks(kind, modes, limit, max_side)
    cache = load_cache(kind)
    todo = [t for t in tasks if t["key"] not in cache or not cache[t["key"]].get("ok")]
    # failures are retried only if the cached row has no 'error' (keep deterministic failures out of the loop)
    todo = [t for t in todo if t["key"] not in cache]
    print(f"[{kind}] {len(tasks)} tasks, {len(todo)} new", flush=True)
    if not todo:
        return 0
    p = cache_dir() / f"{kind}.jsonl"
    n = 0
    with p.open("a", encoding="utf-8") as f:
        if workers <= 1:
            _init_worker()
            it = map(_dispatch, todo)
            pool = None
        else:
            pool = mp.get_context("spawn").Pool(workers, initializer=_init_worker)
            it = pool.imap_unordered(_dispatch, todo, chunksize=1)
        try:
            for r in it:
                f.write(json.dumps(r, default=float) + "\n")
                f.flush()
                n += 1
                if n % 25 == 0:
                    print(f"[{kind}] {n}/{len(todo)}", flush=True)
        finally:
            if pool:
                pool.close()
                pool.join()
    return n


# ======================================================================================= aggregation / report
def _stat(vals: list[float]) -> dict:
    a = np.asarray([v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))], float)
    if not len(a):
        return {"n": 0}
    return {"n": len(a), "mean": float(a.mean()), "sd": float(a.std()), "median": float(np.median(a)),
            "p10": float(np.percentile(a, 10)), "p90": float(np.percentile(a, 90))}


def _mean_ci(vals: list[float]) -> tuple[float, float, float]:
    a = np.asarray(vals, float)
    if not len(a):
        return (float("nan"),) * 3
    m = float(a.mean())
    if len(a) < 2:
        return m, m, m
    rng = np.random.default_rng(0)
    bs = [rng.choice(a, len(a)).mean() for _ in range(300)]
    return m, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def seg_tables(rows: list[dict]) -> tuple[str, dict, list]:
    """Per source & structure Dice/IoU, model vs heuristic."""
    from bench.report import table
    by: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if not r.get("ok"):
            continue
        for k, m in r["metrics"].items():
            by[(r["source"], k, r["mode"])].append((r["id"], m))
    srcs = sorted({k[0] for k in by})
    parts = []
    headline = {}
    worst = []
    for src in srcs:
        structs = sorted({k[1] for k in by if k[0] == src})
        trs = []
        for st in structs:
            row = [st]
            for mode in ("model", "heur"):
                items = by.get((src, st, mode), [])
                if not items:
                    row += ["-", "-", "-", "-"]
                    continue
                d = [m["dice"] for _, m in items]
                i = [m["iou"] for _, m in items]
                mm, lo, hi = _mean_ci(d)
                miss = sum(1 for _, m in items if m["missing"])
                row += [f"{mm:.3f} [{lo:.3f}, {hi:.3f}]", f"{np.mean(i):.3f}", f"{np.median(d):.3f}", f"{len(items)} ({miss} sem máscara)"]
                headline[(src, st, mode)] = (mm, lo, hi, len(items))
                swapped = [m for _, m in items if m.get("dice_swapped", 0) > m["dice"] + 0.2]
                if swapped:
                    row[-1] += f"; {len(swapped)} lado trocado"
                for iid, m in sorted(items, key=lambda x: x[1]["dice"])[:3]:
                    worst.append((src, st, mode, iid, m["dice"]))
            trs.append(row)
        parts.append(f"### {src}\n\n" + table(trs, ["estrutura", "Dice modelo [IC95%]", "IoU modelo", "Dice med. modelo", "N modelo",
                                                    "Dice heurística [IC95%]", "IoU heur.", "Dice med. heur.", "N heur."]))
    return "\n\n".join(parts), headline, worst


def ctr_section(rows: list[dict]) -> tuple[str, dict]:
    from bench.report import table
    out_rows, head = [], {}
    for src in sorted({r["source"] for r in rows}):
        for mode in ("model", "heur"):
            rs = [r for r in rows if r.get("ok") and r["source"] == src and r["mode"] == mode and r.get("ctr_gt") is not None]
            if not rs:
                continue
            e = [(abs(r["ctr_ours"] - r["ctr_gt"]) if r.get("ctr_ours") is not None else None) for r in rs]
            have = [x for x in e if x is not None]
            sgn = [r["ctr_ours"] - r["ctr_gt"] for r in rs if r.get("ctr_ours") is not None]
            pm = [abs(r["ctr_from_pred_masks"] - r["ctr_gt"]) for r in rs if r.get("ctr_from_pred_masks") is not None]
            # cardiomegaly (CTR>0.5) agreement
            agree = [(r["ctr_ours"] > 0.5) == (r["ctr_gt"] > 0.5) for r in rs if r.get("ctr_ours") is not None]
            mae = float(np.mean(have)) if have else float("nan")
            lo, hi = _mean_ci(have)[1:] if have else (float("nan"),) * 2
            out_rows.append([src, mode, len(rs), len(rs) - len(have), f"{mae:.3f} [{lo:.3f}, {hi:.3f}]",
                             f"{np.median(have):.3f}" if have else "-", f"{np.mean(sgn):+.3f}" if sgn else "-",
                             f"{np.mean(pm):.3f}" if pm else "-", f"{np.mean(agree):.2f} ({sum(agree)}/{len(agree)})" if agree else "-"])
            head[(src, mode)] = (mae, len(rs))
    if not out_rows:
        return "_Sem máscaras de coração + pulmões para calcular o ICT de referência._", head
    worst = sorted([r for r in rows if r.get("ok") and r.get("ctr_gt") is not None and r.get("ctr_ours") is not None],
                   key=lambda r: -abs(r["ctr_ours"] - r["ctr_gt"]))[:8]
    t = table(out_rows, ["fonte", "caminho", "N", "sem ICT", "erro abs. médio [IC95%]", "mediana", "viés (nosso−GT)",
                         "erro abs. fórmula nas máscaras previstas", "concordância ICT>0,5"])
    t += "\n\nMaiores erros de ICT: " + "; ".join(f"`{r['source']}/{r['id']}` ({r['mode']}: {r['ctr_ours']:.2f} vs GT {r['ctr_gt']:.2f})" for r in worst)
    return t, head


def _timing(rows: list[dict], label: str) -> list:
    out = []
    for mode in ("model", "heur"):
        ts = [r["t"] for r in rows if r.get("ok") and r.get("mode") == mode and r.get("t") is not None]
        if ts:
            out.append([label, mode, len(ts), f"{np.mean(ts):.2f}", f"{np.median(ts):.2f}", f"{np.percentile(ts, 95):.2f}"])
    return out


def iu_eval(rows: list[dict]) -> tuple[str, dict, list]:
    from bench.report import table
    head: dict = {}
    sec = []
    ok = [r for r in rows if r.get("ok")]
    # ---- view classification
    for mode, vsrc_f in [(m, f) for m in ("model", "heur") for f in ("caption", "order")]:
        imgs = [(r["id"], i) for r in ok if r["mode"] == mode for i in r["images"] if "error" not in i]
        imgs = [(sid, i) for sid, i in imgs if view_class(i["gt_view"]) and i.get("vsrc") == vsrc_f]
        if not imgs:
            continue
        cm = Counter()
        for _, i in imgs:
            g = view_class(i["gt_view"])
            p = "frontal" if i["view"] in ("PA", "AP") else "lateral" if i["view"] == "LATERAL" else "other"
            cm[(g, p)] += 1
        n = len(imgs)
        k = cm[("frontal", "frontal")] + cm[("lateral", "lateral")]
        lo, hi = wilson(k, n)
        head[("iu_view", f"{mode}, GT {vsrc_f}")] = (k / n, lo, hi, n)
        wrong = [(sid, i["id"], i["gt_view"], i["view"]) for sid, i in imgs
                 if view_class(i["gt_view"]) != ("frontal" if i["view"] in ("PA", "AP") else "lateral" if i["view"] == "LATERAL" else "other")]
        sec.append(f"**{mode}, GT view_source={vsrc_f}**: acurácia frontal/perfil {k}/{n} = {k / n:.3f} (IC95% {lo:.3f}–{hi:.3f}). Matriz (verdade→previsto): "
                   + ", ".join(f"{g}→{p}: {c}" for (g, p), c in sorted(cm.items()))
                   + (". Erros: " + ", ".join(f"`{w[1]}` (GT {w[2]}, previsto {w[3]})" for w in wrong[:8]) if wrong else ""))
        pa_ap = Counter(i["view"] for _, i in imgs if view_class(i["gt_view"]) == "frontal")
        sec.append(f"  Distribuição PA/AP previstas nos frontais ({mode}/{vsrc_f}): " + ", ".join(f"{a}={b}" for a, b in sorted(pa_ap.items())))
    view_txt = "\n\n".join(sec)

    # ---- findings agreement
    def codes(r):
        return {f["code"] for f in r["findings"]}

    def abn(r):
        return any(f["severity"] in ("abnormal", "critical", "borderline") and f["code"] not in
                   ("rx.technique_limitations", "rx.cardiothoracic_ratio_normal", "rx.lung_volume_asymmetry") for f in r["findings"])

    def smax(r, names):
        v = [i["scores"].get(n) for i in r["images"] if "error" not in i and i.get("scores") for n in names if i["scores"].get(n) is not None]
        return max(v) if v else None

    def ctrmax(r):
        v = [i["ctr"] for i in r["images"] if "error" not in i and i.get("ctr") is not None]
        return max(v) if v else None

    preds = {  # target -> [(name, mode, binary_fn, score_fn)]
        "cardiomegaly": [("regras (rx.cardiomegaly)", "any", lambda r: "rx.cardiomegaly" in codes(r), ctrmax),
                         ("modelo Cardiomegaly", "model", lambda r: "rx.model.cardiomegaly" in codes(r), lambda r: smax(r, ["Cardiomegaly"]))],
        "effusion": [("regras (seio costofrênico)", "any", lambda r: any(c.startswith("rx.costophrenic_blunting") for c in codes(r)), None),
                     ("modelo Effusion", "model", lambda r: "rx.model.effusion" in codes(r), lambda r: smax(r, ["Effusion"]))],
        "pneumothorax": [("modelo Pneumothorax", "model", lambda r: "rx.model.pneumothorax" in codes(r), lambda r: smax(r, ["Pneumothorax"]))],
        "consolidation": [("modelo Consolidation/Pneumonia", "model",
                           lambda r: bool(codes(r) & {"rx.model.consolidation", "rx.model.pneumonia"}), lambda r: smax(r, ["Consolidation", "Pneumonia"]))],
        "atelectasis": [("modelo Atelectasis", "model", lambda r: "rx.model.atelectasis" in codes(r), lambda r: smax(r, ["Atelectasis"]))],
        "diaphragm": [("regras (elevação hemicúpula)", "any", lambda r: any(c.startswith("rx.hemidiaphragm_elevation") for c in codes(r)), None)],
        "normal": [("sem achados anormais (regras+modelo)", "any", lambda r: not abn(r), None),
                   ("1 − máx. escore do modelo", "model", lambda r: not abn(r),
                    lambda r: (1 - max(v for i in r["images"] if "error" not in i for v in (i.get("scores") or {"x": 0}).values())))],
    }
    trs = []
    for tgt in TARGETS:
        for name, need, bfn, sfn in preds[tgt]:
            for mode in ("model", "heur"):
                if need == "model" and mode != "model":
                    continue
                rs = [r for r in ok if r["mode"] == mode and r["gt_labels"] is not None and r["images"]]
                # positives = study has the label; negatives = rx.normal studies (labels are positive-only);
                # for 'normal' itself, negatives = studies with any other mapped label and no rx.normal
                if tgt == "normal":
                    rs = [r for r in rs if "rx.normal" in r["gt_raw"] or (r["gt_raw"] and "rx.normal" not in r["gt_raw"])]
                else:
                    rs = [r for r in rs if tgt in r["gt_labels"] or "rx.normal" in r["gt_raw"]]
                if need == "model":
                    rs = [r for r in rs if any(i.get("scores") for i in r["images"] if "error" not in i)]
                if not rs:
                    continue
                y = [tgt in r["gt_labels"] for r in rs]
                if sum(y) == 0 or sum(y) == len(y):
                    trs.append([tgt, name, mode, len(rs), f"{sum(y)}", "-", "-", "-", "-"])
                    continue
                p = [bool(bfn(r)) for r in rs]
                st = binary_stats(y, p)
                cell = lambda kn: (f"{kn[0] / kn[1]:.2f} [{wilson(*kn)[0]:.2f}, {wilson(*kn)[1]:.2f}]" if kn[1] else "-")
                auc_txt = "-"
                if sfn is not None:
                    sc = [sfn(r) for r in rs]
                    sel = [j for j, v in enumerate(sc) if v is not None]
                    if sel:
                        a, lo, hi = auc_ci([y[j] for j in sel], [sc[j] for j in sel])
                        auc_txt = f"{a:.3f} [{lo:.3f}, {hi:.3f}]"
                        head[("iu_auc", tgt, name, mode)] = (a, lo, hi, len(sel), sum(y[j] for j in sel))
                head[("iu_find", tgt, name, mode)] = (st["sens"], st["spec"], st["ppv"], st["n"], sum(y))
                trs.append([tgt, name, mode, st["n"], f"{sum(y)} ({100 * sum(y) / len(y):.0f}%)", cell(st["sens"]), cell(st["spec"]),
                            cell(st["ppv"]), auc_txt])
    find_txt = table(trs, ["alvo", "preditor", "caminho", "N estudos", "positivos GT", "sensibilidade [IC95%]",
                           "especificidade [IC95%]", "VPP [IC95%]", "AUC [IC95%]"]) if trs else "_Sem estudos IU com rótulos de laudo._"

    # ---- recon
    rc = [(r["id"], r["mode"], r["recon"]) for r in ok if r.get("recon", {}).get("attempted")]
    rtxt = []
    for mode in ("model", "heur"):
        rr = [x for x in rc if x[1] == mode]
        if not rr:
            continue
        k = sum(1 for x in rr if x[2].get("ok"))
        lo, hi = wilson(k, len(rr))
        ts = [x[2]["t"] for x in rr if x[2].get("ok")]
        head[("recon", mode)] = (k / len(rr), lo, hi, len(rr))
        fails = [f"`{x[0]}` ({x[2].get('error', 'vazio')[:60]})" for x in rr if not x[2].get("ok")][:6]
        rtxt.append(f"**{mode}**: sucesso {k}/{len(rr)} = {k / len(rr):.3f} (IC95% {lo:.3f}–{hi:.3f}); tempo médio {np.mean(ts) if ts else float('nan'):.1f} s, "
                    f"p95 {np.percentile(ts, 95) if ts else float('nan'):.1f} s; malhas média {np.mean([x[2].get('n_meshes', 0) for x in rr if x[2].get('ok')] or [0]):.1f}."
                    + (" Falhas: " + ", ".join(fails) if fails else ""))
    # timing rows
    tm = []
    for mode in ("model", "heur"):
        ts = [i["t"] for r in ok if r["mode"] == mode for i in r["images"] if i.get("t") is not None]
        if ts:
            tm.append(["IU analyze_image", mode, len(ts), f"{np.mean(ts):.2f}", f"{np.median(ts):.2f}", f"{np.percentile(ts, 95):.2f}"])
        tr = [x[2]["t"] for x in rc if x[1] == mode and x[2].get("ok")]
        if tr:
            tm.append(["recon3d.reconstruct", mode, len(tr), f"{np.mean(tr):.2f}", f"{np.median(tr):.2f}", f"{np.percentile(tr, 95):.2f}"])
    n_err = sum(1 for r in rows if not r.get("ok")) + sum(1 for r in ok for i in r["images"] if "error" in i)
    return (f"### Classificação de incidência (frontal vs perfil)\n\n{view_txt or '_sem dados_'}\n\n### Achados vs rótulos do laudo\n\n{find_txt}\n\n"
            f"### Reconstrução 3D (pares frontal+perfil)\n\n" + ("\n\n".join(rtxt) or "_sem pares_")), head, tm, n_err


def cap_eval(rows: list[dict]) -> tuple[str, dict]:
    from bench.report import table
    head = {}
    out = []
    trs = []
    for src in sorted({r["source"] for r in rows}):
        for mode in ("model", "heur"):
            rs = [r for r in rows if r["source"] == src and r["mode"] == mode]
            if not rs:
                continue
            fail = [r for r in rs if not r.get("ok")]
            ok = [r for r in rs if r.get("ok")]
            nochest_seg = [r for r in ok if r["region"] == "chest" and r["n_struct"] == 0]
            hk = [r for r in ok if r["hints"].get("region")]
            reg_ok = [r for r in hk if r["region"] == r["hints"]["region"]]
            hv = [r for r in ok if r["hints"].get("view")]
            def vpred(r):
                return "frontal" if r["view"] in ("PA", "AP") else "lateral" if r["view"] == "LATERAL" else "other"
            v_ok = [r for r in hv if vpred(r) == r["hints"]["view"]]
            fr = len(fail) / len(rs)
            lo, hi = wilson(len(fail), len(rs))
            head[("cap_fail", src, mode)] = (fr, lo, hi, len(rs))
            if hk:
                head[("cap_region", src, mode)] = (len(reg_ok) / len(hk), *wilson(len(reg_ok), len(hk)), len(hk))
            if hv:
                head[("cap_view", src, mode)] = (len(v_ok) / len(hv), *wilson(len(v_ok), len(hv)), len(hv))
            c = lambda a, b: f"{a}/{b} = {a / b:.2f} [{wilson(a, b)[0]:.2f}, {wilson(a, b)[1]:.2f}]" if b else "-"
            trs.append([src, mode, len(rs), f"{len(fail)} ({fr:.1%})", f"{len(nochest_seg)}", c(len(reg_ok), len(hk)), c(len(v_ok), len(hv))])
            miss = [f"`{r['id']}` (legenda: {r['hints']['region']}, previsto: {r['region']})" for r in hk if r not in reg_ok][:6]
            mv = [f"`{r['id']}` (legenda: {r['hints']['view']}, previsto: {r['view']})" for r in hv if r not in v_ok][:6]
            if miss or mv or fail:
                out.append(f"- {src}/{mode}: " + ("região divergente " + ", ".join(miss) + ". " if miss else "") +
                           ("incidência divergente " + ", ".join(mv) + ". " if mv else "") +
                           ("falhas " + ", ".join(f"`{r['id']}` ({r.get('error', '')[:50]})" for r in fail[:5]) if fail else ""))
    t = table(trs, ["fonte", "caminho", "N", "falhas", "tórax sem estruturas", "região vs legenda", "incidência vs legenda"]) if trs else "_sem imagens com legenda_"
    # weak label agreement
    lt = []
    for mode in ("model", "heur"):
        for tgt, code_fn, sc_key in [("cardiomegaly", lambda r: "rx.cardiomegaly" in {f["code"] for f in r["findings"]}, "Cardiomegaly"),
                                     ("effusion", lambda r: any(f["code"].startswith("rx.costophrenic_blunting") or f["code"] == "rx.model.effusion" for f in r["findings"]), "Effusion"),
                                     ("pneumothorax", lambda r: "rx.model.pneumothorax" in {f["code"] for f in r["findings"]}, "Pneumothorax"),
                                     ("consolidation", lambda r: bool({f["code"] for f in r["findings"]} & {"rx.model.consolidation", "rx.model.pneumonia"}), "Consolidation"),
                                     ("atelectasis", lambda r: "rx.model.atelectasis" in {f["code"] for f in r["findings"]}, "Atelectasis")]:
            rs = [r for r in rows if r.get("ok") and r["mode"] == mode and r["region"] == "chest" and r["view"] in ("PA", "AP")]
            pos = [r for r in rs if tgt in r["gt_labels"]]
            neg = [r for r in rs if tgt not in r["gt_labels"]]
            if not pos:
                continue
            a = sum(1 for r in pos if code_fn(r))
            b = sum(1 for r in neg if code_fn(r))
            lt.append([tgt, mode, len(pos), len(neg), f"{a / len(pos):.2f} ({a}/{len(pos)})", f"{b / len(neg):.2f} ({b}/{len(neg)})" if neg else "-"])
    lab = table(lt, ["alvo (legenda cita)", "caminho", "N legenda+", "N demais", "% sinalizado nos legenda+", "% sinalizado nos demais"]) if lt else "_Sem legendas com alvos positivos._"
    return t + "\n\n" + "\n".join(out) + "\n\nConcordância fraca de rótulos (legenda → nosso achado; evidência fraca, legendas citam o que é notável):\n\n" + lab, head


def build_report(path: Optional[Path] = None) -> Path:
    from bench.report import table, write_markdown
    seg = list(load_cache("seg").values())
    iu = list(load_cache("iu").values())
    cap = list(load_cache("cap").values())
    sections = []
    headline = []
    caveats = [
        "Imagens reduzidas a no máx. 1024 px no maior lado; máscaras de referência redimensionadas por vizinho mais próximo.",
        "Convenção de lado: pulmão/clavícula 'esquerdo' = lado esquerdo do paciente (lado direito da imagem). Colunas 'lado trocado' contam imagens em que o Dice com a estrutura contralateral supera em > 0,2; indicam convenção invertida na máscara de referência ou erro de lado.",
        "ICT nosso = largura do coração / largura dos campos pulmonares (proxy da largura torácica interna); o ICT de referência usa a mesma fórmula nas máscaras manuais (não a largura torácica interna real).",
        "Rótulos IU vêm dos laudos (mapeamento por texto/etiquetas, estudo-nível): positivos podem não estar visíveis na imagem; a ausência de menção é tratada como negativo. Escores do DenseNet foram treinados também com IU (nih-pc-chex-mimic_ch-google-openi-kaggle) — risco de vazamento, as métricas de modelo no IU são otimistas.",
        "PA/AP: sem tags DICOM nas imagens PNG a incidência frontal assume PA; só frontal vs perfil é avaliado como acerto.",
        "Legendas de artigos/Wikimedia: dica de região/incidência é heurística de texto (regex) e rótulos são evidência fraca; figuras podem ter painéis múltiplos, setas e texto sobre a imagem.",
    ]
    if seg:
        t, h, worst = seg_tables(seg)
        sections.append(("Segmentação vs máscaras de referência (Dice / IoU por estrutura)", t))
        for (src, st, mode), (m, lo, hi, n) in sorted(h.items()):
            if st in ("lungs", "heart"):
                headline.append([f"Segmentação {st} ({src}, {mode})", "Dice médio [IC95%]", n, f"{m:.3f} [{lo:.3f}, {hi:.3f}]"])
        wt = table([[s, st, mode, f"`{iid}`", f"{d:.3f}"] for s, st, mode, iid, d in sorted(worst, key=lambda x: x[4])[:30]],
                   ["fonte", "estrutura", "caminho", "id", "Dice"])
        sections.append(("Piores casos de segmentação", wt))
        ct, ch = ctr_section(seg)
        sections.append(("ICT: referência (máscaras) vs nosso", ct))
        for (src, mode), (mae, n) in sorted(ch.items()):
            headline.append([f"ICT erro absoluto ({src}, {mode})", "MAE", n, f"{mae:.3f}"])
        errs = [r for r in seg if not r.get("ok")]
        if errs:
            sections.append(("Falhas de segmentação", f"{len(errs)} falhas; exemplos: " + "; ".join(f"`{r['source']}/{r['id']}` {r['error'][:80]}" for r in errs[:8])))
    iu_tm, cap_tm = [], []
    if iu:
        t, h, tm, nerr = iu_eval(iu)
        sections.append(("IU X-ray", t))
        iu_tm = tm
        for (k, *rest), v in sorted(h.items(), key=lambda x: str(x)):
            if k == "iu_view":
                headline.append([f"IU incidência frontal/perfil ({rest[0]})", "acurácia [IC95%]", v[3], f"{v[0]:.3f} [{v[1]:.3f}, {v[2]:.3f}]"])
            elif k == "recon":
                headline.append([f"IU reconstrução 3D ({rest[0]})", "taxa de sucesso [IC95%]", v[3], f"{v[0]:.3f} [{v[1]:.3f}, {v[2]:.3f}]"])
            elif k == "iu_auc" and rest[2] == "model":
                headline.append([f"IU {rest[0]}: {rest[1]}", "AUC [IC95%]", f"{v[3]} (pos {v[4]})", f"{v[0]:.3f} [{v[1]:.3f}, {v[2]:.3f}]"])
        errs = [r for r in iu if not r.get("ok")]
        if errs:
            sections.append(("Falhas IU", f"{len(errs)} estudos com erro; exemplos: " + "; ".join(f"`{r['id']}` {r['error'][:80]}" for r in errs[:8])))
    if cap:
        t, h = cap_eval(cap)
        sections.append(("Imagens com legenda (Europe PMC / Wikimedia)", t))
        cap_tm = _timing([r for r in cap], "legendadas analyze_image")
        for (k, src, mode), v in sorted(h.items()):
            nm = {"cap_fail": "taxa de falha", "cap_region": "região vs legenda", "cap_view": "incidência vs legenda"}[k]
            headline.append([f"Legendadas {src} ({mode})", nm, v[3], f"{v[0]:.3f} [{v[1]:.3f}, {v[2]:.3f}]"])
    tm = _timing(seg, "máscaras analyze_image") + iu_tm + cap_tm
    if tm:
        sections.append(("Tempos (s, 1 thread por worker)", table(tm, ["etapa", "caminho", "N", "média", "mediana", "p95"])))
    sections.append(("Ressalvas", "\n".join(f"- {c}" for c in caveats)))
    if headline:
        sections.insert(0, ("Resumo", table(headline, ["capacidade", "métrica", "N", "valor"])))
    else:
        sections.insert(0, ("Resumo", "_Nenhum resultado em cache ainda — rode `python -m bench.rx_bench`._"))
    path = path or (REPO / "docs" / "benchmarks" / "rx.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_markdown(path, "Benchmark RX (MedLens)", sections)


# ======================================================================================= CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench.rx_bench")
    ap.add_argument("--source", choices=list(SOURCE_ARG), default="all")
    ap.add_argument("--limit", type=int, default=None, help="max items (seg/cap) or studies (iu) per source")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 0))
    ap.add_argument("--models", choices=["on", "off", "both"], default="both")
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    modes = ["model", "heur"] if a.models == "both" else [MODES[a.models]]
    if not a.report_only:
        for kind in SOURCE_ARG[a.source]:
            run_kind(kind, modes, a.limit, a.workers, a.max_side)
    p = build_report(a.out)
    print("report:", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
