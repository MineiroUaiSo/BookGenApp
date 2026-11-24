# Trilha r2-calib (Ação 4: calibração RX)

Ferramenta de apoio; não é dispositivo certificado. **IU está no treino dos pesos 'all' do TorchXRayVision: todos os números de IU são otimistas.** Negativos do dev = só estudos `rx.normal` (prevalência da amostra inflada): a probabilidade calibrada vale para essa amostra, não para a prevalência de um serviço real. Cache IU: amostra aleatória de 800 estudos (seed 0, max-side 512), copiada do worktree E (`data/bench/rx/iu.jsonl`, ignorado pelo git). Cada estudo da amostra é de um paciente distinto (patients = n), então a CV "por paciente" coincide com CV por estudo aqui.

## Ambiente
```
cd <wt>/backend && export MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench MEDLENS_BENCH_DIR=<wt>/data/bench/rx PYTHONPATH=.
PY=/Users/macbook/medlens/backend/.venv/bin/python
```

## Commits
- aecb315 bench(rx): calibração isotônica por patologia no IU dev (CV por paciente, ECE/Brier com IC95%)
- 7f4d2d2 feat(rx): zona indeterminado + probabilidade calibrada na saída de RX
- (T3) bench(rx): avaliação externa de nódulo no JSRT (hash no relatório final)
- (este log) docs

## T1 — calibração isotônica (IU dev, CV 5 folds por paciente, semente 0)
```
$PY -m bench.calibrate_rx            # escreve bench/tuning/rx_calibration.json (só pontos da curva + limiares; sem ids)
```
PAV próprio em numpy (testado contra sklearn.IsotonicRegression, igual a 1e-9). ECE 10 bins equal-width; Brier; IC95% por bootstrap de pacientes (500). Predições fora da amostra (curva ajustada nos outros 4 folds). Meta ECE <= 0,05.

| patologia | n/pos | AUC [IC95%] | ECE antes | ECE depois | Brier antes | Brier depois |
|---|---|---|---|---|---|---|
| Atelectasis | 490/44 | 0,886 [0,838–0,926] | 0,121 [0,101–0,145] | **0,042** [0,029–0,069] | 0,086 [0,075–0,097] | 0,071 [0,055–0,089] |
| Consolidation | 466/20 | 0,856 | 0,157 [0,137–0,177] | **0,019** [0,009–0,038] | 0,074 [0,064–0,087] | 0,041 [0,026–0,057] |
| Pneumonia (rótulo consolidation) | 466/20 | 0,809 | 0,061 [0,049–0,086] | **0,008** [0,002–0,027] | 0,064 [0,049–0,080] | 0,040 [0,026–0,056] |
| Effusion | 459/13 | 0,945 | 0,077 [0,060–0,095] | **0,014** [0,009–0,031] | 0,038 [0,029–0,047] | 0,025 [0,015–0,037] |
| Cardiomegaly | 478/32 | 0,931 | 0,059 [0,044–0,080] | **0,022** [0,015–0,044] | 0,052 [0,042–0,064] | 0,045 [0,032–0,060] |

Estimativa pontual de ECE <= 0,05 em todas; para Atelectasis o limite superior do IC (0,069) passa de 0,05. Com poucos positivos (13–44) os ICs são largos; ECE com 10 bins é ruidoso nesse regime. AUC não muda (calibração monótona).
Sem curva: **Pneumothorax** (3 positivos < 10), **Edema** e **Nódulo** (IU não tem rótulo de edema/nódulo; nódulo foi avaliado externamente no JSRT, T3).

## T2 — zona 'indeterminado' (app/rx/calibration.py, findings.py)
Por patologia com curva: `raw_low` = maior escore com sens >= 95% nos positivos do dev; `raw_high` = limiar de espec 90% do dev (o mesmo de `rx_thresholds.json`); se `raw_low` > `raw_high`, `raw_low` = `raw_high` (sem faixa intermediária). Como a curva é monótona, cortar a probabilidade calibrada em p_low/p_high equivale a cortar o escore cru (a decisão usa o corte cru para evitar ambiguidade nos degraus). Faixas (escore cru L/U → p calibrada L/U): Atelectasis 0,153/0,510 → 0,024/0,200; Consolidation 0,153/0,510 → 0,049/0,164; Pneumonia 0,032/0,323 → 0,054/0,135; Effusion 0,108/0,301 → 0,000/0,071; Cardiomegaly 0,069/0,389 → 0,051/0,111.
- < L: 'não sugerido' (nenhum achado emitido, como antes); >= U: `rx.model.<patologia>` "Sugestivo de … (probabilidade calibrada ≈ x%)"; entre: `rx.model_indeterminate.<patologia>` "Indeterminado … o escore não permite sugerir nem afastar" (código distinto, para o bench não contar como positivo).
- `RXImageAnalysis.model_probs` / `model_zones` novos; `model_scores` (cru) mantido para o bench; o payload ao LLM usa a probabilidade calibrada quando existe.
- Pneumotórax: sem curva -> limiar cru 0,65 (legado) "sugestivo" + nota de evidência insuficiente; nunca "afastado".
- Fallback sem arquivo (`MEDLENS_RX_CALIBRATION` inexistente): comportamento anterior (testado).
- Testes: `backend/tests/test_rx_calibration.py` (13 testes: PAV vs sklearn, folds por paciente, ECE/Brier CV, curva monótona, zonas, pneumotórax, fallback, arquivo versionado válido).

## T3 — JSRT nódulo (externo, nada ajustado)
```
$PY -m bench.jsrt_nodule --workers 3 --cache <scratch>/jsrt_scores.json --out-json <scratch>/jsrt_result.json
```
Rótulos do manifest local (154 `rx.nodule`, 93 `rx.normal`). Escore Nodule do TorchXRayVision via pipeline do app (1 PA por estudo, max-side 1024). Se JSRT está nos dados de treino do TXRV não foi verificado.
| | n/pos | AUC [IC95% bootstrap] | sens/espec no limiar-padrão 0,65 | sens a 90% espec (descritivo; limiar 0,311 derivado dos negativos do próprio JSRT) |
|---|---|---|---|---|
| Nodule | 247/154 | 0,628 [0,555–0,699] | 0,000 [0,000–0,024] / 1,000 | 0,169 [0,118–0,236] (espec 0,903) |
Conclusão: sinal fraco para nódulo; o escore de nódulo não deve sustentar 'sugestivo' (o app segue sem curva/limiar ajustado para nódulo e, no limiar-padrão 0,65, não sinaliza nenhum dos 154 nódulos do JSRT). Max(Nodule, Mass) idêntico.

## T4 — ensemble por dataset do TXRV
**Não feito** (opcional; sem tempo).

## Suíte completa
- Subconjunto rx (test_rx, test_rx_calibration, test_rx_heur_ctr, test_rx_phantoms, test_rx_real_dicom): todos passam.
- Suíte inteira (`pytest -q -p no:cacheprovider`): 2 falhas de `test_collector_litfl` (FileNotFoundError, arquivo de fixture ausente; não relacionadas) e, **na execução completa**, 2 falhas de `test_rx_real_dicom::test_chest_segmented_with_ict[True-…COVID-19-AR]` (ICT ausente com modelo ligado). Esses 2 passam isolados e no subconjunto acima, com e sem calibração; a dependência de ordem/carga não foi bissectada nem comparada com o baseline completo (execução do baseline foi interrompida por tempo/máquina carregada).

## Pendências
- Teste externo de calibração e das zonas: VinDr-CXR/BRAX/VinBigData **pendentes de credencial** (não usados).
- Pneumotórax, edema: sem rótulo/positivos suficientes no IU; precisam de dataset externo.
- Rodada IU completa (2955 estudos) para estreitar ICs.
