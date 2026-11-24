"""Offline tests for the ecglibrary stub and the Wikimedia ECG metadata->Record mapping."""
from medlens_data.collectors import ecglibrary
from medlens_data.collectors.wikimedia_ecg import (extract_labels, licence_free, record_from_imageinfo, strip_html)


def _page(lic="CC BY-SA 4.0", desc="<p>12-lead ECG showing <b>atrial fibrillation</b> with rapid ventricular response</p>",
          cats="Atrial fibrillation ECGs|Electrocardiograms", width=2000, mime="image/png", title="File:AF.png"):
    return {"pageid": 42, "title": title, "imageinfo": [{
        "url": "https://upload.wikimedia.org/x.png", "descriptionurl": "https://commons.wikimedia.org/wiki/File:AF.png",
        "width": width, "height": 1000, "mime": mime,
        "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": '<a href="u">Jane Doe</a>'},
                        "ImageDescription": {"value": desc}, "Categories": {"value": cats}}}]}


def test_maps_free_licence_record():
    rec, why = record_from_imageinfo(_page())
    assert rec and not why
    assert rec.id == "wm42" and rec.source == "wikimedia_ecg" and rec.modality == "ECG"
    assert rec.license.startswith("CC BY-SA 4.0")
    assert rec.attribution == "Jane Doe / Wikimedia Commons"
    assert "<" not in rec.caption and "atrial fibrillation" in rec.caption and "Atrial fibrillation ECGs" in rec.caption
    assert "ecg.atrial_fibrillation" in rec.labels
    assert rec.quality["caption_score"] > 0


def test_rejections():
    assert record_from_imageinfo(_page(lic="CC BY-NC 4.0"))[0] is None
    assert record_from_imageinfo(_page(width=800))[1] == "too_small"
    assert record_from_imageinfo(_page(mime="image/svg+xml"))[1].startswith("mime")
    assert record_from_imageinfo(_page(desc="Schematic diagram of an ECG"))[1] == "diagram_like_text"
    assert record_from_imageinfo(_page(cats="ECG diagrams"))[1] == "diagram_like_text"


def test_licence_and_labels_and_html():
    assert licence_free("CC0") and licence_free("Public domain") and licence_free("CC BY 3.0")
    assert not licence_free("CC BY-ND 4.0") and not licence_free("") and not licence_free("Fair use")
    assert extract_labels("Left bundle branch block, LBBB") == ["ecg.lbbb"]
    assert "ecg.st_elevation" in extract_labels("Acute inferior myocardial infarction")
    assert strip_html("a&nbsp;<i>b</i>&amp;c") == "a b &c"


def test_ecglibrary_refuses_without_permission(capsys):
    assert ecglibrary.main([]) == 2
