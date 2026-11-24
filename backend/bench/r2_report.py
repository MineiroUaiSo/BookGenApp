"""R2 evaluation-base report (PTB-XL dev, enlarged): diagnosis with bootstrap IC95%, measures vs PTB-XL+ 12SL, subgroups.

    cd backend && PYTHONPATH=. python -m bench.r2_report --tag R2base --out ../docs/benchmarks/r2_base.md [--repro "<cmd>"]

Reads the per-record cache written by  python -m bench.ecg_bench --source ptbxl --split dev --set large --tag <TAG>
(data/bench/ecg/ptbxl<TAG>.jsonl); nothing is re-analysed here. Only DEV (strat_fold 1-8) records are accepted.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from bench import ecg_bench as eb  # noqa: E402
from bench import ptbxl_large, ptbxl_plus, splits, subgroups  # noqa: E402
from bench.report import bootstrap_ci, fmt_ci, table  # noqa: E402

REPO = BACKEND.parent


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True,
                              timeout=10).stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def load_results(tag: str, large: bool = True) -> dict[str, dict]:
    eb.CACHE_TAG = tag
    res = eb.load_cache("ptbxl")
    if large:
        want = ptbxl_large.load_list()["ids"]
        res = {k: v for k, v in res.items() if k in want}
    bad = [k for k in res if not (k in ptbxl_large.load_list()["ids"] and
                                    splits.split_of("ptbxl", k, ptbxl_large.load_list()["ids"][k]) == "dev")]
    if bad:
        raise SystemExit(f"refusing: non-dev ids in results: {bad[:5]}")
    return res


def build_recs(res: dict[str, dict], meta: dict[str, dict]) -> list[dict]:
    dev_map = subgroups.device_groups(meta, [k for k in res if res[k]["ok"]])
    recs = []
    for k, r in sorted(res.items()):
        if not r["ok"]:
            continue
        d = r["data"]
        m = meta.get(k, {})
        recs.append({"id": k, "gold": eb.gold_classes(d["scp"], m.get("infarction_stadium1")),
                     "codes": {f["code"] for f in d["findings"]}, "groups": subgroups.groupings(m, dev_map)})
    return recs


def key_metrics(head: dict, stats: dict, recs: list[dict]) -> str:
    def sp(c, which=(0, 2)):
        h = head.get(c)
        if not h:
            return "-"
        pos = h[4]
        return f"sens {h[0]*100:.1f}% / VPP {h[2]*100:.1f}% (N pos {pos})" if 2 in which else ""
    rows = []
    k, n = head["_norm"]
    rows.append(["NORM → normal", f"{k}/{n} = {100*k/n:.1f}%"])
    rows.append(["AF sens / VPP", sp("AF")])
    rows.append(["AV1 sens / VPP", sp("AV1")])
    rows.append(["AV3 sens / VPP", sp("AV3")])
    h = head.get("STD")
    rows.append(["STD sens / espec", f"{h[0]*100:.1f}% / {h[1]*100:.1f}% (N pos {h[4]})" if h else "-"])
    h = head.get("STE_acute")
    if h:
        fp = sum(1 for r in recs if "STE_acute" not in r["gold"] and eb.PRED["STE_acute"](r["codes"]))
        nneg = sum(1 for r in recs if "STE_acute" not in r["gold"])
        rows.append(["STE_acute sens / FP", f"sens {h[0]*100:.1f}% (N pos {h[4]}) / FP {fp} de {nneg} negativos ({100*fp/max(nneg,1):.2f}%)"])
    h = head.get("STE")
    if h:
        rows.append(["STE (gold STE_) sens / VPP", f"{h[0]*100:.1f}% / {h[2]*100:.1f}% (N pos {h[4]})"])
    rows.append(["LVH sens / VPP", sp("LVH")])
    rows.append(["CRBBB sens / VPP", sp("RBBB_complete")])
    rows.append(["LBBB sens / VPP", sp("LBBB_complete")])
    rows.append(["LQT sens / VPP", sp("LQT")])
    if "PR" in stats:
        rows.append(["viés PR vs 12SL (ms)", fmt_ci(*stats["PR"]["bias"], percent=False)])
    st_mae = [stats[f"ST-J {ld}"]["mae"][0] for ld in ptbxl_plus.LEADS if f"ST-J {ld}" in stats]
    if st_mae:
        rows.append(["MAE ST-J médio das 12 derivações vs 12SL (µV)", f"{sum(st_mae)/len(st_mae):.1f}"])
    if "QRS" in stats:
        rows.append(["MAE QRS vs 12SL (ms) / viés", f"{fmt_ci(*stats['QRS']['mae'], percent=False)} / {fmt_ci(*stats['QRS']['bias'], percent=False)}"])
    return table(rows, ["Métrica-chave", "Valor"])


def sample_section(recs: list[dict]) -> str:
    from collections import Counter
    c = Counter()
    for r in recs:
        c.update(r["gold"])
    order = ["NORM", "AF", "AF_AFL", "AV1", "AV2", "AV3", "RBBB_complete", "RBBB_incomplete", "LBBB_complete", "LBBB_any", "LVH", "RVH",
             "STACH", "SBRAD", "PACE", "STD", "STE", "STE_acute", "LQT", "WPW", "LAFB", "LPFB", "MI_any", "STTC", "LOWV"]
    rows = [[k, eb.CLASS_DESC.get(k, k), c[k]] for k in order if k in c or k in eb.CLASS_DESC]
    return (f"{len(recs)} registros válidos. Amostra dev congelada, enriquecida em classes raras (bench/lists/ptbxl_large_dev.json, "
            f"semente {ptbxl_large.SEED}); **prevalências abaixo não são as naturais**.\n\n" +
            table(rows, ["Classe", "Descrição", "N positivos (gold)"]))


def gold_rules_section() -> str:
    return ("- Gold diagnóstico = códigos SCP do ptbxl_database.csv com verossimilhança >= 50 ou 0 (declarações não diagnósticas); todo o resto é negativo "
            "(especificidade/VPP são limites inferiores; rótulos PTB-XL são ruidosos).\n"
            "- **STE_**: declaração SCP, anotada de forma inconsistente no PTB-XL (mantida como gold 'STE').\n"
            "- **STE_acute** (novo): qualquer código de infarto (IMI, AMI, ASMI, ILMI, ALMI, INJAS, LMI, INJAL, IPLMI, IPMI, INJIN, INJLA, PMI, INJIL, MI) "
            "com infarction_stadium1 em {'Stadium I', 'Stadium I-II'}. A predição é a mesma de STE (qualquer ecg.st_elevation_*).\n"
            "- Subgrupos: sexo (0=M, 1=F), idade (<40, 40–65, >65; 300 = '>89' entra em >65), aparelho (6 mais frequentes + other), "
            "flags de ruído do PTB-XL (texto não vazio em baseline_drift, static_noise, burst_noise, electrodes_problems = 'com').\n"
            "- Medidas: PTB-XL+ 1.0.1, algoritmo 12SL (não é padrão-ouro humano).\n"
            "- RX (IU dev): **os metadados do IU X-Ray só trazem PA/LATERAL (incidência frontal por ordem/legenda, sem DICOM ViewPosition): "
            "não há distinção AP vs PA, portanto não há tabela por incidência AP/PA.**")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repro", default="", help="exact command line that generated the cache (shown at the top)")
    a = ap.parse_args(argv)
    res = load_results(a.tag)
    meta = {ptbxl_large.rid_of(r): r for r in ptbxl_large.load_database(ptbxl_large.database_csv(eb.DATA_ROOT))}
    eb.CACHE_TAG = a.tag
    body, head = eb.report_ptbxl(res)
    ok = [r for r in res.values() if r["ok"]]
    ref = ptbxl_plus.load_12sl()
    meas_body, stats = ptbxl_plus.section(ok, ref, len(ok))
    recs = build_recs(res, meta)
    sub_body, _ = subgroups.build(recs, eb.PRED)
    top = (f"_Gerado em {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · commit {_git_head()} · tag `{a.tag}` · "
           f"N = {len(ok)} registros dev (PTB-XL folds 1-8; folds 9-10 BURNED, fora)._\n\n"
           "Linha de base R2: **código atual, nenhuma regra alterada**. Referência para as trilhas E5/E1/E3/E4.\n\n"
           "**Reproduzir** (a partir de `backend/`):\n\n```bash\n" + (a.repro or "(ver docs/benchmarks/trilha_r2_eval_log.md)") + "\n```\n\n"
           + key_metrics(head, stats, recs))
    sections = [("Métricas-chave", ""), ("Composição da amostra dev", sample_section(recs)),
                ("Diagnóstico PTB-XL (dev ampliado, IC95% bootstrap)", body),
                ("Medidas vs 12SL (PTB-XL+)", meas_body),
                ("Subgrupos (sexo, idade, aparelho, ruído)", sub_body),
                ("Regras de gold e limitações", gold_rules_section())]
    parts = ["# R2 — linha de base de avaliação (PTB-XL dev ampliado)", "", top, ""]
    for h, b in sections[1:]:
        parts += [f"## {h}", "", b.rstrip(), ""]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(parts), encoding="utf-8")
    print(f"report: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
