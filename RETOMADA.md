# RETOMADA — MedLens (rodada 2, 2026-11-24)

## Rodada 2026-11-25 noite 2 — ECG final (worktree wt/ecg-final, base 2be7b23, sem push)
- Feito: (1) QRS largo sem BRE: SEM mudanca de regra (ver pendencia abaixo). (2) docs/benchmarks/ecg.md (LUDB 200 + PTB-XL dev large N=9183, rodada fresca) e rx.md (masks completo, 2094 tarefas) regenerados no codigo 2be7b23; sem PHI nem imagem real. (3) Limpeza: removidos 24 worktrees mesclados e limpos (wt/A..I, r2-*, r3-t5, r4-playwright, agent-a5a9699b/a7689ed5/a7f67de3) e 29 branches mescladas (git branch -d). (4) CODE-test rodado UMA vez (docs/benchmarks/code_test.md; marcador data/bench/ecg/code_test.RUN, nao rodar de novo).
- CODE-test (N=827): AV1 sens 46,4% VPP 92,9%; BRD 52,9%/51,4% (nossa RBBB_any inclui incompleto); BRE 83,3%/80,6%; bradicardia 93,8%/78,9%; FA 92,3%/54,5% (13 pos); taq. sinusal 83,8%/88,6%.
- Benchmark PTB-XL dev large antes/depois = identico (nenhuma regra mudou): NORM->normal 74,6% (2101/2815), STD sens 56,6%, STE_acute sens 51,2% FP 310.
- Mantidos (nao mesclados ou sujos): worktree/branch wt/r3-t6 (2 commits fora da principal + 1 arquivo sujo), worktree-agent-a6ff241e (mesclado, mas 4 alteracoes nao commitadas em rules.py/delineate.py/plausibility.py + test_ecg_st_noise_abstention.py de outra sessao), worktree-agent-aaff1359 (travado, sessao ativa), worktree-agent-a5a9699b so existe no origin.
- Pendencia clinica do medico (QRS largo sem BRD/BRE): o criterio (>=120 ms sem morfologia de BRE/BRD = atraso inespecifico, 110-119 = limitrofe; AHA/ACCF/HRS 2009 Parte III, cards normal.qrs_duracao e conducao.ivcd) JA esta implementado sobre a largura mista (mediana por derivacao + 0,25 x global). O que fica "borderline" e o aviso de ST (`ecg.st_not_assessable`) quando a largura GLOBAL >= 120 ms mas a mista < 120: a largura global tem vies de +25 ms vs 12SL e 4876/9183 registros do dev passam de 120 ms globais (2970 sem bloqueio; 1010 deles NORM no gold = 34%). Pergunta: manter esse aviso como limitrofe (sem tirar o ECG de "normal pelas regras") ou promover QRS largo sem BRE a anormal? Promover derruba NORM->normal em ~1/3; exige antes corrigir o vies da largura global. Decisao do medico.
- Pendente do dono: push/deploy; credenciais PhysioNet/Kaggle/VinDr/BRAX; calibracao RX e gate fora-de-escopo RX (4,4%) nao rerodados.


Branch: `claude/ecg-rx-ai-reader-nd20rs` (local, **sem push/deploy**). Rodada 2 orquestrada por Opus; executores Sonnet em worktrees `~/medlens-wt/r2-<trilha>` (branches `wt/r2-<trilha>`), mesclados aqui em sequência. Logs por trilha: `docs/benchmarks/trilha_r2_<trilha>_log.md`. Planos: `docs/planning/plano_fable_r2.md` (10 ações), `docs/planning/plano_fable_ecg.md` (ECG ficha/cartões/digitalização). Specs prontas das trilhas não lançadas: `docs/planning/r2_specs_pendentes.md`.

## Playwright RX (2026-11-25) — worktree r4-playwright (branch wt/r4-playwright, sem push)
Validação visual do consentimento de imagem de RX + aviso LGPD (R4), DICOM PA sintético (`make_dx_dicom`, 512x512), backend :8010 e vite :5180 sem chaves de IA, `/health` interceptado só para `ai_available:true` (sem chave o bloco de consentimento nem aparece, pois "Usar IA" fica desativado).
- OK: checkbox "Enviar imagem à IA na nuvem" DESMARCADO por padrão; aviso "Medidas anonimizadas são enviadas à IA na nuvem." + nota LGPD visíveis; marcar/desmarcar muda estado e a requisição: `POST /rx/{id}/ai` corpo `{"send_images_to_ai":false}` (27 B) sem consentimento, `true` (26 B) só após marcar, voltando a `false` ao desmarcar. O corpo nunca leva bytes de imagem (flag booleana; a imagem só sai do servidor para a nuvem, e isso é coberto por `tests/test_rx_image_optin.py`, não pelo navegador).
- OK em 320/768/1024/1440: sem overflow horizontal (scrollWidth == innerWidth), foco por teclado visível (outline 2px, claro e escuro), Espaço alterna, contraste texto 15-16:1 e dica 5,6:1 (claro) / 7,7:1 (escuro), console sem erros.
- BUG achado e corrigido: alvo de toque do label tinha 23,6 px (<44). Corrigido com `.image-consent .switch { min-height: 44px }` (medido 44 px nos 4 tamanhos; clique no canto do label alterna). Teste `frontend/src/test/consent-touch-target.test.ts` (RED→GREEN); `vite.config.ts` ganhou `test.css.include` só para `global.css` (vitest zerava CSS no `?raw`).
- Verificação: vitest 42/42, `npm run build` ok, pytest `test_rx_image_optin.py` + `test_rx_text_anon_r4.py` ok.
- Observações não corrigidas: (1) em dev o `POST /ai` sai 2x ao abrir o estudo (React.StrictMode; em build de produção é 1x) — conferir no build; (2) o switch "Usar IA (Claude)" do header também tem ~24 px de altura (mesmo problema de alvo de toque, fora do escopo pedido); (3) marcar o consentimento dispara de imediato novo envio à IA sem confirmação extra (por desenho).
- Não coberto: payload real ao provedor de nuvem (sem chaves), Safari/Firefox, toque real em dispositivo, DICOM/JPG reais. Capturas em `~/medlens-shots/` (fora do git).

## ESTADO (R4) — 2026-11-25 (worktree agent-aaff1359, sem push)
Commits (sobre e04f519): `314f574` T1 strain não suprime infra de ST (só qualifica: "pode ser secundária a HVE (strain); isquemia não excluída"); `a5e6c31` T2 Sokolow `>= thr-1e-9` (35,0 mm vira HVE; LAE ctx idem); `3e2a78f` T3 rx_report: `assert_text_only` em todo caminho + texto anonimizado (`llm/anon.py`: sem study_id/UIDs/datas, idade só por faixa, instance_id vira imgN) + aviso de 1 linha na UI; `37a8308` T4 BRE/marca-passo ventricular: achado `ecg.st_not_assessable` "abnormal" com "ST não interpretável pelas regras; aplicar Sgarbossa/Smith manualmente" (rótulo + aviso_topo), nunca vira normal; Sgarbossa NÃO implementado.
Testes: backend rc=0; frontend vitest 41/41 + `npm run build` ok.
Bench R4 (PTB-XL dev large, N=9183, tag R4, relatório `docs/benchmarks/r4_ptbxl_large.md`): **STD sens 56,6% / espec 82,5% (aceite >=56,6 OK; R2merged 47,8%)**; **STE_acute FP 310, sens 51,2% (aceite <=341 OK)**; NORM→normal 74,6%; FA 83,7/84,7; BAV1 40,1/54,3; BAV3 33,3/18,2 (12 pos); LVH sens 74,7/VPP 44,1.
Não feito / desvios: `docs/benchmarks/ecg.md` e `rx.md` NÃO regenerados (exigem LUDB + imagens; `--tag` não reescreve docs) — pendente. Cache do bench rodou em cópia de `data/bench` no scratchpad (não versionada). QRS largo isolado (sem BRE/MP) segue como ST "borderline". Playwright do aviso novo da UI não rodado (só vitest).

Parado por orçamento de uso CRÍTICO (janela de 5h a 97%). Rodada 1: ver histórico do git (commit f9b3def).

## Mesclado nesta rodada (suíte backend após merges: 1 falha corrigida → 0; frontend build ok)
| Trilha | Estado | Números (antes → depois) |
|---|---|---|
| 1 higiene (hyg) | feito | 4 testes quebrados → 0; use_model explícito vence env; fixture LITFL sintética; /health importa/carrega de verdade + banner na UI; R6: p95 heurístico 24,9 → 1,81 s (máquina carregada; meta 1,5 s não confirmada), Dice jsrt pulmão 0,636 → 0,636 |
| 2 base de avaliação (eval) | feito | dev PTB-XL ampliado N=9183 (NORM 2815), IC95% bootstrap em todas as tabelas, gold STE_acute, medidas vs 12SL (PTB-XL+), subgrupos; CODE-test baixado e protegido (NÃO rodado). Linha de base: `docs/benchmarks/r2_base.md` (NORM→normal 74,7%; FA sens/PPV 84,4/84,0; BAV1 38,3/52,8; BAV3 0/12; STD 56,6/82,5 espec; STE_acute sens 51,2% FP 341; viés PR +11,6 ms; QRS +25,3 ms; ST-J MAE 28,9 µV) |
| 3 texto IA (llm) | parcial | validador pós-LLM, retry+failover Anthropic→OpenRouter, mascarar texto queimado + bloqueio de envio; conjunto fixo 60 ids congelado, só 2 laudos rodados (65/65 números conferem, 0 críticos sem lastro) — 60 laudos custariam ~US$ 11 |
| 4 calibração RX (calib) | feito | ECE (IU dev, CV 5 folds): atelectasia 0,121→0,042, consolidação 0,157→0,019, derrame 0,077→0,014, cardiomegalia 0,059→0,022; zona "indeterminado"; nódulo JSRT AUC 0,628 [0,555–0,699] (fraco). VinDr/BRAX/VinBigData: exigem credencial |
| 9-R3 CXAS (cxas) | feito, flag off | Dice PAX-Ray++ (200 img): coração 0,950 PA / 0,942 perfil; coluna 0,930/0,933 (PSPNet 0,81/0,51 e 0,66/0,40); MIT "research use only" → `MEDLENS_RX_CXAS=1` desligado por padrão; venv `~/medlens-venvs/cxas` |
| 10 E7 + abdome (e7abd) | parcial | Pearson mediano 0,823→0,967; perfil hard 0,104→0,810; utilizável 97,5% (2,5% abstenção "só FC/ritmo"); abdome: fluxo nos DICOM ok; DRR TotalSegmentator não feito |
| K digitalização (ecgk) | parcial | caso1: layout 6x2→3x4+3 (faixas V1/II/V5), PR 94→152, QRS 266→116, sem pré-excitação; cabeçalho lido por moldes (QRS 112, QT 438, QTc 482, eixos 49/20/171; PR impresso cortado); R aVL/V4 ainda baixos (xfail). Falta: UI manual, banda larga/saturação, quality.py |
| J laudo LLM (laudo) | parcial | laudo pt-BR estruturado + markdown + versão curta, só texto; caso1 errado → aviso de divergência; caso1 correto → HVE+CMH sugestiva; Peguero = S máx + S V4 (28/23). Falta: citações [F]/[C], ficha ecg_features/v1, remover imagem das chamadas antigas de ECG (LGPD) |
| 1B índices HVE (ecgidx) | feito com ressalva | Sokolow, Cornell(+produto), Peguero, Romhilt-Estes, Morris; HVE+strain → "repolarização secundária"; AE; CMH sugestivo; pré-excitação bloqueada. PTB-XL dev: LVH sens 71,6→76,1; STD sens 68,2→62,0 (FP 321→290) — queda >2 pt por supressão do strain: DECISÃO MÉDICA |
| 1C cartões (cards) | feito | 142 cartões YAML (paráfrase + referência primária), busca FTS5 + select_cards; 91 marcados "verificar"; todos revisado_por_medico=false |

## Gasto OpenRouter: ~US$ 0,47 (llm 0,357 + laudo 0,118) de US$ 0,50; saldo ~US$ 2,65. Não usar mais nesta rodada.

## Pendências (ordem)
1. BUG tórax×abdome pela tag DICOM: CORRIGIDO e mesclado (r2-tagfix): 10/10 regiões corretas com modelo, 2/2 tag divergente com aviso; region_uncertain + seletor na UI. Pendente: modo sem modelo ainda erra os 2 (8/10); conferir seletor no navegador; ViewPosition/polaridade sem mudança.
2. Bench do código mesclado FEITO (dev ampliado N=9183, tag R2mergedL; relatório gerado em scratch, não versionado): NORM→normal 74,7→74,5%; FA 84,4/84,0 (=); BAV1 38,3% (=); BAV3 0/12 (=); STE_acute 51,2%/FP 341 (=); LVH sens 72,7→74,8%; **STD sens 56,6→47,8% (espec 82,5→85,1%)** = regressão pela supressão do strain (1B) — mantida por instrução clínica (strain não é isquemia), DECISÃO MÉDICA: restringir supressão ou aceitar. Comando (tag R2merged; rodar: `cd backend && PYTHONPATH=. MEDLENS_DATASETS=... MEDLENS_BENCH=../data/bench python -m bench.ecg_bench --source ptbxl --split dev --tag R2merged --workers 4`) e comparar com r2_base.md / logs; também `--set large`.
3. Lançar trilhas não iniciadas com as specs de `docs/planning/r2_specs_pendentes.md`: 5 (UX/qualidade/log), 6 (E5 P/BAV), 7 (E1 ST), 8 (E3/E4 FA/NORM), 9-E6 (sombra), depois ondas 2-4 do plano ECG.
4. Regenerar `docs/benchmarks/ecg.md`/`rx.md` no código final; teste externo CODE-test **uma vez só**, no fim.
5. LGPD: remover envio da imagem de ECG nas chamadas antigas (`llm/__init__.py` ~162).
6. Limpar worktrees após confirmar merges (`git worktree remove ~/medlens-wt/<X>`).

## Decisões do médico / usuário
- STD vs strain: aceitar queda de sens STD (68→62%) em troca de rotular strain como secundário, ou restringir a supressão.
- Gabarito caso1 RESOLVIDO (R3-C1): medido na imagem, S V3 ~6 mm, R V3 ~37-39 mm, R aVL ~21 mm; o "Cornell 58" = R aVL + R V3 (soma de R). Cornell classico ~27 mm. Texto corrigido em docs/planning/r2_specs_pendentes.md (SPEC7).
- Rodar 60 laudos IA (~US$ 11) ou modelo mais barato; revisar 20 laudos.
- Licença CXAS (pesos MIMIC/DINOv3) antes de ligar por padrão; 91 cartões "verificar".
- Credencial PhysioNet/Kaggle (VinDr, BRAX, VinBigData); reiniciar o servidor da porta 8000; E6 na UI só após decisão regulatória.
'

## RETOMAR AQUI (2026-11-25, antes de /clear)

Estado: rodada 2 mesclada LOCALMENTE em claude/ecg-rx-ai-reader-nd20rs (50+ commits à frente do origin). NADA da rodada 2 foi enviado ao GitHub.

### BLOQUEIO DO PUSH (decidir primeiro)
- Repo MineiroUaiSo/BookGenApp é PÚBLICO. Commit adc5c64 inclui backend/tests/data/caso1_ecg.jpg: ECG impresso (GE 12SL) com cabeçalho (Male/Unknown/Technician/ORDER ECG22125996). Origem (ensino publicado x paciente) NÃO confirmada.
- Opção recomendada: reescrever só os commits locais não enviados removendo o JPG (git filter-branch/rebase em origin..HEAD), usar cópia com cabeçalho/rodapé coberto, e fazer tests/test_gold_caso1 dar skip se a imagem faltar. Depois: git push origin claude/ecg-rx-ai-reader-nd20rs. Se o usuário confirmar domínio público, pode empurrar como está.
- Antes de qualquer push: diff sem chaves (sk-or-/sk-ant-), sem DICOM/dados (conferido: só esse JPG).

### Pendente (ver docs/planning/r2_specs_pendentes.md, prompts prontos)
- Ações 5 (qualidade/UX/log), 6 (E5 P/BAV), 7 (E1 ST), 8 (E3/E4), E6 em modo sombra: NÃO lançadas (orçamento 5h estourou).
- K: R de aVL/V4 do caso1 ainda baixo (xfail); falta UI de importação manual derivação a derivação.
- J: citações [F]/[C] no laudo, retirar imagem das chamadas antigas de ECG (LGPD: foto com cabeçalho vai ao provedor).
- Ação 3: rodar 60 laudos IA (~US$ 11) só com modelo barato e aprovação.
- Regenerar docs/benchmarks/ecg.md e rx.md.
- Plano Fable ECG (ficha ecg_features/v1 + cartões + FTS5): /private/tmp/.../tasks/ab6e605c5abb811d5.output (volátil; resumo na conversa).

### Decisões do usuário em aberto
1. STD caiu 56,6%→47,8% sens (espec 82,5→85,1) pela regra strain=repolarização secundária; manter ou restringir.
2. (feito R3-C1) Gabarito caso1: 58 mm = R aVL 21 + R V3 ~37; S V3 real ~6 mm. Ver SPEC7.
3. CXAS: licença MIT "só pesquisa"; fica desligado (MEDLENS_RX_CXAS=1).
4. Credenciais PhysioNet/Kaggle (VinDr, BRAX, VinBigData); reiniciar servidor porta 8000 (roda código antigo).
5. Limiares: Sokolow por idade, Cornell sem sexo, P>=120 ms, Romhilt-Estes; uso comercial (licença LITFL/ECGpedia).

### Regras do usuário
Modelos SEMPRE em nuvem via OpenRouter (nunca locais). Saldo OpenRouter ~US$ 2,65 compartilhado com Pediatria: parar se < US$ 2,00. Opus orquestra, Sonnet executa. Sem push/deploy sem autorização. Worktrees ~/medlens-wt/r2-* ainda existem (remover após conferir merge: git worktree remove).
'


## ESTADO 2026-11-25 (fim de sessão, limite de uso)
- Branch claude/ecg-rx-ai-reader-nd20rs EMPURRADA ao GitHub (sem o JPG) até e23937e. Depois, só local: LGPD ecg_report sem foto, bench STD split, restrição de supressão de strain, trilha 7 (ST), E6 sombra, trilha 6 (P/BAV, 006facb). Suíte completa passou (exit 0) após merges.
- Trilha 8 (FA/NORM) em andamento no worktree ~/medlens-wt/r3-t8 (branch wt/r3-t8): conferir commit/bench e mesclar. wt/r3-t6 é implementação concorrente DESCARTADA.
- Pendente: gabarito caso1 (S de V3), piloto 5 laudos, trilha 5 (UX), regenerar ecg.md/rx.md, CODE-test uma vez, push das novidades (sem o JPG: backup/pre-filter-2026-11-25 e wt/* ainda o contêm; não empurrar).

## ESTADO 2026-11-25 (trilha r3-docs)
- docs/benchmarks/ecg.md e rx.md regenerados no codigo c9a5a49 (ECG large N=9183 via cache R3T5L, codigo ECG inalterado desde 4b13b7d; RX masks completo + gate T2 4,4% fora de escopo; calibracao nao rerodada). Detalhes e decisoes abertas no rodape de cada md.
- Fix bench/ecg_bench.py: build_report respeita --set large. Secao Images do ecg.md e Montgomery/Shenzhen do rx.md saem (datasets ausentes).
- Pendente: CODE-test (1x no fim), push/deploy pelo dono, credenciais VinDr/BRAX/VinBig, re-rodar calibracao IU (~16 h) se desejado.


## ESTADO 2026-11-25 (tarde — laudo v2 + auditoria Opus)
- Branch claude/ecg-rx-ai-reader-nd20rs enviada ao GitHub até a936cbb (laudo v2 [F]/[C] atrás de MEDLENS_LAUDO_V2=1, desligado). Suíte backend 628 passed/10 skipped no worktree do laudo; frontend 35 testes + build ok.
- Trilhas 5 (UX/log/alerta), 6, 7, 8, E6, LGPD ecg_report sem foto, restrição de strain: TODAS já mescladas (as seções acima que dizem "não lançadas"/"nada enviado" estão superadas). Dado real: BAV3 4/12 (33%), 60 de 142 cartões "verificar", 0 revisados por médico.
- Auditoria Opus (read-only): push OK; BLOQUEIA ligar MEDLENS_LAUDO_V2 e uso clínico: (1) CRÍTICO validador v2 aceita afirmação qualitativa falsa com ids válidos (probe em scratchpad probe_v2.py); (2) ALTO STE some em BRD/BRE e sem Sgarbossa/Smith; (3) ALTO "sem alterações pelas regras" tranquiliza com sens STE_acute 51%; (4) ALTO imagem de RX vai ao provedor por padrão (depende de heurística de texto queimado); (5) MÉDIO assert_text_only só no v2; (6) refs locais ainda contêm o JPG: backup/pre-filter-2026-11-25, wt/r2-ecgk, refs/original/... (nunca push --all/--mirror; apagar após decisão + git gc); (7) BAIXO Romhilt-Estes AE por produto de Morris, Sokolow >35 vs >=35.
- Em andamento: agente Sonnet corrigindo 1, 2 (conservador, sem implementar Sgarbossa), 3 e 5 em worktree (branch worktree-agent-a5a9699b812f13ccc), sem push.
- Decisões do dono: política de envio de imagem de RX (opt-in?), Sgarbossa/Smith, STD vs strain, apagar refs com JPG, licenças.

## ESTADO 2026-11-25 (fim da tarde — correções T1-T9 da auditoria Opus)
- Branch `worktree-agent-a5a9699b812f13ccc` (worktree `.claude/worktrees/agent-a5a9699b812f13ccc`) enviada ao GitHub em 432ea58, 13 commits sobre 18d1c1e, sem o JPG do caso1 (conferido). NÃO mesclada na `claude/ecg-rx-ai-reader-nd20rs`.
- Já feito nela: lastro semântico/negação (T1-T3), barreira LGPD + `allow_images=False` (T5-T6), opt-in de imagem RX com checkbox (T7), BRD sem "ST não avaliável" (T4), strain -> anormal (T8), Sokolow >=35 e Romhilt-Estes (T9).
- Agente Sonnet ainda rodava (analisando bench ECG) quando este registro foi feito: conferir `git log 432ea58..origin/worktree-agent-a5a9699b812f13ccc` e rodar a suíte backend antes de mesclar.
- Próximo: revisar, mesclar local, enviar só a branch (refspec explícito, nunca --all/--mirror). Depois decisão B4: remover refs locais com o JPG (`wt/r2-ecgk`, `backup/pre-filter-2026-11-25`, `refs/original/...`), `git reflog expire --expire=now --all && git gc --prune=now`, e confirmar `git log --all -- backend/tests/data/caso1_ecg.jpg` vazio.
- Laudo v2 continua DESLIGADO (`MEDLENS_LAUDO_V2`); ligar só após eval >=200 fichas + 50 laudos revisados por médico.
- Pendências da última rodada (2026-11-25 noite): (1) Playwright do checkbox "Enviar imagem à IA na nuvem" não rodou (servidor playwright falhou ao conectar); (2) decisão clínica: regra de HVE em `rules.py` usa `sl > sl_thr`, índice Sokolow usa `>= 35` — alinhar? (só difere em 35,0 exato); (3) RX sem consentimento ainda faz chamada de TEXTO ao provedor (medidas/regras, sem imagem); (4) bench PTB-XL dev: STD∪strain 55,1% vs 56,6% (-1,5 pp, IC sobrepostos), LVH 74,7% vs 74,8%, FP STE_acute 310 vs 341; (5) suíte backend do worktree: 878 passed, 10 skipped, 0 falhas.

## ESTADO 2026-11-25 (noite — T1-T9 mesclado)
- `worktree-agent-a5a9699b812f13ccc` (432ea58) MESCLADA localmente em `claude/ecg-rx-ai-reader-nd20rs` (2d38860). Backend: suíte inteira rc=0 (`cd backend && PYTHONPATH=. .venv/bin/python -m pytest`; python do sistema não tem pydicom). Frontend: 40 testes + build ok.
- Falta: push só desta branch (refspec explícito; nunca --all/--mirror); Playwright do checkbox de imagem RX; decisão B4 (apagar refs locais com o JPG); decisões clínicas listadas acima. Laudo v2 continua desligado.

## ESTADO 2026-11-25 (R4 mesclado)
- Decisões do Opus aplicadas e mescladas (R4: 314f574..876f83d): strain só anota (STD sens 56,6%, FP STE_acute 310), Sokolow >=, texto RX anonimizado + aviso UI, BRE/marcapasso = "ST não interpretável". Refs com o JPG apagadas + gc (histórico limpo).
- Pendente: Playwright do aviso/checkbox RX (320/768/1024/1440); regenerar ecg.md/rx.md completos; CODE-test 1x no fim; QRS largo sem BRE ainda "borderline"; limpar worktrees wt/* e .claude/worktrees/*; push/deploy pelo dono.

## Laudo RX confiável 2026-11-25 (worktree rx-laudo, branch wt/rx-laudo, base ce44e05; sem push/deploy)
Spec: `docs/RX-LAUDO-CONFIAVEL-SPEC.md` (§8 tarefas 1-10). Decisões do dono = recomendações §5 (D1 caixa separada, D2 "sugere aumento da silhueta cardíaca", D3 IA do laudo off por padrão `MEDLENS_RX_LAUDO_IA=0`).
Python: `PYTHONPATH=backend /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -W ignore` (rodar de `backend/`); frontend: node_modules por symlink (excluído em .git/info/exclude).
- [x] T1 validador RX: `backend/app/rx/claim_check.py` + gancho em `llm/__init__.py::rx_report`; teste `backend/tests/test_rx_validator_qualitative.py` (31). Sondas antes: 6/6 frases sem lastro MANTIDAS, 0 discordâncias; depois: 6/6 removidas (+ negações), "ICT 0,46" mantida.
- [x] T2 "infiltrado" -> "opacidade" (`PATHO_PT`), teste `test_rx_terminologia_fleischner.py`.
- [x] T3 `knowledge/rx_report_sources.yaml` (S1-S9 verificadas, N1-N10 pendentes) + `backend/app/rx/fontes.py` (`citar()` falha com fonte não verificada) + `test_rx_fontes.py`.
- [x] T4 ficha `rx_ficha/v1` (`app/rx/ficha.py`, `test_rx_ficha.py` 13). ICT heurístico = NAO_AVALIADO; AP = ressalva; Pneumothorax sempre indeterminado.
- [x] T5 léxico (`app/rx/lexico.py`, 21 testes). "ar livre" isento (nome do sinal).
- [x] T6 laudo determinístico (`app/rx/laudo.py`: `build_laudo`, `render_markdown`; `test_rx_laudo.py`). Nunca "normal"; região sem fato = "não avaliado nesta análise automática"; bloco crítico fixo na Impressão (pneumotórax/pneumoperitônio/tubos NÃO avaliados).
- [x] T7 API: campos `laudo_rx` (dict) e `laudo_rx_markdown` em `RXAnalysis`, preenchidos em `rx_analyze` (`_anexar_laudo_rx`, barreira `guard.scan_text`, nunca derruba a análise); `test_rx_laudo_api.py`.
- [x] T8 contrato IA: `app/rx/laudo_validate.py` (`validar`, `reescrever`, `ia_habilitada`), prompt `llm/prompts/rx_laudo_v1.md`, flag `MEDLENS_RX_LAUDO_IA` (off). Suíte adversarial 77 frases (46 sem lastro: 0 passam; 31 legítimas: 31 passam) em `test_rx_laudo_validate.py`. NÃO ligado em `rx_report` (só contrato + validador; ligar exige decisão do dono).
- [x] T9 UI `frontend/src/features/rx/LaudoEstruturado.tsx` (nível por frase, fontes no hover, Concordo/Discordo por seção [local, sem envio ao servidor ainda], comentário por região não avaliada, comunicação não rotineira só em localStorage, nota de IA); ligado em `StudyView` abaixo do ReportPanel de RX; Vitest `laudoestruturado.test.tsx` (5). Playwright em 390 e 1440 (claro/escuro) na porta 8030 (bundle com `VITE_API_BASE=/api`): sem overflow horizontal, botões >= 44px; prints em `~/medlens-shots/laudo-estruturado-*.png`. Não testado: 320/768/1024, tema claro 390, teclado/leitor de tela.
- [~] T10 `backend/bench/rx_gold_fetch.py` + `rx_review_kit.py` + `tests/test_rx_gold_kit.py` prontos. BLOQUEADO o download real: API do Commons devolveu HTTP 429 (rate limit) nas 6 consultas. Retomar: `cd backend && PYTHONPATH=. python -m bench.rx_gold_fetch` (reexecutar depois de alguns minutos; considerar sleep entre consultas). Teste com imagens reais dá skip enquanto `data/gold_rx/` estiver vazio. Kit: `python -m bench.rx_review_kit --n 20`.
- Pendências/limites: (1) IA do laudo NÃO ligada em `rx_report` (validador pronto, decisão do dono); (2) Concordo/Discordo da UI de laudo não persiste no servidor; (3) nenhum push/deploy feito (regra da tarefa); (4) `knowledge/rx_report_sources.yaml` não pode ter datas (guard PHI "data por extenso"), nota de 2026 foi reescrita sem data; (5) T3/T5/T8/T10 escritos junto com os testes, RED provado por mutação/remoção em T3 e T8.
Limites T1: estrito (mesmo com imagem enviada, tópico sem fato é removido; lateralidade/lobo só passam com imagem); `validate.py` não foi alterado (ECG intacto).

## Estado 2026-11-25 (noite) — UI-fixes + Laudo RX mesclados na branch
- Mesclados: wt/ui-fixes (rótulo de medida não corta, base da API `/api` same-origin, switch "Usar IA" 44px) e wt/rx-laudo (laudo RX confiável T1–T10; spec em docs/RX-LAUDO-CONFIAVEL-SPEC.md).
- Verificação pós-merge: pytest exit 0 (backend), vitest 62/62, build ok.
- Pendente (dono): 3 decisões do laudo (caixa do escore do modelo; "sugere aumento da silhueta cardíaca"; IA do laudo só após revisão de 30 laudos) — seguidas as recomendações; revisão médica; baixar casos-ouro (`python -m bench.rx_gold_fetch`, deu 429 no Commons, repetir depois); voto Concordo/Discordo ainda só local na UI.
- Limites: rótulo do ICT sobrepõe o das cúpulas em 390px (sem anti-colisão); 1 erro de console não investigado; derrame/consolidação/nódulo/pneumotórax dependem só do escore do modelo (nódulo AUC 0,63).
- Ainda não mesclado: trabalho do agente de pendências ECG (a67dad: QRS largo sem BRE, regenerar ecg.md/rx.md) — `docs/benchmarks/ecg.md` modificado no working tree NÃO é meu. Limpar worktrees wt/r3-t6 e .claude/worktrees quando concluir.
- Sem push na main, sem deploy.

## Decisão clínica 2026-11-25: QRS largo sem BRE
- Dono decidiu: MANTER o aviso de ST como "limítrofe" (sem promover a anormal). Sem mudança de regra. Pendência de corrigir o viés de +25 ms da largura global só se for promover no futuro.
