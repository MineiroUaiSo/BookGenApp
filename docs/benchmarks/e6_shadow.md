# E6 - classificador em modo sombra (Ribeiro 2020) vs regras MedLens

**modo sombra: não exibido ao usuário.** Só bench offline; nada em `app/`, API ou UI (decisão regulatória pendente, RDC 657/2022).

## Modelo e licença
- Ribeiro AH et al., Nat Commun 11:1760 (2020), pesos públicos Zenodo registro 3765717 ("Pre-trained deep neural network models for ECG automatic abnormality detection"), DOI 10.5281/zenodo.3765717. Licença registrada no Zenodo: `cc-by-4.0` (campo license.id; sem texto de direitos adicional). Metadados em `data/models/ribeiro/ZENODO_RECORD.json` (fora do git). Pesos: `data/models/ribeiro/model/model.hdf5` (fora do git; no worktree, não no tree principal).
- Treinado no CODE (Brasil); PTB-XL não foi usado no treino, logo sem vazamento.
- Rótulos: 1dAVb, RBBB, LBBB, SB, AF, ST. **IAM não coberto pelo modelo** (meta IAM sens >= 60% a 90% espec: não aplicável; nenhum modelo público sem treino em PTB-XL foi usado).
- Venv separado: `/Users/macbook/medlens-venvs/e6` (python 3.12, tensorflow 2.21, keras 3.15). `backend/.venv` intocado.

## Método
- Conjunto: PTB-XL DEV ampliado (folds 1-8, N=9183, o mesmo do bench R2). Folds 9-10 e code_test não usados.
- Pré-processo: 500 Hz -> 400 Hz (resample_poly 4/5), 4000 amostras + zero-pad até 4096, ordem DI DII DIII aVR aVL aVF V1-V6, unidade mV (README oficial: V x 1000). Verificado em 1000 registros dev: escala x10 piora (AUC AF 0,965 vs 0,989), escala 1 mantida.
- Limiar do artigo: [0,124 0,07 0,05 0,278 0,390 0,174] (max-F1 na validação CODE; `generate_figures_and_tables.py` do repositório antonior92/automatic-ecg-diagnosis). Também: sens a 90% espec (limiar = quantil 90 dos negativos).
- Gold: PTB-XL SCP (AFIB, 1AVB, CRBBB, CLBBB, SBRAD, STACH); variantes IRBBB/ILBBB/AFLT como análise de sensibilidade. Regras: caches do bench (`ptbxlSTDrestrict.jsonl`, código atual; 150/150 registros reproduzidos idênticos no worktree).
- IC95% por bootstrap (1000, semente 0). kappa model x regras no limiar do artigo.
- Scripts: `backend/bench/e6_prep.py` (backend venv), `e6_infer.py` (venv e6), `e6_shadow.py` (relatório). Testes: `backend/tests/test_e6_shadow.py`.

## Resultados

N = 9183 PTB-XL records (DEV, folds 1-8, large class-enriched sample). Probabilities tag: s1; rules cache tag: E6base.

### Model (Ribeiro 2020)

| Label | N pos | AUC [IC95%] | Sens @ spec 90% [IC] | Sens @ paper thr [IC] | Spec @ paper thr [IC] | PPV @ paper thr [IC] |
|---|---|---|---|---|---|---|
| 1dAVb | 616 | 0.959 [0.953-0.965] | 89.8 [87.4-92.3] | 75.6 [72.2-79.0] | 95.5 [95.0-95.9] | 54.6 [51.1-57.7] |
| RBBB | 431 | 0.995 [0.993-0.997] | 99.8 [99.3-100.0] | 98.8 [97.6-99.8] | 97.8 [97.6-98.1] | 69.3 [65.7-72.8] |
| LBBB | 428 | 0.997 [0.995-0.998] | 99.5 [98.8-100.0] | 99.5 [98.8-100.0] | 96.0 [95.6-96.4] | 54.8 [50.9-58.2] |
| SB | 509 | 0.964 [0.956-0.971] | 83.7 [80.6-86.7] | 68.2 [64.4-72.0] | 99.5 [99.4-99.6] | 89.0 [86.1-92.1] |
| AF | 1014 | 0.994 [0.992-0.996] | 99.3 [98.8-99.8] | 93.2 [91.7-94.7] | 98.5 [98.2-98.8] | 88.6 [86.5-90.4] |
| ST | 637 | 0.994 [0.991-0.996] | 99.2 [98.5-99.8] | 95.1 [93.3-96.8] | 98.4 [98.2-98.7] | 81.8 [78.9-84.7] |
| RBBB (gold RBBB_any) | 1162 | 0.772 [0.756-0.790] | 55.4 [52.6-58.5] | 47.6 [44.9-50.4] | 99.2 [99.0-99.4] | 89.9 [87.5-92.1] |
| LBBB (gold LBBB_any) | 489 | 0.986 [0.980-0.990] | 95.3 [93.3-97.1] | 94.7 [92.6-96.6] | 96.4 [96.0-96.8] | 59.5 [55.9-63.0] |
| AF (gold AF_AFL) | 1060 | 0.993 [0.991-0.995] | 99.3 [98.8-99.7] | 90.5 [88.7-92.2] | 98.7 [98.4-98.9] | 89.9 [87.9-91.7] |

### MedLens rules, same records

| Label | N pos | Rules sens [IC] | Rules spec [IC] | Rules PPV [IC] | rules sens - model sens |
|---|---|---|---|---|---|
| 1dAVb | 616 | 38.3 [34.3-42.3] | 97.5 [97.2-97.9] | 52.8 [48.5-57.4] | -0.373 |
| RBBB | 431 | 58.0 [53.5-62.7] | 98.7 [98.5-98.9] | 68.7 [63.7-73.8] | -0.408 |
| LBBB | 428 | 78.5 [74.3-82.2] | 96.0 [95.6-96.4] | 49.0 [45.2-52.8] | -0.210 |
| SB | 509 | 66.0 [62.2-70.2] | 99.7 [99.6-99.8] | 92.6 [89.9-95.2] | -0.022 |
| AF | 1014 | 84.4 [82.4-86.5] | 98.0 [97.7-98.3] | 84.0 [81.8-86.2] | -0.088 |
| ST | 637 | 88.1 [85.6-90.5] | 98.8 [98.6-99.1] | 85.0 [82.4-87.7] | -0.071 |
| RBBB (gold RBBB_any) | 1162 | 47.3 [44.4-50.1] | 99.4 [99.2-99.6] | 92.0 [89.7-94.0] | -0.003 |
| LBBB (gold LBBB_any) | 489 | 78.9 [75.2-82.3] | 95.0 [94.6-95.5] | 47.2 [44.1-50.6] | -0.157 |
| AF (gold AF_AFL) | 1060 | 84.4 [82.4-86.3] | 96.9 [96.5-97.2] | 77.9 [75.5-80.3] | -0.060 |

### Agreement (Cohen kappa; model at the paper threshold)

| Label | kappa model x rules [IC] | kappa model x gold | kappa rules x gold | both + | model + only | rules + only |
|---|---|---|---|---|---|---|
| 1dAVb | 0.541 [0.506-0.575] | 0.603 | 0.411 | 371 | 483 | 76 |
| RBBB | 0.672 [0.639-0.705] | 0.804 | 0.612 | 337 | 278 | 27 |
| LBBB | 0.641 [0.612-0.669] | 0.688 | 0.579 | 490 | 288 | 196 |
| SB | 0.907 [0.882-0.929] | 0.760 | 0.760 | 343 | 47 | 20 |
| AF | 0.811 [0.792-0.829] | 0.896 | 0.822 | 868 | 199 | 151 |
| ST | 0.879 [0.860-0.897] | 0.870 | 0.855 | 622 | 119 | 38 |
| RBBB (gold RBBB_any) | 0.680 [0.647-0.706] | 0.586 | 0.590 | 425 | 190 | 173 |
| LBBB (gold LBBB_any) | 0.581 [0.552-0.610] | 0.712 | 0.561 | 493 | 285 | 325 |
| AF (gold AF_AFL) | 0.777 [0.759-0.797] | 0.889 | 0.784 | 891 | 176 | 258 |

### Complementarity (counts)

| Label | gold+, rules miss, model hits | gold+, rules hit, model miss | gold+, both miss | gold-, model FP only | gold-, rules FP only |
|---|---|---|---|---|---|
| 1dAVb | 240 | 10 | 140 | 243 | 66 |
| RBBB | 176 | 0 | 5 | 102 | 27 |
| LBBB | 90 | 0 | 2 | 198 | 196 |
| SB | 23 | 12 | 150 | 24 | 8 |
| AF | 114 | 25 | 44 | 85 | 126 |
| ST | 60 | 15 | 16 | 59 | 23 |
| RBBB (gold RBBB_any) | 140 | 137 | 472 | 50 | 36 |
| LBBB (gold LBBB_any) | 91 | 14 | 12 | 194 | 311 |
| AF (gold AF_AFL) | 114 | 50 | 51 | 62 | 208 |

## Leitura
- Modelo >= regras em sensibilidade (limiar do artigo) nos 6 rótulos; maiores ganhos: 1dAVb (75,6 vs 38,3), RBBB (98,8 vs 58,0), LBBB (99,5 vs 78,5), AF (93,2 vs 84,4). SB e ST: diferença pequena (SB 68,2 vs 66,0, ICs sobrepostos). PPV comparável: AF 88,6 vs 84,0; SB regras 92,6 vs 89,0 (regras melhores em SB).
- PPV do modelo em LBBB/1dAVb ~55% nesta amostra enriquecida (não corrigido por prevalência).
- Gold "RBBB_any" inclui IRBBB, que o modelo não conhece: AUC 0,77 é esperado.
- Complementaridade: ver tabela (casos gold+ que as regras perdem e o modelo acerta).
- Regras inalteradas: nenhuma métrica do r2_base mudou (nenhum código de regras tocado).
