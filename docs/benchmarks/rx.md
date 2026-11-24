# Benchmark RX (MedLens)

_Generated 2026-11-24 14:24 UTC by `bench`._

## Resumo

| capacidade | métrica | N | valor |
|---|---|---|---|
| Segmentação heart (jsrt_masks, heur) | Dice médio [IC95%] | 120 | 0.153 [0.102, 0.209] |
| Segmentação heart (jsrt_masks, model) | Dice médio [IC95%] | 120 | 0.926 [0.922, 0.931] |
| Segmentação lungs (jsrt_masks, heur) | Dice médio [IC95%] | 120 | 0.205 [0.143, 0.276] |
| Segmentação lungs (jsrt_masks, model) | Dice médio [IC95%] | 120 | 0.863 [0.859, 0.867] |
| Segmentação heart (montgomery, heur) | Dice médio [IC95%] | 120 | 0.043 [0.018, 0.076] |
| Segmentação heart (montgomery, model) | Dice médio [IC95%] | 120 | 0.899 [0.889, 0.909] |
| Segmentação lungs (montgomery, heur) | Dice médio [IC95%] | 120 | 0.047 [0.020, 0.086] |
| Segmentação lungs (montgomery, model) | Dice médio [IC95%] | 120 | 0.873 [0.869, 0.877] |
| Segmentação heart (rx_masks_other [LATERAL], heur) | Dice médio [IC95%] | 64 | 0.022 [0.004, 0.045] |
| Segmentação heart (rx_masks_other [LATERAL], model) | Dice médio [IC95%] | 64 | 0.474 [0.405, 0.548] |
| Segmentação heart (rx_masks_other [PA], heur) | Dice médio [IC95%] | 56 | 0.021 [0.000, 0.056] |
| Segmentação heart (rx_masks_other [PA], model) | Dice médio [IC95%] | 56 | 0.838 [0.791, 0.871] |
| Segmentação lungs (rx_masks_other [PA], heur) | Dice médio [IC95%] | 56 | 0.025 [0.000, 0.062] |
| Segmentação lungs (rx_masks_other [PA], model) | Dice médio [IC95%] | 56 | 0.824 [0.783, 0.848] |
| Segmentação lungs (shenzhen, heur) | Dice médio [IC95%] | 120 | 0.653 [0.581, 0.715] |
| Segmentação lungs (shenzhen, model) | Dice médio [IC95%] | 120 | 0.858 [0.853, 0.865] |
| Região=tórax sem tags (jsrt_masks) | fração [IC95%] | 120 | 1.000 [0.969, 1.000] |
| Região=tórax sem tags (montgomery) | fração [IC95%] | 120 | 1.000 [0.969, 1.000] |
| Região=tórax sem tags (rx_masks_other [LATERAL]) | fração [IC95%] | 64 | 0.828 [0.718, 0.901] |
| Região=tórax sem tags (rx_masks_other [PA]) | fração [IC95%] | 56 | 0.982 [0.906, 0.997] |
| Região=tórax sem tags (shenzhen) | fração [IC95%] | 120 | 1.000 [0.969, 1.000] |
| ICT erro absoluto (jsrt_masks, heur) | MAE | 120 | 0.156 |
| ICT erro absoluto (jsrt_masks, model) | MAE | 120 | 0.026 |
| ICT erro absoluto (montgomery, heur) | MAE | 120 | 0.110 |
| ICT erro absoluto (montgomery, model) | MAE | 120 | 0.022 |
| ICT erro absoluto (rx_masks_other [PA], heur) | MAE | 56 | 0.177 |
| ICT erro absoluto (rx_masks_other [PA], model) | MAE | 56 | 0.032 |

## Segmentação vs máscaras de referência (Dice / IoU por estrutura)

### jsrt_masks

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| heart | 0.926 [0.922, 0.931] | 0.864 | 0.926 | 120 (0 sem máscara) | 0.153 [0.102, 0.209] | 0.120 | 0.000 | 120 (89 sem máscara) |
| left_clavicle | 0.594 [0.572, 0.622] | 0.435 | 0.630 | 120 (0 sem máscara) | 0.007 [0.001, 0.016] | 0.004 | 0.000 | 120 (105 sem máscara) |
| left_lung | 0.797 [0.790, 0.804] | 0.664 | 0.799 | 120 (0 sem máscara) | 0.192 [0.127, 0.260] | 0.165 | 0.000 | 120 (88 sem máscara); 1 lado trocado |
| lungs | 0.863 [0.859, 0.867] | 0.760 | 0.866 | 120 (0 sem máscara) | 0.205 [0.143, 0.276] | 0.174 | 0.000 | 120 (88 sem máscara) |
| right_clavicle | 0.598 [0.571, 0.623] | 0.441 | 0.627 | 120 (0 sem máscara) | 0.009 [0.003, 0.016] | 0.005 | 0.000 | 120 (93 sem máscara) |
| right_lung | 0.923 [0.919, 0.927] | 0.858 | 0.927 | 120 (0 sem máscara) | 0.189 [0.127, 0.255] | 0.162 | 0.000 | 120 (88 sem máscara); 3 lado trocado |

### montgomery

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| heart | 0.899 [0.889, 0.909] | 0.821 | 0.907 | 120 (0 sem máscara) | 0.043 [0.018, 0.076] | 0.035 | 0.000 | 120 (112 sem máscara) |
| left_clavicle | 0.651 [0.623, 0.676] | 0.499 | 0.686 | 120 (0 sem máscara) | 0.001 [0.000, 0.003] | 0.001 | 0.000 | 120 (116 sem máscara) |
| left_lung | 0.837 [0.831, 0.842] | 0.720 | 0.840 | 120 (0 sem máscara) | 0.041 [0.017, 0.078] | 0.034 | 0.000 | 120 (112 sem máscara); 1 lado trocado |
| lungs | 0.873 [0.869, 0.877] | 0.775 | 0.875 | 120 (0 sem máscara) | 0.047 [0.020, 0.086] | 0.039 | 0.000 | 120 (112 sem máscara) |
| right_clavicle | 0.623 [0.599, 0.643] | 0.461 | 0.640 | 120 (0 sem máscara) | 0.002 [0.000, 0.006] | 0.001 | 0.000 | 120 (117 sem máscara) |
| right_lung | 0.906 [0.901, 0.911] | 0.830 | 0.908 | 120 (0 sem máscara) | 0.046 [0.018, 0.086] | 0.040 | 0.000 | 120 (112 sem máscara) |

### rx_masks_other [LATERAL]

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| aorta | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 64 (64 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 64 (64 sem máscara) |
| heart | 0.474 [0.405, 0.548] | 0.356 | 0.521 | 64 (10 sem máscara) | 0.022 [0.004, 0.045] | 0.014 | 0.000 | 64 (58 sem máscara) |
| spine | 0.340 [0.276, 0.410] | 0.236 | 0.344 | 64 (10 sem máscara) | 0.014 [0.003, 0.029] | 0.008 | 0.000 | 64 (56 sem máscara) |
| sternum | 0.273 [0.214, 0.329] | 0.175 | 0.320 | 64 (10 sem máscara) | 0.030 [0.008, 0.057] | 0.019 | 0.000 | 64 (56 sem máscara) |
| trachea | 0.053 [0.025, 0.082] | 0.031 | 0.000 | 64 (38 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 64 (64 sem máscara) |

### rx_masks_other [PA]

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| aorta | 0.215 [0.181, 0.240] | 0.125 | 0.242 | 56 (5 sem máscara) | 0.001 [0.000, 0.003] | 0.001 | 0.000 | 56 (54 sem máscara) |
| heart | 0.838 [0.791, 0.871] | 0.741 | 0.881 | 56 (1 sem máscara) | 0.021 [0.000, 0.056] | 0.016 | 0.000 | 56 (54 sem máscara) |
| left_clavicle | 0.393 [0.303, 0.471] | 0.294 | 0.411 | 56 (12 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 56 (56 sem máscara) |
| left_lung | 0.853 [0.813, 0.878] | 0.757 | 0.879 | 56 (1 sem máscara) | 0.027 [0.000, 0.068] | 0.022 | 0.000 | 56 (54 sem máscara) |
| left_scapula | 0.510 [0.451, 0.558] | 0.365 | 0.526 | 56 (1 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 56 (56 sem máscara) |
| lungs | 0.824 [0.783, 0.848] | 0.713 | 0.843 | 56 (1 sem máscara) | 0.025 [0.000, 0.062] | 0.019 | 0.000 | 56 (54 sem máscara) |
| right_clavicle | 0.474 [0.395, 0.535] | 0.356 | 0.546 | 56 (5 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 56 (55 sem máscara) |
| right_lung | 0.789 [0.749, 0.815] | 0.665 | 0.811 | 56 (1 sem máscara) | 0.022 [0.000, 0.055] | 0.016 | 0.000 | 56 (54 sem máscara) |
| right_scapula | 0.522 [0.464, 0.576] | 0.381 | 0.560 | 56 (2 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 56 (56 sem máscara) |
| spine | 0.709 [0.657, 0.747] | 0.569 | 0.769 | 56 (1 sem máscara) | 0.028 [0.000, 0.070] | 0.023 | 0.000 | 56 (54 sem máscara) |
| sternum | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 56 (56 sem máscara) | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 56 (56 sem máscara) |
| trachea | 0.669 [0.607, 0.723] | 0.535 | 0.747 | 56 (2 sem máscara) | 0.003 [0.000, 0.010] | 0.002 | 0.000 | 56 (54 sem máscara) |

### shenzhen

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| left_lung | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 120 (0 sem máscara); 120 lado trocado | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 120 (27 sem máscara); 93 lado trocado |
| lungs | 0.858 [0.853, 0.865] | 0.754 | 0.864 | 120 (0 sem máscara) | 0.653 [0.581, 0.715] | 0.572 | 0.853 | 120 (27 sem máscara) |
| right_lung | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 120 (0 sem máscara); 120 lado trocado | 0.000 [0.000, 0.000] | 0.000 | 0.000 | 120 (27 sem máscara); 93 lado trocado |

## Piores casos de segmentação

| fonte | estrutura | caminho | id | Dice |
|---|---|---|---|---|
| rx_masks_other [PA] | lungs | model | `RSNAPE_b9716006589c_a52e60d498d8_frontal` | 0.000 |
| rx_masks_other [PA] | lungs | model | `RSNAPE_9bc09ed256ef_057ab2121050_frontal` | 0.692 |
| shenzhen | lungs | model | `CHNCXR_0455_1` | 0.694 |
| shenzhen | lungs | model | `CHNCXR_0228_0` | 0.735 |
| rx_masks_other [PA] | lungs | model | `RSNAPE_ab1671510bec_c96ee2f013e8_frontal` | 0.736 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_0b14caeba6ab_47c0b3be0811_lateral` | 0.000 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_5364d189c001_b76606bb34fe_lateral` | 0.000 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_8b7c88e59589_f03257e42639_lateral` | 0.000 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_c36796f3719c_5df07365de1c_lateral` | 0.000 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_c28ab4020959_16dcdbb982dd_lateral` | 0.000 |
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
| jsrt_masks | 120 | 120/120 = 1.000 [0.969, 1.000] | 120/120 |
| montgomery | 120 | 120/120 = 1.000 [0.969, 1.000] | 120/120 |
| rx_masks_other [LATERAL] | 64 | 53/64 = 0.828 [0.718, 0.901] | 53/64 |
| rx_masks_other [PA] | 56 | 55/56 = 0.982 [0.906, 0.997] | 55/56 |
| shenzhen | 120 | 120/120 = 1.000 [0.969, 1.000] | 120/120 |

## ICT: referência (máscaras) vs nosso

| fonte | caminho | N | sem ICT | erro abs. médio [IC95%] | mediana | viés (nosso−GT) | erro abs. fórmula nas máscaras previstas | concordância ICT>0,5 |
|---|---|---|---|---|---|---|---|---|
| jsrt_masks | model | 120 | 0 | 0.026 [0.023, 0.029] | 0.023 | -0.026 | 0.026 | 0.89 (107/120) |
| jsrt_masks | heur | 120 | 89 | 0.156 [0.120, 0.195] | 0.126 | +0.125 | 0.156 | 0.42 (13/31) |
| montgomery | model | 120 | 0 | 0.022 [0.017, 0.028] | 0.015 | -0.004 | 0.022 | 0.95 (114/120) |
| montgomery | heur | 120 | 112 | 0.110 [0.034, 0.206] | 0.057 | -0.006 | 0.110 | 0.75 (6/8) |
| rx_masks_other [PA] | model | 56 | 1 | 0.032 [0.024, 0.044] | 0.025 | -0.028 | 0.032 | 0.82 (45/55) |
| rx_masks_other [PA] | heur | 56 | 54 | 0.177 [0.165, 0.189] | 0.177 | +0.177 | 0.177 | 0.50 (1/2) |

Maiores erros de ICT: `montgomery/MCUCXR_0213_1` (heur: 0.08 vs GT 0.51); `jsrt_masks/JPCNN036` (heur: 0.79 vs GT 0.43); `jsrt_masks/JPCLN097` (heur: 0.84 vs GT 0.50); `jsrt_masks/JPCNN012` (heur: 0.77 vs GT 0.45); `jsrt_masks/JPCLN087` (heur: 0.76 vs GT 0.45); `jsrt_masks/JPCNN038` (heur: 0.67 vs GT 0.40); `jsrt_masks/JPCNN050` (heur: 0.73 vs GT 0.46); `jsrt_masks/JPCNN065` (heur: 0.75 vs GT 0.49)

## Tempos (s, 1 thread por worker)

| etapa | caminho | N | média | mediana | p95 |
|---|---|---|---|---|---|
| máscaras analyze_image | model | 480 | 6.40 | 6.26 | 7.32 |
| máscaras analyze_image | heur | 480 | 0.28 | 0.16 | 0.91 |

## Modos de falha observados (ver tabelas e ids acima)

- **Sem tags DICOM, o tórax frequentemente não é reconhecido** (região estimada como abdome/outra em imagens PNG/JPG de tórax): sem a região correta não há segmentação nem achados. Ver 'Detecção de região sem tags'.
- **Caminho heurístico**: não encontra o par de campos pulmonares na maioria das imagens reais (sem máscara em > 70% mesmo com região informada); quando segmenta, ICT com erro grande. Está ajustado a fantomas sintéticos.
- **Caminho com modelo (PSPNet ChestX-Det)**: pulmões/coração bons (Dice ~0,86/0,9 em JSRT/Montgomery); clavículas fracas (~0,6); pulmão esquerdo menor que o direito (retrocardíaco); casos de zero em imagens atípicas (ex.: `MCUCXR_0060_0`).
- **Perfil**: heurística de perfil segmenta pouco (coração/coluna/traqueia ausentes em ~metade); impacta a reconstrução 3D (falha 'Incidência lateral sem máscaras').
- **Achados**: regra de ICT>0,5 tem alta especificidade mas baixa sensibilidade em IU; modelos DenseNet com escore >= 0,65 quase nunca disparam (sensibilidade baixa) embora a AUC seja alta (>0,89); regras de seio costofrênico não detectaram derrames.

## Ressalvas

- Imagens reduzidas a no máx. 1024 px no maior lado; máscaras de referência redimensionadas por vizinho mais próximo.
- Convenção de lado: pulmão/clavícula 'esquerdo' = lado esquerdo do paciente (lado direito da imagem). Colunas 'lado trocado' contam imagens em que o Dice com a estrutura contralateral supera em > 0,2; indicam convenção invertida na máscara de referência ou erro de lado.
- ICT nosso = largura do coração / largura dos campos pulmonares (proxy da largura torácica interna); o ICT de referência usa a mesma fórmula nas máscaras manuais (não a largura torácica interna real).
- Para IU e máscaras, a segmentação/achados usam uma execução 'com tags' (BodyPart=CHEST, ViewPosition conforme a verdade) como num DICOM; a detecção de região/incidência é pontuada numa execução sem tags (como PNG/JPG). Rótulos IU vêm dos laudos (mapeamento por texto/etiquetas, estudo-nível): positivos podem não estar visíveis na imagem; a ausência de menção é tratada como negativo. Escores do DenseNet foram treinados também com IU (nih-pc-chex-mimic_ch-google-openi-kaggle) — risco de vazamento, as métricas de modelo no IU são otimistas.
- PA/AP: sem tags DICOM nas imagens PNG a incidência frontal assume PA; só frontal vs perfil é avaliado como acerto.
- Legendas de artigos/Wikimedia: dica de região/incidência é heurística de texto (regex) e rótulos são evidência fraca; figuras podem ter painéis múltiplos, setas e texto sobre a imagem.
