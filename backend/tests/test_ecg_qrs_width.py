"""E4: QRS width rules (per-lead median/global blend, 110-119 ms borderline zone)."""
from __future__ import annotations

from synth_ecg import synth_signal
from test_ecg_analysis import codes, run


def test_qrs_width_normal_synthetic_has_no_conduction_finding():
    a = run(synth_signal(hr=70, qrs_ms=90, noise_mv=0.005, seed=3)[0])
    assert not {"ecg.ivcd", "ecg.qrs_borderline"} & codes(a)


def test_qrs_width_110_119_is_borderline_not_ivcd():
    a = run(synth_signal(hr=70, qrs_ms=120, noise_mv=0.005, seed=3)[0])
    c = codes(a)
    assert "ecg.qrs_borderline" in c and "ecg.ivcd" not in c
    assert next(f for f in a.findings if f.code == "ecg.qrs_borderline").severity == "borderline"
    assert "ecg.within_normal_limits" in c     # borderline alone does not make the tracing abnormal