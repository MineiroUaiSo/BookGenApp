# Trilha D - E2 delineacao do QRS + E4 largura do QRS/NORM

Base: wt/B + merge de wt/C. Commits: 6844dfe (E2), 141f346 (bench --source qtdb), 43e5790 + e33bde8 (E4). Comandos (de backend/, PYTHONPATH=., MEDLENS_* exportados):

    python -m bench.ecg_bench --source ludb --tag D0|D1 --workers 3            # D0 = codigo antes, D1 = depois
    python -m bench.ecg_bench --source ludb --tag D1 --records 1-160 --force   # dev
    python -m bench.ecg_bench --source qtdb --tag D0|D1 --workers 3
    python -m bench.ecg_bench --source ptbxl --split dev --tag D0|D1h --workers 3   # tabelas via report_ptbxl no cache

## E2 - LUDB (limiares ajustados so em 1-160)
| Metrica | D0 dev | D1 dev | meta | D1 teste 161-200 | D1 todos (200) |
|---|---|---|---|---|---|
| QRS onset (CSE 6,5 ms) | 39,8% | 55,6% | >=55 | 65,5% | 57,6% |
| QRS offset (CSE 11,6 ms) | 58,7% | 70,9% | >=70 | 69,6% | 70,7% |
| QRS global (+-20 ms) | 52,5% | 74,4% | >=65 | 95,0% | 78,5% |
| QT global (+-30 ms) | 68,1% | 78,8% | >=78 | 77,5% | 78,5% |
| PR global (+-20 ms) | 61,1% | 66,4% | - | 84,6% | 70,6% |
Baseline LUDB (200): QRS onset 39,2 / offset 59,2 / QRS 46,5 / QT 66,5 / PR 66,5.
Metodo: velocidade do sinal suavizado 20 ms; limiar 3% (onset) / 6% (offset) do pico por derivacao, janela estendida
+20/+14 ms alem da borda global preliminar, borda da derivacao limitada a +-5 ms da mediana das derivacoes; QRS global =
2o onset mais precoce / 2o offset mais tardio (limiar 3%); fim do T global +10 ms. Rhythm usa bordas preliminares (pre_on/pre_off).
Testes sinteticos (tolerancias PR/QRS/QT alargadas de 20 para 30/30/35 ms: o onset global agora e o da derivacao mais precoce).

## QTDB (teste externo, 46 registros com q1c, derivacao V5; so reportado)
| | D0 | D1 |
|---|---|---|
| QRS onset dentro da tol. CSE | 28,2% (+11,2 ms) | 39,3% (+4,9 ms) |
| QRS offset | 49,8% (-5,0 ms) | 45,0% (-1,7 ms) |
| T offset | 47,7% | 47,7% |

## ST apos E2 (PTB-XL dev; B1: STD TP/FP 88/344, STE 1/94)
D1h: STD 88/322 (sens 68%, espec 69%), STE 0/73. Melhora so marginal em FP; o gargalo do ST nao era so o offset.

## E4 - PTB-XL dev (folds 1-8)
| | D0 | D1h |
|---|---|---|
| gold NORM -> dizemos normal (n=51) | 68,6% | 74,5% (meta 80%: NAO atingida) |
| non-NORM com >=1 achado anormal | 88,7% | 86,9% (perda 1,8 pt, <=15) |
| CRBBB sens / LBBB_any sens-espec | 67% / 57%-96% | 56% / 75%-94% |
| LQT sens/espec | 66/87 | 62/88 |
Largura para BBB/IVCD = mediana das derivacoes + 0,25*(global - mediana); IVCD abnormal so >=120 ms, 110-119 vira ecg.qrs_borderline
(borderline, nao bloqueia within_normal_limits). Mediana pura derrubou CRBBB (67->49%); media 0,5 gerou FP de LBBB (77->131).
Os bloqueadores restantes dos NORM nao sao de largura (irregular_rhythm borderline, T invertida, LVH, QT). Correcao JT e QTc usam a
mediana de QRS por derivacao e subtraem 10 ms (compensa onset mais precoce).

## PTB-XL teste (folds 9-10) - 1 execucao, na versao E4 intermediaria (commit 43e5790, ANTES do ajuste e33bde8); nao usada para ajustar
STD 80 TP / 310 FP (sens 61%, espec 82%); STE 0/106 (N pos 6); MI_any sens 32% espec 95%; NORM->normal 67,0% (n=464); non-NORM com anormal 82,2%.
Nao reexecutado na versao final (regra de 1 execucao).

## Testes
tests/test_ecg_qrs_borders.py (E2, sinteticos: onset lento/delta, lead dentro do global), tests/test_ecg_qrs_width.py (E4).
Suite: so as 2 falhas pre-existentes de test_collector_litfl.py.

## Pendencias
- NORM >=80% nao atingido; precisa atacar irregular_rhythm borderline, T invertida anterior, LVH (fora do escopo de largura).
- STE continua 0 TP no dev; ST precisa de outra abordagem (rotulos/medida).
- Pesos E2/E4 ajustados em LUDB dev/PTB-XL dev; teste PTB-XL nao refeito na versao final.
