"""Table tests for app.ecg.analysis.indices (pure functions, amplitudes in mm)."""
from __future__ import annotations

import pytest

from app.ecg.analysis import indices as ix

R = {"I": 22, "aVL": 21, "V4": 35, "V5": 40, "V6": 35}
S = {"V1": 18, "V3": 8, "V4": 6, "III": 3}


def test_indices_sokolow_lyon_sums_s_v1_and_max_r_v5_v6():
    i = ix.sokolow_lyon(R, S)
    assert i["v"] == 58 and i["limiar"] == 35 and i["preenche"] is True and i["unidade"] == "mm"
    assert i["componentes"] == {"S_V1": 18, "R_V5_V6": 40}


@pytest.mark.parametrize("s1,expected", [(5, False), (5.1, True), (-4, False)])
def test_indices_sokolow_lyon_threshold_is_strict_above_35(s1, expected):
    assert ix.sokolow_lyon({"V5": 30}, {"V1": s1})["preenche"] is expected


@pytest.mark.parametrize("sex,thr,fills", [("M", 28, True), ("F", 20, True)])
def test_indices_cornell_voltage_sex_specific_limits(sex, thr, fills):
    i = ix.cornell_voltage({"aVL": 21}, {"V3": 8}, sex)
    assert i["v"] == 29 and i["limiar"] == thr and i["preenche"] is fills


def test_indices_cornell_voltage_without_sex_marks_depends_on_sex_between_limits():
    i = ix.cornell_voltage({"aVL": 15}, {"V3": 9})     # 24 mm: > 20 (F) but <= 28 (M)
    assert i["preenche"] == "depende_do_sexo" and i["limiar"] == {"M": 28, "F": 20}
    assert ix.cornell_voltage({"aVL": 15}, {"V3": 15})["preenche"] is True      # 30 mm
    assert ix.cornell_voltage({"aVL": 10}, {"V3": 8})["preenche"] is False      # 18 mm


def test_indices_cornell_voltage_boundary_is_strict():
    assert ix.cornell_voltage({"aVL": 20}, {"V3": 8}, "M")["preenche"] is False   # exactly 28
    assert ix.cornell_voltage({"aVL": 20}, {"V3": 8.1}, "M")["preenche"] is True


def test_indices_cornell_product_adds_6mm_in_women():
    m = ix.cornell_product({"aVL": 15}, {"V3": 10}, 100, "M")    # 25 x 100 = 2500
    f = ix.cornell_product({"aVL": 15}, {"V3": 10}, 100, "F")    # 31 x 100 = 3100
    assert m["v"] == 2500 and m["preenche"] is True and m["unidade"] == "mm.ms" and m["limiar"] == 2440
    assert f["v"] == 3100 and f["componentes"]["mulher_mais_6mm"] is True
    assert ix.cornell_product({"aVL": 10}, {"V3": 10}, 100, "M")["preenche"] is False   # 2000


def test_indices_cornell_product_without_sex_depends_on_sex_when_only_female_value_fills():
    i = ix.cornell_product({"aVL": 10}, {"V3": 10}, 110)     # 2200 (M) / 2860 (F)
    assert i["preenche"] == "depende_do_sexo"
    assert ix.cornell_product({"aVL": 10}, {"V3": 10}, None) is None


@pytest.mark.parametrize("sex,s,fills", [("M", {"V1": 20, "V4": 8}, True), ("M", {"V1": 20, "V4": 7.9}, False),
                                         ("F", {"V2": 15, "V4": 8}, True), ("F", {"V2": 15, "V4": 7.9}, False)])
def test_indices_peguero_lo_presti_sex_thresholds_are_inclusive(sex, s, fills):
    i = ix.peguero_lo_presti(s, sex)
    assert i["preenche"] is fills
    assert i["limiar"] == (28 if sex == "M" else 23)


def test_indices_peguero_lo_presti_case1_not_met():
    # R grows from V3 with shallow S in precordials: deepest S 8 + S V4 6 = 14 mm
    assert ix.peguero_lo_presti({"V1": 8, "V2": 7, "V3": 4, "V4": 6}, "M")["preenche"] is False


def test_indices_peguero_lo_presti_sex_unknown_between_limits():
    assert ix.peguero_lo_presti({"V2": 17, "V4": 8})["preenche"] == "depende_do_sexo"    # 25


def test_indices_r_avl_and_r_d1_and_gubner():
    assert ix.r_avl({"aVL": 11.5})["preenche"] is True and ix.r_avl({"aVL": 11})["preenche"] is False
    assert ix.r_d1({"I": 20})["preenche"] is True and ix.r_d1({"I": 19})["preenche"] is False
    g = ix.gubner({"I": 22}, {"III": 4})
    assert g["v"] == 26 and g["preenche"] is True and ix.gubner({"I": 22}, {"III": 3})["preenche"] is False


def test_indices_qrst_angle_wraps_around_180():
    assert ix.qrst_angle(20, 171)["v"] == 151
    assert ix.qrst_angle(170, -170)["v"] == 20 and ix.qrst_angle(170, -170)["preenche"] is False
    assert ix.qrst_angle(None, 10) is None


def test_indices_morris_index_depth_times_duration():
    i = ix.morris(1.0, 40)
    assert i["v"] == 0.04 and i["preenche"] is True and i["unidade"] == "mm.s"
    assert ix.morris(0.5, 60)["preenche"] is False and ix.morris(None, 40) is None


def test_indices_romhilt_estes_case1_voltage_plus_strain_is_definite():
    i = ix.romhilt_estes(R, S, strain=True, axis_deg=20, qrs_ms=85)
    assert i["v"] == 6 and i["preenche"] is True and i["componentes"]["classe"] == "definida"
    assert i["componentes"]["voltagem"] == 3 and i["componentes"]["st_t_strain"] == 3


def test_indices_romhilt_estes_items_and_digitalis():
    full = ix.romhilt_estes({"V5": 31}, {}, strain=True, morris_fills=True, axis_deg=-35, qrs_ms=95, idt_ms=55)
    assert full["v"] == 3 + 3 + 3 + 2 + 1 + 1
    dig = ix.romhilt_estes({"V5": 31}, {}, strain=True, digitalis=True)
    assert dig["componentes"]["st_t_strain"] == 1 and dig["v"] == 4 and dig["componentes"]["classe"] == "provavel"
    none = ix.romhilt_estes({"V5": 10}, {"V1": 10}, strain=False)
    assert none["v"] == 0 and none["preenche"] is False


@pytest.mark.parametrize("r,s,expected", [({"V5": 30}, {}, 3), ({}, {"V1": 30}, 3), ({"I": 20}, {}, 3),
                                          ({}, {"III": 20}, 3), ({"V5": 29}, {"V1": 29}, 0)])
def test_indices_romhilt_estes_voltage_item_variants(r, s, expected):
    assert ix.romhilt_estes(r, s, strain=False)["componentes"]["voltagem"] == expected


def test_indices_compute_indices_omits_missing_and_has_contract_keys():
    out = ix.compute_indices(R, S, sex="M", qrs_ms=112, qrs_axis=20, t_axis=171, p_neg_depth_mm=0.5,
                             p_neg_dur_ms=40, strain=True)
    for k in ("sokolow_lyon", "cornell_voltagem", "cornell_produto", "peguero_lo_presti", "r_avl", "r_d1",
              "r_d1_mais_s_d3", "angulo_qrs_t", "morris", "romhilt_estes"):
        assert set(out[k]) == {"v", "unidade", "limiar", "preenche", "componentes"}, k
    assert out["cornell_voltagem"]["v"] == 29 and out["romhilt_estes"]["v"] >= 6
    assert "sokolow_lyon" not in ix.compute_indices({"aVL": 10}, {"V3": 5})
