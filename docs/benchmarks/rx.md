# Benchmark RX (MedLens)

_Generated 2026-11-24 11:26 UTC by `bench`._

## Resumo

| capacidade | métrica | N | valor |
|---|---|---|---|
| Segmentação heart (jsrt_masks, heur) | Dice médio [IC95%] | 247 | 0.176 [0.140, 0.212] |
| Segmentação heart (jsrt_masks, model) | Dice médio [IC95%] | 247 | 0.926 [0.923, 0.930] |
| Segmentação lungs (jsrt_masks, heur) | Dice médio [IC95%] | 247 | 0.236 [0.195, 0.277] |
| Segmentação lungs (jsrt_masks, model) | Dice médio [IC95%] | 247 | 0.863 [0.861, 0.866] |
| Segmentação heart (montgomery, heur) | Dice médio [IC95%] | 138 | 0.073 [0.039, 0.114] |
| Segmentação heart (montgomery, model) | Dice médio [IC95%] | 138 | 0.891 [0.874, 0.905] |
| Segmentação lungs (montgomery, heur) | Dice médio [IC95%] | 138 | 0.092 [0.055, 0.141] |
| Segmentação lungs (montgomery, model) | Dice médio [IC95%] | 138 | 0.862 [0.848, 0.871] |
| Segmentação heart (rx_masks_other, heur) | Dice médio [IC95%] | 6 | 0.129 [0.000, 0.387] |
| Segmentação heart (rx_masks_other, model) | Dice médio [IC95%] | 3 | 0.000 [0.000, 0.000] |
| Segmentação lungs (rx_masks_other, heur) | Dice médio [IC95%] | 3 | 0.228 [0.000, 0.685] |
| Região=tórax sem tags (jsrt_masks) | fração [IC95%] | 247 | 0.506 [0.444, 0.568] |
| Região=tórax sem tags (montgomery) | fração [IC95%] | 138 | 0.167 [0.114, 0.238] |
| Região=tórax sem tags (rx_masks_other) | fração [IC95%] | 6 | 0.167 [0.030, 0.564] |
| ICT erro absoluto (jsrt_masks, heur) | MAE | 247 | 0.169 |
| ICT erro absoluto (jsrt_masks, model) | MAE | 247 | 0.027 |
| ICT erro absoluto (montgomery, heur) | MAE | 138 | 0.123 |
| ICT erro absoluto (montgomery, model) | MAE | 138 | 0.023 |
| ICT erro absoluto (rx_masks_other, heur) | MAE | 3 | 0.189 |
| IU atelectasis: modelo Atelectasis | AUC [IC95%] | 107 (pos 21) | 0.903 [0.840, 0.958] |
| IU cardiomegaly: modelo Cardiomegaly | AUC [IC95%] | 114 (pos 28) | 0.926 [0.874, 0.970] |
| IU cardiomegaly: regras (rx.cardiomegaly) | AUC [IC95%] | 97 (pos 19) | 0.935 [0.884, 0.973] |
| IU consolidation: modelo Consolidation/Pneumonia | AUC [IC95%] | 91 (pos 5) | 0.912 [0.832, 0.977] |
| IU effusion: modelo Effusion | AUC [IC95%] | 92 (pos 6) | 0.924 [0.825, 0.996] |
| IU normal: 1 − máx. escore do modelo | AUC [IC95%] | 241 (pos 86) | 0.675 [0.599, 0.745] |
| IU pneumothorax: modelo Pneumothorax | AUC [IC95%] | 88 (pos 2) | 0.895 [0.724, 1.000] |
| IU tórax reconhecido sem tags (GT caption) | fração região=chest [IC95%] | 36 | 0.333 [0.202, 0.497] |
| IU incidência frontal/perfil (heur, GT caption) | acurácia [IC95%] | 36 | 0.139 [0.061, 0.287] |
| IU reconstrução 3D (heur) | taxa de sucesso [IC95%] | 235 | 0.119 [0.084, 0.167] |
| IU reconstrução 3D (model) | taxa de sucesso [IC95%] | 235 | 0.332 [0.275, 0.394] |

## Segmentação vs máscaras de referência (Dice / IoU por estrutura)

### jsrt_masks

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| heart | 0.926 [0.923, 0.930] | 0.864 | 0.930 | 247 (0 sem máscara) | 0.176 [0.140, 0.212] | 0.139 | 0.000 | 247 (175 sem máscara) |
| left_clavicle | 0.599 [0.584, 0.615] | 0.438 | 0.629 | 247 (0 sem máscara) | 0.005 [0.001, 0.009] | 0.003 | 0.000 | 247 (213 sem máscara) |
| left_lung | 0.797 [0.792, 0.801] | 0.664 | 0.800 | 247 (0 sem máscara) | 0.213 [0.170, 0.254] | 0.182 | 0.000 | 247 (173 sem máscara); 2 lado trocado |
| lungs | 0.863 [0.861, 0.866] | 0.760 | 0.867 | 247 (0 sem máscara) | 0.236 [0.195, 0.277] | 0.199 | 0.000 | 247 (173 sem máscara) |
| right_clavicle | 0.603 [0.584, 0.620] | 0.446 | 0.628 | 247 (0 sem máscara) | 0.011 [0.006, 0.015] | 0.006 | 0.000 | 247 (188 sem máscara) |
| right_lung | 0.925 [0.922, 0.928] | 0.861 | 0.928 | 247 (0 sem máscara) | 0.217 [0.175, 0.259] | 0.187 | 0.000 | 247 (173 sem máscara); 9 lado trocado |

### montgomery

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| heart | 0.891 [0.874, 0.905] | 0.813 | 0.911 | 138 (1 sem máscara) | 0.073 [0.039, 0.114] | 0.057 | 0.000 | 138 (121 sem máscara) |
| left_clavicle | 0.618 [0.580, 0.647] | 0.475 | 0.686 | 138 (5 sem máscara) | 0.001 [0.000, 0.003] | 0.000 | 0.000 | 138 (130 sem máscara) |
| left_lung | 0.827 [0.812, 0.837] | 0.710 | 0.837 | 138 (1 sem máscara) | 0.084 [0.045, 0.134] | 0.073 | 0.000 | 138 (121 sem máscara); 1 lado trocado |
| lungs | 0.862 [0.848, 0.871] | 0.763 | 0.870 | 138 (1 sem máscara) | 0.092 [0.055, 0.141] | 0.078 | 0.000 | 138 (121 sem máscara) |
| right_clavicle | 0.570 [0.538, 0.595] | 0.417 | 0.633 | 138 (4 sem máscara) | 0.006 [0.002, 0.012] | 0.003 | 0.000 | 138 (130 sem máscara) |
| right_lung | 0.894 [0.879, 0.903] | 0.815 | 0.905 | 138 (1 sem máscara) | 0.090 [0.053, 0.138] | 0.078 | 0.000 | 138 (121 sem máscara); 1 lado trocado |

### rx_masks_other

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| aorta | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (3 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 6 (5 sem máscara) |
| heart | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (3 sem máscara) | 0.129 [0.000, 0.387] | 0.105 | 0.000 | 6 (5 sem máscara) |
| left_clavicle | - | - | - | - | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (3 sem máscara) |
| left_lung | - | - | - | - | 0.249 [0.000, 0.748] | 0.199 | 0.000 | 3 (2 sem máscara) |
| left_scapula | - | - | - | - | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (3 sem máscara) |
| lungs | - | - | - | - | 0.228 [0.000, 0.685] | 0.174 | 0.000 | 3 (2 sem máscara) |
| right_clavicle | - | - | - | - | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (2 sem máscara) |
| right_lung | - | - | - | - | 0.207 [0.000, 0.621] | 0.150 | 0.000 | 3 (2 sem máscara) |
| right_scapula | - | - | - | - | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (3 sem máscara) |
| spine | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (3 sem máscara) | 0.126 [0.000, 0.377] | 0.101 | 0.000 | 6 (5 sem máscara) |
| sternum | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (3 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 6 (6 sem máscara) |
| trachea | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 3 (3 sem máscara) | 0.031 [0.000, 0.093] | 0.017 | 0.000 | 6 (5 sem máscara) |

## Piores casos de segmentação

| fonte | estrutura | caminho | id | Dice |
|---|---|---|---|---|
| montgomery | lungs | model | `MCUCXR_0060_0` | 0.000 |
| jsrt_masks | lungs | model | `JPCLN016` | 0.768 |
| montgomery | lungs | model | `MCUCXR_0061_0` | 0.791 |
| jsrt_masks | lungs | model | `JPCNN071` | 0.798 |
| jsrt_masks | lungs | model | `JPCLN002` | 0.800 |
| montgomery | heart | model | `MCUCXR_0060_0` | 0.000 |
| rx_masks_other | heart | model | `RSNAPE_0b14caeba6ab_47c0b3be0811_lateral` | 0.000 |
| rx_masks_other | heart | model | `RSNAPE_2af16d66cc16_eb87ca71cfb0_lateral` | 0.000 |
| rx_masks_other | heart | model | `COVID1910_0460_lateral` | 0.000 |
| montgomery | heart | model | `MCUCXR_0390_1` | 0.662 |
| jsrt_masks | lungs | heur | `JPCLN002` | 0.000 |
| jsrt_masks | lungs | heur | `JPCLN054` | 0.000 |
| jsrt_masks | lungs | heur | `JPCNN056` | 0.000 |
| jsrt_masks | lungs | heur | `JPCNN061` | 0.000 |
| jsrt_masks | lungs | heur | `JPCNN071` | 0.000 |
| jsrt_masks | heart | heur | `JPCLN002` | 0.000 |
| jsrt_masks | heart | heur | `JPCLN054` | 0.000 |
| jsrt_masks | heart | heur | `JPCNN056` | 0.000 |
| jsrt_masks | heart | heur | `JPCNN061` | 0.000 |
| jsrt_masks | heart | heur | `JPCNN071` | 0.000 |

## Detecção de região sem tags (imagens de tórax)

| fonte | N | região=tórax [IC95%] | tórax com incidência reconhecida |
|---|---|---|---|
| jsrt_masks | 247 | 125/247 = 0.506 [0.444, 0.568] | 125/247 |
| montgomery | 138 | 23/138 = 0.167 [0.114, 0.238] | 23/138 |
| rx_masks_other | 6 | 1/6 = 0.167 [0.030, 0.564] | 1/6 |

## ICT: referência (máscaras) vs nosso

| fonte | caminho | N | sem ICT | erro abs. médio [IC95%] | mediana | viés (nosso−GT) | erro abs. fórmula nas máscaras previstas | concordância ICT>0,5 |
|---|---|---|---|---|---|---|---|---|
| jsrt_masks | model | 247 | 0 | 0.027 [0.025, 0.029] | 0.024 | -0.026 | 0.027 | 0.89 (220/247) |
| jsrt_masks | heur | 247 | 175 | 0.169 [0.143, 0.195] | 0.164 | +0.126 | 0.169 | 0.36 (26/72) |
| montgomery | model | 138 | 1 | 0.023 [0.018, 0.028] | 0.015 | -0.010 | 0.023 | 0.93 (128/137) |
| montgomery | heur | 138 | 121 | 0.123 [0.074, 0.189] | 0.078 | +0.024 | 0.123 | 0.65 (11/17) |
| rx_masks_other | heur | 3 | 2 | 0.189 [0.189, 0.189] | 0.189 | +0.189 | 0.189 | 0.00 (0/1) |

Maiores erros de ICT: `montgomery/MCUCXR_0213_1` (heur: 0.08 vs GT 0.51); `jsrt_masks/JPCNN009` (heur: 0.15 vs GT 0.55); `jsrt_masks/JPCNN089` (heur: 0.78 vs GT 0.39); `montgomery/MCUCXR_0080_0` (heur: 0.08 vs GT 0.45); `jsrt_masks/JPCLN130` (heur: 0.82 vs GT 0.46); `jsrt_masks/JPCNN036` (heur: 0.79 vs GT 0.43); `jsrt_masks/JPCNN022` (heur: 0.83 vs GT 0.48); `jsrt_masks/JPCLN139` (heur: 0.83 vs GT 0.48)

## IU X-ray

### Classificação de incidência (frontal vs perfil)

**heur, GT view_source=caption**: acurácia frontal/perfil 5/36 = 0.139 (IC95% 0.061–0.287). Matriz (verdade→previsto): frontal→lateral: 1, frontal→other: 6, lateral→frontal: 6, lateral→lateral: 5, lateral→other: 18. Erros: `CXR1698_IM-0458-2001` (GT LATERAL, previsto OTHER), `CXR3529_IM-1725-1001` (GT LATERAL, previsto OTHER), `CXR3529_IM-1725-2001` (GT LATERAL, previsto PA), `CXR3333_IM-1597-1001` (GT LATERAL, previsto PA), `CXR3860_IM-1954-2001` (GT LATERAL, previsto PA), `CXR3654_IM-1816-1001` (GT LATERAL, previsto OTHER), `CXR3798_IM-1911-2001` (GT LATERAL, previsto PA), `CXR30_IM-1385-1001` (GT LATERAL, previsto OTHER)

  Região detectada sem tags (caption): abdomen=21, chest=12, extremity=3

  Distribuição PA/AP previstas nos frontais (heur/caption): LATERAL=1, OTHER=6

### Achados vs rótulos do laudo

| alvo | preditor | caminho | N estudos | positivos GT | sensibilidade [IC95%] | especificidade [IC95%] | VPP [IC95%] | AUC [IC95%] |
|---|---|---|---|---|---|---|---|---|
| cardiomegaly | regras (rx.cardiomegaly) | model | 136 | 36 (26%) | 0.47 [0.32, 0.63] | 0.91 [0.84, 0.95] | 0.65 [0.46, 0.81] | 0.935 [0.884, 0.973] |
| cardiomegaly | regras (rx.cardiomegaly) | heur | 136 | 36 (26%) | 0.06 [0.02, 0.18] | 0.89 [0.81, 0.94] | 0.15 [0.04, 0.42] | 0.605 [0.273, 0.900] |
| cardiomegaly | modelo Cardiomegaly | model | 114 | 28 (25%) | 0.14 [0.06, 0.31] | 0.99 [0.94, 1.00] | 0.80 [0.38, 0.96] | 0.926 [0.874, 0.970] |
| effusion | regras (seio costofrênico) | model | 108 | 8 (7%) | 0.00 [0.00, 0.32] | 1.00 [0.96, 1.00] | - | - |
| effusion | regras (seio costofrênico) | heur | 108 | 8 (7%) | 0.00 [0.00, 0.32] | 0.99 [0.95, 1.00] | 0.00 [0.00, 0.79] | - |
| effusion | modelo Effusion | model | 92 | 6 (7%) | 0.17 [0.03, 0.56] | 1.00 [0.96, 1.00] | 1.00 [0.21, 1.00] | 0.924 [0.825, 0.996] |
| pneumothorax | modelo Pneumothorax | model | 88 | 2 (2%) | 0.00 [0.00, 0.66] | 1.00 [0.96, 1.00] | - | 0.895 [0.724, 1.000] |
| consolidation | modelo Consolidation/Pneumonia | model | 91 | 5 (5%) | 0.20 [0.04, 0.62] | 0.99 [0.94, 1.00] | 0.50 [0.09, 0.91] | 0.912 [0.832, 0.977] |
| atelectasis | modelo Atelectasis | model | 107 | 21 (20%) | 0.00 [0.00, 0.15] | 1.00 [0.96, 1.00] | - | 0.903 [0.840, 0.958] |
| diaphragm | regras (elevação hemicúpula) | model | 111 | 11 (10%) | 0.36 [0.15, 0.65] | 0.94 [0.88, 0.97] | 0.40 [0.17, 0.69] | - |
| diaphragm | regras (elevação hemicúpula) | heur | 111 | 11 (10%) | 0.09 [0.02, 0.38] | 0.90 [0.83, 0.94] | 0.09 [0.02, 0.38] | - |
| normal | sem achados anormais (regras+modelo) | model | 284 | 100 (35%) | 0.75 [0.66, 0.82] | 0.42 [0.35, 0.49] | 0.41 [0.34, 0.48] | - |
| normal | sem achados anormais (regras+modelo) | heur | 284 | 100 (35%) | 0.80 [0.71, 0.87] | 0.22 [0.17, 0.29] | 0.36 [0.30, 0.42] | - |
| normal | 1 − máx. escore do modelo | model | 241 | 86 (36%) | 0.71 [0.61, 0.79] | 0.50 [0.42, 0.57] | 0.44 [0.36, 0.52] | 0.675 [0.599, 0.745] |

### Reconstrução 3D (pares frontal+perfil)

**model**: sucesso 78/235 = 0.332 (IC95% 0.275–0.394); tempo médio 2.3 s, p95 4.2 s; malhas média 14.5. Falhas: `CXR2903` (ValueError: Sem máscaras de estruturas nas duas incidências.), `CXR2784` (ValueError: Incidência lateral sem máscaras de estruturas.), `CXR1407` (ValueError: Incidência lateral sem máscaras de estruturas.), `CXR1053` (ValueError: Incidência lateral sem máscaras de estruturas.), `CXR1329` (ValueError: Incidência lateral sem máscaras de estruturas.), `CXR1394` (ValueError: Incidência lateral sem máscaras de estruturas.)

**heur**: sucesso 28/235 = 0.119 (IC95% 0.084–0.167); tempo médio 2.4 s, p95 4.2 s; malhas média 11.9. Falhas: `CXR2903` (ValueError: Sem máscaras de estruturas nas duas incidências.), `CXR2784` (ValueError: Incidência lateral sem máscaras de estruturas.), `CXR1407` (ValueError: Sem máscaras de estruturas nas duas incidências.), `CXR1020` (ValueError: Incidência frontal sem máscaras de estruturas.), `CXR1053` (ValueError: Sem máscaras de estruturas nas duas incidências.), `CXR1329` (ValueError: Sem máscaras de estruturas nas duas incidências.)

## Tempos (s, 1 thread por worker)

| etapa | caminho | N | média | mediana | p95 |
|---|---|---|---|---|---|
| máscaras analyze_image | model | 388 | 8.04 | 6.92 | 16.26 |
| máscaras analyze_image | heur | 391 | 0.16 | 0.13 | 0.50 |
| IU analyze_image | model | 579 | 4.13 | 1.65 | 13.60 |
| recon3d.reconstruct | model | 78 | 2.27 | 1.97 | 4.21 |
| IU analyze_image | heur | 579 | 0.47 | 0.15 | 1.73 |
| recon3d.reconstruct | heur | 28 | 2.37 | 2.37 | 4.22 |

## Ressalvas

- Imagens reduzidas a no máx. 1024 px no maior lado; máscaras de referência redimensionadas por vizinho mais próximo.
- Convenção de lado: pulmão/clavícula 'esquerdo' = lado esquerdo do paciente (lado direito da imagem). Colunas 'lado trocado' contam imagens em que o Dice com a estrutura contralateral supera em > 0,2; indicam convenção invertida na máscara de referência ou erro de lado.
- ICT nosso = largura do coração / largura dos campos pulmonares (proxy da largura torácica interna); o ICT de referência usa a mesma fórmula nas máscaras manuais (não a largura torácica interna real).
- Para IU e máscaras, a segmentação/achados usam uma execução 'com tags' (BodyPart=CHEST, ViewPosition conforme a verdade) como num DICOM; a detecção de região/incidência é pontuada numa execução sem tags (como PNG/JPG). Rótulos IU vêm dos laudos (mapeamento por texto/etiquetas, estudo-nível): positivos podem não estar visíveis na imagem; a ausência de menção é tratada como negativo. Escores do DenseNet foram treinados também com IU (nih-pc-chex-mimic_ch-google-openi-kaggle) — risco de vazamento, as métricas de modelo no IU são otimistas.
- PA/AP: sem tags DICOM nas imagens PNG a incidência frontal assume PA; só frontal vs perfil é avaliado como acerto.
- Legendas de artigos/Wikimedia: dica de região/incidência é heurística de texto (regex) e rótulos são evidência fraca; figuras podem ter painéis múltiplos, setas e texto sobre a imagem.
