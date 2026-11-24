# RX: correções de detecção de região/incidência e entrada (fix-rx-view)

Escopo: `backend/app/rx/` + `tests/test_rx*.py`. Medido em dados reais; scripts de medida e cache de probabilidades em scratchpad (não versionados).
Dev = JSRT + Montgomery + PAX-Ray++ (sintético) + IU por ordem de arquivo. Teste = Shenzhen + 60 imagens IU rotuladas **manualmente** (visualização, 30 frontal / 30 perfil, amostra aleatória, rótulo feito antes de ver a previsão).

## Achados sobre os dados
- **IU `view_source=="caption"` não é rótulo por imagem**: as 332 imagens "LATERAL" vêm de legendas de estudo ("PA and lateral"); inspeção visual mostrou imagens frontais com esse rótulo (a PSPNet também vê coração + dois pulmões em ~50% delas). `view_source=="file_order"` também é ruidoso (~28% dos "LATERAL" são frontais). Por isso usei a amostra manual (n=60) como verdade para IU. A métrica de incidência IU do bench (0,14) é dominada por ruído de rótulo.
- **MCUCXR_0060_0** (Dice 0): radiografia normal com **borda preta enorme** (conteúdo ocupa ~50% do canvas, topo-esquerda); o pré-processamento esmagava o tórax e a PSPNet falhava na verificação de plausibilidade. Corrigido com autocrop (Dice pulmões agora 0,88).
- Heurística quando segmenta (35/120 JSRT) tem Dice ~0,69; o Dice 0,1-0,25 do benchmark vem de ~70% de "sem máscara". Os 4 "lado trocado" restantes têm Dice normal 0,04 (máscaras erradas, não convenção de lado).

## Mudanças
1. `view.py`: detecção de região/incidência sem tags por **plausibilidade anatômica da PSPNet** (uma única passada, reutilizada pela segmentação): frontal = coração >= 2% + pulmões >= 8%; perfil = campo pulmonar único (>=4%, prob. >= 0,85), sem coração, **sem máscara de coluna** (a rede só desenha coluna em frontal/abdome) e centroides L/R próximos (< 0,40); resto -> heurística só para abdome/extremidade/outro (nunca volta a "tórax"). Heurística antiga só quando modelo indisponível. Rotação: tenta rot90 k=1,3 em não-tórax e k=2 em frontal com coração na metade superior (passadas extras só nesses casos); imagem devolvida já em pé.
2. `_common.autocrop`: remove bordas planas (padding/letterbox); `analyze.py` cola resultados de volta no canvas original (coordenadas/medidas no sistema da imagem original).
3. `_common.polarity_margin`/`analyze`: inversão de polaridade (PNG MONOCHROME1-like) por contraste anel-vs-centro; margens pequenas (>0,05) são arbitradas pela PSPNet (2/53 imagens normais passavam de 0,05), sem modelo só > 0,12. DICOM com PhotometricInterpretation não é tocado. 16-bit: estiramento robusto (percentis 0,5-99,5) em vez de min-max.
4. Heurística nunca silenciosa: `quality["confiabilidade"]` com aviso explícito (BAIXA CONFIABILIDADE, Dice ~0,1-0,25) e confiança por estrutura <= 0,25 (antes até 0,55).
5. Lateralidade: `quality["lateralidade"]` quando o coração está do lado esquerdo da imagem (espelhada/dextrocardia: D/E não confirmado). Mapeamento padrão mantido (esquerda da imagem = pulmão direito do paciente) em todos os caminhos.
6. Perfil: campo pulmonar da PSPNet (união pulmão E+D) + priors anatômicos em coordenadas relativas ao campo (coração, coluna, esterno, traqueia) em vez do blob de Otsu, que só segmentava ~13% dos perfis. `seg_model` refatorado (`psp_probs`, `masks_from_probs`, `lung_field_from_probs`).
7. Testes: `tests/test_rx_view.py` novo (autocrop, polaridade, classificador, aviso de heurística, lateralidade); stub de `segment_chest_model` ajustado ao novo parâmetro `prob`.

## Antes / depois (sem tags, modelos ligados; `old` = detecção heurística anterior na mesma amostra)
| conjunto | N | antes: tórax frontal | depois: tórax frontal |
|---|---|---|---|
| JSRT (dev) | 25 | 6/25 (24%; completo 51%) | 25/25 (100%) |
| Montgomery (dev) | 25 | 3/25 (12%; completo 17%) | 25/25 (100%) |
| Shenzhen (teste) | 30 | 20/30 (67%) | 30/30 (100%) |
| PAX-Ray++ frontal (sintético, dev) | 10 | 0/10 | 9/10 |
| IU manual, frontal (teste) | 30 | 7/30 (23%) | 30/30 (100%) |

| conjunto (perfil) | N | antes: perfil | depois: perfil |
|---|---|---|---|
| IU manual, perfil (teste) | 30 | 3/30 | 27/30 (os 3 restantes -> "abdome"/outro) |
| PAX-Ray++ lateral (sintético, dev) | 30 | 2/30 | 26/30 |

Acurácia frontal vs perfil, IU manual (n=60): antes 10/60 (7+3 corretos); depois 57/60 = 0,95.
Segmentação de perfil PAX-Ray++ (Dice médio nos 26/30 detectados; contagem sem detecção = 0 dá 0,87x): coração 0,60, coluna 0,40, esterno 0,36, traqueia 0,09, aorta 0 (não segmentada). Antes: 4/30 com máscara; coração 0,21, coluna 0,15, esterno 0,13 nesses 4. Sintético (DRR de CT), pseudo-rótulos; priors ajustados na própria amostra dev de 30 (risco de sobreajuste, IC largo).
Perfis IU (15 primeiros detectados como perfil, modelo ligado): 15/15 com campo pulmonar, coração, coluna, diafragma; 14/15 esterno e traqueia; 13/15 com o conjunto completo (lung_field, heart, spine, trachea, sternum, diaphragm) exigido pela reconstrução 3D.
Segmentação frontal (bench oficial, --limit 25, tagged) inalterada: pulmões 0,86-0,87, coração 0,89-0,93, ICT MAE 0,024-0,039; Shenzhen pulmões (união) 0,866 modelo / 0,573 heurística.
MCUCXR_0060_0: Dice pulmões 0 -> 0,88 (também invertida: 0,88).

## Limitações / pendências
- O bench pontua detecção sem tags usando o modo `heur` (use_model=False), portanto **continua mostrando ~44%/12% de tórax**; não mede este caminho. Sugestão: pontuar `auto_*` com a execução de modelo (editar bench/rx_bench.py: `_analyze(img, id, task["mode"])` na execução sem tags). Os números acima vêm de script próprio.
- Sem modelo, a detecção heurística continua fraca (~12-44% tórax em JSRT/Montgomery); agora é sinalizada.
- Frontal em decúbito/AP: PA continua assumida sem tag. Imagens espelhadas só são sinalizadas (via posição do coração). Perfil de cabeça para baixo e rotações de perfil não tratadas. Abdome/extremidade: poucos dados rotulados (legendas EuropePMC, rótulo fraco) — 29/30 abdomes e 32/35 outros corretamente "não tórax" no cache de probabilidades.
- Traqueia/aorta em perfil continuam praticamente sem acerto.
