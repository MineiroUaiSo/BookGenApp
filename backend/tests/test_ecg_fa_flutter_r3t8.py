"""R3-T8 (E3): flutter is tested before AF (F waves in II/III/aVF/V1, atrial rate 240-340/min) and RR
alternation (bigeminy) excludes AF."""
import numpy as np

from app.ecg.analysis import rhythm, rules
from synth_ecg import synth_signal

FS = 500


def _peaks(rr_ms):
    return np.concatenate([[0.0], np.cumsum(rr_ms)])


def _ctx(irr_cv=0.2, flutter_f=None, alt=False, p_frac=0.1):
    return dict(hr=110.0, cv=irr_cv, rmssd=0.2, av=dict(p_frac=p_frac, pr_sd=60.0), lm={}, p_present=False,
                frac_p=0.0, irr=dict(cv=irr_cv, rmssd=0.2, dfrac=0.9), ectopy=False, flutter={},
                flutter_f=flutter_f, rr_alt=alt)


def test_rr_alternation_detects_bigeminy_not_af():
    big = _peaks([800, 500] * 8)
    assert rhythm.rr_alternation(big)
    rng = np.random.default_rng(1)
    af = _peaks(rng.uniform(450, 950, 16))
    assert not rhythm.rr_alternation(af)
    assert not rhythm.rr_alternation(_peaks([800] * 12))
    assert not rhythm.rr_alternation(_peaks([800, 500] * 2))   # too short to decide


def test_alternation_blocks_af():
    rhy, kind = rules.classify_rhythm(_ctx(alt=True))
    assert kind != "af"
    assert rules.classify_rhythm(_ctx(alt=False))[1] == "af"


def test_flutter_before_af_with_f_waves_in_240_340_band():
    fl = dict(freq_hz=5.0, peak_ratio=rules.FLUTTER_F_RATIO + 0.1, harmonic=False, lead="V1", n_leads=2)
    assert rules.classify_rhythm(_ctx(flutter_f=fl))[1] == "flutter"
    slow = dict(fl, freq_hz=3.8)   # 228/min: out of the 240-340 window -> AF test stays first
    assert rules.classify_rhythm(_ctx(flutter_f=slow))[1] == "af"
    weak = dict(fl, peak_ratio=rules.FLUTTER_F_RATIO - 0.1)
    assert rules.classify_rhythm(_ctx(flutter_f=weak))[1] == "af"


def _with_f_waves(freq_hz, leads_on, amp=0.15):
    leads, fid = synth_signal(hr=75, fs=FS, seconds=10, p_ms=10, seed=3)
    t = np.arange(len(leads["II"])) / FS
    saw = amp * (2 * ((t * freq_hz) % 1.0) - 1.0)
    out = {k: (v + saw if k in leads_on else v) for k, v in leads.items()}
    beats = [dict(qrs_on=int(a * FS), qrs_off=int(b * FS)) for a, b in zip(fid["qrs_on_s"], fid["qrs_off_s"])]
    return out, beats


def test_flutter_multilead_finds_f_waves_in_v1_only():
    leads, beats = _with_f_waves(5.0, {"V1"})
    r = rhythm.flutter_multilead(leads, FS, beats)
    assert r["lead"] == "V1" and 4.8 <= r["freq_hz"] <= 5.2 and r["peak_ratio"] >= 0.35


def test_flutter_multilead_ignores_sinus_and_out_of_band():
    leads, fid = synth_signal(hr=75, fs=FS, seconds=10, seed=3)
    beats = [dict(qrs_on=int(a * FS), qrs_off=int(b * FS)) for a, b in zip(fid["qrs_on_s"], fid["qrs_off_s"])]
    assert rhythm.flutter_multilead(leads, FS, beats)["peak_ratio"] < 0.35
    leads2, beats2 = _with_f_waves(3.7, {"II", "III", "aVF", "V1"})   # 222/min: below the flutter window
    r = rhythm.flutter_multilead(leads2, FS, beats2)
    assert r["freq_hz"] is None or r["peak_ratio"] < 0.35 or not (4.0 <= r["freq_hz"] <= 5.67)
