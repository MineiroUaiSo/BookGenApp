"""PHI em pixels: detecção/mascaramento de texto queimado e política de envio à IA externa."""
import base64
import io

import numpy as np
import pydicom
import pytest
from PIL import Image, ImageDraw, ImageFont

from app import llm
from app.dicom import burned_text as B
from app.rx import analyze_image
from app.schemas import AIReport, RXAnalysis

H, W = 1200, 1000


@pytest.fixture(autouse=True)
def _no_models(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")


def _base(seed=0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:H, 0:W]
    a = 90 + 70 * np.exp(-(((x - W / 2) / (W * 0.3)) ** 2 + ((y - H / 2) / (H * 0.4)) ** 2)) + rng.normal(0, 5, (H, W))
    return np.clip(a, 0, 255).astype(np.uint8)


def _font(size=30):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow antigo
        return ImageFont.load_default()


def _draw(a, lines, size=30, fill=255):
    im = Image.fromarray(a)
    d = ImageDraw.Draw(im)
    f = _font(size)
    for x, y, s in lines:
        d.text((x, y), s, fill=fill, font=f)
    return np.array(im)


CORNER_LINES = [(30, 25, "NOME: MARIA SILVA 1234"), (30, 70, "DN 12/03/1960 F"), (560, 1130, "HOSP CENTRAL 2024")]


def _ds(tag=None):
    ds = pydicom.Dataset()
    if tag is not None:
        ds.BurnedInAnnotation = tag
    return ds


def test_burned_text_clean_image_is_intact():
    a = _base()
    out, res = B.scrub(a)
    assert np.array_equal(out, a) and not res.detected and not res.block_external


def test_burned_text_corners_detected_and_masked():
    a = _draw(_base(), CORNER_LINES)
    out, res = B.scrub(a, _ds("NO"))
    assert res.detected and res.masked and res.n_regions >= 1 and not res.block_external
    assert B.detect_text_mask(out, sensitive=True)[1] == 0
    changed = out != a
    assert changed[:140, :450].any() and changed[1100:, 500:].any()
    assert not changed[300:900, 200:800].any()          # centro (anatomia) intacto
    assert (a[:140, :450] == 255).sum() > (out[:140, :450] == 255).sum()


def test_burned_text_dark_text_on_bright_background():
    a = _draw(255 - _base(), CORNER_LINES, fill=0)
    out, res = B.scrub(a)
    assert res.detected and res.masked
    assert B.detect_text_mask(out, sensitive=True)[1] == 0


def test_burned_text_does_not_touch_center_text_free_anatomy_edges():
    a = _base()
    a[:, :30] = 0                      # tarja preta lateral (colimação)
    a[100:104, :] = 255                # fio fino horizontal
    out, res = B.scrub(a)
    assert not res.detected and np.array_equal(out, a)


def test_policy_tag_yes_blocks_even_if_clean():
    out, res = B.scrub(_base(), _ds("YES"))
    assert res.tag_yes and res.block_external and not res.detected


def test_policy_tag_no_and_missing():
    assert not B.scrub(_base(), _ds("NO"))[1].block_external
    assert B.burned_in_tag(_ds()) == "" and B.burned_in_tag(None) == "" and B.burned_in_tag(_ds(" yes ")) == "YES"


def test_policy_detected_but_not_masked_blocks(monkeypatch):
    a = _draw(_base(), CORNER_LINES)
    real = B.detect_text_mask
    monkeypatch.setattr(B, "detect_text_mask",
                        lambda img, sensitive=False: real(img, sensitive) if not sensitive else (np.ones_like(img, bool), 1))
    _, res = B.scrub(a)
    assert res.detected and not res.masked and res.block_external


def test_scrub_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(B, "detect_text_mask", boom)
    out, res = B.scrub(_base())
    assert res.detected and not res.masked and res.block_external


def _png_array(img):
    return np.array(Image.open(io.BytesIO(base64.b64decode(img.image_png_b64.split(",")[-1]))).convert("L"))


def test_analyze_image_masks_before_png_and_reports():
    a = _draw(_base(), CORNER_LINES)
    r = analyze_image(a, "i1", _ds("NO"))
    assert not r.external_ai_blocked and "mascarado" in r.burned_text
    assert B.detect_text_mask(_png_array(r), sensitive=True)[1] == 0


def test_analyze_image_tag_yes_blocks_external():
    r = analyze_image(_base(), "i2", _ds("YES"))
    assert r.external_ai_blocked and "BurnedInAnnotation=YES" in r.burned_text


def test_analyze_image_switch_off(monkeypatch):
    monkeypatch.setenv("MEDLENS_BURNED_TEXT", "off")
    a = _draw(_base(), CORNER_LINES)
    r = analyze_image(a, "i3", _ds("NO"))
    assert not r.external_ai_blocked and "sem texto detectado" in r.burned_text


def test_rx_report_blocked_never_calls_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(llm._client, "make_client", lambda: (_ for _ in ()).throw(AssertionError("rede!")))
    r = analyze_image(_base(), "i4", _ds("YES"))
    rep = llm.rx_report(RXAnalysis(study_id="s", images=[r]))
    assert isinstance(rep, AIReport) and rep.external_ai_blocked and rep.available is False
    assert "texto queimado não enviada à IA externa" in rep.limitations[0]


def test_rx_report_not_blocked_goes_to_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    called = []
    monkeypatch.setattr(llm._client, "make_client", lambda: object())

    def fake_run(*a, **k):
        called.append(1)
        raise llm._client.LLMProviderError("stop")

    monkeypatch.setattr(llm._client, "run_resilient", fake_run)
    r = analyze_image(_base(), "i5", _ds("NO"))
    llm.rx_report(RXAnalysis(study_id="s", images=[r]))
    assert called
