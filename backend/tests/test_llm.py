import base64
import io
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import llm
from app.llm import client as C
from app.llm import schema as S
from app.schemas import (BodyRegion, ECGAnalysis, ECGSignal, GlobalMeasurements, RXAnalysis, RXImageAnalysis, RXView,
                         SourceKind, Structure)


def _ecg():
    import math
    fs = 250.0
    n = int(fs * 10)
    leads = {k: [0.1 * math.sin(2 * math.pi * 1.2 * i / fs) for i in range(n)] for k in
             ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]}
    sig = ECGSignal(fs=fs, leads=leads, duration_s=10, source=SourceKind.CSV)
    return ECGAnalysis(study_id="s", signal=sig, global_measurements=GlobalMeasurements(heart_rate_bpm=72, pr_ms=210))


def _png(size=(64, 64), color=(120, 120, 120)):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    @contextmanager
    def _stream(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0)
        msg = SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5", stop_details=None,
                              content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=out)],
                              usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0,
                                                    cache_creation_input_tokens=0))
        yield SimpleNamespace(get_final_message=lambda: msg)


GOOD = {
    "description": "desc final",
    "findings": [
        {"code": "ecg.av_block_1", "label": "BAV 1º grau", "severity": "abnormal", "evidence": ["PR 210 ms"],
         "references": ["goldberger_2023", "ref_inventada"], "confidence": 1.7},
        {"code": "x", "label": "y", "severity": "weird", "evidence": [], "references": [], "confidence": 0.2},
    ],
    "differentials": [{"diagnosis": "tônus vagal", "rationale": "r", "supporting": [], "against": [],
                       "references": ["marriott", "fake"], "confidence": 0.4}],
    "disagreements_with_measurements": ["nenhuma"],
    "limitations": ["foto"],
}


def test_unavailable_without_credentials(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert llm.ai_available() is False
    rep = llm.ecg_report(_ecg(), None)
    assert rep.available is False and rep.limitations
    rx = RXAnalysis(study_id="s", images=[])
    assert llm.rx_report(rx).available is False


def test_ai_available_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert llm.ai_available() is True
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "t")
    assert llm.ai_available() is True


def test_output_schema_strict():
    sch = S.output_schema(["a", "b"])

    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "object":
                assert n["additionalProperties"] is False
                assert set(n["required"]) == set(n["properties"])
            assert "minimum" not in n and "maximum" not in n
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(sch)
    json.dumps(sch)


def test_to_report_validates_references():
    rep = S.to_report(GOOD, "m")
    assert [r.id for r in rep.findings[0].references] == ["goldberger_2023"]
    assert rep.findings[0].confidence == 1.0
    assert rep.findings[0].origin == "llm"
    assert rep.findings[1].severity == "abnormal"
    assert [r.id for r in rep.differentials[0].references] == ["marriott"]


def test_ecg_report_two_stage(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("MEDLENS_MODEL", "claude-opus-5-5")
    fake = FakeClient(["descrição etapa 1", json.dumps(GOOD)])
    monkeypatch.setattr(C, "make_client", lambda: fake)
    rep = llm.ecg_report(_ecg(), _png())
    assert rep.available and rep.description == "desc final"
    assert len(fake.calls) == 2
    c1, c2 = fake.calls
    assert c1["model"] == "claude-opus-5-5" and c1["thinking"] == {"type": "adaptive"}
    assert c1["output_config"]["effort"] == "high" and "format" not in c1["output_config"]
    assert c2["output_config"]["format"]["type"] == "json_schema"
    assert c1["system"][-1]["cache_control"] == {"type": "ephemeral"}
    types = [b["type"] for b in c1["messages"][0]["content"]]
    assert types.count("image") == 1  # só o plot do sinal; foto original nunca (LGPD)
    assert "descrição etapa 1" in json.dumps(c2["messages"], ensure_ascii=False)


def test_ecg_report_never_sends_original_image(monkeypatch):
    """LGPD: a foto original do ECG (cabeçalho/PHI) não pode aparecer em nenhum payload ao provedor."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("MEDLENS_LAUDO", "0")
    original = _png(size=(97, 53), color=(7, 200, 33))
    original_b64 = base64.b64encode(original).decode()
    fake = FakeClient(["descrição etapa 1", json.dumps(GOOD)])
    monkeypatch.setattr(C, "make_client", lambda: fake)
    llm.ecg_report(_ecg(), original)
    assert len(fake.calls) == 2
    for call in fake.calls:
        payload = json.dumps(call, ensure_ascii=False, default=str)
        assert original_b64 not in payload
    imgs = [b for b in fake.calls[0]["messages"][0]["content"] if b["type"] == "image"]
    assert len(imgs) == 1 and imgs[0]["source"]["data"] != original_b64


def test_rx_report_with_overlay(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    img_b64 = base64.b64encode(_png()).decode()
    mask = base64.b64encode(_png(color=(255, 255, 255))).decode()
    im = RXImageAnalysis(instance_id="i1", view=RXView.PA, region=BodyRegion.CHEST, image_png_b64=img_b64, width=64,
                         height=64, structures=[Structure(key="heart", label="Coração", category="heart_vessels",
                                                          color="#ff0000", mask_png_b64=mask)])
    fake = FakeClient(["d", json.dumps(GOOD)])
    monkeypatch.setattr(C, "make_client", lambda: fake)
    rep = llm.rx_report(RXAnalysis(study_id="s", images=[im]), send_images=True)   # opt-in explícito
    assert rep.available and rep.findings
    assert [b["type"] for b in fake.calls[0]["messages"][0]["content"]].count("image") == 2


def test_refusal_and_bad_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    fake = FakeClient(["d", "not json"])
    monkeypatch.setattr(C, "make_client", lambda: fake)
    rep = llm.ecg_report(_ecg(), None)
    assert rep.limitations and not rep.findings

    class Refusing(FakeClient):
        @contextmanager
        def _stream(self, **kw):
            msg = SimpleNamespace(stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"), content=[])
            yield SimpleNamespace(get_final_message=lambda: msg)

    monkeypatch.setattr(C, "make_client", lambda: Refusing([]))
    rep = llm.ecg_report(_ecg(), None)
    assert "recusou" in rep.limitations[0]


def test_render_ecg_plot():
    from app.llm.render import render_ecg_plot
    png = render_ecg_plot(_ecg())
    assert png and png[:4] == b"\x89PNG"
