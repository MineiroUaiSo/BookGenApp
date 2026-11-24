# Trilha R2 e7abd - log (E7 foto de ECG + abdome)

Worktree: /Users/macbook/medlens-wt/r2-e7abd (branch wt/r2-e7abd). Base: f9b3def.
Ambiente: `cd backend && MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python ...`

## Parte A - E7 (foto de ECG)

Comando (mesmos 200 renders PTB-XL folds 1-8 da rodada 1; imagens identicas copiadas do run baseline para as tags novas):
`python -m bench.ecg_photo_bench --tag <TAG> --limit 200 --workers 3` (+ `--report-only`). Perfis clean/mild/hard (~67 cada).
Folds 9-10 NAO usados. O limiar de abstencao foi calibrado nesses mesmos renders dev (in-sample; sem teste final).

| metrica | antes (R2B = HEAD f9b3def) | A1 homografia (R2A1) | A1+A2 (R2A2) |
|---|---|---|---|
| Pearson mediano global | 0.823 | 0.967 | 0.967 |
| Pearson clean / mild / hard | 0.993 / 0.814 / 0.104 | 0.993 / 0.967 / 0.810 | 0.993 / 0.967 / 0.810 |
| Utilizavel (sem abstencao) | 97.5% (195/200) | 100% | 97.5% (195/200) |
| Abstencao (so FC/ritmo) | - | - | 5/200 = 2.5% (mild 1, hard 4) |
| Pearson hard, so nao abstidos | - | - | 0.785 |
| Erro mediano RR / QRS / QT (ms) | 12.9 / 56 / 52 | 6.3 / 38 / 36 (run parcial misto) | 5.7 / 36 / 36 |
| Regra na foto | - | - | WPW 27%, BRE 70%, BRD 64%, IAM 73%, NORM 30% (antes 9 / 47 / 46 / 67 / 15) |

Metas: Pearson hard >= 0.7 ATINGIDA (0.81); mediana global >= 0.9 ATINGIDA (0.967); utilizavel >= 97.5% contando abstencao como
nao utilizavel ATINGIDA no limite (97.5%, abstencao 2.5%). Ressalva: ~24 imagens (quase todas hard) seguem com Pearson < 0.5;
nao sao falha de geometria (inclinacao local residual das linhas da grade = 0 graus nos 200 renders retificados) e sim leitura de
escala (grid harmonic x5 -> layout 'strips', 5 linhas detectadas, pulso de calibracao ausente). A abstencao por CV do
espacamento (>= 0.09) captura so 1 delas; o CV nao separa bem (muitas imagens boas tem CV 0.02-0.04), por isso o limiar foi
posto no teto de ~2.5% de abstencao. Proximo passo: abstencao por inconsistencia de layout/escala (warnings 'grid pitch rescaled',
'detected N rows').

### A1 - homografia pela grade (backend/app/ecg/digitize/perspective.py)
Ajusta 4 parametros (rotacao, cisalhamento, 2 termos projetivos) maximizando a nitidez das projecoes linha/coluna do mapa de
escuridao da grade (equivale a levar os pontos de fuga ao infinito). Roda apos o warp do quad do papel (ou sozinho quando a
folha preenche o quadro). Rejeita (comportamento antigo) se no limite, ganho < 8% ou erro. skew_deg passa a ser a rotacao total
removida. ~0.6 s/imagem sem carga.

### A2 - abstencao (perspective.grid_spacing_cv, analysis._rhythm_only)
CV do espacamento das linhas da grade apos retificacao (max dos eixos) >= 0.09 -> calibration['rhythm_only']=1; analyze_signal
devolve so FC, RR e rotulo regular/irregular + aviso em portugues; sem PR/QRS/QT/eixos/ST/achados.

### A3 - ECG-Image-Database (fotos reais)
Nao executado (nao tentado; sem verificacao de download sem credencial nesta rodada). Registrado como pendencia.

## Parte B - abdome (nenhum achado novo na API/UI; continua 'nao validado')

### B1 - fluxo nos 10 DICOM (decoder atual com pylibjpeg)
`python -m bench.abdomen_bench flow` -> regiao 100% (10/10), 0 sem decodificar (antes 5/10 sem decodificar).

| arquivo | photometric | ViewPosition | BodyPart | regiao | incidencia | inversao extra |
|---|---|---|---|---|---|---|
| abdome/1_TCGA-BLCA | MONOCHROME1 | - | ABDOMEN | abdomen | OTHER | nao |
| abdome/2_TCGA-BLCA | MONOCHROME1 | AP | ABDOMEN | abdomen | AP | nao |
| abdome/3_MIDRC-RICORD-1C | MONOCHROME2 | AP | ABDOMEN | abdomen | AP | nao |
| abdome/4_MIDRC-RICORD-1C | MONOCHROME1 | AP | ABDOMEN | abdomen | AP | nao |
| abdome/5_MIDRC-RICORD-1C | MONOCHROME1 | AP | ABDOMEN | abdomen | AP | nao |
| torax/1_COVID-19-AR | MONOCHROME1 | - | CHEST | chest | AP | nao |
| torax/2_COVID-19-AR | MONOCHROME1 | - | CHEST | chest | AP | nao |
| torax/3_COVID-19-AR | MONOCHROME1 | - | CHEST | chest | AP | nao |
| torax/4_MIDRC-RICORD-1C | MONOCHROME2 | AP | CHEST | chest | AP | nao |
| torax/5_MIDRC-RICORD-1C | MONOCHROME2 | AP | CHEST | chest | AP | nao |

KUB sem tag ViewPosition (abdome/1) sai OTHER, como esperado. Polaridade: MONOCHROME1 tratada pelo loader; nenhuma inversao extra.
N=10: indicativo, nao estatistica.

### B2 - DRR a partir de TC TotalSegmentator
NAO feito (venv /Users/macbook/medlens-venvs/abd nao criado; nada baixado). Motivo: orcamento de sessao em nivel ALTO e maquina
com carga ~130; pendente. Dice coluna/pelve e regiao nos DRRs: nao medidos.

## Commits
- 5fced2e feat(digitize): grid-based homography rectification
- a16b9ed feat(digitize): abstention to HR/rhythm only when the rectified grid is irregular
- (este log + abdome_spec): ver git log

## Observacoes operacionais
- Sob carga alta (load ~130) o bench demora ~25 min; runs concorrentes com --force corrompem results.jsonl (escritas intercaladas):
  rodar uma vez por tag e reparar linhas invalidas antes de retomar.
- Suite completa (pytest -q): 4 falhas, todas fora do escopo: test_collector_litfl x2 (pre-existentes, FileNotFoundError) e
  test_rx_real_dicom::test_chest_segmented_with_ict x2 no run completo; esse arquivo passa 14/14 isolado tanto no repo principal quanto
  no worktree (sensivel a ordem/carga). Testes novos: test_digitize_perspective (3), test_ecg_rhythm_only (4); digitize/photo-bench passam.

## Pendencias / proximos passos
1. Abstencao por inconsistencia de layout/escala (aviso 'grid pitch rescaled', 'detected N rows', pulso ausente) para os ~24 renders hard com Pearson < 0.5.
2. A3 ECG-Image-Database (fotos reais) e teste final PTB-XL folds 9-10 (calibracao do limiar so em dev).
3. B2 DRR: criar venv /Users/macbook/medlens-venvs/abd (nibabel), baixar subconjunto pequeno TotalSegmentator, medir Dice coluna/pelve e regiao.
