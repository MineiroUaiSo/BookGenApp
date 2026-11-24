# Benchmark RX (MedLens)

_Generated 2026-11-24 11:10 UTC by `bench`._

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
| Região=tórax sem tags (jsrt_masks) | fração [IC95%] | 247 | 0.506 [0.444, 0.568] |
| Região=tórax sem tags (montgomery) | fração [IC95%] | 138 | 0.167 [0.114, 0.238] |
| ICT erro absoluto (jsrt_masks, heur) | MAE | 247 | 0.169 |
| ICT erro absoluto (jsrt_masks, model) | MAE | 247 | 0.027 |
| ICT erro absoluto (montgomery, heur) | MAE | 138 | 0.123 |
| ICT erro absoluto (montgomery, model) | MAE | 138 | 0.023 |

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

## Piores casos de segmentação

| fonte | estrutura | caminho | id | Dice |
|---|---|---|---|---|
| montgomery | lungs | model | `MCUCXR_0060_0` | 0.000 |
| jsrt_masks | lungs | model | `JPCLN016` | 0.768 |
| montgomery | lungs | model | `MCUCXR_0061_0` | 0.791 |
| jsrt_masks | lungs | model | `JPCNN071` | 0.798 |
| jsrt_masks | lungs | model | `JPCLN002` | 0.800 |
| montgomery | heart | model | `MCUCXR_0060_0` | 0.000 |
| montgomery | heart | model | `MCUCXR_0390_1` | 0.662 |
| montgomery | heart | model | `MCUCXR_0080_0` | 0.687 |
| montgomery | heart | model | `MCUCXR_0251_1` | 0.691 |
| montgomery | heart | model | `MCUCXR_0023_0` | 0.698 |
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

## ICT: referência (máscaras) vs nosso

| fonte | caminho | N | sem ICT | erro abs. médio [IC95%] | mediana | viés (nosso−GT) | erro abs. fórmula nas máscaras previstas | concordância ICT>0,5 |
|---|---|---|---|---|---|---|---|---|
| jsrt_masks | model | 247 | 0 | 0.027 [0.025, 0.029] | 0.024 | -0.026 | 0.027 | 0.89 (220/247) |
| jsrt_masks | heur | 247 | 175 | 0.169 [0.143, 0.195] | 0.164 | +0.126 | 0.169 | 0.36 (26/72) |
| montgomery | model | 138 | 1 | 0.023 [0.018, 0.028] | 0.015 | -0.010 | 0.023 | 0.93 (128/137) |
| montgomery | heur | 138 | 121 | 0.123 [0.074, 0.189] | 0.078 | +0.024 | 0.123 | 0.65 (11/17) |

Maiores erros de ICT: `montgomery/MCUCXR_0213_1` (heur: 0.08 vs GT 0.51); `jsrt_masks/JPCNN009` (heur: 0.15 vs GT 0.55); `jsrt_masks/JPCNN089` (heur: 0.78 vs GT 0.39); `montgomery/MCUCXR_0080_0` (heur: 0.08 vs GT 0.45); `jsrt_masks/JPCLN130` (heur: 0.82 vs GT 0.46); `jsrt_masks/JPCNN036` (heur: 0.79 vs GT 0.43); `jsrt_masks/JPCNN022` (heur: 0.83 vs GT 0.48); `jsrt_masks/JPCLN139` (heur: 0.83 vs GT 0.48)

## Tempos (s, 1 thread por worker)

| etapa | caminho | N | média | mediana | p95 |
|---|---|---|---|---|---|
| máscaras analyze_image | model | 385 | 8.10 | 6.94 | 16.28 |
| máscaras analyze_image | heur | 385 | 0.16 | 0.13 | 0.50 |

## Ressalvas

- Imagens reduzidas a no máx. 1024 px no maior lado; máscaras de referência redimensionadas por vizinho mais próximo.
- Convenção de lado: pulmão/clavícula 'esquerdo' = lado esquerdo do paciente (lado direito da imagem). Colunas 'lado trocado' contam imagens em que o Dice com a estrutura contralateral supera em > 0,2; indicam convenção invertida na máscara de referência ou erro de lado.
- ICT nosso = largura do coração / largura dos campos pulmonares (proxy da largura torácica interna); o ICT de referência usa a mesma fórmula nas máscaras manuais (não a largura torácica interna real).
- Para IU e máscaras, a segmentação/achados usam uma execução 'com tags' (BodyPart=CHEST, ViewPosition conforme a verdade) como num DICOM; a detecção de região/incidência é pontuada numa execução sem tags (como PNG/JPG). Rótulos IU vêm dos laudos (mapeamento por texto/etiquetas, estudo-nível): positivos podem não estar visíveis na imagem; a ausência de menção é tratada como negativo. Escores do DenseNet foram treinados também com IU (nih-pc-chex-mimic_ch-google-openi-kaggle) — risco de vazamento, as métricas de modelo no IU são otimistas.
- PA/AP: sem tags DICOM nas imagens PNG a incidência frontal assume PA; só frontal vs perfil é avaliado como acerto.
- Legendas de artigos/Wikimedia: dica de região/incidência é heurística de texto (regex) e rótulos são evidência fraca; figuras podem ter painéis múltiplos, setas e texto sobre a imagem.
