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
1. **BUG tórax×abdome pela tag DICOM** (prioridade máxima): trilha `r2-tagfix` lançada no fim; conferir `git -C ~/medlens-wt/r2-tagfix log` e mesclar se a suíte passar; senão relançar com a spec em RETOMADA (view.py:146/156).
2. Bench do código mesclado FEITO (dev ampliado N=9183, tag R2mergedL; relatório gerado em scratch, não versionado): NORM→normal 74,7→74,5%; FA 84,4/84,0 (=); BAV1 38,3% (=); BAV3 0/12 (=); STE_acute 51,2%/FP 341 (=); LVH sens 72,7→74,8%; **STD sens 56,6→47,8% (espec 82,5→85,1%)** = regressão pela supressão do strain (1B) — mantida por instrução clínica (strain não é isquemia), DECISÃO MÉDICA: restringir supressão ou aceitar. Comando (tag R2merged; rodar: `cd backend && PYTHONPATH=. MEDLENS_DATASETS=... MEDLENS_BENCH=../data/bench python -m bench.ecg_bench --source ptbxl --split dev --tag R2merged --workers 4`) e comparar com r2_base.md / logs; também `--set large`.
3. Lançar trilhas não iniciadas com as specs de `docs/planning/r2_specs_pendentes.md`: 5 (UX/qualidade/log), 6 (E5 P/BAV), 7 (E1 ST), 8 (E3/E4 FA/NORM), 9-E6 (sombra), depois ondas 2-4 do plano ECG.
4. Regenerar `docs/benchmarks/ecg.md`/`rx.md` no código final; teste externo CODE-test **uma vez só**, no fim.
5. LGPD: remover envio da imagem de ECG nas chamadas antigas (`llm/__init__.py` ~162).
6. Limpar worktrees após confirmar merges (`git worktree remove ~/medlens-wt/<X>`).

## Decisões do médico / usuário
- STD vs strain: aceitar queda de sens STD (68→62%) em troca de rotular strain como secundário, ou restringir a supressão.
- Gabarito caso1 inconsistente: Cornell 58 mm (R aVL 21 + S V3 37) implicaria Peguero positivo; confirmar S V3 real.
- Rodar 60 laudos IA (~US$ 11) ou modelo mais barato; revisar 20 laudos.
- Licença CXAS (pesos MIMIC/DINOv3) antes de ligar por padrão; 91 cartões "verificar".
- Credencial PhysioNet/Kaggle (VinDr, BRAX, VinBigData); reiniciar o servidor da porta 8000; E6 na UI só após decisão regulatória.
