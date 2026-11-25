# RETOMADA — MedLens (rodada 2, 2026-11-24)

Branch: `claude/ecg-rx-ai-reader-nd20rs` (local, **sem push/deploy**). Rodada 2 orquestrada por Opus; executores Sonnet em worktrees `~/medlens-wt/r2-<trilha>` (branches `wt/r2-<trilha>`), mesclados aqui em sequência. Logs por trilha: `docs/benchmarks/trilha_r2_<trilha>_log.md`. Planos: `docs/planning/plano_fable_r2.md` (10 ações), `docs/planning/plano_fable_ecg.md` (ECG ficha/cartões/digitalização). Specs prontas das trilhas não lançadas: `docs/planning/r2_specs_pendentes.md`.

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
