# Plano de melhorias MedLens — 2026-11-25 (v2, reconciliado com a análise Fable)

Papéis: Fable analisou (`docs/ANALISE-FABLE-2026-11-25.md`), Opus orquestra (este plano), Sonnet executa (um agente por lote).
Base: branch `claude/ecg-rx-ai-reader-nd20rs`, HEAD `5b9b1c1` (já no origin). Nada foi implementado ao escrever este plano.

Regras fixas:
- Modelos de IA só em nuvem.
- Sem PHI nem imagem real em commit (`data/` já está no `.gitignore`).
- Decisão clínica é do médico.
- QRS largo sem BRE continua "limítrofe" (decisão do dono).
- O CODE-test NÃO é reexecutado. O marcador `data/bench/ecg/code_test.RUN` não é tocado. Nenhum limiar é ajustado olhando o CODE-test. Re-tabular o cache `code_test.jsonl` só para descrever, sempre rotulado "pós-hoc".
- Item crítico sem decisão do dono: opção conservadora. A barreira falha fechada: remove ou rotula a frase sem lastro e nunca afirma "normal".

## 1. Prioridades e itens

| Prioridade | Lote | Item | Tam. | Evidência principal (análise Fable) |
|---|---|---|---|---|
| 1 CRÍTICO | C1 | Barreira qualitativa no texto de IA do ECG (v1 e laudo v1): remover frase sem lastro | M | R1; sonda A.1: 9/9 frases sem lastro passam, 0 discordâncias; `llm/validate.py:347,419-425`; checagem semântica só no v2 (`validate.py:549`) |
| 2 CRÍTICO | C2 | Barreira `claim_check` do RX: termo clínico desconhecido remove a frase; fechar o atalho `_ABST`; ICT heurístico/AP não vale como lastro; as duas barreiras falham fechadas | M | R2; sonda A.2: 23/30 sem lastro passam; `rx/claim_check.py:45-93,104-107,130-174,188,193-216`; `llm/__init__.py:153-156,335-338` |
| 3 ALTO | E1 | Regra de SVD vira detector de BRD: SVD não dispara com QRS ≥ 120 ms (salvo eixo > 110°); R dominante em V1 + QRS ≥ 120 ms vira BRD ("provável" sem S lateral). Depois: achado `borderline` quando o PR passa de 200 ms sem critério completo de BAV1 | P+P | 2.1: `ecg.rvh` 247 disparos, 171 BRD completo no gold, VPP 17,8%; 119 dos 182 BRD perdidos saem como SVD (`ecg.md:265`); `rules.py:137-153,507`. 2.3: 155 de 370 FN de BAV1 têm PR global > 200; 414 laudos "sem regra" mostram PR > 200 |
| 4 ALTO | E2 | FA: guarda contra dupla contagem de QRS (onda T contada como R) | M | 2.2: 5 dos 10 FP de FA no CODE com FC de 152 a 222 bpm (pós-hoc). O PTB-XL dev não tem esse modo de falha (1 de 153 FP com FC > 150), então medir por teste sintético e metamórfico |
| 4 ALTO | E3 | CODE-test sob suspeita de amplitude: apurar a unidade no harness + teste de invariância no PTB-XL dev + errata em `code_test.md` | P/M | R4: HVE em 64,8% e SAD em 30,1% no CODE, contra 3,2% e 0,9% no PTB-XL NORM; `bench/code_test.py:39` `UNIT_TO_MV = 1.0` contra o README ("1e-4 V") |
| 5 ALTO | U1 | `ReportPanel`: motivo real de IA indisponível; trocar "Nenhuma discordância identificada"; diferenciais com "0%"; VPP sem a prevalência; achados de modelo fora da lista principal; alvo de toque 44 px | P/M | U1, U3, U7, R5, R10; `ReportPanel.tsx:69-71,~190`; `global.css:47,71` |
| 5 ALTO | U2 | `StudyView` e laudo RX: erro de reanálise visível; botão 3D usa a análise reanalisada; `AbortController` no `/ai`; `ErrorBoundary`; voto persistido (local + endpoint existente); copiar `laudo_rx_markdown` com comentários; causa do erro de console (favicon?) | M | U2, U4, U6, U9, 3.2, 3.3; `StudyView.tsx:24-33,42,73-80`; `client.ts:93,103`; `LaudoEstruturado.tsx:26-44` |
| 5 MÉDIO | U3 | Anti-colisão de rótulos do overlay RX (ICT x cúpulas em 390 px) | P | 3.1; `labelLayout.ts:37-54`; `ViewerPane.tsx:200-204` |
| 5 ALTO | R1 | RX `findings.py`: ICT heurístico não gera achado normal nem anormal; rótulo D2 ("sugere aumento da silhueta cardíaca"); faixa cinzenta só se D-C for aprovada | P | R7; `rx/findings.py:86-102`; `rx.md:104-109` |
| antes de uso real | P1 | PHI: autenticação por token, exclusão de estudo, retenção com prazo, teto em `_LAST` | M | R8; `main.py:9-18`; `store.py` sem exclusão; `api/analysis.py:70` |

Fora deste plano (análise Fable §5 e plano v1): Sgarbossa/Smith; corrigir o viés de +25 ms do QRS global; trocar o mapeamento do CODE para "só BRD completo" (pós-hoc: sens 32,4%); BAV2/BAV3; calibração IU de 16 h; IA no laudo RX; 60 laudos; CXAS/DRR/3D; segmentação heurística; nódulo; Safari/Firefox. Adiados do plano v1: CI e backoff do 429 + fumaça do laudo RX (retomar depois de C1 e C2).

### Critérios de aceite por lote (resumo; o detalhe está no prompt)
- **C1:** as 9 frases da sonda A.1 (Apêndice A da análise Fable) entram num teste. Resultado: 0 sobrevivem no v1 e no laudo v1, e um aviso de remoção fica visível no relatório. "FC 72 bpm" e "Ritmo sinusal" (com regra) continuam. Com `ecg.st_not_assessable`, qualquer frase de normalidade ou de negação de isquemia é removida. `test_llm_validate.py` e `test_llm_claim_semantics.py` ficam verdes.
- **C2:** as 30 frases sem lastro de A.2 entram em `test_rx_validator_qualitative.py`, com 0 passando. "Área cardíaca normal." com ICT de modelo em PA continua passando. "Cardiomegalia importante." com ICT heurístico 0,62 é removida. As 31 legítimas de `test_rx_laudo_validate.py` continuam passando. Uma exceção simulada em `validate_report` ou em `sanitize_report` devolve relatório sem narrativa, com limitação "barreira falhou: narrativa descartada", e nunca o texto cru.
- **E1:** PTB-XL dev large com tag. Metas: RBBB_complete sens ≥ 75% com VPP ≥ 65% (hoje 58,0/69,3); RVH VPP ≥ 40% (hoje 17,8%); NORM→normal ≥ 74,1% (hoje 74,6%); LBBB_complete inalterado; STE_acute FP ≤ 310. Passo PR: 0 registros com PR exibido > 200 ms sem achado de PR, e NORM→normal inalterado (um achado `borderline` não tira o registro do neutro).
- **E2:** teste sintético com T = 0,8·R a 75 bpm deve dar FC 75 ± 3 e nenhum `ecg.atrial_fibrillation`. Teste metamórfico em 200 registros NORM do PTB-XL dev com a onda T multiplicada por 2: FC inalterada (± 5 bpm) em ≥ 98%. Bench dev: FA sens ≥ 83% e espec ≥ 98,0%.
- **E3:** relatório com a unidade do CODE determinada por documento + estatística bruta (sem rótulos, sem regras), comparada com a mesma estatística no PTB-XL NORM. Teste de invariância em 1000 registros do dev (400 Hz, deriva de linha de base, escala 0,5 e 2): concordância de códigos ≥ 95% nas duas primeiras transformações, ou a lista do que quebra. `code_test.md` recebe a errata, e o marcador `.RUN` fica intacto (mesmo mtime).
- **U1, U2 e U3:** Vitest dos estados de erro. Playwright em 320/768/1024/1440, claro e escuro: sem overflow horizontal, botões ≥ 44 px, console sem erro (mensagem registrada), sem sobreposição de rótulos em 320/390.
- **R1:** ICT heurístico não gera achado `rx.cardiothoracic_ratio*`. Nenhum rótulo contém "Cardiomegalia (". Com D-C aprovada: ICT 0,49 (modelo) vira limítrofe.
- **P1:** `GET /api/studies` sem token responde 401 quando `MEDLENS_API_TOKEN` está definido. Sem token configurado, só aceita cliente de loopback. `DELETE /api/studies/{id}` remove arquivos e artefatos. Estudos expiram em N horas (variável de ambiente). `_LAST` tem teto (LRU).

## 2. Lotes, arquivos exclusivos e ordem de mesclagem

Todos partem de `5b9b1c1` (ou HEAD posterior já mesclado) com `git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-<lote> -b wt/r5-<lote> <base>`.

| Lote | Arquivos que só ele edita |
|---|---|
| C1 | `backend/app/llm/validate.py`, `backend/app/llm/laudo.py`, `backend/app/llm/ecg_claim_check.py` (novo), `backend/tests/test_ecg_ia_barreira.py` (novo) |
| C2 | `backend/app/rx/claim_check.py`, `backend/app/llm/__init__.py`, `backend/tests/test_rx_validator_qualitative.py`, `backend/tests/test_llm_fail_closed.py` (novo) |
| E1 | `backend/app/ecg/analysis/rules.py`, `backend/tests/test_ecg_svd_brd.py` (novo), `backend/tests/test_ecg_pr_borderline.py` (novo), `docs/benchmarks/trilha_r5_e1_log.md` (novo) |
| E2 | `backend/app/ecg/analysis/rpeaks.py`, `backend/app/ecg/analysis/rhythm.py`, `backend/tests/test_ecg_rpeaks_t_alta.py` (novo), `docs/benchmarks/trilha_r5_e2_log.md` (novo) |
| E3 | `backend/bench/ecg_invariance.py` (novo), `backend/tests/test_ecg_invariance.py` (novo), `docs/benchmarks/code_test.md`, `docs/benchmarks/ecg_invariance.md` (novo) |
| U1 | `frontend/src/features/report/ReportPanel.tsx`, `frontend/src/styles/global.css` (ou onde estiver o `global.css`), `frontend/src/test/report.test.tsx`, `frontend/src/test/reliability.test.tsx` |
| U2 | `frontend/src/features/StudyView.tsx`, `frontend/src/api/client.ts`, `frontend/src/features/rx/LaudoEstruturado.tsx`, `frontend/src/components/ErrorBoundary.tsx` (novo), `frontend/index.html`, `frontend/src/test/laudoestruturado.test.tsx`, `frontend/src/test/client.test.ts`, `frontend/src/test/studyview.test.tsx` (novo) |
| U3 | `frontend/src/features/rx/labelLayout.ts`, `frontend/src/features/rx/ViewerPane.tsx`, `frontend/src/test/labelLayout.test.ts` |
| R1 | `backend/app/rx/findings.py`, `backend/tests/test_rx_findings_ict.py` (novo) |
| P1 | `backend/app/main.py`, `backend/app/store.py`, `backend/app/api/analysis.py`, `backend/app/api/studies.py`, `backend/tests/test_phi_auth_retencao.py` (novo) |

Notas de conflito:
- C1 e C2 são os dois lotes de `llm/`. C1 não edita `llm/__init__.py`. Se precisar de gancho ali, para e relata.
- `claim_semantics.py` só pode ser importado, nunca editado.
- `rule_ppv.json` não é editado. U1 só muda a forma de exibir o VPP.
- Testes que já existem e que o lote precisa mudar devem estar na lista do lote. Os outros não são editados.
- C2 e R1 tocam a origem do ICT. Cada um lê o campo que já existe na ficha/medida (`rx/ficha.py:135` já trata o heurístico como `NAO_AVALIADO`). Nenhum dos dois edita `ficha.py`.
- E1, E2 e E3 rodam bench pesado: não rodar os três ao mesmo tempo (`--workers 3` cada, ou em fila). Cada um usa `--tag` próprio. Nenhum regenera `docs/benchmarks/ecg.md`.
- O worktree `.claude/worktrees/agent-a6ff241e…` tem alterações não commitadas de outra sessão em `rules.py`/`delineate.py`. Ninguém toca nele.

Ordem de mesclagem: **C2, C1** (críticos; C2 primeiro porque também fecha a falha aberta do ECG em `__init__.py:153-156`), depois **R1, U3, U1, U2, E3, P1**, e por último **E1 e E2** (mudam a saída clínica). Depois de E1+E2, o orquestrador roda um bench único do código mesclado.

## 3. Prompts prontos (um por agente Sonnet)

Estas regras valem para todos os lotes e estão repetidas em cada prompt:
1. TDD: mostrar o teste vermelho e depois o verde.
2. Worktree próprio.
3. Editar só os arquivos listados no lote.
4. Sem push, sem main, sem deploy.
5. Sem PHI nem imagem real.
6. `git add <arquivo>` só dos seus arquivos (nunca `-A` ou `-u`).
7. Python: `cd backend && PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q`.
8. Frontend: symlink de `frontend/node_modules` para `/Users/macbook/medlens/frontend/node_modules`, listado em `.git/info/exclude`.
9. Relatório final de no máximo 12 linhas, com números reais (antes e depois), comandos e hashes.

### C1 — barreira do texto de IA do ECG (CRÍTICO)
```
MedLens lote C1. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-c1 -b wt/r5-c1 5b9b1c1; trabalhe só lá.
Edite SÓ: backend/app/llm/validate.py, backend/app/llm/laudo.py, backend/app/llm/ecg_claim_check.py (novo), backend/tests/test_ecg_ia_barreira.py (novo). Não edite llm/__init__.py nem claim_semantics.py (só importe).
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: R1 e Apêndice A.1.
Problema: no caminho padrão (MEDLENS_LAUDO_V2 off) validate_report (validate.py:347) só marca números e 5 tópicos; frases sem lastro passam (9/9 na sonda A.1). laudo.py validate_laudo (~217) idem.
Faça (falha fechada): no v1 e no laudo v1, REMOVA (não marque) a frase que (a) nega isquemia/IAM/supra/BAV/bloqueio, (b) afirma normalidade ("normal", "sem alterações", "dentro dos limites"), ou (c) afirma diagnóstico ausente de achados_por_regras; com ecg.st_not_assessable presente, (a) e (b) são sempre removidas. Reuse claim_semantics.semantic_issues ou o desenho de rx/claim_check.py com tópicos de ECG. Achado ia.* crítico sem regra correspondente: removido ou rebaixado com flag. Conte as remoções em validation (campo novo afirmacoes_removidas) e ponha 1 limitação legível ("N frases sem lastro removidas").
TDD: as 9 frases de A.1 -> 0 sobrevivem; "FC 72 bpm" e "Ritmo sinusal" (com regra) sobrevivem; laudo v1 idem. Suíte backend inteira verde (inclui test_llm_validate.py e test_llm_claim_semantics.py).
Sem push/main/deploy; git add só seus arquivos; sem PHI; não chame IA real.
Relatório <= 12 linhas: frases removidas/mantidas, falsos bloqueios encontrados, commits.
```

### C2 — barreira do RX e falha fechada (CRÍTICO)
```
MedLens lote C2. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-c2 -b wt/r5-c2 5b9b1c1; trabalhe só lá.
Edite SÓ: backend/app/rx/claim_check.py, backend/app/llm/__init__.py, backend/tests/test_rx_validator_qualitative.py, backend/tests/test_llm_fail_closed.py (novo).
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: R2 e Apêndice A.2.
Faça:
1) Lista de permissão aproximada: léxico de termo clínico desconhecido (raízes/sufixos: -ite, -ose, -oma, -megalia, -ectasia, aneurism, neoplas, metást, embol, tubercul, cavit, calcific, aorta, abscess, pneumomediast, DPOC, COVID, escoliose, insuficiência cardíaca, hipotransparên, hipertransparên, condensaç) sem tópico com fato -> remove a frase. Normalidade global ("sem particularidades", "nada digno de nota", "sem evidências de doença", "transparência conservada") sem fato -> remove.
2) _ABST (linhas 194-196) não libera cláusula que afirma achado ("derrame volumoso ... limitando avaliação" -> removida).
3) Fatos.de (130-145): ICT de segmentação heurística ou incidência AP não é lastro para cardiomegalia nem para "área cardíaca normal" (use o campo de origem que a medida/ficha já tem; rx/ficha.py:135 já trata como NAO_AVALIADO; não edite ficha.py).
4) Falha fechada em llm/__init__.py:153-156 (validate_report, ECG) e 335-338 (sanitize_report, RX): exceção -> descarta a narrativa, mantém regras/medidas, limitação "barreira de verificação falhou: narrativa descartada"; log sem texto.
TDD: as 30 frases sem lastro de A.2 -> 0 passam; "Área cardíaca normal." com ICT de modelo PA 0,46 passa; "Cardiomegalia importante." com ICT heurístico 0,62 removida; as 31 legítimas de test_rx_laudo_validate.py passam; exceção simulada (monkeypatch) -> sem texto cru. Suíte backend inteira verde.
Sem push/main/deploy; git add só seus arquivos; sem PHI; não chame IA real.
Relatório <= 12 linhas: antes/depois (23/30 -> ?), falsos bloqueios, commits.
```

### E1 — SVD/BRD e PR acima de 200 ms (ALTO)
```
MedLens lote E1. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-e1 -b wt/r5-e1 5b9b1c1; trabalhe só lá.
Edite SÓ: backend/app/ecg/analysis/rules.py, backend/tests/test_ecg_svd_brd.py (novo), backend/tests/test_ecg_pr_borderline.py (novo), docs/benchmarks/trilha_r5_e1_log.md (novo). Não toque em .claude/worktrees/agent-a6ff241e* (trabalho de outra sessão).
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: 2.1, 2.3 e Apêndice A.5. NÃO use o CODE-test para ajustar nada.
Passo A (commit próprio): (1) SVD (rules.py ~501-507) só com QRS de decisão < 120 ms, salvo eixo > 110°; (2) QRS de decisão >= 120 ms + R dominante em V1 (mesma condição que hoje dispara SVD) + sem padrão de BRE -> BRD; sem S larga lateral, rótulo "Bloqueio de ramo direito provável". Nenhum limiar numérico novo.
Passo B (commit próprio): PR exibido > 200 ms sem critério completo de BAV1 -> achado borderline "PR medido acima de 200 ms sem critério completo de BAV de 1º grau: conferir no traçado". Não muda ecg.av_block_1 nem os limiares AV1_*.
TDD: unitários sintéticos para A e B (RED antes).
Bench (A e B separados): cd backend && PYTHONPATH=. MEDLENS_BENCH=/Users/macbook/medlens/data/bench MEDLENS_DATASETS=<copie do comando em /Users/macbook/medlens/RETOMADA.md, pendência 2> /Users/macbook/medlens/backend/.venv/bin/python -m bench.ecg_bench --source ptbxl --split dev --set large --tag R5E1A --workers 3 (depois R5E1B). Não rode junto com outro bench.
Aceite A: RBBB_complete sens >= 75% e VPP >= 65% (era 58,0/69,3), RVH VPP >= 40% (era 17,8%), NORM->normal >= 74,1% (era 74,6%), LBBB_complete inalterado, STE_acute FP <= 310. Se falhar, não commite a regra; commite teste+log e relate.
Aceite B: 0 registros com PR exibido > 200 ms sem achado de PR; NORM->normal inalterado.
Suíte backend inteira verde. Sem push/main/deploy; git add só seus arquivos. No log, 3 linhas para o médico revisar a mudança de saída.
Relatório <= 12 linhas com IC95%.
```

### E2 — FA por dupla contagem de QRS (ALTO)
```
MedLens lote E2. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-e2 -b wt/r5-e2 5b9b1c1; trabalhe só lá.
Edite SÓ: backend/app/ecg/analysis/rpeaks.py, backend/app/ecg/analysis/rhythm.py, backend/tests/test_ecg_rpeaks_t_alta.py (novo), docs/benchmarks/trilha_r5_e2_log.md (novo). NÃO edite rules.py (é do lote E1).
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: 2.2. NÃO calibre no CODE-test (os 5 FP com FC 152-222 são pós-hoc, só motivação).
Faça: guarda de plausibilidade na detecção de R: se FC > 150 e os picos alternam amplitude/morfologia (R-T-R-T) ou o intervalo entre picos alternados é ~ QT, redetecte com período refratário maior; se ainda ambíguo, exponha um sinal (ex.: rpeaks_unreliable=True) nas features e relate (a mensagem "ritmo não classificado" em rules.py fica para depois do merge com E1).
TDD: sinal sintético 75 bpm com T = 0,8·R -> FC 75 ± 3 e sem ecg.atrial_fibrillation (RED antes); taquicardia sintética real a 160 bpm continua 160 ± 5.
Metamórfico: 200 registros NORM do PTB-XL dev, onda T x2 (janela após o QRS) -> FC inalterada (± 5) em >= 98%; script dentro do teste ou do log, sem arquivo novo fora da lista.
Bench dev (tag R5E2, --workers 3, não rodar junto com outro bench; mesmo comando do E1): FA sens >= 83% (era 83,7) e espec >= 98,0% (era 98,1); STACH sem queda > 1 pp.
Suíte backend inteira verde. Sem push/main/deploy; git add só seus arquivos.
Relatório <= 12 linhas com números reais.
```

### E3 — harness do CODE-test e invariância (ALTO, só investigação)
```
MedLens lote E3. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-e3 -b wt/r5-e3 5b9b1c1; trabalhe só lá.
Edite SÓ: backend/bench/ecg_invariance.py (novo), backend/tests/test_ecg_invariance.py (novo), docs/benchmarks/code_test.md, docs/benchmarks/ecg_invariance.md (novo). NÃO edite bench/code_test.py (UNIT_TO_MV fica como está), regras, nem o marcador data/bench/ecg/code_test.RUN (confira o mtime antes e depois). NÃO reexecute o CODE-test nem rode regras sobre ele.
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: R4, 2.4, Apêndices A.3 e A.4.
1) Unidade: leia a documentação do dataset (README do Zenodo 3765780 já baixado em MEDLENS_DATASETS, ou a página do Zenodo) e compare a estatística bruta de A.4 (sem rótulos) com a mesma estatística no PTB-XL NORM do dev. Conclua: fator provável e grau de certeza.
2) Invariância (ecg_invariance.py): 1000 registros do PTB-XL dev, transformações 500->400 Hz, deriva de linha de base (0,3 Hz, 0,2 mV), amplitude x0,5 e x2; métrica: concordância de códigos com o original e taxa de ecg.lvh/ecg.rae por transformação. Aceite: >= 95% de concordância nas duas primeiras, ou lista do que quebra; x2 no NORM: comparar a taxa de HVE/SAD com 64,8%/30,1% do CODE.
3) Errata em code_test.md (sem mudar a tabela original): rótulos de amplitude e BRD/BRE sob suspeita até a unidade ser confirmada; "14 dos 17 FP de BRD são bloqueio incompleto (re-tabulação pós-hoc do cache)"; HVE em 64,8% do CODE vs 3,2% no PTB-XL NORM; FA VPP explicado por prevalência 1,6%.
TDD: teste da transformação (reamostragem preserva duração, escala multiplica amplitude) com sinal sintético. Suíte backend verde.
Sem push/main/deploy; git add só seus arquivos; sem PHI.
Relatório <= 12 linhas: unidade concluída, concordâncias, recomendação para a decisão D-B.
```

### U1 — ReportPanel (ALTO, uso real)
```
MedLens lote U1. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-u1 -b wt/r5-u1 5b9b1c1; symlink frontend/node_modules -> /Users/macbook/medlens/frontend/node_modules (em .git/info/exclude).
Edite SÓ: frontend/src/features/report/ReportPanel.tsx, o global.css do frontend (ache com find), frontend/src/test/report.test.tsx, frontend/src/test/reliability.test.tsx. Não edite StudyView, client.ts nem rule_ppv.json.
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: seção 4 (U1, U3, U7), R5, R10.
Faça: (1) ai.available=false mostra ai.limitations (motivo real: LGPD, recusa, erro do provedor), não o genérico "sem chave"; (2) trocar "Nenhuma discordância identificada." por "Conferência automática: números e tópicos verificados; não substitui leitura do traçado." e mostrar o nº de frases removidas pela barreira se o campo existir; (3) diferenciais usam confidence_display quando presente, nunca "0%"; (4) VPP exibido sempre com a prevalência da base ("em base com X% de prevalência") ou trocado por sens/espec, a partir do próprio rule_ppv.json; (5) achados rx.model.* em bloco separado "Escore do modelo (não medido)"; (6) .btn.small e .tab com min-height 44px.
TDD: Vitest com ai={available:false, limitations:["Envio à IA bloqueado pela barreira LGPD"]} exige o texto; diferencial com confidence 0 e confidence_display exige o display; nenhum "VPP" sem prevalência.
Playwright 320/768/1024/1440, claro e escuro, DICOM/ECG sintético, sem chaves de IA: scrollWidth == innerWidth, botões >= 44 px, console sem erro. Prints em ~/medlens-shots/.
npx vitest run + npm run build ok. Sem push/main/deploy; git add só seus arquivos.
Relatório <= 12 linhas com medidas por largura.
```

### U2 — StudyView e laudo RX (ALTO, uso real)
```
MedLens lote U2. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-u2 -b wt/r5-u2 5b9b1c1; symlink frontend/node_modules como no U1.
Edite SÓ: frontend/src/features/StudyView.tsx, frontend/src/api/client.ts, frontend/src/features/rx/LaudoEstruturado.tsx, frontend/src/components/ErrorBoundary.tsx (novo), frontend/index.html, frontend/src/test/laudoestruturado.test.tsx, frontend/src/test/client.test.ts, frontend/src/test/studyview.test.tsx (novo). NÃO edite global.css (é do U1): se precisar de estilo, use classes existentes.
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: seção 4 (U2, U4, U6, U9), 3.2, 3.3.
Faça: (1) erro de reanálise (StudyView.tsx:42) renderizado com role="alert" fora do bloco recon3d; (2) botão 3D lê (rx ?? result.rx).recon3d_available; (3) client.ts aceita AbortSignal no /ai e StudyView aborta a chamada anterior; (4) ErrorBoundary em volta de ViewerPane/Recon3DViewer; (5) LaudoEstruturado recebe studyId: persiste o voto Concordo/Discordo em localStorage (estudo x seção) e envia ao endpoint existente POST /feedback/{study_id} (client.ts:103) com {kind:"rx", code:"rx.laudo.<secao.id>", verdict}, sem texto livre; falha de rede não quebra a UI; (6) botão "Copiar laudo" copia laudo_rx_markdown + comentários do médico; (7) erro de console: reproduza no bundle servido pelo backend, registre a mensagem exata; se for favicon 404, ícone SVG inline (data:) no index.html.
TDD: Vitest: analyzeRX rejeitando em estudo de 1 incidência -> role="alert" visível; voto sobrevive a remontar; fetch recebe corpo exato; StrictMode -> 1 chamada /ai concluída; copiar inclui comentário.
Playwright 320/768/1024/1440 claro/escuro: laudo sem overflow, botões >= 44 px, foco por Tab, console 0 erro.
npx vitest run + npm run build ok. Sem push/main/deploy; git add só seus arquivos.
Relatório <= 12 linhas: mensagem do console e causa, medidas por largura.
```

### U3 — anti-colisão do overlay RX (MÉDIO)
```
MedLens lote U3. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-u3 -b wt/r5-u3 5b9b1c1; symlink frontend/node_modules como no U1.
Edite SÓ: frontend/src/features/rx/labelLayout.ts, frontend/src/features/rx/ViewerPane.tsx, frontend/src/test/labelLayout.test.ts.
Problema: em 390 px o rótulo do ICT sobrepõe o das cúpulas; placeLabel (labelLayout.ts:37-54) não conhece caixas ocupadas; ViewerPane.tsx:200-204 chama uma vez por medida.
Faça: placeLabel(…, ocupados?: Bounds[]) desloca em passos de lineHeight (acima, depois abaixo) até 4 tentativas, dentro do viewport; ViewerPane ordena por y do âncora e acumula as caixas. Não mude texto, cor nem fonte.
TDD: 2 âncoras a 4 px em viewport de 390 px -> caixas sem interseção e dentro dos limites (RED antes); testes antigos verdes.
Playwright 320/390/768/1024/1440 com DICOM PA sintético: validar por captura (canvas) e pelo teste unitário. Prints em ~/medlens-shots/.
npx vitest run + npm run build ok. Sem push/main/deploy; git add só seus arquivos.
Relatório <= 8 linhas.
```

### R1 — ICT em findings.py (ALTO)
```
MedLens lote R1. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-r1 -b wt/r5-r1 5b9b1c1; trabalhe só lá.
Edite SÓ: backend/app/rx/findings.py, backend/tests/test_rx_findings_ict.py (novo).
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: R7, D-C.
Faça: (1) ICT de segmentação heurística não gera rx.cardiothoracic_ratio_normal nem achado de aumento (use a origem que a medida já carrega; não edite ficha.py nem claim_check.py); (2) rótulo de findings.py:97 vira "Sugere aumento da silhueta cardíaca (ICT > 0,50 em PA)" (decisão D2 já tomada); (3) faixa cinzenta 0,47-0,53 SÓ se o prompt disser "D-C=sim": ___ (então: "ICT limítrofe/indeterminado pela medida automática", severidade borderline).
TDD: ICT heurístico 0,62 e 0,40 -> nenhum achado de ICT; ICT de modelo 0,55 PA -> rótulo novo; nenhum label contém "Cardiomegalia ("; com D-C, 0,49 -> limítrofe. Suíte backend inteira verde (ajuste só testes que esperavam o rótulo antigo, se estiverem listados; se não, pare e relate).
Sem push/main/deploy; git add só seus arquivos.
Relatório <= 8 linhas.
```

### P1 — PHI antes de uso real
```
MedLens lote P1. git -C /Users/macbook/medlens worktree add ~/medlens-wt/r5-p1 -b wt/r5-p1 5b9b1c1; trabalhe só lá.
Edite SÓ: backend/app/main.py, backend/app/store.py, backend/app/api/analysis.py, backend/app/api/studies.py, backend/tests/test_phi_auth_retencao.py (novo). Use a skill lgpd.
Leia em /Users/macbook/medlens/docs/ANALISE-FABLE-2026-11-25.md: R8.
Faça: (1) com MEDLENS_API_TOKEN definido, toda rota /api exige Authorization: Bearer (401 sem); sem token definido, só aceita cliente de loopback (403 caso contrário); /health continua aberto sem dados; (2) DELETE /api/studies/{id} remove arquivos e artefatos; (3) retenção MEDLENS_RETENCAO_HORAS (padrão 24): estudos vencidos são apagados na inicialização e a cada upload; (4) _LAST (analysis.py:70) vira LRU com teto (padrão 32) e a mensagem 409 em pt-BR.
TDD para cada item (TestClient). Suíte backend inteira verde. O frontend não é alterado: se o token quebrar o fluxo local sem token, o padrão loopback deve mantê-lo funcionando (teste).
Sem push/main/deploy; git add só seus arquivos; sem segredo em commit.
Relatório <= 10 linhas.
```

## 4. Decisões do dono (3, com recomendação)

- **D-A. Narrativa livre de IA no ECG.** As opções são: (1) desligar por padrão a "Descrição minuciosa" e o laudo v1 do ECG; (2) manter ligada com a barreira C1; (3) deixar como está.
  - Recomendação: (2) assim que C1 e C2 forem mesclados, e (1) até lá se houver uso real antes disso.
  - Sem resposta: C1 entra (falha fechada) e a opção (3) nunca é aplicada.
  - Desligar por padrão é 1 linha em `llm/__init__.py` depois de C2. O orquestrador faz isso se o dono escolher (1).
- **D-B. CODE-test com possível erro de unidade.** As opções são: (1) não reexecutar e publicar a errata; (2) autorizar uma única "execução 2, não cega, correção de harness", publicada ao lado da primeira, só se E3 confirmar o erro e com as regras congeladas de novo; (3) ignorar.
  - Recomendação: (1) já, que é o que E3 faz, e (2) só após E3 + E1 + E2 mesclados.
  - Sem resposta: (1).
- **D-C. Faixa cinzenta do ICT (0,47 a 0,53) como "limítrofe/indeterminado pela medida automática".**
  - Recomendação: aprovar. O erro médio com modelo é de 0,027 a 0,041, com viés negativo, então um corte seco em 0,50 gera falso "dentro do limite" justamente onde importa. O médico define os limites.
  - Sem resposta: R1 faz só a parte conservadora (ICT heurístico sem achado + rótulo D2) e não cria a faixa.
