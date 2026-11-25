# Trilha r2-e5 (E5: onda P global, BAV1, BAV3)

Base (antes) = cache R2mergedL do repo principal (código d5ae272, PTB-XL dev ampliado N=9183). Depois = tag E51 (mesmo comando, código desta trilha).
Comandos (de backend/, PYTHONPATH=., MEDLENS_DATASETS/MEDLENS_BENCH absolutos):

    python -m bench.ecg_bench --source ptbxl --split dev --set large --tag E51 --workers 9
    python -m bench.r2_report --tag E51 --out /tmp/E51.md

Nota: uma execução E50 foi descartada (iniciada antes das edições, contaminada por código misto); baseline = R2mergedL.

| Métrica-chave | antes | depois |
|---|---|---|
| viés PR vs 12SL (ms) | 11,6 [10,7-12,5] | 1,5 [0,7-2,2] |
| AV1 sens / VPP | 38,3% / 52,8% (TP 236, N pos 616) | 39,9% / 54,2% (TP 246) |
| AV3 sens / VPP | 0,0% / 0,0% (N pos 12) | 33,3% [8,3-62,5] / 18,2% (TP 4, FP 18; espec 99,8%) |
| STD sens / espec | 47,8% / 85,1% | 52,9% / 83,3% (espec -1,8 pt) |
| NORM -> normal | 74,5% | 74,5% |
| AF sens / VPP | 84,4% / 84,0% | 84,4% / 84,0% |
| STE_acute sens / FP | 51,2% / 3,76% | 51,2% / 3,76% |
| LVH, LBBB, LQT | 74,8/44,1; 78,5/49,0; 61,7/6,9 | iguais |
| CRBBB sens / VPP | 58,0% / 68,7% | 58,0% / 69,3% |
| MAE QRS / viés QRS | 27,1 / 25,3 | 27,1 / 25,3 |

## O que mudou
- delineate.py: P_ON_RANK=-1, onset global de P = mediana entre derivações com P significativa (antes: mais precoce). Escolha: varredura rank 0/1/mediana em ~930 registros dev (viés PR 13,6 / -0,1 / +0,7; MAE 39,1 / 33,5 / 32,0).
- rules.py (BAV1): decisão por PR por batimento: mediana > 200 ms, >= 60% dos batimentos > 200 ms, pico P ao QRS >= 165 ms (AV1_BEAT_FRAC, AV1_MIN_BEATS). Varredura offline no dev: fronteira sens x FP; meta 55% NÃO atingida (sem piora de espec).
- rhythm.py: atrial_grid (resíduo QRS-T cancelado de II+V1+aVF, z-score, polaridade alinhada, período por autocorrelação, fase por pente) e _av3_from_grid (FC atrial 40-150, ventricular regular CV<0,12 e <85% da atrial, razão não inteira, fase QRS/grade dispersa R<0,45). Descarta grade harmônica (2 FP iniciais).
- analysis/__init__.py: chama atrial_grid e passa a av_analysis (2 linhas).
- rules.py (BAV3): ritmo regular lento (<60 bpm, CV<0,04) sem P (no_p/flutter) => "Bloqueio atrioventricular total (sugestivo)". BAV3 sempre rotulado (sugestivo).
- tests/test_ecg_p_wave_av.py: 4 testes sintéticos (BAV3 P 75/QRS 40; sinusal normal; grade harmônica; grade multiderivação).

## Limitações
- BAV1 55% não atingido: correlação PR vs 12SL r~0,64, MAE ~32 ms; a medida de PR é o gargalo, não a regra.
- BAV3 33% < meta 40%, N=12 (IC 8-63%); 4 TP, ajuste feito nos mesmos 12 positivos (risco de sobreajuste). Teste (folds 9-10) não usado.
