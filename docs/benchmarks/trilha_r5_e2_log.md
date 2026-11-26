# Trilha R5 / lote E2: guarda contra dupla contagem de QRS (onda T contada como R)

Base: 9a9ea2c. Arquivos: `backend/app/ecg/analysis/rpeaks.py` (guarda `_t_wave_guard`, novo
`detect_r_peaks_ex`), `backend/tests/test_ecg_rpeaks_t_alta.py` (novo). `rhythm.py` e `rules.py` nao foram editados.
O CODE-test nao foi usado para nada (nem leitura de resultado, nem ajuste). Os 5 FP de FA com FC 152-222 do CODE
(ANALISE-FABLE 2.2) sao so motivacao pos-hoc.

## O que mudou

Na deteccao de R (`rpeaks.py`), depois dos candidatos por energia de inclinacao:

- So age se a FC detectada > 150 bpm e houver >= 6 candidatos.
- Prova de R-T: os candidatos alternam forca (mediana da energia do par forte/fraco), o forte vence o vizinho fraco
  em >= 80% dos pares e o intervalo R->pico fraco e estavel (CV <= 10%) e cai em 0,12-0,50 s.
- Separa (remove o pico fraco, periodo refratario = 0,6 x espacamento dos fortes) so se os picos NAO forem simetricos
  (|offset/espacamento - 0,5| >= 0,05, a taquicardia real/alternancia eletrica fica em 0,5) e a razao fraco/forte
  <= 0,85 (ou <= 0,97 com assimetria >= 0,10).
- Ambiguo (simetrico com alternancia, ou ainda > 150 bpm depois de remover a T): picos mantidos e
  `unreliable=True` em `detect_r_peaks_ex(amp, fs) -> (peaks, ref, unreliable)`. `detect_r_peaks` mantem a assinatura
  `(peaks, ref)`.
- PENDENTE POS-MERGE (fora da lista do lote): `analysis/__init__.py` ainda chama `detect_r_peaks` e descarta o sinal.
  Ligar `unreliable` nas features e a mensagem "ritmo nao classificado" em `rules.py` fica para depois do merge com E1.

## Testes (TDD, RED antes)

RED confirmado antes do codigo: sinal sintetico 75 bpm com onda T em pico estreito 0,8 x R, 0,30 s depois do R,
dava FC 151,7 bpm e `ecg.irregular_rhythm`; 110 bpm dava 220 bpm.

| Teste | Resultado |
|---|---|
| T = 0,5 e 0,8 x R a 75 bpm: FC 75 +- 3, sem `ecg.atrial_fibrillation`, sem `irregular_rhythm` | verde (antes 151,7 bpm) |
| mesmo com jitter de RR 8% | verde |
| T a 110 bpm (T em 0,25 s): FC 110 +- 4 (antes 220,5) | verde |
| taquicardia sintetica real 160 e 180 bpm: FC +- 5 | verde (sem mudanca) |
| taquicardia 160 bpm com alternancia eletrica 100%/85% | verde (a primeira versao da guarda dividia a FC; a regra de simetria corrigiu) |
| guarda: ambiguo marca `unreliable`; taquicardia real e FC normal nao marcam | verde |
| metamorfico PTB-XL (abaixo) | verde |

Suite backend: `1252 passed, 12 skipped, 1 xfailed` (o metamorfico e pulado sem `MEDLENS_DATASETS`; rodou com ele).

## Metamorfico (200 NORM do dev, folds 1-8; sorteio seed 0 entre os NORM >= 80 da lista large do dev)

Onda T x2 na janela R+80 ms a R+min(450 ms, 0,7 RR), com borda Hanning (sem degrau), as 12 derivacoes; FC pela mediana
dos RR dos picos. Criterio: |FC depois - FC antes| <= 5 bpm.

| Variante | FC inalterada | IC95% (Wilson) |
|---|---|---|
| com a guarda | **197/200 = 98,5%** | [95,7-99,5] |
| sem a guarda (referencia, mesmo script) | 195/200 = 97,5% | [94,3-98,9] |

A guarda corrige 2 registros (ptbxl-13645: 65 -> 221 bpm antes; ptbxl-01891: 62 -> 222 antes). Falhas que sobram
(ptbxl-07583 58 -> 81, ptbxl-05482 65 -> 134, ptbxl-05271 48 -> 66) sao FC < 150 depois do T x2: fora do gatilho da
guarda (FC > 150), seguem como estavam. Com T x3 (nao exigido) cai para 158/200 (79,0% [72,8-84,1]) e a guarda nao
muda nada: T acima de R ou a meio ciclo nao e separavel por forca/simetria.

## Bench dev (PTB-XL dev ampliado, N=9183, `--source ptbxl --split dev --set large --tag R5E2 --workers 3`)

Antes = cache `ptbxl.jsonl` (mesmo conjunto, mesma base de AF/STACH). Sem outro bench em paralelo. IC95% bootstrap
(`bench.report.bootstrap_binary_ci`).

| Classe | Aceite | Antes | Depois |
|---|---|---|---|
| FA sensibilidade | >= 83% | 83,7% [81,4-86,0] (TP 849/1014) | 83,7% [81,4-86,0] (TP 849) |
| FA especificidade | >= 98,0% | 98,1% [97,8-98,4] (FP 153) | 98,1% [97,8-98,4] (FP 153) |
| STACH sensibilidade | queda <= 1 pp | 88,2% [85,7-90,7] | 88,2% [85,7-90,7] |
| STACH especificidade | | 98,8% [98,6-99,1] | 98,8% [98,6-99,1] |

Aceite: **APROVADO**. O resultado e identico registro a registro: 0 dos 9183 registros mudaram de FC (> 1 bpm) ou de
achado (58 registros com FC > 150 antes e depois). Era esperado: o plano ja dizia que o PTB-XL dev quase nao tem este
modo de falha (so 1 dos 153 FP de FA com FC > 150, ptbxl-19046, 155 bpm, segue igual). O ganho esperado (FP de FA com
FC alta, visto no CODE) so pode ser medido apos o merge, em bench unico do codigo mesclado; esta guarda e
validada aqui por teste sintetico e metamorfico, e a ausencia de regressao no dev.

## 3 linhas para o medico revisar a mudanca de saida

1. Quando o ECG tem onda T alta (picos R-T alternando forca, a mais de 150 bpm detectados), o aparelho deixa de contar
   a T como batimento: a FC volta ao valor real (ex.: 75 bpm em vez de 152) e o ritmo deixa de ser chamado de
   irregular/FA por esse motivo.
2. Taquicardia verdadeira (160-180 bpm, picos simetricos, inclusive com alternancia eletrica) continua como esta;
   se houver duvida, o sinal interno `unreliable` fica ligado (ainda sem texto na tela: depende do merge com E1).
3. No dev PTB-XL (9183 ECG) nenhum laudo mudou; o efeito so aparece em traçados com T alta + FC aparente > 150.
