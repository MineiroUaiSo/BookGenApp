# Trilha E — RX achados (R1, R2, R5)

## Commits
- 4555021 fix(rx-bench): remove prosa "AUC > 0,89"; nota de achados só com números medidos (R1)
- 4f3173a feat(rx): limiar por patologia em JSON + tune IU dev + caminho VinDr (R2)
- ff85446 feat(rx): rebaixa regra costofrênica se sens < 30% (R5)
- d0d77b0 bench(rx): limiares ajustados no IU dev + decisão R5 (JSON gerado)

## Execução
Cache IU: **amostra aleatória de 800 estudos (seed 0, `--limit 800`, `--max-side 512`)** dos 2955; ~530 estudos avaliáveis por patologia (rótulos por heurística de texto; negativos = estudos rx.normal). Rodada completa (2955) foi inviável em CPU (~10 estudos/min). Positivos poucos: IC largos.
```
cd backend && export MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench MEDLENS_BENCH_DIR=<wt>/data/bench/rx PYTHONPATH=.
python -m bench.rx_bench --source iu --models on --workers 3 --max-side 512 --limit 800
python -m bench.tune_rx_thresholds
```
Tudo em IU = DEV (com vazamento: pesos 'all' do TorchXRayVision incluem OpenI = IU; números otimistas). Não é teste. Teste primário VinDr-CXR test: **pendente (credencial PhysioNet)**; código pronto (`--source vindr`).

## Antes (limiar 0,65) → depois (limiar por patologia, espec. 90% em dev)
N/pos = estudos/positivos. Sens/espec no formato sens/espec. PPV na prevalência da amostra (inflada: negativos só rx.normal). ECE dos escores crus (não calibrados).

| patologia | N/pos | AUC [IC95% bootstrap] | antes sens/espec | limiar | depois sens/espec | VPP antes → depois | prev. | ECE |
|---|---|---|---|---|---|---|---|---|
| Atelectasis | 490/44 | 0.886 [0.838,0.926] | 0.07/1.00 | 0.51 | 0.59/0.90 | 0.75 -> 0.37 | 0.09 | 0.121 |
| Consolidation | 466/20 | 0.856 [0.789,0.914] | 0.05/1.00 | 0.51 | 0.45/0.90 | 1.00 -> 0.17 | 0.04 | 0.157 |
| Pneumonia | 466/20 | 0.809 [0.751,0.862] | 0.00/0.98 | 0.323 | 0.25/0.90 | 0.00 -> 0.10 | 0.04 | 0.061 |
| Effusion | 459/13 | 0.945 [0.910,0.975] | 0.23/0.99 | 0.301 | 0.85/0.90 | 0.37 -> 0.20 | 0.03 | 0.077 |
| Pneumothorax | 449/3 | - | - | - | - | - | - | - | - | skip (pos<10) |
| Cardiomegaly | 478/32 | 0.931 [0.901,0.961] | 0.31/0.99 | 0.389 | 0.75/0.90 | 0.77 -> 0.35 | 0.07 | 0.059 |
Pneumotórax: só 3 positivos, limiar mantido 0,65 (achado crítico segue "sugestivo"). Pneumonia: AUC 0,81 e sens 0,25 a 90% espec.: sinal fraco. Consolidação/Pneumonia usam o mesmo rótulo IU "consolidation".

## R5 — derrame por ângulo costofrênico
Regra geométrica vs rótulo de derrame IU: sens 1/13 = 0,08 (IC95% 0,01–0,33), espec 0,99 → **< 30%: rebaixada** (`costophrenic_rule.demoted=true`: confiança ≤ 0,15 e nota de evidência). Escore do modelo para derrame (AUC 0,945, sens 0,85 a 90% espec.) é o sinal principal. Ressalva: 13 positivos; revalidar com mais dados.

## Não feito
Ensemble de pesos por dataset (opcional); teste VinDr; ECE/calibração (só reportado).
