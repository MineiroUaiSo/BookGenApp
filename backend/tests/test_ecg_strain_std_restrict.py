"""Strain suppression of ST depression is restricted (clinical decision 2026-11-25): suppress only mild lateral STD
with HVE by voltage (Sokolow/Cornell), no STD in V1-V3/II/III/aVF and no STE."""
from __future__ import annotations

from app.ecg.analysis.rules_lvh import has_voltage_hve, strain_std_suppressed

STRAIN = {"I", "aVL", "V4", "V5", "V6"}
HVE = {"sokolow_lyon": {"v": 55, "preenche": True}, "cornell_voltagem": {"v": 20, "preenche": False}}
RE_ONLY = {"sokolow_lyon": {"v": 30, "preenche": False}, "cornell_voltagem": {"v": 20, "preenche": False},
           "romhilt_estes": {"v": 6, "preenche": True}}


def sup(std, ste=None, idx=HVE, lead="V5"):
    return strain_std_suppressed(lead, STRAIN, idx, std, ste or {})


def test_typical_strain_is_suppressed():
    assert sup({"V4": -0.1, "V5": -0.15, "V6": -0.1}) is True


def test_cornell_alone_counts_as_voltage_hve():
    assert has_voltage_hve({"cornell_voltagem": {"preenche": True}}) is True


def test_j60_above_2mm_not_suppressed():
    assert sup({"V4": -0.1, "V5": -0.25, "V6": -0.1}) is False


def test_std_in_v2_not_suppressed():
    assert sup({"V2": -0.08, "V5": -0.1, "V6": -0.1}) is False


def test_inferior_std_not_suppressed():
    for l in ("II", "III", "aVF"):
        assert sup({l: -0.07, "V5": -0.1, "V6": -0.1}) is False


def test_reciprocal_ste_not_suppressed():
    assert sup({"aVL": -0.1, "V5": -0.1}, ste={"III": 0.12}, lead="aVL") is False


def test_romhilt_estes_only_not_suppressed():
    assert has_voltage_hve(RE_ONLY) is False
    assert sup({"V5": -0.1, "V6": -0.1}, idx=RE_ONLY) is False


def test_non_strain_lead_not_suppressed():
    assert sup({"V3": -0.1}, lead="V3") is False
