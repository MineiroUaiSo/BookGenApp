# Plano Rodada 2 — MedLens

Só leitura: nada editado, executado, baixado ou instalado. Causas vêm da leitura do código, não de reprodução. Contagens de datasets são de memória: conferir antes de usar.

## Achado transversal
Parte das metas "não atingidas" é ruído estatístico, não só algoritmo.
- NORM tem N=51 no dev: 74,5% = 38/51 e 80% = 41/51, diferença de 3 registros.
- PPV de FA 0,796 fica a 1 FP da meta. BAV3 tem N=12.
- Folds 9-10 do PTB-XL estão queimados e o limiar de RX foi ajustado no IU, que está no treino do TorchXRayVision.
- Sem N maior, IC95% e teste externo intocado, a rodada 2 repete o ciclo.

## Top-10

| # | Ação | Meta | Esf. | Risco | Modelo |
|---|---|---|---|---|---|
| 1 | Higiene: 4 testes, R6, health real, regenerar `ecg.md`/`rx.md` | suíte 0 falhas; p95 heurístico < 1,5 s com Dice jsrt ≥ 0,63 | P | baixo | Sonnet (Haiku: fixture, docs) |
| 2 | Base de avaliação: N maior, IC95%, teste externo, subgrupos, PTB-XL+ | NORM N ≥ 400; toda meta com IC; 1 teste externo intocado | M | baixo | Opus desenha, Sonnet/Haiku executam |
| 3 | Texto IA: validador contra medidas, failover, texto queimado (PHI) | 0 afirmação crítica sem lastro em 60 laudos; ≥ 98% dos números conferem | M | alto (LGPD, alucinação) | Opus spec, Sonnet |
| 4 | R2 externo, calibração e zona de abstenção | AUC ≥ 0,85 e sens ≥ 0,70 a 90% espec. (derrame, cardiomegalia, pneumotórax); ECE ≤ 0,05 | M | médio | Sonnet |
| 5 | Gate de qualidade/fora de escopo, UX de confiança, monitoramento | 100% dos casos ruins/fora de escopo com aviso ou abstenção | M | médio | Sonnet |
| 6 | E5: onset global de P, série atrial multiderivação | BAV1 sens ≥ 55% com espec ≥ 95%; viés de PR ≤ 8 ms; BAV3 ≥ 40% com IC | G | alto (BAV3 crítico) | Opus planeja, Sonnet |
| 7 | E1: ST medido contra 12SL, morfologia, gate de ruído | MAE ST-J ≤ 30 µV; STD espec ≥ 85% com sens ≥ 55%; STE sens ≥ 50% em IAM agudo, FP < 40 | G | alto (STE crítico) | Opus planeja, Sonnet |
| 8 | E3 + E4: flutter/bigeminismo, NORM por idade/sexo | PPV FA ≥ 0,85 com sens ≥ 0,83; NORM ≥ 80% com IC inferior ≥ 76% | M | médio | Sonnet |
| 9 | E6 em sombra + R3 CXAS (venvs separados) | E6: IAM sens ≥ 60% a 90% espec. só no bench; R3: coração ≥ 0,80, coluna ≥ 0,75 | M-G | E6 alto se for à UI | Opus (E6), Sonnet (R3) |
| 10 | E7 homografia pela grade + bench de abdome | Pearson hard ≥ 0,7 e mediana ≥ 0,9; abdome: Dice coluna/pelve �� 0,7, região ≥ 98% | G | baixo | Sonnet (Opus: geometria) |

## Detalhe por ação

**1. Higiene**
- **2 falhas de ordem:** `backend/tests/test_integration.py:15` faz `os.environ.setdefault("MEDLENS_RX_MODELS","0")` no import e vaza para a sessão inteira.
  - `seg_model.psp_probs` (`backend/app/rx/seg_model.py:118`) relê o env e ignora `use_model=True` (`backend/app/rx/analyze.py:143,206`).
  - Cai na heurística, que retira o ICT em tórax/1 e 2, e o `assert ict` falha (`backend/tests/test_rx_real_dicom.py:52`).
  - Correção: trocar por fixture com `monkeypatch`, e fazer o `use_model` explícito prevalecer sobre o env. Isso é bug de produto, não só de teste.
- **2 falhas litfl:** `backend/tests/test_collector_litfl.py:5` aponta para `tests/data/litfl_sample.html`, que não existe; só os testes das linhas 10 e 25 usam o arquivo. Criar HTML sintético com a mesma estrutura, sem copiar a página (CC BY-NC-SA).
- **R6:** `find_lung_pair` (`backend/app/rx/seg_heuristic.py:100-110`) roda 3 raios × 3 limiares = 9 passadas de `bopen(disk(r))`, com raio até 2,5% do lado.
  - Quando falha, é chamada de novo em `seg_heuristic.py:177` e `:543`, além de `backend/app/rx/view.py:182`: até 27 passadas.
  - Correção: memoizar o resultado negativo por imagem, fazer a morfologia em 256 px, dar orçamento de tempo e parar em 3 tentativas.
- **Health:** `backend/app/api/health.py:15-19` usa só `find_spec`, então reporta "ok" mesmo com import quebrado (foi a causa do caso real). Carregar o modelo de verdade e mostrar banner na UI. Reiniciar o servidor da porta 8000 segue pendente do usuário.

**2. Base de avaliação**
- Ampliar o dev do PTB-XL (hoje 3000 registros; NORM ≥ 400) e pôr IC95% por bootstrap em toda tabela.
- Usar PTB-XL+ (medidas 12SL/ECGdeli) como verdade de medida para PR, QRS e ST-J.
- Teste externo tocado 1 vez: CODE-test (827, consenso de cardiologistas), CPSC2018, Georgia, Chapman/Ningbo.
- Dev grande para BAV1 e FA: CODE-15% (rótulos 1dAVb, AF).
- Subgrupos: sexo, idade, aparelho, flags de ruído do PTB-XL; no RX, AP contra PA.
- O gold atual conta código com probabilidade ≥ 50 ou 0 (`backend/bench/ecg_bench.py:353`); STD_/STE_ são anotados de forma inconsistente.

**3. Texto IA**
- `to_report` (`backend/app/llm/schema.py:66-100`) valida só as referências. Número citado, achado crítico inventado e a confiança autodeclarada (`:78`) passam direto.
- Correção: validador pós-LLM.
  - Extrair ms, mm, bpm e ICT do texto e comparar com `ecg_data_summary`/`rx_data_summary`.
  - Achado crítico sem regra ou escore de apoio vira "não corroborado" e entra em discordâncias.
  - LLM dizendo "normal" com regra crítica gera alerta.
- Failover: `provider()` (`backend/app/llm/client.py:57`) escolhe o provedor uma vez. Não há troca para o OpenRouter em 429/5xx do Anthropic, nem retry.
- PHI: `_anonymise` (`backend/app/dicom/ingest.py:67`) limpa só as tags; não há tratamento de `BurnedInAnnotation` em `app/`. O texto queimado vai para o provedor externo via `rx_image_png` (`backend/app/llm/__init__.py:181`).
  - Correção: mascarar o texto (top-hat + componentes pequenos nas bordas) antes da heurística e antes do envio; bloquear o envio se não mascarado.
- Avaliação: conjunto fixo de 30 ECG + 30 RX, checagem automática por regra e revisão do médico em 20.

**4. R2**
- Dev sem vazamento: VinBigData train (Kaggle) ou BRAX (brasileiro, PhysioNet credenciado). Teste: VinDr-CXR test, que depende da credencial PhysioNet.
- Grátis agora: nódulo no JSRT (154 casos), já no disco.
- Calibração isotônica por patologia (ECE atual 0,06-0,16) e zona "indeterminado" entre dois limiares.
- Pneumotórax tem 3 positivos no IU: sem dado externo, fica "sugestivo".
- Ensemble de pesos por dataset do TorchXRayVision (hoje só `densenet121-res224-all`, `backend/app/rx/seg_model.py:101`).

**5. Qualidade, UX, monitoramento**
- ECG: ruído alto por derivação hoje só gera aviso (`backend/app/ecg/analysis/__init__.py:163`). Passar a abster ST/Q nessa derivação.
- RX fora de escopo: erro de reconstrução do autoencoder do TorchXRayVision mais sanidade da área pulmonar; benchmark de região com o dataset UNIFESP de partes do corpo (Kaggle).
- UX:
  - A IA bloqueia a resposta (`backend/app/api/analysis.py:94-101,156-163`). Devolver regras primeiro e buscar a IA em chamada separada.
  - `ReportPanel.tsx:58` mostra a confiança fixa das regras como "%". Trocar pelo PPV medido no bench, por código.
  - "Baixa confiabilidade" aparece como parágrafo comum (`RXViewer.tsx:110-111`). Virar alerta.
  - Botão concordo/discordo por achado.
- Monitoramento: log JSONL local sem PHI (hash do commit, latência, flags, códigos, feedback) e conjunto de regressão no CI.

**6. E5**
- BAV1: o onset global de P é o mínimo entre derivações (`backend/app/ecg/analysis/delineate.py:515`), daí o viés de +30 ms. A regra compensa com AND triplo (`backend/app/ecg/analysis/rules.py:297`, `AV1_PEAK_MS` em `:158`).
  - Correção: usar o 2º onset mais precoce ou a mediana, como no E2; calibrar em LUDB dev e PTB-XL+; depois simplificar a regra.
- BAV3: a série de P usa uma derivação só (`analysis/__init__.py:216-225`) e detecção de picos; o resíduo dá 30-60 picos em 10 s. Os critérios estão em `backend/app/ecg/analysis/rhythm.py:203-207`.
  - Correção: resíduo atrial de D2 + V1 + aVF, frequência atrial por autocorrelação, dissociação por teste de fase P-R.
  - Regra extra: FA com RR regular e lento vira "BAV total sugestivo".

**7. E1**
- STE dispara com amplitude de J em uma derivação (`rules.py:493`). Não exige morfologia, recíproca nem razão ST/S; com HVE só anexa texto de cautela (`:510-511`).
- J é lido em janela de ±4 ms no offset da derivação (`backend/app/ecg/analysis/measure.py:96-104`); o offset precoce cai dentro do S ou R'.
- Correção:
  - Validar ST-J contra o 12SL antes de mexer em regra.
  - ST por batimento com consistência (MAD).
  - STE exige J e J60 elevados; rebaixar se QRS ≥ 120 ms ou HVE com ST/S < 25%; recíproca aumenta a confiança.
  - Gold de STE = IAM "Stadium I" (`infarction_stadium1` do PTB-XL), no lugar de STE_.

**8. E3 + E4**
- FA: os FP restantes são ~6 flutter, ~10 bigeminismo/PAC e 4 PACE sem espícula. O teste de FA vem antes do de flutter (`rules.py:182-186`).
  - Correção: testar flutter primeiro, detectar alternância de RR (autocorrelação lag-2) e usar V1 para atividade atrial.
- NORM: os bloqueios restantes são T invertida (`rules.py:558`), HVE por voltagem (`:431`) e QTc sem corte por sexo (`:481`).
  - Correção: Sokolow em menores de 40 anos e T invertida isolada em V1-V3 de mulher jovem viram limítrofe; QTc por sexo.

**9. E6 sombra + R3**
- E6: rodar o modelo de Ribeiro (CODE; 1dAVb, FA, BRD, BRE; sem vazamento com PTB-XL) só no bench, como segunda opinião offline. Nada na UI antes da decisão regulatória (RDC 657/2022).
- R3: CXAS em venv próprio, chamado por subprocesso com JSON. Conferir a licença dos pesos. Avaliar no PAX-Ray++ test e em 30-50 perfis anotados.

**10. E7 + abdome**
- E7: quando a folha preenche o quadro, sobra só rotação de até 6° (`backend/app/ecg/digitize/geometry.py:116,155`); a perspectiva não é corrigida.
  - Correção: homografia pelos pontos de fuga das linhas da grade, e abstenção ("só FC/ritmo") se o passo da grade ficar irregular.
  - Dados: ECG-Image-Kit e ECG-Image-Database (fotos reais).
- Abdome: DRR AP a partir das TC do TotalSegmentator (Zenodo), exige `nibabel`. Refazer o fluxo nos 10 DICOM agora que há decoder. Incidência KUB sem tag sai OTHER. Nenhum achado emitido até haver rótulo de radiologista.

## Dependências e paralelismo
- **Primeiro:** 1.
- **Em paralelo depois de 1:** 2, 3, 4 (preparo), 5, 9-R3 e 10. Mexem em arquivos disjuntos.
- **6, 7 e 8 dependem de 2.** 6 e 7 podem ir em worktrees paralelos (P/AV contra ST); 8 entra depois, porque todos tocam `rules.py`. Mesclar em sequência e rodar o dev a cada merge.
- **Dentro de 9:** E6 em sombra depende de 2; R3 não depende de nada além da instalação.
- **Teste externo:** 1 execução, só no fim.

## Decisões suas
- Autorizar downloads e instalações: PTB-XL completo, PTB-XL+, CODE, CPSC, pesos do CXAS, `nibabel`.
- Credencial PhysioNet (VinDr, BRAX) ou conta Kaggle (VinBigData).
- STD de 0,5-1 mm como limítrofe? Manter o limiar UDMI-4 de mulher em V2-V3?
- E6 na UI: só depois de decisão regulatória.
- Anotar 100-150 RX de abdome e 30-50 perfis.
- Reiniciar o servidor da porta 8000.

Arquivos de referência: `/Users/macbook/medlens/RETOMADA.md` e `/Users/macbook/medlens/docs/benchmarks/trilha_*_log.md`.