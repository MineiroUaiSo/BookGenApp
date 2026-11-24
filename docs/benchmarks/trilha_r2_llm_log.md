# Trilha r2-llm (Ação 3: texto IA + PHI) — log

Worktree `/Users/macbook/medlens-wt/r2-llm` (branch `wt/r2-llm`). Ferramenta de apoio a laudo; não é dispositivo certificado.
Ambiente de todos os comandos (a partir de `<worktree>/backend`):

```
export MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<worktree>/data/bench PYTHONPATH=.
PY=/Users/macbook/medlens/backend/.venv/bin/python
```

## Commits

| tarefa | commit | assunto |
|---|---|---|
| T1 | 6c1dd66 | feat(llm): validador pos-LLM (numeros, criticos sem lastro, normal vs regra critica, confianca) |
| T2 | 1425d81 | feat(llm): retry exponencial e failover Anthropic -> OpenRouter com campo provider |
| T3 | 2777fe1 | feat(dicom): PHI em pixels - detecta/mascara texto queimado e bloqueia envio a IA externa |
| T4 | (ver git log) | bench(llm): conjunto fixo de avaliação do texto IA + llm_bench |

## T1 — validador pós-LLM (`app/llm/validate.py`, chamado em `_two_stage` após `to_report`)

- (a) números com unidade (ms, mm, mV/µV, bpm, %, ICT 0,xx) comparados a `ecg_data_summary`/`rx_data_summary`. Tolerâncias: ms ±10% ou ±10 ms; bpm ±5; ICT ±0,03; mm ±0,5; mV ±0,1 ou 10%; % ±5 pp. Divergente: frase/item marcado (`[⚠ valor X não confere com a medida Y]`) e acrescentado a `disagreements_with_measurements`. Limiares/faixas de referência ("normal", "acima de", "<") e constantes de grade (25 mm/s, 1 mm = 40 ms) não são tratados como afirmação. Sem medida correspondente => "não verificável" (fora do denominador).
- (b) lista fechada de críticos (IAM/supra de ST, BAV total, Mobitz II, TV/FV, FA de alta resposta, QT longo grave, pneumotórax, derrame volumoso, pneumoperitônio, edema agudo, cardiomegalia) citados sem regra/escore de apoio (regra disparada, escore do modelo >= 0,5, ICT >= 0,50, FC/QTc conforme o caso) => `(não corroborado)` + discordância. Menções negadas ("sem supra de ST") ignoradas.
- (c) IA diz "normal/sem alterações" com regra crítica disparada => ALERTA em discordâncias e limitações.
- (d) confiança autodeclarada nunca exibida: vira `confidence_display="não aplicável"` (ou a confiança da regra de mesmo `code`, `confidence_source="rules"`).
- Campos aditivos em `schemas.py`: `Finding/Differential.{confidence_source,confidence_display,validation_flags}`, `AIReport.{provider,external_ai_blocked,validation}`.
- Testes: `tests/test_llm_validate.py` (saídas de LLM fabricadas, sem rede).

## T2 — retry e failover (`app/llm/client.py::run_resilient`)

Máx. 2 tentativas por provedor, backoff 1–4 s com jitter, respeita `Retry-After` (> 30 s: pula direto ao failover), failover Anthropic → OpenRouter em 429/5xx/timeout/conexão, sem retry em 4xx != 429 (nem failover), recusa/truncamento propagam. SDK anthropic com `max_retries=0` (política é nossa). `AIReport.provider` registra quem respondeu (`anthropic+openrouter` se as etapas divergirem). Testes: `tests/test_llm_failover.py` (clientes stubados).

## T3 — PHI em pixels (`app/dicom/burned_text.py`)

- Detector sem OCR/modelo: top-hat morfológico (polaridades separadas), componentes tipo caractere nas bordas, agrupados em linhas regulares (altura/linha-base), máscara = mediana do anel; re-verificação com passe mais sensível. Executa no início de `analyze_image`, antes de polaridade/segmentação e do PNG enviado. Lê `BurnedInAnnotation` (0028,0301); `ingest` avisa quando é YES.
- Política: tag YES, ou texto detectado e não mascarado com segurança => `rx_report` NÃO chama o provedor (`AIReport.external_ai_blocked=True`, "imagem com texto queimado não enviada à IA externa"); regras e medidas locais seguem. Chave `MEDLENS_BURNED_TEXT=off` (só para bench A/B).
- Validação local (nada enviado) nos 10 DICOM de `~/Downloads/dicom-exemplos` (comando: script ad hoc com `load_dicom`+`render_to_uint8`+`scrub`): tag BurnedInAnnotation presente em **6/10** (todas "NO"), ausente em 4, **YES em 0/10**. Detector marcou **4/10** (abdome/1_TCGA-BLCA, torax/1,2,3_COVID-19-AR; todas sem tag), 6/10 sem detecção. PNGs mascarados em `data/bench/burned/*_masked.png` (fora do git); conferência visual: torax_2 — "Portable UPRIGHT" mascarado, marcador "R" preservado; torax_1 — "UPRIGHT" mascarado, mas "Portable"/"AP" permaneceram; torax_3 — bloco no canto superior direito mascarado, "L 48" permaneceu; abdome_1 — faixa no canto inferior direito mascarada é falso positivo (borda de colimação). Falso positivo anterior em torax_4 (clavícula) eliminado ao exigir linha regular.
- **Limitação honesta**: recall limitado (linhas com < 5 caracteres alinhados, texto fora das bordas ou de baixo contraste podem escapar; os exemplos acima mostram resíduos). A tag e o cabeçalho continuam sendo o sinal primário; esses 10 exemplos (TCIA) não têm identificadores queimados evidentes, só rótulos técnicos. Tempo do scrub: ~1–4 s por imagem.
- Bench `python -m bench.rx_bench --source dicom-exemplos --models both --out data/bench/t3_new` (scrub ligado) vs `MEDLENS_BURNED_TEXT=off ... t3_base`: incidência, região, segmentação e ICT **idênticos** nas 20 linhas (ICT modelo: 0,462 / 0,459 / 0,523 / 0,505 / 0,518; heurística: -, -, 0,637, 0,561, 0,645; abdome sem ICT).
- Testes: `tests/test_burned_text.py` (texto sintético nos cantos detectado/mascarado; sem texto intacto; política; `rx_report` bloqueado não chama provedor).

## T4 — conjunto fixo + `bench/llm_bench.py`

- Ids congelados (sem imagens) em `backend/bench/llm_eval_ids.json` (semente 20261124): 30 ECG PTB-XL folds 1-8 (normal 6, BAV 6, BRE 4, IAM 4, BRD 3, HVE 3, QT longo 3, **FA 1** — a amostra local do PTB-XL tem só 1 AFIB nos folds 1-8) + 30 RX (15 JSRT dev + 15 IU dev frontal: 7 normais / 8 com achado). Listas em ordem round-robin: qualquer prefixo é estratificado. Folds 9-10 e LUDB 161-200 nunca usados.
- Comandos: `python -m bench.llm_bench --freeze`; `python -m bench.llm_bench --run --n-ecg N --n-rx M --budget 0.30`; `--report-only`. Cache por hash do payload em `data/bench/llm/resp_*.json` (reexecução sem custo), laudos em `data/bench/llm/reports/`.
- **Custo medido (modelo de produção `anthropic/claude-sonnet-5.5` via OpenRouter, 2 etapas com imagem por laudo): ECG ≈ US$ 0,207; RX ≈ US$ 0,150 por laudo.** Para 60 laudos ≈ US$ 10,7, muito acima do orçamento de US$ 0,30. Com US$ 0,30 não cabem nem 10 ECG + 10 RX; rodados **N = 1 ECG + 1 RX** (os 2 medidos). Gasto real US$ 0,3565 (excedeu o teto de US$ 0,30 em US$ 0,0565: o 2º laudo só foi cortado após terminar; o guard foi corrigido para estimar o custo do próximo laudo antes de iniciá-lo). Saldo antes US$ 3,0111 → depois US$ 2,6546 (> US$ 2,00).
- Resultados (N=2, só ilustrativos; **não** permitem concluir sobre a meta): números que conferem 65/65 = 100% (ECG ptbxl-00001: 57/57; RX JPCLN022: 8/8); afirmações críticas sem lastro: 0; "normal" com regra crítica: 1 (JPCLN022: regras dispararam "Sugestivo de cardiomegalia" e "derrame" por escore do modelo 0,60/0,51, enquanto a IA descreveu ICT 0,42 e exame sem alterações, e já havia citado a divergência nas discordâncias; alerta tecnicamente correto).
- Para rodar os 60 laudos: ≈ US$ 11 com o modelo de produção; alternativa: `--model` mais barato (muda a fidelidade ao produto) — decisão do dono.
- Lista de 20 laudos para revisão médica: só 2 laudos existem em cache (ids `ptbxl-00001` e `JPCLN022`; caminhos em `data/bench/llm/reports/ptbxl-00001.json` e `.../JPCLN022.json`, fora do git). Os 18 restantes dependem de orçamento (a lista é gerada por `llm_bench` ao fim de cada execução: sinalizados primeiro, depois estratificados).

## Suíte completa

Comando: `python -m pytest -q -p no:cacheprovider tests` (a partir de backend/). Resumo da última linha: FAILED tests/test_rx_real_dicom.py::test_chest_segmented_with_ict[True-/Users/macbook/Downloads/dicom-exemplos/torax/2_COVID-19-AR/00000001.dcm]
Falhas na suíte completa: 2x `test_collector_litfl` (pré-existente: falta `tests/data/litfl_sample.html` neste worktree) e 2x `test_rx_real_dicom::test_chest_segmented_with_ict` (torax_1 e torax_2). Esses dois passam isolados (`pytest tests/test_rx_real_dicom.py`: 14 passed, reexecutado ao final); aparecem só na suíte completa em duas execuções, então parecem dependentes de ordem/carga, mas a causa não foi isolada. Honestamente: não confirmei que o scrub de texto queimado não contribui (o bench A/B de ICT/região foi idêntico).
