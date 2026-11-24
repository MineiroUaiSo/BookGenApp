# Trilha C - E3 ECG ritmo: marca-passo + ectopia na FA

Dados: PTB-XL dev (strat_fold 1-8, n=1183), 500 Hz. Comandos (a partir de backend/, PYTHONPATH=.):
`python -m bench.ecg_bench --source ptbxl --split dev --tag C0 --workers 3` (baseline, codigo do commit 2adf53a)
`python -m bench.ecg_bench --source ptbxl --split dev --tag C4 --workers 3` (codigo final, equivale ao commit 50e3752)

## Antes -> depois (dev)
| Metrica | C0 | final |
|---|---|---|
| FA: PPV | 0.771 (TP135 FP40) | 0.796 (TP133 FP34) |
| FA: sensibilidade | 0.854 | 0.842 (-1.2 pt) |
| PACE (rotulo SCP, n=43): sensibilidade da regra nova | 0 | 0.605 (TP26 FP2) |
| FP de IAM (MI_any) em registros PACE | 32 | 9 |
| FP de ritmo sinusal em registros PACE | 20 | 5 |
| MI_any PPV | 0.548 | 0.611 |
| SR PPV | 0.896 | 0.919 |
| STE FP | 87 | 65 |

Metas: FP de IAM por PACE < 10: atingida (9). Perda de sensibilidade de FA <= 3 pt: atingida (1.2). PPV FA >= 80%: NAO atingida (0.796; falta 1 FP).

## Teste (PTB-XL folds 9-10, 1 execucao unica, tag C1test, n=1817)
FA PPV 0.760 / sens 0.814 (TP127 FP40 FN29); PACE PPV 0.946 / sens 0.614 (TP35 FP2 FN22). Baseline de teste nao rodado (evitar queimar o fold).

## O que foi feito
- pacing.py: espicula no sinal BRUTO (passa-alta 100 Hz, limiar max(10 sigma_MAD, 0.05 mV), >=8 derivacoes na mesma amostra +-3 ms, largura a meia altura <= 6 ms). Validacao temporal contra picos R (>=40% dos batimentos com espicula 0-300 ms antes, SD do atraso <= 20 ms, espiculas <= 1.5x batimentos). Via relaxada (5 sigma, 0.02 mV) so com QRS >= 120 ms e criterios mais estritos. Tipo: ventricular (atraso <= 150 ms + QRS >= 100 ms), atrial (atraso > 150 ms, QRS estreito), dual. Espiculas sao interpoladas (+-3 ms) antes do passa-baixa para nao criar falso inicio de QRS.
- rules.py: ctx["paced"] -> achado ecg.paced_rhythm "Ritmo de marca-passo <tipo> (sugestivo)"; remove sinusal/normal; em estimulacao ventricular remove ST/Q/T/BRE/BRD/IVCD/eixo/HVE/QT.
- ectopy.py: batimento ectopico = prematuro (RR < 0.8 mediana) com correlacao < 0.90 com o batimento mediano, ou prematuro com pausa compensatoria, ou prematuro isolado em base regular (CV < 0.08). Intervalos adjacentes sao excluidos do teste de irregularidade da FA.
- bench: classe PACE (predicado ecg.paced_rhythm, ouro SCP PACE).

## Tentativas descartadas (dev)
- Regra de intervalo de acoplamento fixo (bigeminismo/trigeminismo): PPV FA 0.808 mas sensibilidade 0.78-0.80 (perde 7 FA verdadeiras para remover 4 FP). Revertida.
- BASE_CV_MAX 0.12: sens 0.804 por ganho marginal. Mantido 0.08.

## Pendencias
- 17/43 PACE sem deteccao: ~10 sem espicula visivel a 500 Hz (amplitude < 0.05 mV), outros com espicula em < 40% dos batimentos ou atraso ~0 ms.
- FP de FA restantes: ~6 flutter (AFLT), ~10 bigeminismo/PAC com RR alternante, 4 registros PACE sem espicula.
- Commit 0de23b4 importa ectopy.py que so entra em 95999bb (commit intermediario nao importavel isoladamente).
