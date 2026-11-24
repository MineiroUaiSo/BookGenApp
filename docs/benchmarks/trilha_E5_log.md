# Trilha E5 - onda P, BAV1, BAV2/3, taquicardia sinusal

Codigo: 379c2c7 (P no ponto do batimento mediano + serie atrial sem QRS-T), 581104e (taquicardia sinusal provavel, BAV3 sugestivo), 77f5cb4 (testes), dc18908 (alt so p/ dissociacao).
Antes (E5a) = 5443a92. Depois (E5b..E5e) = codigo final. Comandos (de backend/, PYTHONPATH=., MEDLENS_* exportados):

    python -m bench.ecg_bench --source ludb --tag E5a|E5b --workers 3
    python -m bench.ecg_bench --source ptbxl --split dev --tag E5a|E5e --workers 3   # tabelas por classe lidas do cache da tag

## LUDB dev (registros 1-160), sensibilidade de P por derivacao-batimento
Antes 81.7% (10520/12873) -> depois 90.3% (11630/12873); PPV 76.1% -> 76.1%. V2 59%->85%, V3 71%->85%.
Causa: P pequeno (precordiais) abaixo do limiar de proeminencia; agora aceito com limiar menor so a +-50 ms da posicao da P do batimento mediano.

## PTB-XL dev (folds 1-8, N=1183)
| Classe | antes TP/FN/FP | antes sens / espec | depois TP/FN/FP | depois sens / espec | meta |
|---|---|---|---|---|---|
| STACH | 65/31/30 | 67.7% / 97.2% | 85/11/47 | 88.5% / 95.7% | >=85% ATINGIDA |
| AV1 (BAV1) | 23/52/33 | 30.7% / 97.0% | 23/52/33 | 30.7% / 97.0% | >=55% NAO atingida |
| AV2 | 0/12/3 | 0% | 0/12/3 | 0% | - |
| AV3 | 0/12/0 | 0% | 0/12/1 | 0% / 99.9% | >40% NAO atingida |
| SR (sinusal) | 547/139/48 | espec 90.3% | 547/139/47 | espec 90.5% | sem piora: OK |
| NORM | 35/16/128 | espec 88.7% | 35/16/126 | espec 88.9% | sem piora: OK |
| AF | 133/25/34 | 84.2% / 96.7% | igual | igual | sem mudanca |

## PTB-XL teste (folds 9-10, 1 execucao, tag E5test, N=1817; codigo de 77f5cb4, antes do fix de dc18908 que so afeta AV)
STACH sens 86.2% (TP75 FN12 FP46) espec 97.3%; AV1 sens 34.1% (TP46 FP47); AV2 0/2; AV3 0/4; SR espec 81.0%; NORM espec 82.9%; AF sens 81.4% / PPV 76.0%. Nao usado para ajustar nada.

## O que foi feito
- delineate.py: detect_p(prom=, near=) + delineate_beat(p_prior=): P fraco so na janela do batimento mediano.
- analysis/__init__.py: batimento mediano calculado antes do loop por batimento (fornece p_prior); ctx['pr_beats'].
- rhythm.py: atrial_residual (subtrai molde mediano QRS-T escalado por minimos quadrados), detect_p_series_resid, av_analysis(p_alt=) (reaproveita a serie residual so para dissociacao AV3).
- rules.py: FC>100 regular (CV<0.10) sem FA/flutter com P ectopica/sem P -> 'Taquicardia sinusal (provavel; onda P fundida a T)'; sinusal irregular >100 bpm com P ligada ao QRS (p_frac>=0.4, DP PR<=30 ms) tambem emite taquicardia sinusal; BAV3 rotulado '(sugestivo)'.
- tests/test_ecg_p_wave_av.py: sinteticos (P dentro da T a FC 130; BAV2 2:1; dissociacao AV; PR 1:1 normal).

## Limitacoes / pendencias
- BAV1: medida de PR enviesada +~30 ms (NORM com PR>200 em 25%); varredura offline (PR por batimento, PR por derivacao, pico-P->QRS, p_frac, DP) nao passou da fronteira atual (23 TP/33 FP); 55% de sens custa >100 FP. Regra mantida. Precisa de melhor onset de P/QRS (trilha D) antes de reavaliar.
- BAV2/BAV3: N=12 cada na dev (2 e 4 no teste); nao ajustei limiar. Serie residual de D2 tem picos demais (30-60 por 10 s) em 3AVB; precisa de deteccao multi-derivacao antes de render TP.
- STACH: 17 dos 31 FN iniciais eram 'sinusal irregular' com ectopia; flutter espectral falso (FC 105-147) permanece (nao mexi para nao perder AFLT).
- Suite completa: unica falha extra era test_conduction (falso Mobitz II) corrigida em dc18908; sobram so as 2 pre-existentes de test_collector_litfl.py (ignorado na rodada).
