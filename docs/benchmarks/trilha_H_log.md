# Trilha H — log (E7 benchmark de foto de ECG, E6 spec)

Comando: `cd backend && MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench PYTHONPATH=. python -m bench.ecg_photo_bench --tag <TAG> --limit 200 --workers 3`
Dados: 200 registros PTB-XL folds 1-8 (40 cada WPW/BRE/BRD/IAM/NORM), renderizados com matplotlib (A4, 25 mm/s, 10 mm/mV, ~8 px/mm), 3 perfis de degradacao (clean/mild/hard, ~67 cada). Folds 9-10 nao usados.

## Antes (tag H, HEAD 91b4eb2 = so a validacao de quad degenerado)
- Utilizavel (sem excecao, grid_conf >= 0.3, >= 2 batimentos): 180/200 = 90.0% (excecoes 0)
- Pearson mediano (mediana das derivacoes por imagem): 0.19 (clean 0.99, mild 0.13, hard 0.05)
- Erro mediano abs vs sinal original: RR 33.7 ms, QRS 54 ms, QT 53 ms

## Depois (tag H2, commit fix pink-grid)
- Utilizavel: 195/200 = 97.5% (clean 100, mild 98.5, hard 93.9); excecoes 0
- Pearson mediano: 0.82 (clean 0.993, mild 0.81 [P25 0.55], hard 0.10)
- Erro mediano abs: RR 12.9 ms, QRS 56 ms, QT 52 ms
- Regras na foto dado detectado no sinal: BRE 45%, BRD 50%, IAM 62%, WPW 0% (1 deteccao), NORM 26%

Metas: utilizavel >= 85% ATINGIDA; Pearson mediano >= 0.9 NAO atingida no geral (so no perfil clean).

## Excecoes originais (bench sintetico, 45 imagens, antes das correcoes)
- ValueError "no ECG trace found" (__init__.py:80) e "All-NaN slice" (geometry.py:48): quad de papel degenerado (cantos duplicados) quando a folha e cortada pelo quadro -> warp lixo. Corrigido (commit 91b4eb2).

## Causa dos baixos Pearson restantes (perfil hard, parte do mild)
- Sem quad de papel (folha preenche o quadro), a keystone (perspectiva 3.5%) + rotacao 5 graus nao e corrigida: linhas viram 5 "rows", pulso de calibracao nao e achado, tracos de colunas se misturam.
- Proximo passo sugerido: retificar por geometria da grade (pontos de fuga das linhas de grade) em vez de depender do contorno da folha.
- BRD/BRE/WPW na foto: WPW (onda delta) some com blur/JPEG; BRD/BRE dependem de QRS ~50 ms de erro. NORM 26% mostra que a foto gera achados espurios (so sinal-verdade valido como NORM).

## Teste final (PTB-XL folds 9-10)
Nao executado (limiar nao foi ajustado; nenhuma mudanca de limiar nesta trilha).

## Commits
- 37a5796 bench(ecg): photo-digitizer benchmark ...
- 91b4eb2 fix(ecg-digitize): reject degenerate paper quad ...
- a8ed42f docs(ecg): spec E6 ...
- 621ae55 fix(ecg-digitize): detect paper by pink grid too
- 1014f63 bench(ecg): skip PTB-XL records not yet downloaded
