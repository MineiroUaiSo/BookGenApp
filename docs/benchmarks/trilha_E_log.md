# Trilha E — RX achados (R1, R2, R5)

Status: código entregue; **métricas reais pendentes** — `/Users/macbook/medlens/data/datasets/iu_xray/manifest.jsonl` não apareceu em ~60 min de espera (diretório `iu_xray/raw` vazio).

## Commits
ff85446 feat(rx): demote costophrenic-angle effusion rule when IU sensitivity < 30% (data-driven flag)
4f3173a feat(rx): per-pathology model thresholds from versioned JSON + IU dev tuning + VinDr eval path
4555021 fix(rx-bench): remove hardcoded AUC prose; findings note built from measured IU numbers
## O que foi feito
- R1: prosa "AUC > 0,89" removida de `bench/rx_bench.py`; a nota de achados agora é gerada só de números medidos (`_findings_note`). A seção IU já existia e é preenchida quando houver cache.
- R2: limiar por patologia em `backend/bench/tuning/rx_thresholds.json` (hoje `status: untuned`, fallback 0,65), carregado por `app/rx/findings.py`. `bench/tune_rx_thresholds.py` fixa limiar em DEV (IU) para especificidade 90%, com AUC IC95% bootstrap, sens, PPV na prevalência, ECE. Vazamento: pesos 'all' do TorchXRayVision incluem OpenI (= IU), logo IU é otimista. Caminho `--source vindr` (CSV de consenso do test) pronto; **VinDr-CXR test pendente (credencial PhysioNet)**.
- R5: regra do ângulo costofrênico é rebaixada (confiança ≤ 0,15 + nota de evidência) quando o tune mede sensibilidade < 30% no rótulo de derrame IU (`costophrenic_rule.demoted` no JSON). Não decidido ainda: depende de dados.

## Comandos para gerar números (quando o manifest existir)
```
cd backend && export MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench MEDLENS_BENCH_DIR=<wt>/data/bench/rx
PYTHONPATH=. python -m bench.rx_bench --source iu --models on --workers 3
PYTHONPATH=. python -m bench.tune_rx_thresholds        # escreve rx_thresholds.json
```

## Antes → depois (IU dev)
| alvo | AUC | sens@limiar 0,65 | sens@espec 90% | espec |
|---|---|---|---|---|
| (pendente: sem dados IU) | | | | |
