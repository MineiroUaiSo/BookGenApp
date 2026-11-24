# Trilha r2-eval (Ação 2, base de avaliação) — log

Worktree /Users/macbook/medlens-wt/r2-eval (branch wt/r2-eval). Ambiente comum: `cd backend; export MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<worktree>/data/bench PYTHONPATH=.`; python = venv do servidor (nada instalado nele).

## Insumos (fora do git)
- PTB-XL 1.0.3 completo: zip 1839504686 B, testzip OK, extraído (sem records100) em data/datasets/ptbxl_full/.
- PTB-XL+ 1.0.1: zip 733758236 B, testzip OK, extraído só features/ em data/datasets/ptbxl_plus/.
- CODE-test (Zenodo 3765780 v1.0.3, data.zip 218189452 B, CC BY 4.0) em data/datasets/code_test/data/. h5py não existe no venv: o HDF5 foi convertido uma vez para tracings_float32.npy com um venv descartável (`python -m bench.code_test convert`).
- CPSC2018/Georgia/Chapman NÃO baixados (só URLs/tamanhos): PhysioNet/CinC Challenge 2020 completo (CPSC2018+CPSC-Extra+Georgia+...) https://physionet.org/static/published-projects/challenge-2020/classification-of-12-lead-ecgs-the-physionetcomputing-in-cardiology-challenge-2020-1.0.2.zip = 4814544948 B; Chapman-Shaoxing/Ningbo https://physionet.org/static/published-projects/ecg-arrhythmia/a-large-scale-12-lead-electrocardiogram-database-for-arrhythmia-study-1.0.0.zip = 2498709074 B. Ambos > 2 GB.

## Tarefas e commits
- T1 8797099: amostra dev congelada (bench/ptbxl_large.py, bench/lists/ptbxl_large_dev.json, splits.json "lists"), N=9183, só strat_fold 1-8, NORM=2815; `--source ptbxl --split dev --set large` (comportamento antigo = --set default). Testes de vazamento cobrem a lista.
- T2 72e0fa8: bench/report.py bootstrap (2000 reamostras, semente 20261124; bootstrap_ci, bootstrap_mean_ci, bootstrap_binary_ci, bootstrap_prop_ci, fmt_ci "74,5% [62,1–85,0]"); usado em ecg_bench (tabela PTB-XL + pct(ci=True)) e rx_bench (cédulas IU sens/espec/VPP, AUC, IC de médias, proporções). Tabelas binárias usam multinomial das 4 células (equivalente em distribuição à reamostragem por registro). tests/test_bench_report.py.
- T3 389d8b9: gold STE_acute (código de infarto + infarction_stadium1 em {Stadium I, Stadium I-II}), reportado junto de STE_ (mantido). tests/test_bench_gold.py.
- T4 b9e8b7a: bench/ptbxl_plus.py (12SL: PR, QRS, QT, QTc Bazett, FC, ST-J por derivação em µV; viés e MAE com IC95%); o cache passa a guardar stj_mv por derivação. tests/test_ptbxl_plus.py.
- T5 5e88958: bench/subgroups.py (sexo, idade <40/40-65/>65, aparelho, flags de ruído com/sem) para NORM, AF, AV1, CRBBB, LBBB, STD, STE_acute, LVH + bench/r2_report.py. RX: IU só tem PA/LATERAL, sem AP vs PA -> registrado, sem tabela.
- T6 3a3589e: CODE-test preparado e NÃO executado (bench/code_test.py; fs 400 Hz, 4096 amostras, 12 derivações, unidade empiricamente mV apesar do README; mapeamento 1dAVb->AV1, RBBB->RBBB_any, LBBB->LBBB_any, SB->SBRAD, AF->AF, ST->STACH). Só roda com --i-know-this-is-the-final-external-test e grava data/bench/ecg/code_test.RUN (recusa 2a vez). Smoke: 2 traçados (shape/unidade) sem analisador nem métricas. Verificado: sem a flag, recusa e não cria marcador. tests/test_code_test.py; splits.json ganhou code_test (external_test).
- T7 (este commit): docs/benchmarks/r2_base.md.

## T7: execução
```
python -m bench.ecg_bench --source ptbxl --split dev --set large --tag R2base --workers 3     # 9183/9183 em 3723 s (máquina compartilhada, carga ~100), 0 falhas
python -m bench.r2_report --tag R2base --out ../docs/benchmarks/r2_base.md
```
Medição de tempo prévia: 150 registros = 38 s (0,25 s/registro de parede, 3 workers); sob carga alta a execução completa levou ~62 min (previsão sem carga ~25-40 min).

## Linha de base (código atual, nada alterado em app/ecg)
NORM->normal 74,7% (2102/2815); AF sens 84,4% / VPP 84,0%; AV1 sens 38,3% / VPP 52,8%; AV3 0/12; STD sens 56,6% / espec 82,5%; STE_acute sens 51,2% (N=123) / FP 341 de 9060 (3,76%); STE_ (gold) 0/22; LVH sens 72,7% / VPP 44,3%; CRBBB 58,0% / 68,7%; LBBB 78,5% / 49,0%; LQT sens 61,7% / VPP 6,9%. Medidas vs 12SL: viés PR +11,6 ms; MAE ST-J médio 28,9 µV; QRS viés +25,3 ms (MAE 27,1). Detalhes e ICs em docs/benchmarks/r2_base.md.

## Suíte
Suíte completa: 4 falhas. test_collector_litfl (2): faltam tests/data/litfl_sample.html (diretório data/ ignorado pelo git; falha também no commit base f9b3def). test_rx_real_dicom torax 1_/2_ COVID (2): passam isoladamente e no commit base; falharam só na suíte completa sob carga ~100 (provável timeout/flaky), não tocam código alterado. Nenhuma falha nova atribuível a esta trilha.

## Não feito / pendente
- Execução do CODE-test (por desenho; só no fim de tudo). CPSC2018/Georgia/Chapman não baixados.
- Tabelas de subgrupo RX (AP vs PA): metadados inexistentes. Bench IU/RX não reexecutado nesta trilha (só IC95% no código; smoke com dados sintéticos e relatório sobre cache existente).
- Reexecutar a suíte sem carga para confirmar os 2 testes rx_real_dicom.
