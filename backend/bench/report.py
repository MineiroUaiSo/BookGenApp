"""Tiny shared helpers for benchmark reports (markdown). Used by ecg_bench and rx_bench.

    table(rows, headers) -> str                      GitHub-flavoured markdown table
    write_markdown(path, title, sections) -> Path     sections = [(heading, body_markdown), ...]
    wilson(k, n, z=1.96) -> (lo, hi)                  Wilson score interval for a proportion
    pct(k, n) -> "87.5% (7/8)"
    fmt(x, nd=1) -> str                               None/NaN -> "-"
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
    if ci:
        lo, hi = wilson(k, n)
        s = f"{100.0 * k / n:.1f}% [{max(0, 100 * lo):.1f}-{100 * hi:.1f}] (n={n})"
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
