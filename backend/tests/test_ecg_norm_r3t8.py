"""R3-T8 (E4): age/sex dependent NORM rules (thresholds unchanged, only logic)."""
from app.ecg.analysis import analyze_signal, rules
from app.schemas import ECGSignal, SourceKind
from synth_ecg import synth_signal


def _sig(**kw):
    leads, _ = synth_signal(fs=500, seconds=10, seed=2, **kw)
    return ECGSignal(fs=500.0, leads={k: list(map(float, v)) for k, v in leads.items()}, duration_s=10.0,
                     source=SourceKind.IMAGE)


def _codes(an, sex=None, age=None):
    return {f.code: f.severity for f in an.findings}


def _qtc_probe():
    """QT (ms) at hr=60 whose decided QTc falls between the male and female limits."""
    for qt in range(440, 520, 4):
        an = analyze_signal(_sig(hr=60, qt_ms=qt), "t", age=50, sex="M")
        f = [x for x in an.findings if x.code == "ecg.long_qt"]
        if f:
            ev = " ".join(f[0].evidence)
            import re
            v = float(re.search(r"QTc \w+ (\d+)", ev).group(1))
            if 452 <= v <= 458:
                return qt
    return None


def test_qtc_limits_by_sex_constants():
    assert rules.QTC_LIM_M == 450.0 and rules.QTC_LIM_F == 460.0


def test_qtc_455_flagged_in_man_not_in_woman():
    qt = _qtc_probe()
    assert qt is not None
    man = {f.code for f in analyze_signal(_sig(hr=60, qt_ms=qt), "t", age=50, sex="M").findings}
    wom = {f.code for f in analyze_signal(_sig(hr=60, qt_ms=qt), "t", age=50, sex="F").findings}
    assert "ecg.long_qt" in man and "ecg.long_qt" not in wom


def test_sokolow_alone_under_40_is_borderline_not_lvh():
    amp = {"V1": (0.1, -0.1, 0.1, -2.8, 0.2), "V5": (0.1, -0.1, 2.0, -0.2, 0.4), "V6": (0.1, -0.1, 1.0, -0.1, 0.4)}
    young = analyze_signal(_sig(hr=70, amp=amp), "t", age=30, sex="M")
    old = analyze_signal(_sig(hr=70, amp=amp), "t", age=60, sex="M")
    cy = {f.code for f in young.findings}
    co = {f.code for f in old.findings}
    assert "ecg.lvh" not in cy
    assert "ecg.lvh" in co or "ecg.lvh_voltage" in co

def test_t_inversion_v2_v3_young_woman_is_borderline():
    amp = {"V2": (0.1, -0.1, 0.6, -0.8, -0.25), "V3": (0.1, -0.1, 0.8, -0.6, -0.25)}
    sev = lambda age, sex: {f.code: f.severity for f in analyze_signal(_sig(hr=70, amp=amp), "t", age=age, sex=sex).findings}
    young = [v for k, v in sev(28, "F").items() if k.startswith("ecg.t_inversion")]
    older = [v for k, v in sev(55, "F").items() if k.startswith("ecg.t_inversion")]
    assert young and all(s == "borderline" for s in young)
    assert older and all(s == "abnormal" for s in older)
