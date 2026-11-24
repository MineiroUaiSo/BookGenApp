"""Abstention: photos with irregular grid -> only HR / rhythm regularity."""
import numpy as np

from app.ecg.analysis import analyze_signal
from app.ecg.digitize import perspective
from app.schemas import ECGSignal, SourceKind
from synth_ecg import synth_signal


def _signal(rhythm_only: bool) -> ECGSignal:
    leads, _ = synth_signal(hr=72, fs=500, seconds=10, seed=5)
    cal = {"rhythm_only": 1.0} if rhythm_only else {}
    return ECGSignal(fs=500.0, leads={k: list(map(float, v)) for k, v in leads.items()}, duration_s=10.0,
                     source=SourceKind.IMAGE, calibration=cal)


def test_rhythm_only_keeps_hr_and_drops_intervals_and_findings():
    an = analyze_signal(_signal(True), "abst")
    gm = an.global_measurements
    assert gm.heart_rate_bpm is not None and 65 <= gm.heart_rate_bpm <= 80
    assert gm.qrs_ms is None and gm.qt_ms is None and gm.pr_ms is None
    assert not an.findings and not an.lead_measurements and not an.waves
    assert any("apenas frequência cardíaca" in w for w in an.warnings)


def test_normal_signal_not_affected_by_abstention_path():
    an = analyze_signal(_signal(False), "full")
    assert an.global_measurements.qrs_ms is not None


def test_spacing_cv_regular_grid_is_low():
    prof = np.zeros(900)
    prof[::9] = 1.0
    cv = perspective._spacing_cv(prof)
    assert cv is not None and cv < perspective.GRID_CV_ABSTAIN


def test_spacing_cv_warped_grid_is_high():
    rng = np.random.default_rng(0)
    pos = np.cumsum(rng.uniform(4, 20, 80)).astype(int)
    prof = np.zeros(pos.max() + 10)
    prof[pos] = 1.0
    cv = perspective._spacing_cv(prof)
    assert cv is None or cv > perspective.GRID_CV_ABSTAIN
