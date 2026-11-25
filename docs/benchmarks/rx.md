# Benchmark RX (MedLens)

_Generated 2026-11-25 22:56 UTC by `bench`._

## Resumo

| capacidade | métrica | N | valor |
|---|---|---|---|
| Segmentação heart (jsrt_masks, heur) | Dice médio [IC95%] | 247 | 0.452 [0.417, 0.487] |
| Segmentação heart (jsrt_masks, model) | Dice médio [IC95%] | 247 | 0.926 [0.923, 0.929] |
| Segmentação lungs (jsrt_masks, heur) | Dice médio [IC95%] | 247 | 0.641 [0.615, 0.666] |
| Segmentação lungs (jsrt_masks, model) | Dice médio [IC95%] | 247 | 0.864 [0.861, 0.866] |
| Segmentação heart (rx_masks_other [LATERAL], heur) | Dice médio [IC95%] | 400 | 0.026 [0.016, 0.037] |
| Segmentação heart (rx_masks_other [LATERAL], model) | Dice médio [IC95%] | 400 | 0.503 [0.474, 0.530] |
| Segmentação heart (rx_masks_other [PA], heur) | Dice médio [IC95%] | 400 | 0.412 [0.379, 0.445] |
| Segmentação heart (rx_masks_other [PA], model) | Dice médio [IC95%] | 400 | 0.829 [0.815, 0.842] |
| Segmentação lungs (rx_masks_other [PA], heur) | Dice médio [IC95%] | 400 | 0.378 [0.352, 0.404] |
| Segmentação lungs (rx_masks_other [PA], model) | Dice médio [IC95%] | 400 | 0.833 [0.822, 0.841] |
| Região=tórax sem tags (jsrt_masks) | fração [IC95%] | 247 | 1.000 [1.000, 1.000] |
| Região=tórax sem tags (rx_masks_other [LATERAL]) | fração [IC95%] | 400 | 0.843 [0.807, 0.877] |
| Região=tórax sem tags (rx_masks_other [PA]) | fração [IC95%] | 400 | 0.993 [0.983, 1.000] |
| ICT erro absoluto (jsrt_masks, heur) | MAE | 247 | 0.123 |
| ICT erro absoluto (jsrt_masks, model) | MAE | 247 | 0.027 |
| ICT erro absoluto (rx_masks_other [PA], heur) | MAE | 400 | 0.082 |
| ICT erro absoluto (rx_masks_other [PA], model) | MAE | 400 | 0.041 |

## Segmentação vs máscaras de referência (Dice / IoU por estrutura)

### jsrt_masks

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| heart | 0.926 [0.923, 0.929] | 0.864 | 0.930 | 247 (0 sem máscara) | 0.452 [0.417, 0.487] | 0.340 | 0.475 | 247 (13 sem máscara) |
| left_clavicle | 0.599 [0.581, 0.614] | 0.438 | 0.629 | 247 (0 sem máscara) | 0.030 [0.015, 0.049] | 0.017 | 0.000 | 70 (0 sem máscara) |
| left_lung | 0.797 [0.792, 0.801] | 0.664 | 0.800 | 247 (0 sem máscara) | 0.631 [0.600, 0.660] | 0.499 | 0.708 | 247 (11 sem máscara); 1 lado trocado |
| lungs | 0.864 [0.861, 0.866] | 0.760 | 0.867 | 247 (0 sem máscara) | 0.641 [0.615, 0.666] | 0.501 | 0.685 | 247 (11 sem máscara) |
| right_clavicle | 0.603 [0.584, 0.620] | 0.446 | 0.628 | 247 (0 sem máscara) | 0.057 [0.044, 0.072] | 0.032 | 0.000 | 148 (0 sem máscara) |
| right_lung | 0.925 [0.922, 0.928] | 0.861 | 0.928 | 247 (0 sem máscara) | 0.607 [0.576, 0.636] | 0.475 | 0.669 | 247 (11 sem máscara); 10 lado trocado |

### rx_masks_other [LATERAL]

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| aorta | não suportado | - | - | 400 | não suportado | - | - | 400 |
| heart | 0.503 [0.474, 0.530] | 0.383 | 0.595 | 400 (64 sem máscara) | 0.026 [0.016, 0.037] | 0.017 | 0.000 | 400 (357 sem máscara) |
| spine | 0.379 [0.352, 0.405] | 0.268 | 0.468 | 400 (64 sem máscara) | 0.025 [0.018, 0.033] | 0.014 | 0.000 | 400 (338 sem máscara) |
| sternum | 0.305 [0.284, 0.325] | 0.197 | 0.345 | 400 (66 sem máscara) | 0.030 [0.021, 0.040] | 0.018 | 0.000 | 400 (338 sem máscara) |
| trachea | 0.067 [0.054, 0.080] | 0.041 | 0.000 | 400 (235 sem máscara) | 0.001 [0.000, 0.002] | 0.000 | 0.000 | 400 (382 sem máscara) |

### rx_masks_other [PA]

| estrutura | Dice modelo [IC95%] | IoU modelo | Dice med. modelo | N modelo | Dice heurística [IC95%] | IoU heur. | Dice med. heur. | N heur. |
|---|---|---|---|---|---|---|---|---|
| aorta | 0.207 [0.194, 0.219] | 0.121 | 0.238 | 400 (56 sem máscara) | 0.098 [0.089, 0.107] | 0.054 | 0.100 | 400 (125 sem máscara) |
| heart | 0.829 [0.815, 0.842] | 0.728 | 0.866 | 400 (4 sem máscara) | 0.412 [0.379, 0.445] | 0.316 | 0.517 | 400 (122 sem máscara) |
| left_clavicle | 0.430 [0.397, 0.461] | 0.329 | 0.469 | 400 (67 sem máscara) | 0.061 [0.042, 0.081] | 0.034 | 0.000 | 77 (0 sem máscara) |
| left_lung | 0.856 [0.845, 0.865] | 0.758 | 0.874 | 400 (4 sem máscara) | 0.365 [0.339, 0.391] | 0.254 | 0.472 | 400 (122 sem máscara) |
| left_scapula | 0.499 [0.478, 0.520] | 0.359 | 0.529 | 400 (13 sem máscara) | não suportado | - | - | 400 |
| lungs | 0.833 [0.822, 0.841] | 0.722 | 0.847 | 400 (4 sem máscara) | 0.378 [0.352, 0.404] | 0.264 | 0.504 | 400 (122 sem máscara) |
| right_clavicle | 0.415 [0.386, 0.444] | 0.310 | 0.451 | 400 (61 sem máscara) | 0.052 [0.035, 0.070] | 0.029 | 0.000 | 85 (0 sem máscara) |
| right_lung | 0.805 [0.794, 0.815] | 0.683 | 0.819 | 400 (4 sem máscara) | 0.383 [0.357, 0.410] | 0.271 | 0.514 | 400 (122 sem máscara); 2 lado trocado |
| right_scapula | 0.504 [0.482, 0.527] | 0.368 | 0.543 | 400 (15 sem máscara) | não suportado | - | - | 400 |
| spine | 0.696 [0.679, 0.712] | 0.556 | 0.765 | 400 (5 sem máscara) | 0.404 [0.376, 0.433] | 0.293 | 0.531 | 400 (122 sem máscara) |
| sternum | não suportado | - | - | 400 | não suportado | - | - | 400 |
| trachea | 0.629 [0.605, 0.652] | 0.496 | 0.723 | 400 (19 sem máscara) | 0.013 [0.009, 0.017] | 0.007 | 0.000 | 400 (145 sem máscara) |

## Piores casos de segmentação

| fonte | estrutura | caminho | id | Dice |
|---|---|---|---|---|
| rx_masks_other [PA] | lungs | model | `RSNAPE_b9716006589c_a52e60d498d8_frontal` | 0.000 |
| rx_masks_other [PA] | lungs | model | `RSNAPE_50d8f2306c3c_07884b46c2c9_frontal` | 0.000 |
| rx_masks_other [PA] | lungs | model | `RSNAPE_b7dd19241d7d_7cea76752154_frontal` | 0.000 |
| rx_masks_other [PA] | lungs | model | `COVID1910_0591_frontal` | 0.000 |
| rx_masks_other [PA] | lungs | model | `0619a_frontal` | 0.440 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_0b14caeba6ab_47c0b3be0811_lateral` | 0.000 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_5364d189c001_b76606bb34fe_lateral` | 0.000 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_8b7c88e59589_f03257e42639_lateral` | 0.000 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_c36796f3719c_5df07365de1c_lateral` | 0.000 |
| rx_masks_other [LATERAL] | heart | model | `RSNAPE_c28ab4020959_16dcdbb982dd_lateral` | 0.000 |
| jsrt_masks | lungs | heur | `JPCLN059` | 0.000 |
| jsrt_masks | lungs | heur | `JPCLN107` | 0.000 |
| jsrt_masks | lungs | heur | `JPCLN066` | 0.000 |
| jsrt_masks | lungs | heur | `JPCNN044` | 0.000 |
| jsrt_masks | lungs | heur | `JPCLN061` | 0.000 |
| jsrt_masks | heart | heur | `JPCNN071` | 0.000 |
| jsrt_masks | heart | heur | `JPCLN059` | 0.000 |
| jsrt_masks | heart | heur | `JPCLN070` | 0.000 |
| jsrt_masks | heart | heur | `JPCLN044` | 0.000 |
| jsrt_masks | heart | heur | `JPCLN107` | 0.000 |

## Detecção de região sem tags (imagens de tórax)

| fonte | N | região=tórax [IC95%] | tórax com incidência reconhecida |
|---|---|---|---|
| jsrt_masks | 247 | 247/247 = 1.000 [1.000, 1.000] | 247/247 |
| rx_masks_other [LATERAL] | 400 | 337/400 = 0.843 [0.807, 0.877] | 337/400 |
| rx_masks_other [PA] | 400 | 397/400 = 0.993 [0.983, 1.000] | 397/400 |

## ICT: referência (máscaras) vs nosso

| fonte | caminho | N | sem ICT | erro abs. médio [IC95%] | mediana | viés (nosso−GT) | erro abs. fórmula nas máscaras previstas | concordância ICT>0,5 |
|---|---|---|---|---|---|---|---|---|
| jsrt_masks | model | 247 | 0 | 0.027 [0.025, 0.029] | 0.024 | -0.026 | 0.027 | 0.89 (220/247) |
| jsrt_masks | heur | 247 | 70 | 0.123 [0.113, 0.133] | 0.119 | +0.109 | 0.164 | 0.35 (62/177) |
| rx_masks_other [PA] | model | 400 | 5 | 0.041 [0.036, 0.046] | 0.026 | -0.033 | 0.041 | 0.80 (315/395) |
| rx_masks_other [PA] | heur | 400 | 256 | 0.082 [0.072, 0.093] | 0.064 | +0.064 | 0.177 | 0.70 (101/144) |

Maiores erros de ICT: `rx_masks_other [PA]/COVID1910_0088_frontal` (model: 0.22 vs GT 0.53); `jsrt_masks/JPCLN079` (heur: 0.67 vs GT 0.37); `rx_masks_other [PA]/RSNAPE_4194e29bbe7e_f4987177ca24_frontal` (heur: 0.69 vs GT 0.39); `rx_masks_other [PA]/COVID19AR_162_frontal` (model: 0.27 vs GT 0.55); `jsrt_masks/JPCNN038` (heur: 0.67 vs GT 0.40); `rx_masks_other [PA]/RSNAPE_2b4a1c8c4573_059eee9bc745_frontal` (model: 0.40 vs GT 0.68); `jsrt_masks/JPCLN096` (heur: 0.69 vs GT 0.41); `rx_masks_other [PA]/0407a_frontal` (heur: 0.68 vs GT 0.41)

## Tempos (s, 1 thread por worker)

| etapa | caminho | N | média | mediana | p95 |
|---|---|---|---|---|---|
| máscaras analyze_image | model | 1047 | 4.02 | 3.89 | 6.85 |
| máscaras analyze_image | heur | 1047 | 0.98 | 0.47 | 2.93 |

## Modos de falha observados (ver tabelas e ids acima)

- **Sem tags DICOM, o tórax frequentemente não é reconhecido** (região estimada como abdome/outra em imagens PNG/JPG de tórax): sem a região correta não há segmentação nem achados. Ver 'Detecção de região sem tags'.
- **Caminho heurístico**: não encontra o par de campos pulmonares na maioria das imagens reais (sem máscara em > 70% mesmo com região informada); quando segmenta, ICT com erro grande. Está ajustado a fantomas sintéticos.
- **Caminho com modelo (PSPNet ChestX-Det)**: pulmões/coração bons (Dice ~0,86/0,9 em JSRT/Montgomery); clavículas fracas (~0,6); pulmão esquerdo menor que o direito (retrocardíaco); casos de zero em imagens atípicas (ex.: `MCUCXR_0060_0`).
- **Perfil**: heurística de perfil segmenta pouco (coração/coluna/traqueia ausentes em ~metade); impacta a reconstrução 3D (falha 'Incidência lateral sem máscaras').
- **Achados**: sem resultados IU medidos neste cache (ver seção IU X-ray quando houver).

## Ressalvas

- Imagens reduzidas a no máx. 1024 px no maior lado; máscaras de referência redimensionadas por vizinho mais próximo.
- Convenção de lado: pulmão/clavícula 'esquerdo' = lado esquerdo do paciente (lado direito da imagem). Colunas 'lado trocado' contam imagens em que o Dice com a estrutura contralateral supera em > 0,2; indicam convenção invertida na máscara de referência ou erro de lado.
- ICT nosso = largura do coração / largura dos campos pulmonares (proxy da largura torácica interna); o ICT de referência usa a mesma fórmula nas máscaras manuais (não a largura torácica interna real).
- Para IU e máscaras, a segmentação/achados usam uma execução 'com tags' (BodyPart=CHEST, ViewPosition conforme a verdade) como num DICOM; a detecção de região/incidência é pontuada numa execução sem tags (como PNG/JPG). Rótulos IU vêm dos laudos (mapeamento por texto/etiquetas, estudo-nível): positivos podem não estar visíveis na imagem; a ausência de menção é tratada como negativo. Escores do DenseNet foram treinados também com IU (nih-pc-chex-mimic_ch-google-openi-kaggle) — risco de vazamento, as métricas de modelo no IU são otimistas.
- PA/AP: sem tags DICOM nas imagens PNG a incidência frontal assume PA; só frontal vs perfil é avaliado como acerto.
- Legendas de artigos/Wikimedia: dica de região/incidência é heurística de texto (regex) e rótulos são evidência fraca; figuras podem ter painéis múltiplos, setas e texto sobre a imagem.

---
## Estado desta geracao (RX)
- Data: 2026-11-25. Codigo base 2be7b23, worktree wt/ecg-final. Bench de masks completo e fresco (sem --limit; JSRT 247, rx_masks_other 400 PA + 400 LATERAL), modelos on/off, 2094 tarefas, `--source masks --models both --workers 8`.
- Segmentacao/vista/medidas (app/rx: seg_*, view, measure, region, calibration) inalteradas desde c9a5a49; desde entao so mudaram anonimizacao de texto (analyze.py, 5 linhas), findings.py (2 linhas) e os modulos novos do laudo (ficha, laudo, claim_check, lexico, fontes), que o bench de segmentacao nao exercita. Resultados anteriores reproduzidos; diferencas sao so de IC bootstrap.
- Montgomery/Shenzhen nao existem em data/datasets (fora desta versao). Calibracao RX e gate de fora-de-escopo (4,4% na geracao anterior) NAO rerodados; ver decisoes abertas no RETOMADA.md.
- Teste externo CODE-test e do ECG; nao se aplica ao RX.
