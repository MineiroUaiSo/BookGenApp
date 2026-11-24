"""Subgroup helpers (bench/subgroups.py)."""
from __future__ import annotations

from bench import subgroups as sg


def test_has_flag_ignores_separators_and_blanks():
    assert sg.has_flag(", I-V1,  ") and sg.has_flag(" , drift")
    assert not sg.has_flag("") and not sg.has_flag(None) and not sg.has_flag(" , ,  ")


def test_age_band_edges_and_over_89_sentinel():
    assert [sg.age_band(x) for x in (18, 39.9, 40, 65, 65.5, 66, 89)] == ["<40", "<40", "40-65", "40-65", "40-65", ">65", ">65"]
    assert sg.age_band(300) == ">65" and sg.age_band("") is None and sg.age_band(float("nan")) is None


def test_sex_and_groupings():
    assert sg.sex_of("0") == "M" and sg.sex_of("1.0") == "F" and sg.sex_of("") is None
    g = sg.groupings({"sex": "1", "age": "70", "device": "AT-6", "baseline_drift": ", V1", "static_noise": ""}, {"AT-6": "AT-6"})
    assert ("sexo", "F") in g and ("idade", ">65") in g and ("aparelho", "AT-6") in g
    assert ("ruído: baseline_drift", "com") in g and ("ruído: static_noise", "sem") in g


def test_device_groups_top_n_rest_other():
    meta = {f"r{i}": {"device": d} for i, d in enumerate(["A"] * 5 + ["B"] * 3 + ["C"] * 1)}
    m = sg.device_groups(meta, list(meta), top=2)
    assert m == {"A": "A", "B": "B", "C": "other"}


def test_subgroup_table_counts():
    recs = []
    for i in range(20):
        pos = i < 10
        recs.append({"gold": {"AF"} if pos else set(), "codes": {"ecg.atrial_fibrillation"} if (i < 8 or i == 15) else set(),
                     "groups": [("sexo", "M" if i % 2 else "F")]})
    t, raw = sg.subgroup_table(recs, "AF", lambda c: "ecg.atrial_fibrillation" in c)
    allrow = [r for r in raw if r[0] == ("todos", "todos")][0]
    assert allrow[1:] == (8, 1, 2, 9)                 # tp, fp, fn, tn
    assert "Sens [IC95%]" in t and "sexo" in t
    assert sum(r[1] + r[2] + r[3] + r[4] for r in raw if r[0][0] == "sexo") == 20
