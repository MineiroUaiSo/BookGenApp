"""Tests for bench.rx_bench using tiny synthetic fixtures (heuristic path only, no network/models)."""
import json
import math

import numpy as np
import pytest
from PIL import Image

from bench import rx_bench as B
from test_rx_phantoms import pa_phantom


def test_dice_iou_and_wilson_auc():
    a = np.zeros((10, 10), bool); a[:5] = True
    b = np.zeros((10, 10), bool); b[:5, :5] = True
    d, i = B.dice_iou(a, b)
    assert d == pytest.approx(2 * 25 / 75) and i == pytest.approx(0.5)
    assert B.dice_iou(np.zeros((3, 3), bool), np.zeros((3, 3), bool)) == (1.0, 1.0)
    lo, hi = B.wilson(8, 10)
    assert 0.4 < lo < 0.8 < hi <= 1.0
    assert B.auc_score([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == 1.0
    assert B.auc_score([1, 0, 1, 0], [0.5, 0.5, 0.5, 0.5]) == 0.5
    assert math.isnan(B.auc_score([1, 1], [0.1, 0.2]))
    a_, lo, hi = B.auc_ci([1, 1, 0, 0, 1, 0], [0.9, 0.7, 0.4, 0.2, 0.6, 0.5], n_boot=50)
    assert lo <= a_ <= hi


def test_norm_struct_and_gt_paths():
    assert B.norm_struct("left lung") == "left_lung"
    assert B.norm_struct("mask_right") == "right_lung"
    assert B.norm_struct("Heart") == "heart"
    assert B.norm_struct("right_clavicle") == "right_clavicle"
    assert B.norm_struct("mask") == "lungs"

    class R:  # minimal Record stand-in
        extra = {"masks": {"left lung": "m/l.png", "right lung": "m/r.png", "heart": "m/h.png"}, "other": 1}
    assert B.gt_paths(R) == {"left_lung": "m/l.png", "right_lung": "m/r.png", "heart": "m/h.png"}

    class R2:
        extra = {"mask_path": "m/x.png"}
    assert B.gt_paths(R2) == {"lungs": "m/x.png"}


def test_caption_hints_and_labels():
    h = B.caption_hints("Chest radiograph, lateral view, shows pleural effusion")
    assert h["region"] == "chest" and h["view"] == "lateral"
    assert B.caption_hints("PA chest x-ray")["view"] == "frontal"
    assert B.caption_hints("Abdominal film with dilated bowel loops")["region"] == "abdomen"
    assert B.caption_labels("There is cardiomegaly. No pneumothorax.") == {"cardiomegaly"}
    assert "normal" not in B.caption_labels("Normal chest")  # normal only via structured labels


def test_ctr_from_masks():
    heart = np.zeros((50, 100), bool); heart[20:40, 30:60] = True
    lungs = np.zeros((50, 100), bool); lungs[5:45, 10:90] = True
    assert B.ctr_from_masks(heart, lungs) == pytest.approx(30 / 80)
    assert B.ctr_from_masks(None, lungs) is None


def _make_seg_source(tmp_path, monkeypatch):
    root = tmp_path / "ds"
    src = root / "fake_masks"
    (src / "m").mkdir(parents=True)
    img, truth = pa_phantom(256)
    Image.fromarray(img).save(src / "a.png")
    # GT: crude lungs = dark regions
    lung = img < 80
    Image.fromarray((lung * 255).astype(np.uint8)).save(src / "m" / "a_lungs.png")
    rec = {"id": "a", "source": "fake_masks", "modality": "RX", "kind": "image", "path": "a.png", "url": "", "license": "cc0",
           "extra": {"masks": {"lungs": "m/a_lungs.png"}}, "labels": [], "caption": "", "quality": {}}
    (src / "manifest.jsonl").write_text(json.dumps(rec) + "\n")
    import medlens_data
    monkeypatch.setattr(medlens_data, "DATA_ROOT", root)
    monkeypatch.setenv("MEDLENS_BENCH_DIR", str(tmp_path / "bench"))
    monkeypatch.setattr(B, "MASK_SOURCES", ["fake_masks"])
    monkeypatch.setitem(B.KIND_SOURCES, "seg", ["fake_masks"])
    return root


def test_seg_pipeline_and_report(tmp_path, monkeypatch):
    _make_seg_source(tmp_path, monkeypatch)
    n = B.run_kind("seg", ["heur"], None, 1, 256)
    assert n == 1
    assert B.run_kind("seg", ["heur"], None, 1, 256) == 0  # cached
    rows = list(B.load_cache("seg").values())
    assert rows[0]["ok"], rows[0].get("error")
    assert 0.0 <= rows[0]["metrics"]["lungs"]["dice"] <= 1.0
    out = B.build_report(tmp_path / "rx.md")
    txt = out.read_text()
    assert "Segmentação" in txt and "lungs" in txt


def test_iu_task_and_report(tmp_path, monkeypatch):
    root = tmp_path / "ds"
    src = root / "iu_xray"
    src.mkdir(parents=True)
    img, _ = pa_phantom(256)
    Image.fromarray(img).save(src / "f.png")
    Image.fromarray(img).save(src / "l.png")
    recs = [{"id": "f", "source": "iu_xray", "modality": "RX", "kind": "image", "path": "f.png", "url": "", "license": "cc",
             "view": "PA", "group": "S1", "labels": ["rx.normal"], "caption": "normal", "extra": {}, "quality": {}},
            {"id": "l", "source": "iu_xray", "modality": "RX", "kind": "image", "path": "l.png", "url": "", "license": "cc",
             "view": "LATERAL", "group": "S1", "labels": ["rx.normal"], "caption": "normal", "extra": {}, "quality": {}}]
    (src / "manifest.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    import medlens_data
    monkeypatch.setattr(medlens_data, "DATA_ROOT", root)
    monkeypatch.setenv("MEDLENS_BENCH_DIR", str(tmp_path / "bench"))
    assert B.run_kind("iu", ["heur"], None, 1, 256) == 1
    r = list(B.load_cache("iu").values())[0]
    assert r["ok"] and r["gt_labels"] == ["normal"] and len(r["images"]) == 2
    assert r["recon"]["attempted"]
    B.build_report(tmp_path / "rx.md")
    assert "IU X-ray" in (tmp_path / "rx.md").read_text()


def test_cap_task_and_report(tmp_path, monkeypatch):
    root = tmp_path / "ds"
    src = root / "europepmc_rx"
    src.mkdir(parents=True)
    img, _ = pa_phantom(256)
    Image.fromarray(img).save(src / "c.png")
    rec = {"id": "c", "source": "europepmc_rx", "modality": "RX", "kind": "image", "path": "c.png", "url": "", "license": "cc",
           "view": None, "group": None, "labels": [], "caption": "PA chest radiograph shows cardiomegaly. No pneumothorax.",
           "extra": {}, "quality": {}}
    (src / "manifest.jsonl").write_text(json.dumps(rec) + "\n")
    import medlens_data
    monkeypatch.setattr(medlens_data, "DATA_ROOT", root)
    monkeypatch.setenv("MEDLENS_BENCH_DIR", str(tmp_path / "bench"))
    assert B.run_kind("cap", ["heur"], None, 1, 256) == 1
    r = list(B.load_cache("cap").values())[0]
    assert r["ok"] and r["gt_labels"] == ["cardiomegaly"] and r["hints"]["view"] == "frontal"
    B.build_report(tmp_path / "rx.md")
    assert "Imagens com legenda" in (tmp_path / "rx.md").read_text()


def test_findings_note_only_measured():
    assert "sem resultados IU" in B._findings_note({})
    head = {("iu_auc", "effusion", "modelo Effusion", "model"): (0.81, 0.7, 0.9, 120, 30),
            ("iu_find", "effusion", "modelo Effusion", "model"): ((3, 30), (85, 90), (3, 8), 120, 30)}
    txt = B._findings_note(head)
    assert "0.81" in txt and "3/30" in txt and "0,89" not in txt
