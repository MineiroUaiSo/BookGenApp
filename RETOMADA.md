# RETOMADA — MedLens (plano de melhoria, 2026-11-24)

Branch: `claude/ecg-rx-ai-reader-nd20rs` (local, **sem push/deploy**). Trilhas executadas em worktrees `~/medlens-wt/<trilha>` (branches `wt/<trilha>`), mescladas aqui em sequência. Logs detalhados com comandos e hashes: `docs/benchmarks/trilha_<X>_log.md`. Plano original: Fable (E1-E7, R1-R6, abdome).

## Estado por item (antes → depois)
| Item | Estado | Métrica |
|---|---|---|
| Dados (A) | feito | LUDB 200, PTB-XL 3000, QTDB 105, IU 5910 (espelho HF), JSRT 247, PAX-Ray++ test 800; splits congelados; teste anti-vazamento; LUDB dev/teste separados no relatório |
| E1 ST (B) | feito, meta não | PTB-XL dev STD espec 69→67% (sens 69→68%); STE FP 87→94 (UDMI-4 mulher 1,5 mm sobe FP por construção). Após E2: STD 88/322, STE 0/73 |
| E2 delineação (D) | feito, meta sim (dev) | LUDB dev QRS on 39,8→55,6%, off 58,7→70,9%, QRS global 52,5→74,4%, QT 68,1→78,8%. QTDB: on 28→39%, off 50→45% (piorou) |
| E3 marca-passo/FA (C) | feito, quase | PPV FA 0,771→0,796 (meta 0,80), sens 0,854→0,842; FP IAM em PACE 32→9; regra PACE sens 0,61 |
| E4 NORM/IVCD (D) | feito, meta não | NORM como normal 68,6→74,5% (meta 80); IVCD só ≥120 ms; 110-119 = `ecg.qrs_borderline` |
| E5 P/BAV/STACH | feito parcial | Sens P LUDB 81,7→90,3%; STACH 67,7→88,5%; BAV1 30,7% (=); BAV3 0/12 (=) |
| E6 classificador | só spec | `docs/research/e6_classificador_spec.md` |
| E7 foto ECG (H) | feito parcial | 200 renders PTB-XL: utilizável 90→97,5%, Pearson mediano 0,19→0,82 (meta 0,9; perfil hard 0,10) |
| R1 IU publicado (E) | feito (amostra) | prosa fixa removida; bench IU 800 estudos (seed 0, max-side 512), números em trilha_E_log.md; rx.md ainda não regenerado |
| R2 limiar por patologia (E) | feito em dev | IU dev, sensibilidade com limiar 0,65 → limiar a 90% espec.: derrame 0,23→0,85 (AUC 0,945), cardiomegalia 0,31→0,75 (0,931), atelectasia 0,07→0,59, consolidação 0,05→0,45, pneumonia 0→0,25; pneumotórax (3 pos) fica 0,65. Otimista (IU no treino do TorchXRayVision). VinDr test pendente |
| R3 CXAS | não feito | instalação em venv separado negada/sem tempo |
| R4 estruturas não segmentadas (F) | feito | esterno/costelas/aorta-perfil = "não suportado"; lado do Shenzhen só com teste unitário (dataset indisponível) |
| R5 derrame costofrênico (E) | feito | regra acerta 1/13 derrames (sens 0,08) => rebaixada (confiança ≤0,15); escore do modelo é o sinal principal |
| R6 latência (F) | parcial | PSPNet MPS 0,6 s vs CPU 6,7 s; bench p50 6,3→3,4 s (máquina carregada); **regressão**: cauda heurística p95 0,9→24,9 s (`find_lung_pair` 9 estratégias) |
| Abdome (G) | esqueleto | `bench/abdomen_bench.py` flow/drr/gas + `docs/benchmarks/abdome_spec.md`; região 10/10 nos DICOM; nenhum achado de abdome emitido (gás = "medida/sugestivo, não validado") |
| Caso DICOM real (F) | feito | Causa: venv do servidor sem torch/torchxrayvision/pylibjpeg (instalados agora). Heurística de pulmão robusta; 10/10 região correta; ICT modelo 0,46-0,52; ICT heurístico implausível vira "não confiável" |
| IA OpenRouter (I) | feito | fallback quando sem ANTHROPIC_API_KEY; 1 laudo RX real testado (2 chamadas, Sonnet 5.5, custo de centavos) |
| Heur. Dice (F) | melhor | jsrt pulmão 0,21→0,64, coração 0,15→0,44; PAX-Ray PA pulmão 0,03→0,34 |

Suíte backend: 2 falhas pré-existentes de `tests/test_collector_litfl.py` (fixture `litfl_sample.html` ausente) + 2 falhas **dependentes de ordem** em `tests/test_rx_real_dicom.py::test_chest_segmented_with_ict[True-torax/1|2]` (passam isoladas e com os outros test_rx*; algum teste anterior da suíte deixa o modelo/estado stubado — investigar isolamento, ex. `seg_model` cache/monkeypatch).

## Pendências
1. Trilha E mesclada (bench IU em amostra de 800; rodar completo exige mais tempo/GPU).
2. Regenerar `docs/benchmarks/ecg.md` e `rx.md` no código mesclado (`python -m bench.ecg_bench` / `bench.rx_bench --report-only` após rodar) — os números novos estão só nos logs por trilha.
3. R6: limitar tentativas de `find_lung_pair` (cauda 24,9 s); medir latência com máquina ociosa.
4. BAV1 (PR enviesado ~+30 ms), BAV2/3 (N=12), NORM ≥80%, STE 0 TP: precisam de onset de P/QRS melhor ou mais dados (Chapman/CPSC, TODO em DATASETS.md).
5. E7: retificação por pontos de fuga da grade (perfil hard).
6. R3 (CXAS) em venv separado; Montgomery/Shenzhen bloqueados por robots do Open-i.
7. PTB-XL folds 9-10: queimados (rodados 1x por trilha B, C, D, E5). Próximo teste deve ser externo.
8. Limpar worktrees: `git worktree remove ~/medlens-wt/<X>` após confirmar merges.

## Decisões do médico / usuário
- Reiniciar o servidor da porta 8000 para carregar torch/torchxrayvision/pylibjpeg (instalados no `.venv`; não reiniciei).
- Credenciamento PhysioNet para VinDr-CXR (teste primário de achados RX).
- Aceitar IU via espelho HF `abdulhaseeb1308/IU-Xray` (rótulos por heurística de texto, só dev) ou fornecer outra fonte.
- Limiar STE UDMI-4 por sexo (mulher V2-V3 1,5 mm) aumenta FP: manter diretriz ou não.
- Anotar 100-150 RX de abdome (diâmetro de alça) e 30-50 perfis para R3.
- E6 (classificador IAM/HVE): decisão regulatória (SaMD, RDC 657/2022) antes de qualquer código.
- Push/deploy: não feitos (regra desta tarefa).
