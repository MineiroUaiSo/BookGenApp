# Trilha r2-hyg (Acao 1, higiene) - log

Worktree: /Users/macbook/medlens-wt/r2-hyg (branch wt/r2-hyg). Python: backend/.venv do repo principal.
Env: PYTHONPATH=. MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets (rodar em backend/).

## Commits
- T1 fix(rx): explicit use_model overrides MEDLENS_RX_MODELS env (tests/test_rx_use_model_precedence.py; tests/test_rx.py stub ajustado)
- T2 test: scope MEDLENS_RX_MODELS=0 to test_integration via fixture
- T3 test: synthetic LITFL-style fixture (backend/tests/data/litfl_sample.html, force-added: data/ is gitignored; texto e URLs fictícios)
- T4 perf(rx): memoise find_lung_pair, 384px search, CPU-time budget
- T5 fix(api): /health real import checks + frontend banner

## T4 numeros (bench masks heur, --limit 100 --workers 2 --models off; cache isolado via MEDLENS_BENCH_DIR)
Comando: MEDLENS_BENCH_DIR=<dir> python -m bench.rx_bench --source masks --limit 100 --workers 2 --models off --out <md em scratch>
(atencao: --out e o relatorio .md; sem MEDLENS_BENCH_DIR o cache vai para /Users/macbook/medlens/data/bench/rx, o do repo principal.)

| metrica | antes | depois |
|---|---|---|
| jsrt lungs Dice | 0.636 | 0.636 |
| jsrt heart Dice | 0.444 | 0.444 |
| rx_masks_other PA lungs Dice | 0.336 | 0.348 |
| rx_masks_other PA heart Dice | 0.372 | 0.387 |
| ICT MAE jsrt | 0.116 | 0.116 |
| latencia analyze p50 / p95 (200 itens) | 0.48 / 10.11 s | 0.86 / 1.81 s |
| jsrt p95 | 0.73 s | 1.54 s |
| rx_masks_other p95 | 10.83 s | 2.16 s |

Ressalva: o "depois" rodou com load average 40-130 na maquina (outras trilhas), o "antes" com maquina ociosa; p50 do jsrt subiu por carga, nao por codigo. Meta p95 < 1.5 s NAO confirmada (1.81 s sob carga); refazer com maquina ociosa.
Desvio: teto de 3 tentativas custou 0.014 de Dice pulmao (0.622; 2 imagens jsrt ganham so nas tentativas 6 e 9), entao ficou 9 tentativas, limitadas por orcamento de 1 s de CPU, imagem reduzida a 384 px e memoizacao (LRU 8, inclui negativo). Dice nao caiu.
dicom-exemplos (models off): regiao inalterada nos que existiam; ICT torax/3 0.637->0.620, torax/4 0.561->0.568, torax/5 0.645->0.683; tempo 4-13 s -> 0.9-3 s. Os DICOM foram reorganizados durante a rodada (abdome/3,4 viraram torax-tag-errada/3,4).

## Suite completa
pytest -q -p no:cacheprovider: 0 falhas (exit 0), incl. test_rx_real_dicom torax/1 e torax/2 [True].

## T5
Frontend: tsc --noEmit ok, vite build ok (outDir em scratch), vitest 29 passed. /health primeira chamada leva ~10 s (carrega torch+PSPNet); acima de 10 s reporta "erro: carregamento excedeu 10 s" e o frontend re-consulta 1x apos 15 s.

## Pendente (nao feito)
- T6 (tag DICOM x conteudo, tórax rotulado ABDOMEN; region_uncertain na API + seletor na UI; testes nos 10 DICOM): NAO iniciada (pedido de outra sessao, orcamento critico). Pontos de partida: backend/app/rx/view.py:146 region_from_tags e :156 (modelo so roda se region in (None, CHEST)).
- Refazer bench T4 com maquina ociosa para confirmar p95 < 1.5 s.
- Linhas heur extras foram anexadas por engano ao cache do repo principal (/Users/macbook/medlens/data/bench/rx/seg.jsonl) por uma rodada abortada; rows de modo heur, codigo do commit f9b3def.
- docs/benchmarks/ecg.md e rx.md nao regenerados (conforme instrucao).
