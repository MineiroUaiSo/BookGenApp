from medlens_data.collectors.iu_xray import map_labels, parse_report

XML = """<?xml version="1.0" encoding="utf-8"?>
<eCitation><uId id="CXR9"/><licenseURL>http://creativecommons.org/licenses/by-nc-nd/4.0/</licenseURL>
<MedlineCitation><Article><Abstract>
<AbstractText Label="INDICATION">dyspnea</AbstractText>
<AbstractText Label="FINDINGS">Heart is enlarged. Small left pleural effusion. No pneumothorax.</AbstractText>
<AbstractText Label="IMPRESSION">Cardiomegaly with effusion.</AbstractText>
</Abstract></Article></MedlineCitation>
<MeSH><major>Cardiomegaly/mild</major><major>Pleural Effusion/left/small</major>
<major>Catheters, Indwelling/right</major><automatic>Heart</automatic></MeSH>
<parentImage id="CXR9_IM-1-1001"><caption>Chest radiograph PA and lateral</caption></parentImage>
<parentImage id="CXR9_IM-1-2001"><caption>Chest radiograph PA and lateral</caption></parentImage>
</eCitation>"""


def test_parse_report():
    recs = parse_report(XML)
    assert [r.id for r in recs] == ["CXR9_IM-1-1001", "CXR9_IM-1-2001"]
    r = recs[0]
    assert r.group == "CXR9" and r.modality == "RX" and r.path == "images/CXR9_IM-1-1001.png"
    assert r.caption.startswith("Heart is enlarged") and r.caption.endswith("effusion.")
    assert set(r.labels) == {"rx.cardiomegaly", "rx.pleural_effusion", "rx.device"}
    assert r.extra["indication"] == "dyspnea" and r.extra["mesh_automatic"] == ["Heart"]
    assert r.license == "CC BY-NC-ND 4.0"
    assert [x.view for x in recs] == ["PA", "LATERAL"]
    assert r.quality["caption_score"] > 0


def test_missing_images_filtered_and_labels():
    assert len(parse_report(XML, image_exists=lambda n: n.endswith("2001.png"))) == 1
    assert map_labels(["normal"]) == ["rx.normal"]
    assert "rx.costophrenic_blunting" in map_labels(["Costophrenic Angle/bilateral/blunted"])
    assert map_labels(["No Indexing"]) == []
