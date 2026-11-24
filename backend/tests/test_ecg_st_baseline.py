"""E1: ST reference on the PR segment, per-lead J point, STE threshold by sex/age."""
from __future__ import annotations

import numpy as np
import pytest

from app.ecg.analysis.delineate import pr_baseline
from app.ecg.analysis.rules import ste_threshold_mv

FS = 500


def _beat(pr_level=0.05, noise=0.0, seed=0):
    """Flat TP (0.0), P bump, flat PR at pr_level, ramp (late QRS onset) 20 ms before 'on'."""
    rng = np.random.default_rng(seed)
    y = np.zeros(400)
    p_on, p_off, on = 100, 150, 220
    y[p_on:p_off] = 0.1 * np.sin(np.linspace(0, np.pi, p_off - p_on))
    y[p_off:on] = pr_level
    y[on - 10:on] = np.linspace(pr_level, pr_level + 0.3, 10)  # 20 ms ramp right before onset
    return y + rng.normal(0, noise, y.size), p_on, p_off, on


def test_pr_baseline_flat_pr_returns_pr_level_not_onset_ramp():
    y, p_on, p_off, on = _beat(pr_level=0.05)
    old = float(np.median(y[on - 12:on - 2]))   # legacy 20 ms window glued to the onset
    b = pr_baseline(y, FS, on, p_on, p_off, 0)
    assert b == pytest.approx(0.05, abs=1e-6)
    assert abs(old - 0.05) > 0.05


def test_pr_baseline_picks_lowest_variance_window_with_noise():
    y, p_on, p_off, on = _beat(pr_level=0.0, noise=0.002)
    y[p_off:p_off + 8] += 0.05  # P tail contaminates the start of the PR segment
    b = pr_baseline(y, FS, on, p_on, p_off, 0)
    assert abs(b) < 0.01


def test_pr_baseline_short_pr_falls_back_to_tp():
    y, p_on, p_off, on = _beat(pr_level=0.0)
    p_off = on - 10  # PR segment (10 samples = 20 ms) too short for a 40 ms window
    y[:p_on] = 0.02   # TP segment of previous beat
    b = pr_baseline(y, FS, on, p_on, p_off, 0)
    assert b == pytest.approx(0.02, abs=1e-6)


def test_pr_baseline_no_p_uses_tp_and_returns_none_when_no_room():
    y, _, _, on = _beat()
    assert pr_baseline(y, FS, on, None, None, 0) is not None
    assert pr_baseline(y, FS, on, None, None, on - 5) is None


@pytest.mark.parametrize("lead,age,sex,expected", [
    ("V2", 30, "M", 0.25), ("V3", 39, "M", 0.25), ("V2", 40, "M", 0.20), ("V3", 70, "M", 0.20),
    ("V2", 30, "F", 0.15), ("V3", None, "F", 0.15),
    ("V2", None, None, 0.20), ("V2", 30, None, 0.20), ("V2", None, "M", 0.20),
    ("II", 30, "M", 0.10), ("V4", 70, "F", 0.10), ("aVF", None, None, 0.10),
])
def test_ste_threshold_by_sex_age(lead, age, sex, expected):
    assert ste_threshold_mv(lead, age, sex) == pytest.approx(expected)
