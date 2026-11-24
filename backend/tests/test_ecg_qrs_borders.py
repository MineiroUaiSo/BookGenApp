"""E2: per-lead QRS borders from the smoothed velocity (slow starts), global = rank-robust extremes."""
from __future__ import annotations

import numpy as np

from app.ecg.analysis.delineate import delineate_beat

FS = 500
ON_TRUE, A = 200, 240   # slow start at sample 200 (400 ms), R peak at 240


def _beat(slow_ramp: bool):
    """Single beat: optional 40 ms delta-like ramp (0 -> 0.15 mV), fast upstroke to 1 mV, return to 0 by 30 ms."""
    x = np.zeros(700)
    start = ON_TRUE if slow_ramp else ON_TRUE + 20
    if slow_ramp:
        x[ON_TRUE:ON_TRUE + 20] = np.linspace(0, 0.15, 20, endpoint=False)
    x[ON_TRUE + 20:A] = np.linspace(0.15 if slow_ramp else 0.0, 1.0, A - ON_TRUE - 20, endpoint=False)
    x[A:A + 15] = np.linspace(1.0, 0.0, 15, endpoint=False)
    return x, start


def _delineate(x):
    seg = x[None, :]
    return delineate_beat(seg, seg, FS, A, ["II"], np.array([0.005]), 800.0, 800.0)


def test_qrs_borders_slow_start_onset_is_found_near_the_true_start():
    x, start = _beat(slow_ramp=True)
    bd = _delineate(x)
    assert abs(bd.leads["II"].qrs_on - start) <= 8      # 16 ms; a 5%-of-peak threshold would sit at the fast part


def test_qrs_borders_slow_start_is_earlier_than_without_ramp():
    on_ramp = _delineate(_beat(True)[0]).leads["II"].qrs_on
    on_plain = _delineate(_beat(False)[0]).leads["II"].qrs_on
    assert on_ramp < on_plain - 6                      # at least ~12 ms earlier


def test_qrs_borders_lead_inside_global_span():
    x, _ = _beat(True)
    bd = _delineate(x)
    ld = bd.leads["II"]
    assert bd.qrs_on <= ld.qrs_on < ld.qrs_off <= bd.qrs_off
    assert bd.pre_on <= A <= bd.pre_off
