"""Unit tests for the captioned-radiograph sieve (synthetic captions / images, no network)."""
import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from medlens_data import Record
from medlens_data import sieve_rx as S
from medlens_data.collectors import europepmc_rx as E

GOOD = ("Chest radiograph (PA view) of a 54-year-old man showing a right-sided pneumothorax with a visible pleural line "
        "(arrows) and partial collapse of the right lung; the mediastinum is not shifted and there is no pleural effusion.")


# ------------------------------------------------------------ synthetic images
def xray(h=520, w=480, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    base = 60 + 90 * np.exp(-(((xx - w / 2) / (w / 3)) ** 2 + ((yy - h / 2) / (h / 2.5)) ** 2))
    a = np.clip(base + rng.normal(0, 18, (h, w)) + 20 * np.sin(xx / (9 + seed)), 0, 255).astype("uint8")
    return Image.fromarray(a, "L")


def to_bytes(im, fmt="PNG"):
    b = io.BytesIO()
    im.save(b, fmt)
    return b.getvalue()


def montage(ims, sep=14, color=255, vertical=False):
    if vertical:
        W, H = max(i.width for i in ims), sum(i.height for i in ims) + sep * (len(ims) - 1)
        out = Image.new("L", (W, H), color)
        y = 0
        for i in ims:
            out.paste(i, (0, y)); y += i.height + sep
    else:
        W, H = sum(i.width for i in ims) + sep * (len(ims) - 1), max(i.height for i in ims)
        out = Image.new("L", (W, H), color)
        x = 0
        for i in ims:
            out.paste(i, (x, 0)); x += i.width + sep
    return out


def cand(cap, img, cid="PMC1_fig1"):
    return S.Candidate(id=cid, caption=cap, image_bytes=to_bytes(img), ext="png", url="http://x", license="CC BY 4.0",
                       attribution="t", extra={"pmcid": "PMC1"})


# ------------------------------------------------------------ caption sieve
def test_good_caption_passes():
    r = S.caption_sieve(GOOD)
    assert r["ok"], r
    assert r["q"]["caption_score"] >= S.MIN_CAPTION_SCORE


@pytest.mark.parametrize("cap,reason", [
    ("", "no_caption"),
    ("Photograph of the patient's leg showing swelling of the lung and heart region with extensive description of many "
     "structures lobe opacity effusion mediastinum", "no_radiograph_word"),
    ("Axial CT scan of the chest showing a nodule in the right lung; chest radiograph was normal. CT also showed effusion "
     "and consolidation. MRI of the brain was normal.", "other_modality_dominates"),
    ("Chest X-ray.", "caption_score_low"),
    ("Histology of the lung biopsy (H&E stain) showing consolidation; the chest x-ray is shown in Fig 1.", "other_modality_dominates"),
])
def test_caption_rejections(cap, reason):
    r = S.caption_sieve(cap)
    assert not r["ok"] and r["reason"] == reason, r


def test_fact_does_not_trigger_ct_penalty():
    cap = ("In fact the chest radiograph showed a large right pleural effusion with a lung opacity and blunting of the "
           "costophrenic angle and heart shift to the left with mediastinal displacement.")
    r = S.caption_sieve(cap)
    assert r["ok"] and r["q"]["other_modality_mentions"] == 0


def test_extract_view_region_labels_arrows():
    assert S.extract_view(GOOD) == "PA"
    assert S.extract_view("Portable AP chest film, supine") == "AP"
    assert S.extract_view("Lateral view of the chest") == "LATERAL"
    assert S.extract_view("Right lateral decubitus film") == "DECUBITUS"
    assert S.extract_view("Radiograph of the hand") is None
    assert S.extract_region(GOOD) == "chest"
    assert S.extract_region("Abdominal radiograph showing dilated small bowel loops") == "abdomen"
    assert S.extract_region("Radiograph of the right wrist showing a distal radius fracture") == "extremity"
    labs = S.extract_labels(GOOD)
    assert "rx.pneumothorax" in labs
    assert "rx.pleural_effusion" not in labs          # "no pleural effusion" is negated
    assert "rx.cardiomegaly" in S.extract_labels("Radiograph showing marked cardiomegaly and bilateral pleural effusions")
    assert "rx.pneumoperitoneum" in S.extract_labels("Erect abdominal film showing free air under the diaphragm")
    assert "rx.bowel_obstruction" in S.extract_labels("Abdominal radiograph: dilated small bowel loops with air-fluid levels")
    ar = S.extract_arrows(GOOD)
    assert ar and "arrows" in ar[0]
    assert S.extract_arrows("Plain chest radiograph on admission.") == []


def test_split_subcaptions():
    head, subs = S.split_subcaptions("Chest X-ray. (A) PA view before treatment. (B) Lateral view after treatment.")
    assert head.startswith("Chest X-ray")
    assert subs["A"].startswith("PA view") and subs["B"].startswith("Lateral view")
    assert S.split_subcaptions("Chest X-ray on admission, no markers.")[1] == {}
    assert S.split_subcaptions("Only (A) one marker here.")[1] == {}


# ------------------------------------------------------------ image sieve
def test_image_stats_and_checks():
    ok, why = S.image_ok(S.image_stats(xray()))
    assert ok, why
    small = S.image_stats(xray(200, 200))
    assert S.image_ok(small) == (False, "too_small")
    rgb = np.zeros((500, 500, 3), "uint8"); rgb[..., 0] = 220; rgb[..., 1] = 40
    assert S.image_ok(S.image_stats(Image.fromarray(rgb))) == (False, "colour_image")
    blank = Image.new("L", (500, 500), 128)
    assert S.image_ok(S.image_stats(blank))[1] == "low_contrast_or_blank"


def test_small_coloured_arrow_tolerated():
    im = xray().convert("RGB")
    a = np.asarray(im).copy()
    a[100:112, 100:160] = (255, 215, 0)               # yellow arrow, tiny area
    assert S.image_ok(S.image_stats(Image.fromarray(a)))[0]


def test_panel_detection():
    a, b, c = xray(500, 450, 1), xray(500, 450, 2), xray(500, 450, 3)
    assert len(S.detect_panels(xray())) == 1
    m2 = montage([a, b])
    boxes = S.sort_reading_order(S.detect_panels(m2))
    assert len(boxes) == 2 and boxes[0][0] < boxes[1][0]
    assert len(S.detect_panels(montage([a, b], color=0))) == 2          # black separators
    assert len(S.detect_panels(montage([a, b], vertical=True))) == 2
    grid = montage([montage([a, b]), montage([c, a])], vertical=True)    # 2x2
    assert len(S.detect_panels(grid)) == 4


# ------------------------------------------------------------ end to end
def test_sieve_keeps_single_good_figure(tmp_path):
    st = S.SieveStats()
    recs = S.sieve_candidate(cand(GOOD, xray()), tmp_path, "t", st)
    assert len(recs) == 1 and st.kept == 1
    r = recs[0]
    assert (tmp_path / r.path).exists()
    assert r.view == "PA" and r.extra["region"] == "chest" and "rx.pneumothorax" in r.labels
    assert r.quality["caption_score"] >= 0.35 and r.quality["min_side"] if "min_side" in r.quality else True
    assert r.quality["width"] == 480 and r.license == "CC BY 4.0"


def test_sieve_rejects_with_reasons(tmp_path):
    st = S.SieveStats()
    assert S.sieve_candidate(cand("Chest X-ray.", xray()), tmp_path, "t", st) == []
    rgb = Image.fromarray(np.stack([np.full((500, 500), v, "uint8") for v in (230, 40, 40)], 2))
    assert S.sieve_candidate(cand(GOOD, rgb), tmp_path, "t", st) == []
    assert S.sieve_candidate(cand(GOOD, xray(200, 200)), tmp_path, "t", st) == []
    assert st.kept == 0 and st.reasons["caption:caption_score_low"] == 1
    assert st.reasons["image:colour_image"] == 1 and st.reasons["image:too_small"] == 1


def test_montage_split_and_subcaptions(tmp_path):
    cap = ("Chest radiographs of the patient. (A) PA view on admission showing a right pleural effusion with lung "
           "opacity and costophrenic blunting. (B) Lateral view showing the effusion with posterior pleural layering "
           "and an anterior mediastinal line.")
    st = S.SieveStats()
    recs = S.sieve_candidate(cand(cap, montage([xray(520, 460, 1), xray(520, 460, 2)])), tmp_path, "t", st)
    assert [r.id for r in recs] == ["PMC1_fig1_A", "PMC1_fig1_B"]
    assert recs[0].view == "PA" and recs[1].view == "LATERAL"
    assert recs[0].quality["panel_split"] and recs[0].extra["n_panels_in_figure"] == 2
    assert recs[0].caption.startswith("Chest radiographs of the patient. PA view")
    assert Image.open(tmp_path / recs[0].path).size[0] < 520


def test_montage_without_matching_subcaptions_dropped(tmp_path):
    st = S.SieveStats()
    recs = S.sieve_candidate(cand(GOOD, montage([xray(520, 460, 1), xray(520, 460, 2)])), tmp_path, "t", st)
    assert recs == [] and st.reasons["panels:montage_unassignable"] == 1
    recs = S.sieve_candidate(cand(GOOD.replace("(arrows)", "(A) arrows (B) here"), xray()), tmp_path, "t", st)
    assert recs == [] and st.reasons["panels:subcaptions_but_single_image"] == 1


def test_sub_panel_that_is_ct_is_dropped_but_xray_kept(tmp_path):
    cap = ("Imaging. (A) Chest radiograph showing right lower lobe consolidation with air bronchograms and lung opacity "
           "(arrow). (B) Axial CT scan of the chest showing the consolidation and a small effusion.")
    st = S.SieveStats()
    recs = S.sieve_candidate(cand(cap, montage([xray(520, 460, 1), xray(520, 460, 2)])), tmp_path, "t", st)
    assert [r.id for r in recs] == ["PMC1_fig1_A"] and "rx.consolidation" in recs[0].labels
    assert any(k.startswith("caption:") and k.endswith("(panel)") for k in st.reasons)


def test_dedupe_and_summary(tmp_path):
    st = S.SieveStats()
    recs = []
    recs += S.sieve_candidate(cand(GOOD, xray(seed=5), "a"), tmp_path, "t", st)
    recs += S.sieve_candidate(cand(GOOD, xray(seed=5), "b"), tmp_path, "t", st)     # identical image
    recs += S.sieve_candidate(cand(GOOD.replace("54", "70"), xray(seed=9).transpose(Image.FLIP_LEFT_RIGHT), "c"), tmp_path, "t", st)
    kept = S.finalize_dedupe(recs, tmp_path, st)
    assert [r.id for r in kept][0] == "a" and "b" not in [r.id for r in kept]
    assert st.reasons["duplicate_image"] >= 1
    summ = S.summarize(kept)
    assert summ["n"] == len(kept) and summ["views"]["PA"] == len(kept)


# ------------------------------------------------------------ Europe PMC XML parsing
XML = """<?xml version="1.0"?><article article-type="case-report" xmlns:xlink="http://www.w3.org/1999/xlink"><front>
<journal-meta><journal-title-group><journal-title>Case Rep Radiol</journal-title></journal-title-group></journal-meta>
<article-meta><article-id pub-id-type="doi">10.1/abc</article-id><title-group><article-title>A case</article-title></title-group>
<contrib-group><contrib><name><surname>Silva</surname></name></contrib></contrib-group>
<pub-date><year>2024</year></pub-date>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"><license-p>CC BY</license-p></license></permissions>
</article-meta></front><body>
<fig id="f1"><label>Figure 1</label><caption><p>Chest <italic>radiograph</italic> (PA) with arrows.</p></caption><graphic xlink:href="x-g001"/></fig>
<fig id="f2"><label>Figure 2</label><caption><p>No graphic here.</p></caption></fig>
</body></article>"""


def test_parse_article_xml():
    a = E.parse_article(XML)
    assert a["license"] == "CC BY 4.0" and a["doi"] == "10.1/abc" and a["year"] == "2024" and a["authors"] == ["Silva"]
    assert len(a["figs"]) == 1 and a["figs"][0]["caption"] == "Chest radiograph (PA) with arrows."
    assert a["figs"][0]["href"] == "x-g001" and a["article_type"] == "case-report"
    nc = XML.replace("licenses/by/4.0", "licenses/by-nc-nd/4.0")
    assert E.parse_article(nc)["license"] == "CC BY-NC-ND 4.0"
    zero = XML.replace("licenses/by/4.0", "publicdomain/zero/1.0")
    assert E.parse_article(zero)["license"] == "CC0 1.0"


def test_record_roundtrip(tmp_path):
    recs = S.sieve_candidate(cand(GOOD, xray()), tmp_path, "t")
    r2 = Record(**__import__("json").loads(recs[0].to_json()))
    assert r2.labels == recs[0].labels and r2.quality["sieve"] == "rx_captioned_v1"
