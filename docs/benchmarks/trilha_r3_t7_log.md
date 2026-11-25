# Trilha R3-T7 (E1 ST) + T1 da trilha 5 (abstenção ST/Q por ruído)

Bench: `cd backend && PYTHONPATH=. MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=/Users/macbook/medlens/data/bench python -m bench.ecg_bench --source ptbxl --split dev --tag <TAG> --workers 4` (N=1183, dev folds 1-8). Base = HEAD d5ae272 (tag R3T7_B), depois = S1.

| Indicador (sens/espec %) | Antes | Depois (STE J+J60, rebaixa QRS largo/HVE, recíproca, abstenção) |
|---|---|---|
| STE_acute | 55,6 / 94,6 (FP 63) | 55,6 / 94,9 (FP 59) |
| STD | 65,9 / 70,0 | 65,9 / 70,0 |
| STTC | 54,4 / 67,0 | 54,4 / 67,6 |
| MI_any | 35,3 / 91,3 | 35,3 / 91,8 |
| NORM | 74,5 / 87,1 | 74,5 / 86,9 |
| LVH | 76,1 / 83,6 | 76,1 / 83,6 |
| MAE ST-J médio vs 12SL (µV) | 29,1 | 29,1 (meta <= 30 já atendida) |

Variantes testadas e descartadas:
- J no offset global (S2): MAE ST-J 29,1 -> 34,6; STD sens 65,9 -> 61,2. Revertida.
- STD 0,5-1 mm com severidade borderline (S3): NORM 74,5/87,1 -> 76,5/84,6 (espec -2,5). Revertida (regra: só se bench não piorar).

Abstenção por ruído (limiar existente: sigma > 50 uV ou qualidade < 0,5): sem efeito no PTB-XL dev (STD/Q inalterados), só em sinais muito ruidosos. Meta STD espec >= 85% com sens >= 55% NÃO atingida neste conjunto (70,0/65,9; no conjunto large o último valor medido era 83,3/52,9).
