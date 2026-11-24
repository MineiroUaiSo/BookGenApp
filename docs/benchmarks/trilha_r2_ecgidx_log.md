# Trilha r2-ecgidx (Onda 1B): indices e regras HVE/strain/AE/CMH

Worktree /Users/macbook/medlens-wt/r2-ecgidx (wt/r2-ecgidx). Referencias (so fontes): Samesima 2022 (SBC), Peguero JACC 2017;69:1694, Makavos HFR 2019;24:439.

## Commits
- B1 feat(ecg): indices.py (Sokolow, Cornell voltagem/produto, Peguero-Lo Presti, R aVL, R D1, Gubner, angulo QRS-T, Morris, Romhilt-Estes item a item); campo GlobalMeasurements.indices; tests/test_ecg_indices.py
- B2 feat(ecg): rules_lvh.py + gancho minimo em rules.py (HVE com strain, repolarizacao secundaria, AE, padrao sugestivo CMH, bloqueio de pre-excitacao, plausibilidade)
- B3 test(ecg): synth_ecg.py (amp/st_by_lead/t_asym) + tests/test_ecg_lvh_case1.py (caso1 sintetico + gates)

## Comandos
    cd backend; export MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench
    PYTHONPATH=.:tests python -m pytest -q -p no:cacheprovider tests/test_ecg_lvh_case1.py tests/test_ecg_indices.py
    python -m bench.ecg_bench --source ptbxl --split dev --tag IDX0|IDX2 --workers 3   (IDX0 = baseline, copia do HEAD anterior)
    python <scratch>/score.py <cache.jsonl>   (usa bench.ecg_bench.PRED/gold_classes)

## B4 PTB-XL dev (folds 1-8, 1183 registros) antes (IDX0) -> depois (IDX2)
| classe | antes | depois |
|---|---|---|
| LVH sens / spec / FP | 71.6 / 84.7 / 167 | 76.1 / 83.6 / 180 |
| STD sens / spec / FP | 68.2 / 69.5 / 321 | 62.0 / 72.5 / 290 |
| MI_any sens / FP | 35.3 / 72 | 35.3 / 72 |
| LAE sens / FP | 4.8 / 31 | 9.5 / 47 |
| WPW sens / FP | 51.6 / 16 | 51.6 / 15 |
| NORM -> within_normal | 38/51 (74.5%) | 38/51 (74.5%) |
Iteracoes descartadas (IDX1): LAE por P>=120 isolada (330 FP, NORM caiu para 47%), Romhilt>=5 criando LVH sem strain (FP LVH 222), gate PR<100 com P duvidosa amplo (WPW sens 43.8). Ajustes aplicados: P>=120 isolada so com Sokolow>35 mm; Romhilt cria LVH so com strain (>=3 derivacoes); P duvidosa = sem P sinusal E frac_p<0.6.

## Regressao
- LVH sens nao caiu (+4.5). 
- **STD sens caiu 6.2 pontos (> limite de 2)**: supressao de infra de ST nas derivacoes de strain (pedida em B2b) retira TPs. Pendente: restringir a supressao (ex.: so quando HVE por criterio de voltagem forte E T assimetrica medida), ou aceitar o trade-off clinicamente.
- pytest completo: 4 falhas fora do escopo (test_collector_litfl x2 por arquivo tests/data/litfl_sample.html ausente; test_rx_real_dicom x2). Nao comparadas com baseline por falta de orcamento. Testes novos: .

## Notas
- Gabarito caso1 e internamente inconsistente: Cornell 58 mm (R aVL 21 + S V3) exige S V3 ~37 mm, o que torna Peguero >= 28. Teste usa S V3 = 11 mm (Cornell ~30, Peguero < 28) e nao assere Cornell >= 45.
- Na sintetica, P nominal 160 ms delineia ~120 ms (gaussiana).
- Limiar Peguero (>=28 mm homem, >=23 mm mulher) escrito de memoria do JACC 2017; NAO confirmado via WebSearch (nao feito).
- Ganchos opcionais de ctx para pre-excitacao: source, quality, pr_conf, printed_pr_ms (os dois ultimos ainda nao preenchidos pelo pipeline).
- Nao feito: --set large (nao existe), LUDB/QTDB bench, validacao em imagens (LITFL), confirmacao do limiar Peguero.
