"""Tiny shared helpers for benchmark reports (markdown). Used by ecg_bench and rx_bench.

    table(rows, headers) -> str                      GitHub-flavoured markdown table
    write_markdown(path, title, sections) -> Path     sections = [(heading, body_markdown), ...]
    wilson(k, n, z=1.96) -> (lo, hi)                  Wilson score interval for a proportion
    pct(k, n) -> "87.5% (7/8)"
    fmt(x, nd=1) -> str                               None/NaN -> "-"
    bootstrap_ci / bootstrap_mean_ci / bootstrap_binary_ci / bootstrap_prop_ci / fmt_ci   2000-resample bootstrap CIs, "74,5% [62,1–85,0]"
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


def fmt(x, nd: int = 1) -> str:
    if x is None:
        return "-"
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return "-"
        if isinstance(x, (int,)) and not isinstance(x, bool):
            return str(x)
        return f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def pct(k: int, n: int, ci: bool = False) -> str:
    if n <= 0:
        return "-"
    s = f"{100.0 * k / n:.1f}% ({k}/{n})"
    if ci:  # bootstrap CI (2000 resamples, fixed seed), "74,5% [62,1–85,0] (n=..)"
        s = f"{fmt_ci(*bootstrap_prop_ci(k, n))} (n={n})"
    return s


def table(rows: Iterable[Sequence], headers: Sequence[str]) -> str:
    rows = [[("" if c is None else str(c)).replace("|", "\\|").replace("\n", " ") for c in r] for r in rows]
    headers = [str(h).replace("|", "\\|") for h in headers]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def write_markdown(path, title: str, sections: Sequence[tuple[str, str]], preamble: str = "") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"# {title}", "", f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `bench`._", ""]
    if preamble:
        parts += [preamble, ""]
    for h, body in sections:
        parts += [f"## {h}", "", body.rstrip(), ""]
    p.write_text("\n".join(parts), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------------------------
# Bootstrap confidence intervals (R2 evaluation base). ONE implementation shared by ecg_bench / rx_bench.
#   - percentile bootstrap, BOOT_N resamples, fixed seed -> fully deterministic
#   - resampling unit = the record (ECG) / study (RX)
#   - fmt_ci(...) -> "74,5% [62,1–85,0]" (decimal comma, en dash)
# ---------------------------------------------------------------------------------------------
BOOT_N = 2000
BOOT_SEED = 20261124
_NAN = float("nan")


def _pctl(vals, alpha: float = 0.05):
    import numpy as np
    a = np.asarray(vals, float)
    a = a[~np.isnan(a)]
    if not len(a):
        return _NAN, _NAN
    return float(np.percentile(a, 100 * alpha / 2)), float(np.percentile(a, 100 * (1 - alpha / 2)))


def bootstrap_ci(stat, *arrays, n_boot: int = BOOT_N, seed: int = BOOT_SEED, alpha: float = 0.05):
    """Percentile bootstrap CI of stat(*arrays) resampling records (rows) with replacement.

    arrays: equal-length sequences (resampled with the same indices). Returns (point, lo, hi); NaN replicates
    (e.g. an AUC resample without positives) are dropped. Deterministic for a given seed."""
    import numpy as np
    arrs = [np.asarray(a) for a in arrays]
    n = len(arrs[0])
    if n == 0:
        return _NAN, _NAN, _NAN
    point = float(stat(*arrs))
    rng = np.random.default_rng(seed)
    reps = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        reps[b] = stat(*[a[idx] for a in arrs])
    lo, hi = _pctl(reps, alpha)
    return point, lo, hi


def bootstrap_mean_ci(values, n_boot: int = BOOT_N, seed: int = BOOT_SEED):
    """Bootstrap CI of the mean (fast vectorised path), NaN values removed."""
    import numpy as np
    a = np.asarray([v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))], float)
    if not len(a):
        return _NAN, _NAN, _NAN
    rng = np.random.default_rng(seed)
    reps = np.concatenate([a[rng.integers(0, len(a), (min(250, n_boot - i), len(a)))].mean(axis=1)
                           for i in range(0, n_boot, 250)])
    lo, hi = _pctl(reps)
    return float(a.mean()), lo, hi


def _safe_div(a, b):
    import numpy as np
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(b > 0, a / np.where(b > 0, b, 1), np.nan)


def bootstrap_binary_ci(tp: int, fp: int, fn: int, tn: int, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """Bootstrap CIs of sens/spec/PPV/accuracy for a binary classifier given its confusion counts.

    Resampling N records with replacement and re-counting TP/FP/FN/TN is *exactly* a multinomial draw of N records
    over the four cells (probabilities = observed cell fractions), so the draw is done directly (fast and identical
    in distribution to per-record resampling). Returns {"sens","spec","ppv","acc"} -> (point, lo, hi); a statistic whose
    denominator is 0 in the sample is (nan, nan, nan); replicates with an empty denominator are dropped."""
    import numpy as np
    n = tp + fp + fn + tn
    out = {}
    pts = {"sens": (tp, tp + fn), "spec": (tn, tn + fp), "ppv": (tp, tp + fp), "acc": (tp + tn, n)}
    if n == 0:
        return {k: (_NAN, _NAN, _NAN) for k in pts}
    rng = np.random.default_rng(seed)
    cells = rng.multinomial(n, np.array([tp, fp, fn, tn], float) / n, size=n_boot)
    b_tp, b_fp, b_fn, b_tn = (cells[:, i] for i in range(4))
    reps = {"sens": _safe_div(b_tp, b_tp + b_fn), "spec": _safe_div(b_tn, b_tn + b_fp),
            "ppv": _safe_div(b_tp, b_tp + b_fp), "acc": _safe_div(b_tp + b_tn, np.full(n_boot, n))}
    for k, (num, den) in pts.items():
        if den == 0:
            out[k] = (_NAN, _NAN, _NAN)
        else:
            lo, hi = _pctl(reps[k])
            out[k] = (num / den, lo, hi)
    return out


def bootstrap_binary_arrays(gold, pred, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """bootstrap_binary_ci from per-record boolean arrays (gold, pred). Adds the counts under key "counts"."""
    import numpy as np
    g = np.asarray(gold, bool)
    p = np.asarray(pred, bool)
    tp, fp = int((g & p).sum()), int((~g & p).sum())
    fn, tn = int((g & ~p).sum()), int((~g & ~p).sum())
    res = bootstrap_binary_ci(tp, fp, fn, tn, n_boot, seed)
    res["counts"] = (tp, fp, fn, tn)
    return res


def bootstrap_prop_ci(k: int, n: int, n_boot: int = BOOT_N, seed: int = BOOT_SEED):
    """Bootstrap CI of a proportion k/n (per-record resampling == binomial draw)."""
    import numpy as np
    if n <= 0:
        return _NAN, _NAN, _NAN
    rng = np.random.default_rng(seed)
    lo, hi = _pctl(rng.binomial(n, k / n, size=n_boot) / n)
    return k / n, lo, hi


def fmt_ci(point, lo, hi, nd: int = 1, percent: bool = True, unit: str = "") -> str:
    """"74,5% [62,1–85,0]" (percent=True, inputs are fractions) or "-3,2 ms [-4,1–-2,3]" (percent=False)."""
    def one(x):
        if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
            return None
        return f"{100 * x if percent else x:.{nd}f}".replace(".", ",")
    p, l, h = one(point), one(lo), one(hi)
    if p is None:
        return "-"
    suffix = "%" if percent else (f" {unit}" if unit else "")
    if l is None or h is None:
        return f"{p}{suffix}"
    return f"{p}{suffix} [{l}–{h}]"
