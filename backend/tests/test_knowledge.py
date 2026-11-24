from app import knowledge as K


def test_load_criteria_both_domains():
    for d in ("ecg", "rx"):
        items = K.load_criteria(d)
        assert len(items) >= 15
        for it in items:
            for k in ("id", "domain", "label_pt", "criteria", "measurements_used", "differentials", "pitfalls", "references"):
                assert k in it, (it["id"], k)
            assert it["domain"] == d


def test_all_item_references_exist():
    known = K.known_reference_ids()
    for d in ("ecg", "rx"):
        for it in K.load_criteria(d):
            assert it["references"], it["id"]
            assert set(it["references"]) <= known, (it["id"], set(it["references"]) - known)


def test_required_references_present():
    need = {"goldberger_2023", "marriott", "chou", "bayes_de_luna", "aha_2007_part_i", "aha_2009_part_vi", "sbc_laudos_2022",
            "udmi4_2018", "esc_brady_2021", "felson_2025", "fraser_pare", "fleischner_glossary", "webb_higgins", "squire",
            "brant_helms", "keats_variants", "weir_abrahams", "abdominal_xray_made_easy", "greenspan"}
    assert need <= K.known_reference_ids()


def test_reference_lookup():
    r = K.reference("goldberger_2023")
    assert r.id == "goldberger_2023" and "Goldberger" in r.source
    u = K.reference("nao_existe")
    assert u.id == "nao_existe" and u.source == "nao_existe"


def test_select_relevant():
    sel = K.select_relevant("ecg", ["ecg.av_block_1"], ["pr_ms"])
    ids = [i["id"] for i in sel]
    assert ids[0] == "ecg.normal_intervals"
    assert "ecg.av_block_1" in ids
    sel = K.select_relevant("rx", ["rx.pleural_effusion"], [])
    assert "rx.pleural_effusion" in [i["id"] for i in sel] and "rx.systematic_approach" in [i["id"] for i in sel]
    assert K.format_items(sel)
