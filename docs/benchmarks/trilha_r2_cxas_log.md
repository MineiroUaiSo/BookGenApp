# Trilha R2 - CXAS (Acao 9 parte R3: segmentacao anatomica CXAS)

Worktree `/Users/macbook/medlens-wt/r2-cxas` (branch wt/r2-cxas). Ferramenta de apoio; NAO e dispositivo certificado.

## T0 - Licenca (verificada 2026-11-24)
- Pacote PyPI `cxas` 0.1.2 (instalado no venv): campo license = "MIT"; GitHub API spdx_id = MIT. (O arquivo LICENSE em raw.githubusercontent main/master retornou 404; a licenca consta no README e na API do GitHub.)
- README, secao Licence (texto exato): "Code and model weights: MIT. CXAS is a research tool; it is not a medical device and must not be used for clinical decisions."
- Pesos (HF `cmseibold/cxas-models`, card): "license: mit" / "Licence: MIT." / "Research use only. Not a medical device; not for clinical decisions."
- Ressalvas NAO resolvidas: (a) modelo frontal "further trained on MIMIC-CXR radiographs with automatically generated labels" (termos PhysioNet nao verificados); (b) encoders DINOv3 (frontal) e RAD-DINO (lateral) tem licencas proprias (nao verificadas); (c) PAX-Ray++ (treino e nosso GT) e CC BY-NC 4.0. Por isso a integracao fica atras de flag DESLIGADA por padrao (MEDLENS_RX_CXAS=1) e e rotulada pesquisa/nao certificada.

## T1 - venv + runner
```
/Users/macbook/.pyenv/shims/python3.12 -m venv /Users/macbook/medlens-venvs/cxas
/Users/macbook/medlens-venvs/cxas/bin/pip install cxas      # cxas 0.1.2, torch 2.15, ~1.6 GB; backend/.venv intocado
```
Pesos baixados automaticamente do HF em ~/.cxas/weights na 1a execucao. Runner: `backend/app/rx/cxas_runner.py` (executado pelo venv cxas; JSON na ultima linha do stdout + PNG 0/255 por estrutura, + tempo de inferencia). CXAS publico so aceita cpu/cuda; o runner move os bundles para MPS manualmente (funciona; cai para CPU em erro).
Comando de exemplo: `cxas/bin/python -I backend/app/rx/cxas_runner.py --out DIR --view frontal|lateral|auto [--device mps|cpu] IMG...`

## T2 - Bench PAX-Ray++ (rx_masks_other)
- Verificacao de vazamento: os 800 ids do manifest estao todos em `paxrayplusplus_raw/paxray_test.json` (split de teste oficial do PAX-Ray++). Nao e possivel garantir que os pesos M2F_anatomy_v2 nao viram esses volumes (README: treinado em PAX-Ray++ + ajuste em MIMIC-CXR). Alem disso o GT e pseudo-label projetado de CT em radiografias SINTETICAS - os numeros abaixo devem ser tratados como POSSIVELMENTE OTIMISTAS e nao valem para filmes reais.
- Amostra: 200 imagens (100 PA + 100 lateral; as 100 primeiras de cada vista por id), NAO as 800 (tempo/orcamento). Comandos (a partir de backend/, PYTHONPATH=., MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets, MEDLENS_BENCH=<wt>/data/bench):
```
python -m bench.cxas_bench --stage cxas  --tag v1 --limit 200
python -m bench.cxas_bench --stage model --tag v1 --limit 200
python -m bench.cxas_bench --stage heur  --tag v1 --limit 200
python -m bench.cxas_bench --stage report --tag v1
python -m bench.cxas_bench --stage latency --tag v1 --limit 40
```
(CXAS com --view forcado pela vista do GT; PSPNet = modo "model" do analyze_image; heuristica = modo "heur"; "n/a" = estrutura nao suportada pelo pipeline, nao pontuada.)

### PA (frontal)  (mean Dice [CI95 bootstrap], n)

| estrutura | CXAS | PSPNet(model) | heuristic |
|---|---|---|---|
| heart | 0.950 [0.946,0.954] n=100 | 0.810 [0.779,0.838] n=100 | 0.469 [0.400,0.535] n=100 |
| left_lung | 0.964 [0.960,0.968] n=100 | 0.848 [0.824,0.866] n=100 | 0.391 [0.342,0.440] n=100 |
| right_lung | 0.961 [0.948,0.968] n=100 | 0.794 [0.769,0.814] n=100 | 0.401 [0.349,0.451] n=100 |
| spine | 0.930 [0.927,0.934] n=100 | 0.655 [0.615,0.691] n=100 | 0.457 [0.402,0.511] n=100 |
| aorta | 0.897 [0.888,0.906] n=100 | 0.179 [0.151,0.208] n=100 | 0.112 [0.093,0.130] n=100 |
| left_clavicle | 0.855 [0.834,0.873] n=100 | 0.318 [0.260,0.379] n=100 | 0.073 [0.033,0.123] n=16 |
| right_clavicle | 0.878 [0.860,0.893] n=100 | 0.336 [0.280,0.394] n=100 | 0.096 [0.055,0.141] n=21 |
| ribs_left | 0.885 [0.877,0.892] n=100 | n/a | n/a |
| ribs_right | 0.892 [0.884,0.899] n=100 | n/a | n/a |
| left_hemidiaphragm | 0.924 [0.911,0.935] n=100 | n/a | n/a |
| right_hemidiaphragm | 0.964 [0.960,0.968] n=100 | n/a | n/a |
| sternum | 0.811 [0.791,0.828] n=100 | n/a | n/a |
| trachea | 0.864 [0.852,0.875] n=100 | 0.588 [0.529,0.646] n=100 | 0.016 [0.008,0.026] n=100 |
| cardiomediastinum | 0.844 [0.836,0.852] n=100 | n/a | n/a |
| left_scapula | 0.884 [0.874,0.893] n=100 | 0.493 [0.445,0.539] n=100 | n/a |
| right_scapula | 0.893 [0.881,0.903] n=100 | 0.539 [0.489,0.587] n=100 | n/a |
| clavicles | 0.867 [0.850,0.882] n=100 | 0.327 [0.275,0.381] n=100 | 0.115 [0.069,0.162] n=5 |
| ribs | 0.888 [0.881,0.895] n=100 | n/a | n/a |
| hemidiaphragms | 0.944 [0.937,0.951] n=100 | n/a | n/a |

### LATERAL  (mean Dice [CI95 bootstrap], n)

| estrutura | CXAS | PSPNet(model) | heuristic |
|---|---|---|---|
| heart | 0.942 [0.937,0.946] n=100 | 0.505 [0.440,0.563] n=100 | 0.059 [0.033,0.089] n=100 |
| left_lung | n/a | n/a | n/a |
| right_lung | n/a | n/a | n/a |
| spine | 0.933 [0.929,0.937] n=100 | 0.401 [0.344,0.454] n=100 | 0.071 [0.048,0.095] n=100 |
| aorta | 0.905 [0.898,0.912] n=100 | n/a | n/a |
| left_clavicle | n/a | n/a | n/a |
| right_clavicle | n/a | n/a | n/a |
| ribs_left | n/a | n/a | n/a |
| ribs_right | n/a | n/a | n/a |
| left_hemidiaphragm | n/a | n/a | n/a |
| right_hemidiaphragm | n/a | n/a | n/a |
| sternum | 0.877 [0.869,0.884] n=100 | 0.297 [0.253,0.338] n=100 | 0.087 [0.057,0.121] n=100 |
| trachea | 0.888 [0.875,0.899] n=100 | 0.110 [0.078,0.142] n=100 | 0.000 [0.000,0.000] n=100 |
| cardiomediastinum | 0.943 [0.940,0.946] n=100 | n/a | n/a |
| left_scapula | n/a | n/a | n/a |
| right_scapula | n/a | n/a | n/a |
| clavicles | n/a | n/a | n/a |
| ribs | n/a | n/a | n/a |
| hemidiaphragms | n/a | n/a | n/a |

Metas: coracao >= 0,80 -> CXAS 0,950 (PA) / 0,942 (perfil), PSPNet 0,810 / 0,505. Coluna >= 0,75 -> CXAS 0,930 / 0,933, PSPNet 0,655 / 0,401. Metas atingidas por CXAS nesta amostra (ressalva de vazamento/dominio acima). PSPNet atual nao atinge coluna em PA nem coracao em perfil.

### Latencia (40 imgs, um metodo por vez, MPS)
- CXAS (so inferencia do runner, ja carregado; carga do modelo ~13 s por processo): p50 0,88 s, p95 1,31 s.
- PSPNet (analyze_image completo, modo model, MPS): p50 4,84 s, p95 8,52 s. Heuristica: p50 1,43 s, p95 8,07 s. (Nao comparaveis 1:1: analyze_image inclui deteccao de vista, medidas etc.)
- Em producao via subprocesso cada chamada paga a carga (~13 s) + PNG; um worker persistente seria necessario (NAO feito).

### Sanidade em DICOM real (sem GT)
2 DICOM de torax (~/Downloads/dicom-exemplos): runner OK em MPS, 3,8-4,5 s/img; fracao de area plausivel (coracao ~8-9%, pulmoes ~21-26%). Sem verificacao visual nem Dice.

## T3 - Integracao opcional (feita)
- `backend/app/rx/seg_cxas.py`: flag MEDLENS_RX_CXAS=1 (padrao desligado) + venv/runner existentes; subprocesso com timeout (MEDLENS_RX_CXAS_TIMEOUT, 180 s); qualquer falha -> None (comportamento atual). So PREENCHE estruturas ausentes (esterno, costelas, aorta, coluna/traqueia/clavicula/escapula/hemidiafragma quando o pipeline nao as gera). `analyze.py` chama apos a segmentacao do torax; origin "cxas" (schemas.py e frontend/src/types/api.ts atualizados), confianca 0,7, nota em quality["observacoes"]. supported_structures inclui chaves CXAS so com flag ligada.
- Testes: `backend/tests/test_rx_cxas.py` (subprocesso stubado; 9 casos).

## Suite
`pytest` completo: 297 passed, 4 failed (sem meu test_rx_cxas: os mesmos 4). Falhas: test_collector_litfl x2 (FileNotFoundError: dados nao presentes no worktree) e test_rx_real_dicom::test_chest_segmented_with_ict[True-*] x2 (passam isolados e em test_rx*.py; falham so na suite completa - interacao de ordem, aparentemente pre-existente; nao confirmado em HEAD limpo). Com meu teste: 12 passed nos arquivos alvo.

## Pendente / proximos passos
1. Rodar o bench nas 800 imagens (hoje 200) e comparar.
2. Validar em RX real com GT radiologico (JSRT/Montgomery/Shenzhen cobrem so pulmao/coracao) - numeros sinteticos nao provam desempenho clinico.
3. Worker persistente (evita ~13 s de carga por chamada) e/ou cache de resultado.
4. Revisar licencas MIMIC-CXR / DINOv3 / RAD-DINO antes de ativar flag fora de pesquisa.
5. Investigar flaky test_rx_real_dicom na suite completa em HEAD limpo.
