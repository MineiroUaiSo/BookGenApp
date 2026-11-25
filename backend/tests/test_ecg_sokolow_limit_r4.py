"""R4 T2: Sokolow-Lyon limit aligned with the index (>= 35 mm, tolerance 1e-9) in the findings rule and LAE context."""
from __future__ import annotations

import pytest

import app.ecg.analysis as an
from test_ecg_lvh_case1 import case1

AMP = {"II": (0.15, -0.05, 1.0, -0.2, 0.2), "V1": (0.06, 0, 0.2, -1.5, 0.1),
       "V5": (0.08, -0.05, 2.0, -0.1, 0.3), "V6": (0.07, -0.05, 1.5, -0.05, 0.3)}


def _with_sokolow(monkeypatch, value_mv):
    real = an.measure_median

    def patched(*a, **k):
        lms, gm, extras = real(*a, **k)
        gm.sokolow_lyon_mv = value_mv
        return lms, gm, extras
    monkeypatch.setattr(an, "measure_median", patched)
    return case1(amp=AMP, t_asym=(), st_by_lead={})


def test_sokolow_exactly_35mm_becomes_lvh(monkeypatch):
    a = _with_sokolow(monkeypatch, 3.5)
    lvh = next((f for f in a.findings if f.code == "ecg.lvh"), None)
    assert lvh is not None
    assert any("Sokolow-Lyon 35 mm (≥35 mm)" in e for e in lvh.evidence)


def test_sokolow_just_below_35mm_is_not_lvh(monkeypatch):
    a = _with_sokolow(monkeypatch, 3.49)
    assert all(f.code != "ecg.lvh" for f in a.findings)
