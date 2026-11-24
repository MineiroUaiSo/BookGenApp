# Trilha A log (dados + salvaguardas)

## LUDB delineacao, separada dev/teste (antes: ecg.md misturava 1-200)
Comando: `cd backend && MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench PYTHONPATH=. python -m bench.ecg_bench --source ludb --tag _trilhaA --workers 3`
(metricas por registro inalteradas; so o agrupamento mudou; commit e938b77; sem mudanca de limiares).

| Split | N | QRS on/off dentro da tol. CSE | P on | T off | Se QRS/P/T |
|---|---|---|---|---|---|
| dev (1-160) | 160 | 40% / 59% | 50% | 81% | 99% / 82% / 93% |
| teste (161-200) | 40 | 37% / 61% | 50% | 88% | 100% / 91% / 97% |

PTB-XL folds 9-10 nao foram rodados nesta trilha (queimados).

## Dados (manifests em /Users/macbook/medlens/data/datasets)
ludb 200, ptbxl 3000, qtdb 105, jsrt_masks 247, rx_masks_other (PAX-Ray++ test) 800, iu_xray 5910 (espelho HF). Montgomery/Shenzhen: nao baixados (Open-i robots Disallow). VinDr-CXR: pendencia do usuario (credencial PhysioNet).
Commits ate aqui: ver git log de wt/A (HEAD 1a33567 antes deste commit).
