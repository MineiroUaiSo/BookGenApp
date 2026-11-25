"""R3 T7: STE needs J and J+60; wide QRS / LVH downgrade; reciprocal depression; per-lead noise abstention."""
from __future__ import annotations

from types import SimpleNamespace as NS

from app.ecg.analysis import rules_st as R
from tests.test_ecg_analysis import run, sinus


def bd(**noises):
    return NS(leads={l: NS(noise=n) for l, n in noises.items()})


def test_true_contiguous_ste_confirmed():
    assert R.ste_confirmed(0.15, 0.12) is True


def test_j_only_notch_not_confirmed():
    assert R.ste_confirmed(0.15, 0.01) is False


def test_j60_unmeasurable_keeps_candidate():
    assert R.ste_confirmed(0.15, None) is True


def test_wide_qrs_downgrades():
    assert R.ste_downgrade_reason(130.0, False, {"V2": 0.3, "V3": 0.3}, {}) is not None


def test_lbbb_discordant_st_not_plain_mi():
    assert "QRS largo" in R.ste_downgrade_reason(140.0, False, {"V1": 0.4, "V2": 0.5}, {"V1": -1.5, "V2": -2.0})


def test_hve_small_st_over_deep_s_downgrades():
    assert R.ste_downgrade_reason(95.0, True, {"V2": 0.2, "V3": 0.2}, {"V2": -2.5, "V3": -2.0}) is not None


def test_hve_large_st_over_s_is_kept():
    assert R.ste_downgrade_reason(95.0, True, {"V2": 0.2, "V3": 0.2}, {"V2": -0.5, "V3": -0.6}) is None


def test_narrow_qrs_no_hve_kept():
    assert R.ste_downgrade_reason(90.0, False, {"II": 0.15, "III": 0.2}, {}) is None


def test_reciprocal_depression():
    assert R.reciprocal_depression("inferior", {"aVL": -0.1}) is True
    assert R.reciprocal_depression("inferior", {"V5": -0.1}) is False
    assert R.reciprocal_depression("anterior", {"III": -0.06}) is True


def test_noisy_leads_by_noise_and_quality():
    b = bd(V1=0.01, V2=0.08, V3=0.02)
    assert R.noisy_leads(b) == ["V2"]
    assert R.noisy_leads(b, {"V3": 0.3}) == ["V2", "V3"]

def test_integration_true_inferior_ste_kept_critical():
    L, _ = sinus(70, st={"II": 0.25, "III": 0.25, "aVF": 0.25}, noise=0.005)
    f = [f for f in run(L).findings if f.code == "ecg.st_elevation_inferior"]
    assert f and f[0].severity == "critical"


def test_integration_noisy_leads_abstain_and_warn():
    L, _ = sinus(70, st={"II": 0.25, "III": 0.25, "aVF": 0.25}, noise=0.25)
    a = run(L)
    assert not [f for f in a.findings if f.code.startswith("ecg.st_elevation_")]
    assert any("ST/Q não avaliados" in w for w in a.warnings)
