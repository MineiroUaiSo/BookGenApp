"""Conjunto fixo de avaliação do texto da IA (laudo = regras + LLM) + métricas do validador pós-LLM.

Uso (a partir de backend/; precisa de OPENROUTER_API_KEY no ambiente; NUNCA imprime a chave):
    python -m bench.llm_bench --freeze                 # congela bench/llm_eval_ids.json (sem imagens)
    python -m bench.llm_bench --run --n-ecg 30 --n-rx 30 --budget 0.30
    python -m bench.llm_bench --report-only

Dados: só públicos (PTB-XL folds 1-8, JSRT e IU X-Ray dev). Cache das chamadas ao LLM em
$MEDLENS_BENCH/llm/ (fora do git): reexecutar não gasta nada. Métricas (meta): % de números que conferem
(>= 98%), afirmações críticas sem lastro (0), 'normal' com regra crítica disparada (0).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Optional

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from bench import splits  # noqa: E402

REPO = BACKEND.parent
IDS_PATH = Path(__file__).with_name("llm_eval_ids.json")
SEED = 20261124
DATA_ROOT = Path(os.environ.get("MEDLENS_DATASETS", REPO / "data" / "datasets"))
OUT_DIR = Path(os.environ.get("MEDLENS_BENCH", REPO / "data" / "bench")) / "llm"
MIN_BALANCE = 2.00
# classe -> (códigos SCP-ECG do PTB-XL, cota em 30 laudos)
ECG_CLASSES: dict[str, tuple[list[str], int]] = {
    "normal": (["NORM"], 6), "FA": (["AFIB"], 4), "BAV": (["1AVB", "2AVB", "3AVB"], 4),
    "BRE": (["CLBBB"], 3), "BRD": (["CRBBB"], 3), "IAM": (["IMI", "AMI", "ASMI", "ALMI", "ILMI"], 4),
    "HVE": (["LVH"], 3), "QT longo": (["LNGQT"], 3),
}


# ----------------------------------------------------------------------------- seleção
def _manifest(source: str) -> list[dict]:
    p = DATA_ROOT / source / "manifest.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _round_robin(groups: list[list[Any]]) -> list[Any]:
    out, i = [], 0
    while any(groups):
        for g in groups:
            if g:
                out.append(g.pop(0))
    return out


def select_ids(seed: int = SEED) -> dict:
    rng = random.Random(seed)
    recs = [r for r in _manifest("ptbxl") if r.get("kind", "signal") != "image"]
    dev = [r for r in recs if (r.get("extra") or {}).get("strat_fold") not in (None, "")
           and int(float(r["extra"]["strat_fold"])) <= 8]               # folds 9-10 = teste: nunca
    used: set[str] = set()
    per_class: list[list[dict]] = []
    pools: list[tuple[str, list[dict]]] = []
    for cls, (codes, quota) in ECG_CLASSES.items():
        def has(r, ok=codes):
            scp = (r.get("extra") or {}).get("scp_codes") or {}
            return any(float(scp.get(c, 0) or 0) >= 50 for c in ok)
        cands = sorted((r for r in dev if has(r) and r["id"] not in used and
                        (cls == "normal" or not has(r, ["NORM"]))), key=lambda r: r["id"])
        pick = rng.sample(cands, min(quota, len(cands)))
        used |= {r["id"] for r in pick}
        per_class.append([{"id": r["id"], "cls": cls} for r in sorted(pick, key=lambda r: r["id"])])
        pools.append((cls, [r for r in cands if r["id"] not in used]))
    short = sum(q for _, q in ECG_CLASSES.values()) - sum(len(g) for g in per_class)
    for cls, rest in pools:                       # classe rara na amostra local: completa com as demais
        if short <= 0:
            break
        take = rng.sample(rest, min(short, len(rest), 2)) if cls != "normal" else []
        for r in take:
            per_class[[c for c in ECG_CLASSES].index(cls)].append({"id": r["id"], "cls": cls})
            short -= 1
    ecg = _round_robin(per_class)
    jsrt = sorted((r for r in _manifest("jsrt_masks") if r.get("kind") == "image"
                   and splits.split_of("jsrt_masks", r["id"]) == "dev"), key=lambda r: r["id"])
    j = [{"source": "jsrt_masks", "id": r["id"], "cls": "jsrt:" + ("achado" if r.get("labels") else "sem rótulo")}
         for r in rng.sample(jsrt, min(15, len(jsrt)))]
    iu_all = sorted((r for r in _manifest("iu_xray") if r.get("view") in ("PA", "AP") and r.get("kind") == "image"),
                    key=lambda r: r["id"])
    norm = [r for r in iu_all if any("normal" in str(l) for l in r.get("labels") or [])]
    abn = [r for r in iu_all if r not in norm and r.get("labels")]
    iu = [{"source": "iu_xray", "id": r["id"], "cls": "iu:normal"} for r in rng.sample(norm, min(7, len(norm)))] + \
         [{"source": "iu_xray", "id": r["id"], "cls": "iu:achado"} for r in rng.sample(abn, min(8, len(abn)))]
    rx = _round_robin([j, iu])
    return {"seed": seed, "note": "ids públicos congelados (sem imagens); ECG: PTB-XL strat_fold 1-8; RX: JSRT/IU dev. "
            "Listas em ordem round-robin por classe: qualquer prefixo é estratificado.", "ecg": ecg, "rx": rx}


def load_ids() -> dict:
    return json.loads(IDS_PATH.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- OpenRouter: saldo, cache, custo
def balance() -> Optional[float]:
    import httpx
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    try:
        r = httpx.get("https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {key}"}, timeout=20)
        d = r.json()["data"]
        return float(d["total_credits"]) - float(d["total_usage"])
    except Exception:
        return None


class Meter:
    def __init__(self, budget: float):
        self.budget = budget
        self.cost = 0.0
        self.calls = 0
        self.cached = 0
        self.unknown_cost_calls = 0


def install_cache(meter: Meter) -> None:
    """Cache por hash do payload + contabilidade de custo (usage.cost) em OpenRouterClient.post."""
    from app.llm import client as C
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    real = C.OpenRouterClient.post

    def post(self, payload: dict) -> dict:
        h = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]
        f = OUT_DIR / f"resp_{h}.json"
        if f.exists():
            meter.cached += 1
            return json.loads(f.read_text(encoding="utf-8"))
        if meter.cost >= meter.budget:
            raise C.LLMProviderError("Orçamento do benchmark esgotado.")
        data = real(self, payload)
        meter.calls += 1
        c = (data.get("usage") or {}).get("cost")
        if isinstance(c, (int, float)):
            meter.cost += float(c)
        else:
            meter.unknown_cost_calls += 1
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    C.OpenRouterClient.post = post  # type: ignore[assignment]


# ----------------------------------------------------------------------------- análise determinística
def analyse_ecg(rec_id: str):
    from app.ecg.analysis import analyze_signal
    from app.ecg.ingest import load_ecg
    rec = next(r for r in _manifest("ptbxl") if r["id"] == rec_id)
    sig = load_ecg(DATA_ROOT / "ptbxl" / rec["path"])
    ex = rec.get("extra") or {}
    try:
        age = float(ex.get("age")) if ex.get("age") not in (None, "") else None
        age = None if age is not None and age > 120 else age
    except (TypeError, ValueError):
        age = None
    sex = {"0": "M", "1": "F"}.get(str(ex.get("sex")).split(".")[0])
    return analyze_signal(sig, rec_id, age=age, sex=sex)


def analyse_rx(source: str, rec_id: str):
    import types
    from app.rx import analyze_image, study_findings
    from app.schemas import RXAnalysis
    from bench.rx_bench import load_gray
    rec = next(r for r in _manifest(source) if r["id"] == rec_id)
    img = load_gray(DATA_ROOT / source / rec["path"], 1024)
    a = analyze_image(img, rec_id, types.SimpleNamespace(BodyPartExamined="CHEST", ViewPosition="PA"))
    return RXAnalysis(study_id=rec_id, images=[a], findings=study_findings([a]))


# ----------------------------------------------------------------------------- execução
def run_one(kind: str, item: dict) -> dict:
    from app import llm
    t0 = time.time()
    if kind == "ecg":
        an = analyse_ecg(item["id"])
        rep = llm.ecg_report(an, None)
    else:
        an = analyse_rx(item["source"], item["id"])
        rep = llm.rx_report(an)
    out = {"kind": kind, **item, "available": rep.available, "provider": rep.provider, "model": rep.model,
           "validation": rep.validation, "n_rule_findings": len(an.findings),
           "rule_critical": [f.code for f in an.findings if f.severity == "critical"],
           "limitations": rep.limitations[:3], "t_s": round(time.time() - t0, 1)}
    rp = OUT_DIR / "reports" / f"{item['id']}.json"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(rep.model_dump_json(indent=1), encoding="utf-8")
    out["report_path"] = str(rp)
    return out


def metrics(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("available") and r.get("validation")]
    s = lambda k: sum(r["validation"].get(k, 0) for r in ok)  # noqa: E731
    conf, div = s("numeros_conferem"), s("numeros_divergentes")
    return {"laudos_ok": len(ok), "laudos_total": len(rows),
            "numeros_conferem": conf, "numeros_divergentes": div, "numeros_nao_verificaveis": s("numeros_nao_verificaveis"),
            "pct_numeros_conferem": round(100.0 * conf / (conf + div), 1) if conf + div else None,
            "criticos_sem_lastro": s("criticos_sem_lastro"),
            "laudos_com_critico_sem_lastro": sum(1 for r in ok if r["validation"].get("criticos_sem_lastro")),
            "normal_com_regra_critica": s("normal_com_regra_critica")}


def review_list(rows: list[dict], n: int = 20) -> list[dict]:
    """20 laudos para revisão médica: prioriza os sinalizados pelo validador, completa estratificando por classe."""
    ok = [r for r in rows if r.get("available")]
    flagged = [r for r in ok if (r["validation"].get("numeros_divergentes") or r["validation"].get("criticos_sem_lastro")
                                 or r["validation"].get("normal_com_regra_critica"))]
    rest = [r for r in ok if r not in flagged]
    pick = flagged[:n // 2] + rest
    seen, out = set(), []
    for r in pick:
        if r["id"] not in seen and len(out) < n:
            seen.add(r["id"])
            out.append({"id": r["id"], "classe": r["cls"], "caminho_cache": r["report_path"]})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench.llm_bench")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--n-ecg", type=int, default=30)
    ap.add_argument("--n-rx", type=int, default=30)
    ap.add_argument("--budget", type=float, default=0.30, help="US$ máximo gasto nesta execução")
    ap.add_argument("--model", default=None, help="id OpenRouter (default: o de produção)")
    a = ap.parse_args(argv)
    if a.freeze:
        ids = select_ids()
        IDS_PATH.write_text(json.dumps(ids, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"congelado: {len(ids['ecg'])} ECG + {len(ids['rx'])} RX em {IDS_PATH}")
        return 0
    ids = load_ids()
    res_path = OUT_DIR / "results.json"
    if a.report_only:
        rows = json.loads(res_path.read_text(encoding="utf-8"))["rows"]
    else:
        for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            os.environ.pop(k, None)               # força OpenRouter
        if a.model:
            os.environ["MEDLENS_OR_MODEL"] = a.model
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("OPENROUTER_API_KEY ausente")
            return 2
        meter = Meter(a.budget)
        install_cache(meter)
        b0 = balance()
        print(f"saldo inicial US$ {b0}")
        rows = []
        worst_item = 0.0
        work = [("ecg", x) for x in ids["ecg"][:a.n_ecg]] + [("rx", x) for x in ids["rx"][:a.n_rx]]
        for kind, item in work:
            b = balance()
            if b is not None and b < MIN_BALANCE:
                print(f"PARANDO: saldo {b:.2f} < {MIN_BALANCE}")
                break
            if meter.cost + worst_item > a.budget:      # não começa um laudo que estoura o orçamento
                print(f"PARANDO: próximo laudo (~US$ {worst_item:.3f}) estouraria o orçamento US$ {a.budget:.2f}")
                break
            c0 = meter.cost
            try:
                r = run_one(kind, item)
            except Exception as e:  # noqa: BLE001
                r = {"kind": kind, **item, "available": False, "error": f"{type(e).__name__}: {str(e)[:200]}",
                     "tb": traceback.format_exc(limit=3)[-400:]}
            worst_item = max(worst_item, meter.cost - c0)
            rows.append(r)
            print(f"{kind} {item['id']:<22} {item['cls']:<14} ok={r.get('available')} prov={r.get('provider')} "
                  f"val={r.get('validation')} custo_acum=US$ {meter.cost:.4f} (chamadas {meter.calls}, cache {meter.cached})",
                  flush=True)
            if meter.cost >= meter.budget:
                print("PARANDO: orçamento da execução atingido")
                break
        b1 = balance()
        print(f"saldo final US$ {b1}; gasto (usage.cost) US$ {meter.cost:.4f}; "
              f"delta de saldo US$ {None if b0 is None or b1 is None else round(b0 - b1, 4)}")
        res_path.parent.mkdir(parents=True, exist_ok=True)
        res_path.write_text(json.dumps({"rows": rows, "spent_usd": round(meter.cost, 5), "balance_before": b0,
                                        "balance_after": b1}, ensure_ascii=False, indent=1), encoding="utf-8")
    m_all = metrics(rows)
    m_ecg = metrics([r for r in rows if r["kind"] == "ecg"])
    m_rx = metrics([r for r in rows if r["kind"] == "rx"])
    print(json.dumps({"total": m_all, "ecg": m_ecg, "rx": m_rx}, ensure_ascii=False, indent=1))
    print("revisão médica (20):")
    for x in review_list(rows):
        print(f"  {x['id']:<22} {x['classe']:<14} {x['caminho_cache']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
