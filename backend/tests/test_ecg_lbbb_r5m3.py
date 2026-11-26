"""R5-M3: BRE completo em traçado real (PTB-XL 180) lido como QRS implausível + HVE/HCM falsos.

Causas-raiz cobertas:
 (1) V1 Qr (QS com subida terminal por ST elevado) era tratado como rSr' e vetava o BRE (`rb_inc_lbbb_excl`);
 (2) a nota 'medida de PR/QRS implausível' saía antes de o BRE ser classificado (c["bbb"] ainda vazio);
 (3) critérios de voltagem de HVE valem pouco com BRE (AHA/ACCF/HRS 2009 Parte III/V): viram nota, não achado.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from app.ecg.analysis import rules, rules_lvh
from app.llm import descricao_ecg as D
from tests.test_ecg_analysis import _lbbb_prec, codes, run, sinus


def _bd(**leads):
    """Fake beat delineation: lead -> list of (kind, amp) waves (r_max/s_min derived)."""
    out = {}
    for l, ws in leads.items():
        waves = [NS(kind=k, amp=a) for k, a in ws]
        out[l] = NS(waves=waves, r_max=max([a for k, a in ws if a > 0], default=0.0),
                    s_min=min([a for k, a in ws if a < 0], default=0.0))
    return NS(leads=out)


LATERAL = dict(I=[("R", 1.3), ("S", -0.39)], aVL=[("R", 1.2), ("S", -0.35)],
               V5=[("R", 1.55), ("S", -0.63)], V6=[("R", 1.65), ("S", -0.6)])


def test_qr_v1_with_late_positive_bump_is_lbbb():
    # PTB-XL 180: V1 = Q -2.8 mV then a late R 0.77 mV (ST elevation read as R'); no initial r -> not rSr'
    bd = _bd(V1=[("Q", -2.815), ("R", 0.77)], V2=[("R", 0.29), ("S", -5.73), ("R'", 1.56)], **LATERAL)
    assert rules._classify_bbb(bd, 224.0, 2.0)[0] == "lbbb"


def test_rsr_v1_with_initial_r_still_vetoes_lbbb():
    bd = _bd(V1=[("R", 0.3), ("S", -1.5), ("R'", 0.5)], V2=[("R", 0.2), ("S", -2.0)], **LATERAL)
    assert rules._classify_bbb(bd, 150.0, 2.0)[0] != "lbbb"


def test_rb_inc_lbbb_excl_requires_initial_r():
    qr = dict(r=0.77, s=-2.8, last=("R", 0.77), q=-2.8, first="Q")
    rsr = dict(r=0.5, s=-1.5, last=("R'", 0.5), q=0.0, first="R")
    assert rules.rb_inc_lbbb_excl(qr) is False
    assert rules.rb_inc_lbbb_excl(rsr) is True


def test_ceiling_only_without_bbb():
    c_none = {"bbb": None, "paced": None, "lm": {}}
    assert "sem bloqueio" in (rules_lvh.implausible_reason(c_none, 150.0, 216.0) or "")
    assert rules_lvh.implausible_reason({**c_none, "bbb": "lbbb"}, 150.0, 260.0) is None   # BRE real de 200-260 ms


def test_no_implausible_note_when_lbbb_is_classified(monkeypatch):
    # synthetic lead-median QRS ~169 ms: lower the ceiling below it to reproduce the order bug of PTB-XL 180
    monkeypatch.setattr(rules_lvh, "QRS_IMPLAUSIBLE_MS", 160.0)
    L, _ = sinus(70, qrs_scale=2.1, pr=0.16, prec=_lbbb_prec(), axis_deg=10, noise=0.005)
    c = codes(run(L))
    assert "ecg.lbbb" in c
    assert "ecg.implausible_measurement" not in c


def test_lvh_voltage_and_hcm_not_emitted_with_lbbb():
    prec = _lbbb_prec()
    prec["V5"] = [(0, 14, 3.2), (30, 14, 2.0)]
    prec["V6"] = [(0, 14, 3.0), (30, 14, 1.8), (60, 10, -0.05)]
    L, _ = sinus(70, qrs_scale=1.35, prec=prec, axis_deg=10, noise=0.005, st={"V1": 0.25, "V2": 0.3, "V3": 0.25})
    a = run(L)
    c = codes(a)
    assert "ecg.lbbb" in c
    assert not ({"ecg.lvh", "ecg.lvh_voltage", "ecg.hcm_pattern", "ecg.secondary_repolarization_lvh"} & c)
    nota = next(f for f in a.findings if f.code == "ecg.lvh_not_assessable_lbbb")
    assert nota.severity == "borderline"
    assert "não avaliável na presença de BRE" in nota.label
    assert any("Sokolow" in e for e in nota.evidence)


def test_lvh_still_emitted_without_bbb():
    from tests.test_ecg_lvh_case1 import case1
    a = case1()
    assert "ecg.lvh" in codes(a)
    assert "ecg.lvh_not_assessable_lbbb" not in codes(a)


@pytest.mark.parametrize("bbb", ["rbbb", "irbbb", None])
def test_note_only_for_lbbb(bbb):
    # the suppression helper itself is keyed on LBBB only
    assert rules_lvh.lvh_voltage_suppressed({"bbb": bbb, "paced": None}) is False
    assert rules_lvh.lvh_voltage_suppressed({"bbb": "lbbb", "paced": None}) is True


def test_descricao_qt_sinaliza_qtc_sem_ajuste_com_qrs_largo():
    from tests.test_ecg_descricao_completa import NORMAL_G, R_SINUS, _sum
    largo = D.montar_deterministico(_sum({**NORMAL_G, "qrs_ms": 216, "qtc_bazett_ms": 614}, [R_SINUS]))
    estreito = D.montar_deterministico(_sum({**NORMAL_G, "qrs_ms": 90}, [R_SINUS]))
    assert "não tem ajuste ao QRS largo" in largo
    assert "não tem ajuste ao QRS largo" not in estreito
