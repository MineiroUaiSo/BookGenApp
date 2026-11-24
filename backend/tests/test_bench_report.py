"""Deterministic tests of the shared bootstrap CI helpers (bench/report.py)."""
from __future__ import annotations

import math

import numpy as np

from bench.report import (BOOT_N, bootstrap_binary_arrays, bootstrap_binary_ci, bootstrap_ci, bootstrap_mean_ci,
                          bootstrap_prop_ci, fmt_ci)


def test_fmt_ci_percent_uses_decimal_comma_and_en_dash():
    assert fmt_ci(0.745, 0.621, 0.85) == "74,5% [62,1–85,0]"


def test_fmt_ci_numeric_with_unit_and_nan():
    assert fmt_ci(-3.24, -4.11, -2.3, percent=False, unit="ms") == "-3,2 ms [-4,1–-2,3]"
    assert fmt_ci(float("nan"), 0.1, 0.2) == "-"
    assert fmt_ci(0.5, float("nan"), float("nan")) == "50,0%"


def test_boot_n_is_2000():
    assert BOOT_N == 2000


def test_binary_ci_perfect_classifier_is_degenerate():
    r = bootstrap_binary_ci(tp=50, fp=0, fn=0, tn=50)
    for k in ("sens", "spec", "ppv", "acc"):
        assert r[k] == (1.0, 1.0, 1.0)


def test_binary_ci_deterministic_and_brackets_point():
    a = bootstrap_binary_ci(tp=30, fp=10, fn=20, tn=140)
    b = bootstrap_binary_ci(tp=30, fp=10, fn=20, tn=140)
    assert a == b
    assert a["sens"][0] == 30 / 50 and a["spec"][0] == 140 / 150 and a["ppv"][0] == 30 / 40
    assert a["acc"][0] == 170 / 200
    for k, (pt, lo, hi) in a.items():
        assert 0 <= lo <= pt <= hi <= 1, k
    # sens CI for n=50, p=0.6 is about +-0.14: loose sanity bounds
    assert 0.42 < a["sens"][1] < 0.52 and 0.68 < a["sens"][2] < 0.78


def test_binary_ci_undefined_when_no_positives():
    r = bootstrap_binary_ci(tp=0, fp=3, fn=0, tn=97)
    assert all(math.isnan(x) for x in r["sens"])
    assert r["spec"][0] == 97 / 100


def test_binary_arrays_counts_and_determinism():
    g = [1, 1, 1, 0, 0, 0, 0, 0]
    p = [1, 1, 0, 1, 0, 0, 0, 0]
    r = bootstrap_binary_arrays(g, p)
    assert r["counts"] == (2, 1, 1, 4)
    assert bootstrap_binary_arrays(g, p) == r


def test_bootstrap_ci_mean_is_deterministic_and_matches_fast_path():
    x = np.arange(100, dtype=float)
    a = bootstrap_ci(np.mean, x, n_boot=500)
    assert a == bootstrap_ci(np.mean, x, n_boot=500)
    assert a[0] == 49.5 and a[1] < 49.5 < a[2]
    m = bootstrap_mean_ci(x)
    assert m[0] == 49.5 and 42 < m[1] < 46 and 53 < m[2] < 57


def test_bootstrap_ci_two_arrays_resampled_together():
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0], bool)
    s = np.array([0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1])

    def perfect(yy, ss):
        return float(ss[yy].min() > ss[~yy].max()) if yy.any() and (~yy).any() else float("nan")

    assert bootstrap_ci(perfect, y, s, n_boot=200) == (1.0, 1.0, 1.0)  # same indices for both arrays


def test_prop_ci():
    p, lo, hi = bootstrap_prop_ci(50, 100)
    assert p == 0.5 and 0.38 < lo < 0.43 and 0.57 < hi < 0.62
    assert all(math.isnan(v) for v in bootstrap_prop_ci(0, 0))
