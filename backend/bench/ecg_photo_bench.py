"""Benchmark of the ECG *photo* pipeline (digitizer) with real ground truth.

PTB-XL development records (strat_fold 1-8 only, never the 9-10 test folds) are rendered as printed 12-lead ECG
paper (matplotlib), degraded like a phone photo (rotation, perspective, blur, noise, shadow, JPEG), pushed through
app.ecg.digitize.digitize_image and compared with the original signal.

    python -m bench.ecg_photo_bench --tag H [--limit 200] [--workers 3] [--force] [--source ptbxl|synth]

Metrics: % usable (no exception, grid_conf >= 0.3, >= 2 beats), exceptions by cause, median Pearson per lead,
RR / QRS / QT error, and agreement of the rule-based findings (BRD/BRE/WPW/IAM/NORM) with the truth signal.
Images and caches live under $MEDLENS_BENCH/ecg_photo/<tag>/ (never versioned).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
BENCH_ROOT = Path(os.environ.get("MEDLENS_BENCH", REPO / "data" / "bench")) / "ecg_photo"
DEV_FOLDS = range(1, 9)  # PTB-XL folds 9-10 are held-out test: never used for tuning
FS = 500.0
LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
GRID_ROWS = [["I", "aVR", "V1", "V4"], ["II", "aVL", "V2", "V5"], ["III", "aVF", "V3", "V6"]]
PROFILES = ("clean", "mild", "hard")

# stratum -> PTB-XL SCP codes (a record is assigned to the first stratum it matches; NORM must be pure)
STRATA: dict[str, set[str]] = {
    "WPW": {"WPW"},
    "BRE": {"CLBBB", "ILBBB"},
    "BRD": {"CRBBB", "IRBBB"},
    "IAM": {"IMI", "ASMI", "ILMI", "AMI", "ALMI", "LMI", "IPLMI", "IPMI", "INJAS", "INJAL", "INJIN", "INJIL", "INJLA"},
    "NORM": {"NORM"},
}
# stratum -> gold key in ecg_bench.GOLD_SCP / ecg_bench.PRED
STRATUM_KEY = {"WPW": "WPW", "BRE": "LBBB_any", "BRD": "RBBB_any", "IAM": "MI_any", "NORM": "NORM"}


# ------------------------------------------------------------------------------------------ selection
def stratum_of(scp: dict[str, float]) -> str | None:
    codes = {k for k, v in scp.items() if v is None or float(v) >= 50.0} or set(scp)
    for name in ("WPW", "BRE", "BRD", "IAM"):
        if codes & STRATA[name]:
            return name
    if codes == {"NORM"} or (codes <= {"NORM", "SR"} and "NORM" in codes):
        return "NORM"
    return None


def select_records(recs: list[dict], limit: int, seed: int = 0, parse_scp=None) -> list[dict]:
    """Stratified, deterministic pick of dev-fold records. Rare classes (WPW) take all they have, the rest is split
    evenly; leftover quota goes to NORM/BRD/IAM."""
    from bench.ecg_bench import parse_scp as _p
    parse_scp = parse_scp or _p
    pools: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        fo = (r.get("extra") or {}).get("strat_fold")
        try:
            if int(float(fo)) not in DEV_FOLDS:
                continue
        except (TypeError, ValueError):
            continue
        s = stratum_of(parse_scp(r))
        if s:
            pools[s].append(r)
    rng = np.random.default_rng(seed)
    for s in pools:
        pools[s].sort(key=lambda r: r["id"])
        rng.shuffle(pools[s])
    names = [s for s in STRATA if pools.get(s)]
    quota = {s: 0 for s in names}
    left = limit
    while left > 0 and names:
        open_ = [s for s in names if quota[s] < len(pools[s])]
        if not open_:
            break
        share = max(1, left // len(open_))
        for s in open_:
            take = min(share, len(pools[s]) - quota[s], left)
            quota[s] += take
            left -= take
            if left <= 0:
                break
    out = []
    for s in names:
        for r in pools[s][:quota[s]]:
            out.append({**r, "_stratum": s})
    return out


# ------------------------------------------------------------------------------------------ rendering
def _fit500(sig_leads: dict[str, list[float]], fs: float) -> dict[str, np.ndarray]:
    from scipy.signal import resample_poly
    out = {}
    for k in LEADS:
        if k not in sig_leads:
            continue
        y = np.asarray(sig_leads[k], float)
        if abs(fs - FS) > 1e-6:
            from fractions import Fraction
            fr = Fraction(FS / fs).limit_denominator(100)
            y = resample_poly(y, fr.numerator, fr.denominator)
        y = np.nan_to_num(y)
        n = int(10 * FS)
        out[k] = y[:n] if len(y) >= n else np.pad(y, (0, n - len(y)), mode="edge")
    return out


def render_ecg_page(leads: dict[str, np.ndarray], px_per_mm: float = 8.0, gain_mm_mv: float = 10.0,
                    speed_mm_s: float = 25.0, seed: int = 0) -> np.ndarray:
    """Draw a 3x4 + II rhythm-strip ECG on pink paper (A4 landscape, 297x210 mm) with matplotlib; RGB uint8."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.collections import LineCollection
    from matplotlib.figure import Figure
    rng = np.random.default_rng(seed)
    W, H = 297.0, 210.0
    fig = Figure(figsize=(W / 25.4, H / 25.4), dpi=px_per_mm * 25.4)
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    tint = rng.uniform(-12, 12)
    minor = (1.0, 0.80 + tint / 255, 0.80 + tint / 255)
    major = (0.95, 0.55 + tint / 255, 0.55 + tint / 255)
    xs = np.arange(0, W + 0.01, 1.0)
    ys = np.arange(0, H + 0.01, 1.0)
    for coll, col, lw, sel in (
            (None, minor, 0.15, lambda v: v % 5 != 0), (None, major, 0.45, lambda v: v % 5 == 0)):
        segs = [[(x, 0), (x, H)] for x in xs if sel(x)] + [[(0, y), (W, y)] for y in ys if sel(y)]
        ax.add_collection(LineCollection(segs, colors=[col], linewidths=lw))
    pitch, y0, x_data = 38.0, 32.0, 15.0  # data starts where the calibration pulse ends
    seg = 2.5 * speed_mm_s
    tr = []

    def row_y(r):
        return y0 + r * pitch

    for r in range(4):
        y = row_y(r)
        h = 10.0 * gain_mm_mv / 10.0
        tr.append([(8, y), (10, y), (10, y - h), (15, y - h), (15, y)])
    for r, names in enumerate(GRID_ROWS):
        for c, name in enumerate(names):
            y = row_y(r)
            seg_y = leads[name][int(2.5 * c * FS):int(2.5 * (c + 1) * FS)]
            x = x_data + c * seg + np.arange(len(seg_y)) / FS * speed_mm_s
            tr.append(np.c_[x, y - seg_y * gain_mm_mv])
            ax.text(x[0] + 1.0, y - 11.0, name, fontsize=7, color="black")
            if c > 0:
                tr.append([(x[0], y - 2), (x[0], y + 2)])
    y = row_y(3)
    full = leads["II"]
    x = x_data + np.arange(len(full)) / FS * speed_mm_s
    tr.append(np.c_[x, y - full * gain_mm_mv])
    ax.text(x[0] + 1.0, y - 11.0, "II", fontsize=7, color="black")
    ax.add_collection(LineCollection(tr, colors=["#101010"], linewidths=0.65, capstyle="round", joinstyle="round"))
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
    return buf


def degrade(img: np.ndarray, profile: str, seed: int = 0) -> np.ndarray:
    """Phone-photo degradations; profile in PROFILES. Deterministic given seed."""
    import cv2
    rng = np.random.default_rng(seed)
    if profile == "clean":
        rot, persp, blur, noise, shadow, jpeg, scale = 0.0, 0.0, 0.0, 0.0, 0.0, 92, 1.0
    elif profile == "mild":
        rot, persp, blur, noise, shadow, jpeg, scale = 2.0, 0.012, 0.8, 3.0, 0.15, 75, 0.9
    else:
        rot, persp, blur, noise, shadow, jpeg, scale = 5.0, 0.035, 1.6, 8.0, 0.40, 50, 0.65
    h, w = img.shape[:2]
    out = img
    if scale != 1.0:
        out = cv2.resize(out, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h, w = out.shape[:2]
    if rot or persp:
        a = np.deg2rad(rng.uniform(-rot, rot))
        c, s = np.cos(a), np.sin(a)
        corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        ctr = np.float32([w / 2, h / 2])
        rotated = (corners - ctr) @ np.float32([[c, -s], [s, c]]).T + ctr
        jit = rng.uniform(-persp, persp, (4, 2)).astype(np.float32) * np.float32([w, h])
        dst = rotated + jit
        m = cv2.getPerspectiveTransform(corners, dst.astype(np.float32))
        out = cv2.warpPerspective(out, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                  borderValue=(190, 185, 180))
    out = out.astype(np.float32)
    if shadow:
        gx, gy = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
        ang = rng.uniform(0, 2 * np.pi)
        g = np.cos(ang) * gx + np.sin(ang) * gy
        g = (g - g.min()) / max(1e-6, g.max() - g.min())
        out *= (1.0 - shadow * g)[:, :, None]
    if blur:
        out = cv2.GaussianBlur(out, (0, 0), blur)
    if noise:
        out += rng.normal(0, noise, out.shape).astype(np.float32)
    out = np.clip(out, 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", out[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, int(jpeg)])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)[:, :, ::-1].copy()


# ------------------------------------------------------------------------------------------ metrics
def _pearson(a: np.ndarray, b: np.ndarray, max_lag: int) -> float:
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    best = -1.0
    for d in range(-max_lag, max_lag + 1):
        x, y = np.roll(a, d)[max_lag + 1:n - max_lag - 1], b[max_lag + 1:n - max_lag - 1]
        if len(x) < 10 or x.std() < 1e-9 or y.std() < 1e-9:
            continue
        best = max(best, float(np.corrcoef(x, y)[0, 1]))
    return best


def lead_correlations(sig, truth: dict[str, np.ndarray], max_lag_ms: float = 40.0) -> dict[str, float]:
    out = {}
    k = int(max_lag_ms * FS / 1000)
    for name, y in sig.leads.items():
        if name not in truth:
            continue
        y = np.asarray(y, float)
        off = int(round(float((sig.calibration or {}).get(f"offset_s.{name}", 0.0)) * FS))
        t = truth[name][off:off + len(y)]
        if len(t) < 100:
            continue
        out[name] = _pearson(y, t, k)
    return out


def classify_exception(exc: BaseException) -> dict:
    """Cause = exception type + normalised message; where = innermost frame inside app/."""
    tb = traceback.extract_tb(exc.__traceback__)
    where = next((f"{Path(f.filename).name}:{f.lineno}" for f in reversed(tb) if "/app/" in f.filename), "?")
    msg = re.sub(r"\d+(\.\d+)?", "N", str(exc))[:80]
    return {"type": type(exc).__name__, "msg": msg, "where": where}


def _gm(an) -> dict:
    g = an.global_measurements
    return {"rr": g.rr_mean_ms, "qrs": g.qrs_ms, "qt": g.qt_ms, "hr": getattr(g, "heart_rate_bpm", None)}


def _task(job: dict) -> dict:
    """Render -> degrade -> digitize -> compare. Never raises: failures are returned with their cause."""
    from app.ecg.analysis import analyze_signal
    from app.ecg.digitize import digitize_image
    from bench.ecg_bench import _findings
    res: dict = {"id": job["id"], "stratum": job["stratum"], "profile": job["profile"], "ok": False}
    try:
        truth = {k: np.asarray(v, float) for k, v in job["truth"].items()} if "truth" in job else \
            _load_truth(job["path"])
        img_path = Path(job["img"])
        if img_path.exists():
            import cv2
            deg = cv2.imread(str(img_path))[:, :, ::-1]
        else:
            page = render_ecg_page(truth, px_per_mm=job.get("ppm", 8.0), seed=job["seed"])
            deg = degrade(page, job["profile"], job["seed"])
            img_path.parent.mkdir(parents=True, exist_ok=True)
            import cv2
            cv2.imwrite(str(img_path), deg[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 95])
    except Exception as e:  # truth/render failure is a bench bug, not a digitizer failure
        res["stage"] = "render"
        res["exc"] = classify_exception(e)
        return res
    t0 = time.time()
    try:
        sig = digitize_image(deg)
    except Exception as e:
        res["stage"] = "digitize"
        res["exc"] = classify_exception(e)
        res["t_s"] = round(time.time() - t0, 2)
        return res
    res["t_s"] = round(time.time() - t0, 2)
    res["ok"] = True
    cal = sig.calibration or {}
    res["grid_conf"] = float(cal.get("grid_confidence", 0.0) or 0.0)
    res["n_leads"] = len(sig.leads)
    res["corr"] = lead_correlations(sig, truth)
    try:
        an = analyze_signal(sig, job["id"])
        res["n_beats"] = len(an.r_peaks_ms)
        res["gm"] = _gm(an)
        res["codes"] = sorted({f["code"] for f in _findings(an)})
        tr_sig = _truth_signal(truth)
        tan = analyze_signal(tr_sig, job["id"] + "-truth")
        res["truth_gm"] = _gm(tan)
        res["truth_codes"] = sorted({f["code"] for f in _findings(tan)})
    except Exception as e:
        res["stage"] = "analyze"
        res["exc_analyze"] = classify_exception(e)
        res.setdefault("n_beats", 0)
    return res


def _truth_signal(truth: dict[str, np.ndarray]):
    from app.schemas import ECGSignal, SourceKind
    return ECGSignal(fs=FS, leads={k: v.tolist() for k, v in truth.items()}, duration_s=len(truth["II"]) / FS,
                     source=SourceKind.WFDB)


def _load_truth(path: str) -> dict[str, np.ndarray]:
    from app.ecg.ingest import load_ecg
    sig = load_ecg(path)
    return _fit500(sig.leads, sig.fs)


def is_usable(r: dict) -> bool:
    return bool(r.get("ok") and (r.get("grid_conf") or 0) >= 0.3 and r.get("n_beats", 0) >= 2)


# ------------------------------------------------------------------------------------------ report
def _med(x):
    x = [v for v in x if v is not None and np.isfinite(v)]
    return float(np.median(x)) if x else None


def summarize(results: list[dict]) -> dict:
    n = len(results)
    usable = [r for r in results if is_usable(r)]
    exc = [r for r in results if not r["ok"] and "exc" in r]
    causes = Counter(f"{r['exc']['type']}: {r['exc']['msg']} @ {r['exc']['where']}" for r in exc)
    per_lead: dict[str, list[float]] = defaultdict(list)
    all_corr = []
    for r in results:
        if r.get("ok"):
            for k, v in (r.get("corr") or {}).items():
                per_lead[k].append(v)
            if r.get("corr"):
                all_corr.append(_med(list(r["corr"].values())))
    err = {"rr": [], "qrs": [], "qt": []}
    for r in usable:
        for k in err:
            a, b = (r.get("gm") or {}).get(k), (r.get("truth_gm") or {}).get(k)
            if a is not None and b is not None:
                err[k].append(abs(a - b))
    from bench.ecg_bench import PRED
    det: dict[str, dict] = {}
    for s, key in STRATUM_KEY.items():
        rs = [r for r in results if r["stratum"] == s and "truth_codes" in r]
        if not rs or key not in PRED:
            continue
        f = PRED[key]
        hit_img = sum(bool(f(set(r.get("codes") or []))) for r in rs if r.get("ok"))
        hit_truth = sum(bool(f(set(r["truth_codes"]))) for r in rs)
        det[s] = {"n": len(rs), "detected_on_truth": hit_truth,
                  "detected_on_photo": hit_img, "photo_given_truth_pct": None}
        both = sum(bool(f(set(r.get("codes") or []))) and bool(f(set(r["truth_codes"]))) for r in rs if r.get("ok"))
        det[s]["photo_given_truth_pct"] = round(100 * both / hit_truth, 1) if hit_truth else None
    by_profile = {}
    for p in PROFILES:
        rp = [r for r in results if r["profile"] == p]
        if rp:
            by_profile[p] = {"n": len(rp), "usable_pct": round(100 * sum(map(is_usable, rp)) / len(rp), 1)}
    by_stratum = {}
    for s in STRATA:
        rs = [r for r in results if r["stratum"] == s]
        if rs:
            by_stratum[s] = {"n": len(rs), "usable_pct": round(100 * sum(map(is_usable, rs)) / len(rs), 1)}
    return {
        "n": n, "usable": len(usable), "usable_pct": round(100 * len(usable) / max(1, n), 1),
        "exceptions": len(exc), "causes": causes.most_common(),
        "median_corr_overall": _med(all_corr), "median_corr_per_lead": {k: _med(v) for k, v in sorted(per_lead.items())},
        "median_abs_err_ms": {k: _med(v) for k, v in err.items()}, "n_err": {k: len(v) for k, v in err.items()},
        "detection": det, "by_profile": by_profile, "by_stratum": by_stratum,
    }


def render_report(s: dict, tag: str) -> str:
    L = [f"# ECG photo bench (tag {tag})", "",
         f"- N = {s['n']}; usable = {s['usable']} ({s['usable_pct']}%); exceptions = {s['exceptions']}",
         f"- median Pearson (median over leads, per image): {s['median_corr_overall']}", "",
         "## Exceptions by cause", ""]
    L += [f"- {c} x{k}" for c, k in s["causes"]] or ["- none"]
    L += ["", "## Usable by profile / stratum", ""]
    L += [f"- {k}: {v['usable_pct']}% (n={v['n']})" for k, v in {**s["by_profile"], **s["by_stratum"]}.items()]
    L += ["", "## Median Pearson per lead", ""]
    L += [f"- {k}: {None if v is None else round(v, 3)}" for k, v in s["median_corr_per_lead"].items()]
    L += ["", "## Median abs error (ms) vs truth signal, usable images", ""]
    L += [f"- {k}: {None if v is None else round(v, 1)} (n={s['n_err'][k]})" for k, v in s["median_abs_err_ms"].items()]
    L += ["", "## Rule detection on photo (given detected on truth signal)", ""]
    L += [f"- {k}: n={v['n']} truth={v['detected_on_truth']} photo={v['detected_on_photo']} "
          f"photo|truth={v['photo_given_truth_pct']}%" for k, v in s["detection"].items()]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------------------------------ main
def build_jobs(recs: list[dict], out_dir: Path, seed: int = 0) -> list[dict]:
    from bench.ecg_bench import resolve
    jobs = []
    for i, r in enumerate(recs):
        profile = PROFILES[i % len(PROFILES)]
        jobs.append({"id": r["id"], "stratum": r["_stratum"], "profile": profile, "seed": seed * 100003 + i,
                     "path": str(resolve("ptbxl", r["path"])), "img": str(out_dir / "img" / f"{r['id']}_{profile}.jpg")})
    return jobs


def run(jobs: list[dict], out_dir: Path, workers: int, force: bool) -> list[dict]:
    cache = out_dir / "results.jsonl"
    done: dict[str, dict] = {}
    if cache.exists() and not force:
        for ln in cache.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                done[r["id"]] = r
    todo = [j for j in jobs if j["id"] not in done]
    out_dir.mkdir(parents=True, exist_ok=True)
    workers = max(1, min(3, workers))  # hard cap: other tracks run in parallel
    with cache.open("a" if not force else "w") as fh:
        if workers == 1 or len(todo) <= 1:
            it = map(_task, todo)
            for r in it:
                done[r["id"]] = r
                fh.write(json.dumps(r) + "\n")
                fh.flush()
        else:
            with ProcessPoolExecutor(workers) as ex:
                for r in ex.map(_task, todo, chunksize=2):
                    done[r["id"]] = r
                    fh.write(json.dumps(r) + "\n")
                    fh.flush()
    return [done[j["id"]] for j in jobs if j["id"] in done]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", required=True, help="cache/report namespace (never touches docs/benchmarks/ecg.md)")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args(argv)
    from bench.ecg_bench import read_manifest
    out_dir = BENCH_ROOT / a.tag
    recs = [r for r in read_manifest("ptbxl") if r.get("kind", "signal") != "image"]
    if not recs:
        print("no PTB-XL manifest at $MEDLENS_DATASETS/ptbxl/manifest.jsonl; nothing to do")
        return 2
    from bench.ecg_bench import resolve
    recs = [r for r in recs if resolve("ptbxl", r["path"]).exists()
            and resolve("ptbxl", r["path"]).with_suffix(".dat").exists()]  # download may still be running
    sel = select_records(recs, a.limit, a.seed)
    print(f"selected {len(sel)}: {dict(Counter(r['_stratum'] for r in sel))}")
    jobs = build_jobs(sel, out_dir, a.seed)
    results = run(jobs, out_dir, a.workers, a.force) if not a.report_only else \
        [json.loads(x) for x in (out_dir / "results.jsonl").read_text().splitlines() if x.strip()]
    s = summarize(results)
    md = render_report(s, a.tag)
    (out_dir / "report.md").write_text(md)
    (out_dir / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
