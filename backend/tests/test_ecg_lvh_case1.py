"""Case 1 (cardiologist gold standard, echo-confirmed): sinus rhythm, LVH with strain, left atrial enlargement and
an HCM-suggestive pattern, rendered as a synthetic 12-lead signal with the reported amplitudes (mm = 10 x mV).

Gold amplitudes: R aVL ~21 and R D1 ~22 mm, R V3-V6 30-45 mm, S V1 ~18 mm, ST J60 -1 to -2 mm with asymmetric T
-4 to -6 mm in I, aVL, V4-V6, P 120 ms in D2, QRS 112 ms, PR 148 ms, axis near +20 deg. The printed Cornell (58 mm)
cannot coexist with a Peguero-Lo Presti below 28 mm and 'low S in the precordials', so S V3 is kept low (11 mm) and
the test asserts the Cornell value computed from the signal instead of the printed one.
"""
from __future__ import annotations

import pytest

from app.ecg.analysis import analyze_signal
from app.schemas import ECGSignal, SourceKind
from synth_ecg import synth_signal

STRAIN = ("I", "aVL", "V4", "V5", "V6")
AMP = {
    "I": (0.10, -0.05, 2.2, -0.05, -0.45),
    "II": (0.15, -0.05, 1.0, -0.20, 0.20),
    "aVL": (0.02, 0.0, 2.1, -0.05, -0.50),
    "V1": (0.06, 0.0, 0.2, -1.8, 0.10),
    "V2": (0.08, 0.0, 0.4, -1.2, 0.30),
    "V3": (0.08, 0.0, 3.0, -1.1, 0.20),
    "V4": (0.08, -0.05, 4.0, -0.3, -0.50),
    "V5": (0.08, -0.10, 4.5, -0.1, -0.55),
    "V6": (0.07, -0.10, 3.5, -0.05, -0.45),
}


def case1(sex="M", **over):
    kw = dict(hr=70, pr_ms=148, qrs_ms=112, qt_ms=400, p_ms=160,   # nominal Gaussian P width; delineated ~120+ ms
              amp=AMP, t_asym=STRAIN,
              st_by_lead={l: -0.15 for l in STRAIN}, noise_mv=0.005, seed=3)
    kw.update(over)
    leads, _ = synth_signal(**kw)
    sig = ECGSignal(fs=500, leads={k: [float(x) for x in v] for k, v in leads.items()}, duration_s=10.0,
                    source=SourceKind.CSV)
    return analyze_signal(sig, "case1", sex=sex)


@pytest.fixture(scope="module")
def a():
    return case1()


def codes(a):
    return {f.code for f in a.findings}


def test_lvh_case1_indices_match_gold_amplitudes(a):
    ix = a.global_measurements.indices
    assert ix["sokolow_lyon"]["v"] >= 50 and ix["sokolow_lyon"]["preenche"] is True
    assert ix["cornell_voltagem"]["v"] >= 28 and ix["cornell_voltagem"]["preenche"] is True
    assert ix["romhilt_estes"]["v"] >= 5 and ix["romhilt_estes"]["componentes"]["classe"] == "definida"
    assert ix["peguero_lo_presti"]["v"] < 28 and ix["peguero_lo_presti"]["preenche"] is False
    assert ix["r_avl"]["preenche"] is True and ix["r_d1"]["preenche"] is True


def test_lvh_case1_reports_lvh_with_strain_and_secondary_repolarization(a):
    c = codes(a)
    assert "ecg.lvh" in c and "ecg.secondary_repolarization_lvh" in c
    lvh = next(f for f in a.findings if f.code == "ecg.lvh")
    assert "strain" in lvh.label and any("Romhilt-Estes" in e for e in lvh.evidence)


def test_lvh_case1_mild_strain_leads_do_not_raise_ischemia_findings():
    m = case1(st_by_lead={l: -0.08 for l in STRAIN})   # J60 ~ -1.4 mm: within the 2 mm strain limit
    bad = [f.code for f in m.findings if f.code.startswith(("ecg.st_depression", "ecg.t_inversion", "ecg.st_elevation"))]
    assert bad == []
    assert "ecg.secondary_repolarization_lvh" in codes(m)


def test_lvh_case1_deep_strain_std_above_2mm_is_reported_with_caution(a):
    f = next(f for f in a.findings if f.code.startswith("ecg.st_depression"))
    assert any("pode ser secundário à sobrecarga" in e for e in f.evidence)

def test_lvh_case1_no_preexcitation_and_left_atrial_overload(a):
    c = codes(a)
    assert "ecg.preexcitation" not in c and "ecg.short_pr" not in c and "ecg.implausible_measurement" not in c
    assert "ecg.lae" in c
    assert "ecg.left_axis_deviation" not in c


def test_lvh_case1_suggests_hypertrophic_cardiomyopathy_pattern_never_diagnosis(a):
    f = next(f for f in a.findings if f.code == "ecg.hcm_pattern")
    assert "sugestivo" in f.label and "ecocardiograma" in f.label
    assert f.severity == "abnormal" and f.confidence <= 0.5


# ---------------------------------------------------------------- plausibility / pre-excitation gates
class _M:
    def __init__(self, p=0.15):
        self.p_amplitude_mv = p


def _ctx(**kw):
    base = dict(paced=None, bbb=None, sinus_p=True, frac_p=1.0, lm={"II": _M()})
    base.update(kw)
    return base


def test_lvh_gate_image_with_low_quality_blocks_preexcitation():
    from app.ecg.analysis import rules_lvh as rl
    assert rl.preexc_block_reason(_ctx(source="image", quality={"II": 0.4}), 110, 120)
    assert rl.preexc_block_reason(_ctx(source="image", quality={"II": 0.9}), 110, 120) is None
    assert rl.preexc_block_reason(_ctx(source="csv", quality={"II": 0.4}), 110, 120) is None


def test_lvh_gate_low_pr_confidence_or_printed_divergence_blocks_preexcitation():
    from app.ecg.analysis import rules_lvh as rl
    assert rl.preexc_block_reason(_ctx(pr_conf=0.5), 110, 120)
    assert rl.preexc_block_reason(_ctx(printed_pr_ms=148), 88, 120)
    assert rl.preexc_block_reason(_ctx(printed_pr_ms=148), 140, 120) is None


def test_lvh_gate_qrs_over_200_without_bbb_or_pacing_is_implausible():
    from app.ecg.analysis import rules_lvh as rl
    assert "270" in rl.implausible_reason(_ctx(), 88, 270)
    assert rl.implausible_reason(_ctx(bbb="lbbb"), 140, 270) is None
    assert rl.implausible_reason(_ctx(paced={"type": "ventricular"}), 140, 270) is None


def test_lvh_gate_short_pr_with_doubtful_p_is_implausible():
    from app.ecg.analysis import rules_lvh as rl
    assert rl.implausible_reason(_ctx(sinus_p=False, frac_p=0.3), 88, 100)
    assert rl.implausible_reason(_ctx(), 88, 100) is None
