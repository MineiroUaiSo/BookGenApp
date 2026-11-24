from pathlib import Path

from medlens_data.collectors.litfl import best_image_url, build_record, map_labels, parse_page, ecg_image_check

SAMPLE = Path(__file__).parent / "data" / "litfl_sample.html"
URL = "https://litfl.com/first-degree-heart-block-ecg-library/"


def test_parse_sample_page():
    pp = parse_page(SAMPLE.read_text(encoding="utf-8"), URL)
    assert pp.title == "First Degree Heart Block"
    assert pp.authors == ["John Larkin", "Robert Buttner"]
    assert "ecg-library" in pp.categories
    assert len(pp.figures) >= 1
    f = pp.figures[0]
    assert f.image_url.endswith("ECG-Rhythm-strip-PR-interval-prolonged-1st-degree-AV-block.jpg")
    assert (f.width, f.height) == (900, 225)
    assert f.figcaption == "First degree heart block"
    assert "PR interval" in f.before
    # author box image must not be picked up
    assert all("author.jpg" not in x.image_url for x in pp.figures)


def test_record_labels_and_attribution():
    pp = parse_page(SAMPLE.read_text(encoding="utf-8"), URL)
    chk = {"width": 900, "height": 225}
    r = build_record(pp, pp.figures[0], "images/x.jpg", chk, "attr")
    assert "ecg.av_block_1" in r["labels"]
    assert r["license"] == "CC BY-NC-SA 4.0"
    assert r["extra"]["page_title"] == "First Degree Heart Block"
    assert r["extra"]["image_size"] == [900, 225]


def test_map_labels():
    assert "ecg.lbbb" in map_labels("Left bundle branch block with Sgarbossa criteria")
    assert "ecg.rbbb" in map_labels("RBBB pattern")
    assert "ecg.atrial_fibrillation" in map_labels("Irregularly irregular rhythm, atrial fibrillation")
    assert "ecg.hyperkalemia" in map_labels("Hyperkalaemia, peaked T waves")
    assert map_labels("nothing relevant") == []


def test_best_image_url_srcset():
    from bs4 import BeautifulSoup
    img = BeautifulSoup('<img src="https://litfl.com/a-340x85.jpg" srcset="https://litfl.com/a-340x85.jpg 340w, https://litfl.com/a-900x225.jpg 900w">', "html.parser").img
    assert best_image_url(img, URL) == "https://litfl.com/a-900x225.jpg".replace("-900x225", "")


def test_image_check_rejects_small_logo():
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buf, "PNG")
    assert not ecg_image_check(buf.getvalue(), "https://litfl.com/logo.png")["is_ecg"]
