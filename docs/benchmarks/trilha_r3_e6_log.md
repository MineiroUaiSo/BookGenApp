# Trilha r3-e6 (modo sombra) - log
Comandos (cwd=<wt>/backend, py=/Users/macbook/medlens/backend/.venv/bin/python, MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets, MEDLENS_BENCH=<wt>/data/bench):
1. pesos: Zenodo 3765717 -> <wt>/data/models/ribeiro (fora do git); venv /Users/macbook/medlens-venvs/e6 (tensorflow, h5py, scipy, wfdb)
2. `python -m bench.e6_prep --workers 4` (9183 ok, 0 falhas)
3. `/Users/macbook/medlens-venvs/e6/bin/python -I bench/e6_infer.py --scale 1 --tag s1`
4. `python -m bench.e6_shadow --tag s1 --rules-tag E6base`
Antes/depois das regras: cache ptbxlSTDrestrict reproduzido 150/150 idêntico com o código do worktree (nenhuma regra tocada); métricas r2_base inalteradas (AF 84,4/84,0; BAV1 38,3).
Testes: `pytest -k "ecg or e6"` = 171 passed.
Resultados: docs/benchmarks/e6_shadow.md. Não feito: code_test, folds 9-10, UI/API, IAM.
