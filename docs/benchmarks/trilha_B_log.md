# Trilha B - E1 ECG-ST (baseline PR, ponto J por derivacao, limiar STE por sexo/idade)

Codigo: commits c5108c3 (codigo morto), cc15fb0 (baseline PR + J por derivacao), e833010 (limiar STE sexo/idade).
Antes (B0) = 2adf53a. Depois (B1) = e833010. Comandos (de backend/, PYTHONPATH=., MEDLENS_* exportados):

    python -m bench.ecg_bench --source ludb  --tag B0|B1 --workers 3
    python -m bench.ecg_bench --source ptbxl --split dev --tag B0|B1 --workers 3   # tabelas via report_ptbxl no cache da tag

## PTB-XL dev (folds 1-8, N=1183)

| Classe | B0 TP / FP | B0 sens / espec | B1 TP / FP | B1 sens / espec |
|---|---|---|---|---|
| STD (N pos 129) | 89 / 325 | 69% / 69% | 88 / 344 | 68% / 67% |
| STE (N pos 22) | 2 / 87 | 9% / 93% | 1 / 94 | 5% / 92% |
| MI_any (N pos 357) | 121 / 100 | 34% / 88% | 127 / 100 | 36% / 88% |

Metas (STD espec >= 88% com sens >= 55%; FP de STE < 60): NAO atingidas.

Diagnostico (dump por derivacao dos 1183 registros, analise offline):
- Varredura de limiar no ST (J60/J80, k derivacoes) so atinge espec 88% com sens ~10-15% (melhor: 15,5% em k=3, 0,105 mV).
  A discriminacao do ST contra o rotulo SCP e fraca; o gargalo e a medida/rotulos (espec e limite inferior: negativos incluem
  registros nao rotulados, FP gold: SR, ABQRS, AFIB, LVH, PACE), nao o limiar. Nao reduzi limiares UDMI para empurrar a metrica.
- J lido no offset global fica ~0,4-0,7 mm abaixo de J60 em V2/V4/V5 de ECG normais (offset do QRS precoce, vies -5,9 ms em LUDB).
  Deslocar a leitura +8 ms nao ajudou (STD 92/347, STE 0/106), descartado.
- Limiar por sexo/idade (mulher V2-V3 1,5 mm) aumenta FP de STE por construcao (era 2 mm para todos).

## LUDB (N=200, delineacao): inalterada (B1 == B0)
PR 66,5% (<=20 ms), QRS 46,5%, QT 66,5%, HR 94,5%; a mudanca toca so a leitura de ST.

## PTB-XL teste (folds 9-10) - 1 execucao, so B1 (nao usada para ajustar nada)
STD 83 TP / 349 FP (sens 63%, espec 79%); STE 0 TP / 121 FP (N pos 6); MI_any sens 33% espec 92%.

## Testes
backend/tests/test_ecg_st_baseline.py (sinais sinteticos: baseline PR vs rampa no onset, janela de menor variancia,
fallback TP, limiar por sexo/idade). Suite: so as 2 falhas pre-existentes de test_collector_litfl.py.
