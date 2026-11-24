# Trilha G - benchmark de abdome (log)

Commits: spec 7631ea3; abdomen_bench+testes ok 3 files changed, 285 insertions(+), 1 deletion(-)
ok
8999e6c.

## Modo flow - 10 DICOM de ~/Downloads/dicom-exemplos
Comando: `cd backend && MEDLENS_BENCH_DIR=... PYTHONPATH=. python -m bench.abdomen_bench flow` (use_model=off)

Acuracia de regiao nos decodificaveis: 100% (5/5). 5/10 nao decodificam: JPEG Lossless (1.2.840.10008.1.2.4.70) exige
gdcm ou pylibjpeg no venv (nao instalados; pendencia de ambiente).

| arquivo | photometric | ViewPosition | BodyPart | regiao | incidencia | inversao extra | ok |
|---|---|---|---|---|---|---|---|
| abdome/1_TCGA-BLCA | MONOCHROME1 | - | ABDOMEN | abdomen | OTHER | nao | sim |
| abdome/2_TCGA-BLCA | MONOCHROME1 | AP | ABDOMEN | abdomen | AP | nao | sim |
| abdome/3_MIDRC-RICORD-1C | MONOCHROME2 | AP | ABDOMEN | - | - | - | sem decodificar |
| abdome/4_MIDRC-RICORD-1C | MONOCHROME1 | AP | ABDOMEN | - | - | - | sem decodificar |
| abdome/5_MIDRC-RICORD-1C | MONOCHROME1 | AP | ABDOMEN | - | - | - | sem decodificar |
| torax/1_COVID-19-AR | MONOCHROME1 | - | CHEST | chest | AP | nao | sim |
| torax/2_COVID-19-AR | MONOCHROME1 | - | CHEST | chest | AP | nao | sim |
| torax/3_COVID-19-AR | MONOCHROME1 | - | CHEST | chest | AP | nao | sim |
| torax/4_MIDRC-RICORD-1C | MONOCHROME2 | AP | CHEST | - | - | - | sem decodificar |
| torax/5_MIDRC-RICORD-1C | MONOCHROME2 | AP | CHEST | - | - | - | sem decodificar |

Observacoes: MONOCHROME1 tratado pelo loader (nenhuma inversao extra necessaria nos 5 decodificados). A incidencia do abdome 1
saiu OTHER (sem tag ViewPosition; heuristica de incidencia nao decide em KUB) - ponto a investigar.

## Modo drr / gas
- drr: so teste unitario sintetico (nibabel ausente; nenhuma TC baixada). Dice real pendente.
- gas: formato CSV validado por teste; sem anotacoes do medico (pendencia). MAE nao medido.

## Findings
Achado de gas: label agora "... - medida/sugestivo, nao validado". Nada mais alterado em findings.py. Suite: so as 2 falhas
pre-existentes de test_collector_litfl.py.
