import numpy as np

from app.rx.analyze import analyze_image
from app.rx.scope import check_scope
from app.schemas import BodyRegion


def test_blank_image_out_of_scope():
    oos, why = check_scope(np.full((256, 256), 200, np.uint8), BodyRegion.CHEST, "chest_frontal")
    assert oos and "branco" in why


def test_lineart_out_of_scope():
    img = np.full((300, 400), 235, np.uint8)
    img[::20, :] = 40
    img[:, ::20] = 40
    oos, why = check_scope(img, BodyRegion.CHEST, "chest_frontal")
    assert oos and "documento" in why


def test_radiograph_like_noise_in_scope():
    rng = np.random.default_rng(0)
    img = np.clip(rng.normal(120, 70, (256, 256)), 0, 255).astype(np.uint8)
    assert check_scope(img, BodyRegion.CHEST, "chest_frontal") == (False, None)


def test_non_chest_region_flagged():
    rng = np.random.default_rng(1)
    img = np.clip(rng.normal(120, 70, (256, 256)), 0, 255).astype(np.uint8)
    oos, why = check_scope(img, BodyRegion.ABDOMEN, "abdomen")
    assert oos and "abdome" in why


def test_tiny_image_out_of_scope():
    assert check_scope(np.zeros((20, 20), np.uint8), BodyRegion.CHEST, "x")[0]


def test_analyze_blank_gives_no_findings_and_flag():
    from app.rx.findings import study_findings
    res = analyze_image(np.full((256, 256), 128, np.uint8), "i1", use_model=False)
    assert res.out_of_scope and res.scope_reason
    assert study_findings([res]) == []
