"""Funções puras do bench/llm_bench.py (sem rede, sem custo)."""
import json
from pathlib import Path

import pytest

from bench import llm_bench as L

IDS = Path(L.__file__).with_name("llm_eval_ids.json")


def test_frozen_ids_have_no_images_and_respect_splits():
    d = json.loads(IDS.read_text(encoding="utf-8"))
    assert len(d["ecg"]) == 30 and len(d["rx"]) == 30
    assert all(set(x) == {"id", "cls"} for x in d["ecg"])
    assert all(set(x) == {"source", "id", "cls"} for x in d["rx"])
    assert len({x["id"] for x in d["ecg"]}) == 30
    assert {x["source"] for x in d["rx"]} == {"jsrt_masks", "iu_xray"}


def test_frozen_ptbxl_ids_are_dev_folds_only():
    import os
    root = Path(os.environ.get("MEDLENS_DATASETS", L.DATA_ROOT)) / "ptbxl" / "manifest.jsonl"
    if not root.exists():
        pytest.skip("manifest PTB-XL ausente")
    folds = {}
    for line in root.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        folds[r["id"]] = int(float((r.get("extra") or {}).get("strat_fold") or 99))
    for x in json.loads(IDS.read_text(encoding="utf-8"))["ecg"]:
        assert folds[x["id"]] <= 8, x


def test_frozen_jsrt_ids_are_dev():
    from bench import splits
    for x in json.loads(IDS.read_text(encoding="utf-8"))["rx"]:
        if x["source"] == "jsrt_masks":
            assert splits.split_of("jsrt_masks", x["id"]) == "dev"


def test_select_ids_is_deterministic():
    try:
        a, b = L.select_ids(), L.select_ids()
    except FileNotFoundError:
        pytest.skip("datasets ausentes")
    assert a == b


def test_metrics_and_review_list():
    rows = [
        {"kind": "ecg", "id": "a", "cls": "x", "available": True, "report_path": "p/a",
         "validation": {"numeros_conferem": 9, "numeros_divergentes": 1, "numeros_nao_verificaveis": 2,
                        "criticos_sem_lastro": 1, "normal_com_regra_critica": 0}},
        {"kind": "rx", "id": "b", "cls": "y", "available": True, "report_path": "p/b",
         "validation": {"numeros_conferem": 10, "numeros_divergentes": 0, "numeros_nao_verificaveis": 0,
                        "criticos_sem_lastro": 0, "normal_com_regra_critica": 1}},
        {"kind": "rx", "id": "c", "cls": "y", "available": False},
    ]
    m = L.metrics(rows)
    assert m["pct_numeros_conferem"] == 95.0 and m["criticos_sem_lastro"] == 1
    assert m["normal_com_regra_critica"] == 1 and m["laudos_ok"] == 2 and m["laudos_total"] == 3
    rl = L.review_list(rows)
    assert [x["id"] for x in rl] == ["a", "b"] and rl[0]["caminho_cache"] == "p/a"


def test_cache_avoids_second_call(tmp_path, monkeypatch):
    from app.llm import client as C
    monkeypatch.setattr(L, "OUT_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(C.OpenRouterClient, "post", lambda self, p: calls.append(1) or {"usage": {"cost": 0.01}, "x": 1})
    real = C.OpenRouterClient.post
    meter = L.Meter(1.0)
    L.install_cache(meter)
    try:
        cl = C.OpenRouterClient("k")
        assert cl.post({"a": 1}) == cl.post({"a": 1})
        assert len(calls) == 1 and meter.cached == 1 and abs(meter.cost - 0.01) < 1e-9
        meter.cost = 5.0
        with pytest.raises(C.LLMProviderError):
            cl.post({"a": 2})
    finally:
        C.OpenRouterClient.post = real
