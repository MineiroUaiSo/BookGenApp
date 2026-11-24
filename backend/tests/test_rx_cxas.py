"""R3: CXAS integration is opt-in (MEDLENS_RX_CXAS=1), subprocess-based and fails soft. The subprocess is stubbed."""
from __future__ import annotations

import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from app.rx import analyze_image, seg_cxas
from app.rx.analyze import supported_structures
from test_rx_phantoms import pa_phantom


def _fake_python(tmp_path, monkeypatch, flag="1"):
    py = tmp_path / "python"
    py.write_text("")
    monkeypatch.setenv("MEDLENS_CXAS_PYTHON", str(py))
    if flag is None:
        monkeypatch.delenv("MEDLENS_RX_CXAS", raising=False)
    else:
        monkeypatch.setenv("MEDLENS_RX_CXAS", flag)


def _stub_run(monkeypatch, keys, ok=True, shape=(512, 512)):
    calls = []

    def run(cmd, timeout):
        calls.append(cmd)
        out = cmd[cmd.index("--out") + 1]
        d = f"{out}/00000"
        import os
        os.makedirs(d)
        masks = {}
        for k in keys:
            m = np.zeros(shape, np.uint8)
            m[100:200, 100:200] = 255
            Image.fromarray(m).save(f"{d}/{k}.png")
            masks[k] = f"{d}/{k}.png"
        body = {"ok": True, "device": "cpu", "load_s": 0.0,
                "results": [{"image": "x", "view": "frontal", "t": 0.1, "shape": list(shape), "masks": masks}]} \
            if ok else {"ok": False, "error": "boom"}
        return subprocess.CompletedProcess(cmd, 0 if ok else 1, "noise\n" + json.dumps(body), "")

    monkeypatch.setattr(seg_cxas, "_run", run)
    return calls


def test_off_by_default(tmp_path, monkeypatch):
    _fake_python(tmp_path, monkeypatch, flag=None)
    assert not seg_cxas.enabled()
    assert seg_cxas.segment(np.zeros((8, 8), np.uint8), "frontal") is None
    assert "sternum" not in supported_structures("model", "frontal")


def test_flag_without_venv_is_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_CXAS", "1")
    monkeypatch.setenv("MEDLENS_CXAS_PYTHON", str(tmp_path / "missing" / "python"))
    assert not seg_cxas.enabled()


def test_segment_parses_runner_json(tmp_path, monkeypatch):
    _fake_python(tmp_path, monkeypatch)
    calls = _stub_run(monkeypatch, ["sternum", "ribs_left"])
    out = seg_cxas.segment(np.zeros((512, 512), np.uint8), "lateral")
    assert set(out) == {"sternum", "ribs_left"} and out["sternum"].sum() == 100 * 100
    assert calls[0][calls[0].index("--view") + 1] == "lateral"


@pytest.mark.parametrize("exc", [subprocess.TimeoutExpired("x", 1), OSError("no exec")])
def test_segment_fails_soft(tmp_path, monkeypatch, exc):
    _fake_python(tmp_path, monkeypatch)

    def boom(cmd, timeout):
        raise exc

    monkeypatch.setattr(seg_cxas, "_run", boom)
    assert seg_cxas.segment(np.zeros((8, 8), np.uint8), "frontal") is None


def test_segment_runner_error_returns_none(tmp_path, monkeypatch):
    _fake_python(tmp_path, monkeypatch)
    _stub_run(monkeypatch, [], ok=False)
    assert seg_cxas.segment(np.zeros((8, 8), np.uint8), "frontal") is None


def test_fill_masks_only_adds_missing():
    m = np.ones((4, 4), bool)
    cx = {"sternum": m, "spine": m, "ribs_left": m, "ribs_right": m, "left_hemidiaphragm": m}
    out = seg_cxas.fill_masks(cx, {"spine"})
    assert set(out) == {"sternum", "ribs", "left_diaphragm"}


def test_analyze_adds_cxas_structures_when_enabled(tmp_path, monkeypatch):
    img, _ = pa_phantom()
    base = analyze_image(img, "i1", None, use_model=False)
    _fake_python(tmp_path, monkeypatch, flag=None)
    off = analyze_image(img, "i1", None, use_model=False)
    assert [s.key for s in off.structures] == [s.key for s in base.structures]
    _fake_python(tmp_path, monkeypatch)
    _stub_run(monkeypatch, ["sternum", "ribs_left", "ribs_right", "spine"], shape=img.shape)
    on = analyze_image(img, "i1", None, use_model=False)
    added = [s for s in on.structures if s.origin == "cxas"]
    base_keys = {s.key for s in base.structures}
    assert "sternum" in {s.key for s in added}
    assert not ({s.key for s in added} & base_keys)  # only fills what the base pipeline did not produce
    assert "CXAS" in on.quality["observações"]
    assert {s.key for s in base.structures} <= {s.key for s in on.structures}


def test_analyze_unchanged_when_cxas_fails(tmp_path, monkeypatch):
    img, _ = pa_phantom()
    base = analyze_image(img, "i1", None, use_model=False)
    _fake_python(tmp_path, monkeypatch)
    _stub_run(monkeypatch, [], ok=False)
    on = analyze_image(img, "i1", None, use_model=False)
    assert [s.key for s in on.structures] == [s.key for s in base.structures]
    assert "CXAS" not in on.quality.get("observações", "")
