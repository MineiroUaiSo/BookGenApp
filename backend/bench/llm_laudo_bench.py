"""Benchmark qualitativo do laudo de ECG (ecg_laudo_v1): 10 ECG PTB-XL (folds 1-8) + caso1 (estruturado, sem imagem).

Uso (a partir de backend/; OPENROUTER_API_KEY no ambiente; NUNCA imprime a chave):
    python -m bench.llm_laudo_bench --run --budget 0.15 [--model anthropic/claude-haiku-5.5] [--only ecg|caso1]
    python -m bench.llm_laudo_bench --report-only

Só sinais/medidas de datasets públicos (PTB-XL) e fixtures sintéticas; nada de DICOM de paciente. A LLM recebe só
medidas e regras (sem imagem). Cache das respostas em $MEDLENS_BENCH/llm_laudo/ (reexecutar não gasta).
Checagem automática: todo número do texto do laudo existe nas medidas (laudo.number_stats) + gabarito do caso1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

REPO = BACKEND.parent
IDS_PATH = Path(__file__).with_name("llm_laudo_ids.json")
DATA_ROOT = Path(os.environ.get("MEDLENS_DATASETS", REPO / "data" / "datasets"))
OUT_DIR = Path(os.environ.get("MEDLENS_BENCH", REPO / "data" / "bench")) / "llm_laudo"
MIN_BALANCE = 2.00
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"


def balance() -> Optional[float]:
    import httpx
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    try:
        d = httpx.get("https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {key}"},
                      timeout=20).json()["data"]
        return float(d["total_credits"]) - float(d["total_usage"])
    except Exception:
        return None


class Meter:
    def __init__(self, budget: float):
        self.budget, self.cost, self.calls, self.cached = budget, 0.0, 0, 0


def install_cache(meter: Meter) -> None:
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
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    C.OpenRouterClient.post = post  # type: ignore[assignment]


def ecg_summary(rec_id: str) -> tuple[dict, Optional[str]]:
    from app.ecg.analysis import analyze_signal
    from app.ecg.ingest import load_ecg
    from app.llm import ecg_data_summary
    p = DATA_ROOT / "ptbxl" / "manifest.jsonl"
    rec = next(r for r in (json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip())
               if r["id"] == rec_id)
    ex = rec.get("extra") or {}
    sex = {"0": "M", "1": "F"}.get(str(ex.get("sex")).split(".")[0])
    an = analyze_signal(load_ecg(DATA_ROOT / "ptbxl" / rec["path"]), rec_id, sex=sex)
    return ecg_data_summary(an), sex


def checks_caso1(item: dict, lau: dict, gab: dict) -> list[str]:
    """Falhas do gabarito (fatos) do caso1; lista vazia = passou."""
    fails = []
    text = " ".join([lau["complexo_qrs"], lau["st_t"], lau["eixos"], *lau["impressao"]]).lower()
    if item["fixture"] == "CASO1_OK":
        g = gab["ok"]
        fails += [f"impressão/texto sem '{k}'" for k in g["impressao_deve_conter"] if k not in text]
        if lau["aviso_topo"]:
            fails.append("aviso_topo não deveria existir")
        if g["eixo"] not in lau["eixos"].lower():
            fails.append("não afirma ausência de desvio de eixo")
        if "peguero" not in lau["complexo_qrs"].lower() or "não preench" not in lau["complexo_qrs"].lower():
            fails.append("não diz que Peguero não preenche")
        for k in g["nao_deve_afirmar"]:
            if re.search(r"(?<!não como )(?<!sem )" + k + r"(?! )", " ".join(lau["impressao"]).lower()) and \
                    "não como isquemia" not in " ".join(lau["impressao"]).lower():
                fails.append(f"afirma '{k}'")
    else:
        g = gab["errada"]
        if not lau["aviso_topo"]:
            fails.append("laudo não abre com a discordância")
        for k in g["nao_deve_afirmar"]:
            for s in re.split(r"(?<=[.!?])\s+", " ".join([lau["complexo_qrs"], lau["st_t"], *lau["impressao"]])):
                if k.lower() in s.lower() and not re.search(r"n[aã]o|diverg|discord|poss[ií]vel|suspeit", s, re.I):
                    fails.append(f"afirma '{k}': {s[:80]}")
    return fails


def run_one(kind: str, item: dict, gab: dict) -> dict:
    from app import llm
    from app.llm import laudo as L
    t0 = time.time()
    if kind == "ecg":
        summary, sex = ecg_summary(item["id"])
    else:
        import laudo_fixtures as F
        summary, sex = getattr(F, item["fixture"]), "M"
    prepared = L.prepare_summary(summary, sexo=sex)
    fields = llm.ecg_laudo_fields(summary, sexo=sex)
    row = {"kind": kind, **item, "available": bool(fields), "t_s": round(time.time() - t0, 1)}
    if not fields:
        return row
    lau = fields["laudo"]
    texts = [lau[k] for k in L._TEXT_SECTIONS + ["qtc_formula"]] + lau["impressao"] + lau["limitrofes"] + lau["aviso_topo"]
    tot = bad = 0
    bad_list: list[str] = []
    for t in texts:
        a, b = L.number_stats(t, prepared)
        tot, bad = tot + a, bad + len(b)
        bad_list += b
    row.update({"numeros_total": tot, "numeros_fora": bad, "numeros_fora_lista": bad_list[:8],
                "validacao": lau["validacao"], "alertas": len(lau["aviso_topo"]),
                "n_impressao": len(lau["impressao"])})
    if kind == "caso1":
        row["falhas_gabarito"] = checks_caso1(item, lau, gab)
    rp = OUT_DIR / "reports" / f"{item['id']}.md"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(fields["laudo_markdown"], encoding="utf-8")
    row["report_path"] = str(rp)
    return row


def metrics(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("available")]
    tot, bad = sum(r["numeros_total"] for r in ok), sum(r["numeros_fora"] for r in ok)
    c1 = [r for r in rows if r["kind"] == "caso1"]
    return {"laudos_ok": len(ok), "laudos_total": len(rows), "numeros_total": tot, "numeros_fora_das_medidas": bad,
            "pct_numeros_nas_medidas": round(100.0 * (tot - bad) / tot, 1) if tot else None,
            "laudos_com_numero_fora": sum(1 for r in ok if r["numeros_fora"]),
            "validador_divergentes": sum(r["validacao"].get("numeros_divergentes", 0) for r in ok),
            "criticos_sem_lastro": sum(r["validacao"].get("criticos_sem_lastro", 0) for r in ok),
            "caso1_passou": sum(1 for r in c1 if r.get("available") and not r.get("falhas_gabarito")),
            "caso1_total": len(c1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench.llm_laudo_bench")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--only", choices=["ecg", "caso1"], default=None)
    ap.add_argument("--budget", type=float, default=0.15)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--tag", default="results")
    a = ap.parse_args(argv)
    ids = json.loads(IDS_PATH.read_text(encoding="utf-8"))
    res_path = OUT_DIR / f"{a.tag}.json"
    if a.report_only:
        rows = json.loads(res_path.read_text(encoding="utf-8"))["rows"]
    else:
        for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            os.environ.pop(k, None)
        os.environ["MEDLENS_OR_MODEL"] = a.model
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("OPENROUTER_API_KEY ausente")
            return 2
        meter = Meter(a.budget)
        install_cache(meter)
        b0 = balance()
        print(f"modelo {a.model}; saldo inicial US$ {b0}")
        work = ([("ecg", x) for x in ids["ecg"]] if a.only != "caso1" else []) + \
               ([("caso1", x) for x in ids["caso1"]] if a.only != "ecg" else [])
        rows = []
        for kind, item in work:
            b = balance()
            if b is not None and b < MIN_BALANCE:
                print(f"PARANDO: saldo {b:.2f} < {MIN_BALANCE}")
                break
            try:
                r = run_one(kind, item, ids["caso1_gabarito"])
            except Exception as e:  # noqa: BLE001
                r = {"kind": kind, **item, "available": False, "error": f"{type(e).__name__}: {str(e)[:200]}",
                     "tb": traceback.format_exc(limit=3)[-400:]}
            rows.append(r)
            print(f"{kind} {item['id']:<16} {item['cls']:<28} ok={r.get('available')} "
                  f"num={r.get('numeros_total')} fora={r.get('numeros_fora')} {r.get('numeros_fora_lista')} "
                  f"gab={r.get('falhas_gabarito')} custo=US$ {meter.cost:.4f}", flush=True)
            if meter.cost >= meter.budget:
                print("PARANDO: orçamento da execução atingido")
                break
        b1 = balance()
        print(f"saldo final US$ {b1}; gasto US$ {meter.cost:.4f}; chamadas {meter.calls}, cache {meter.cached}")
        res_path.write_text(json.dumps({"model": a.model, "rows": rows, "spent_usd": round(meter.cost, 5),
                                        "balance_before": b0, "balance_after": b1}, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    print(json.dumps(metrics(rows), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
