"""K2/K3: plausibility of digitised ECGs: printed-header cross-check and physiological sanity abstention."""
import numpy as np

from app.ecg import plausibility
from app.schemas import ECGSignal, Finding, GlobalMeasurements, LeadMeasurements, SourceKind


def _signal(cal=None, source=SourceKind.IMAGE):
    t = np.arange(1500) / 500.0
    v = np.sin(2 * np.pi * 1.2 * t)
    return ECGSignal(fs=500.0, leads={"I": v.tolist(), "II": v.tolist(), "III": (0 * v).tolist()}, duration_s=3.0,
                     source=source, quality={}, calibration=cal or {"px_per_mm_x": 8.0, "px_per_mm_y": 8.0})


def _f(code):
    return Finding(code=code, label=code, severity="abnormal")


def _lm(lead, st=0.0, r=1.0, s=-0.2, p=0.1):
    return LeadMeasurements(lead=lead, st_j60_mv=st, r_amplitude_mv=r, s_amplitude_mv=s, p_amplitude_mv=p, p_duration_ms=100.0)


def test_plausibility_printed_divergence_withholds_dependent_findings():
    sig = _signal({"printed.qrs_ms": 112.0, "px_per_mm_x": 8.0, "px_per_mm_y": 8.0})
    gm = GlobalMeasurements(qrs_ms=170.0, pr_ms=150.0)
    warnings: list[str] = []
    out = plausibility.apply(sig, gm, [_lm("II")], [_f("ecg.preexcitation"), _f("ecg.lbbb"), _f("ecg.sinus_rhythm")], warnings)
    codes = [f.code for f in out]
    assert "ecg.preexcitation" not in codes and "ecg.lbbb" not in codes
    assert "ecg.sinus_rhythm" in codes and "ecg.digitization_suspect" in codes
    assert any("divergente do impresso" in w for w in warnings)


def test_plausibility_wide_qrs_without_bundle_branch_block_is_suspect():
    sig = _signal()
    out = plausibility.apply(sig, GlobalMeasurements(qrs_ms=270.0), [_lm("II")], [_f("ecg.preexcitation")], [])
    assert [f.code for f in out] == ["ecg.digitization_suspect"]


def test_plausibility_short_pr_without_clear_p_wave_is_suspect():
    sig = _signal()
    out = plausibility.apply(sig, GlobalMeasurements(qrs_ms=110.0, pr_ms=88.0), [_lm("II", p=0.01)], [_f("ecg.preexcitation")], [])
    assert "ecg.preexcitation" not in [f.code for f in out]


def test_plausibility_isolated_large_st_shift_withholds_st_findings():
    sig = _signal()
    lms = [_lm("II", st=0.0), _lm("aVF", st=-0.49)]
    out = plausibility.apply(sig, GlobalMeasurements(qrs_ms=100.0, pr_ms=150.0), lms, [_f("ecg.st_depression_inferior")], [])
    assert "ecg.st_depression_inferior" not in [f.code for f in out]


def test_plausibility_consistent_measurements_keep_findings():
    sig = _signal({"printed.qrs_ms": 112.0, "px_per_mm_x": 8.0, "px_per_mm_y": 8.0})
    gm = GlobalMeasurements(qrs_ms=118.0, pr_ms=150.0)
    findings = [_f("ecg.lvh")]
    assert plausibility.apply(sig, gm, [_lm("II"), _lm("V5", r=3.5)], findings, []) == findings


def test_plausibility_non_image_signals_are_untouched():
    sig = _signal({"printed.qrs_ms": 50.0}, source=SourceKind.DICOM) if hasattr(SourceKind, "DICOM") else None
    if sig is None:
        return
    findings = [_f("ecg.preexcitation")]
    assert plausibility.apply(sig, GlobalMeasurements(qrs_ms=270.0), [], findings, []) == findings


def test_plausibility_low_resolution_warns():
    warnings: list[str] = []
    plausibility.apply(_signal({"px_per_mm_x": 3.0, "px_per_mm_y": 3.0}), GlobalMeasurements(qrs_ms=100.0, pr_ms=150.0), [_lm("II")], [], warnings)
    assert any("Resolução baixa" in w for w in warnings)
