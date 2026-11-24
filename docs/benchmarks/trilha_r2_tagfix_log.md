# Trilha r2-tagfix — RX de tórax tratado como abdome

Causa: `view.py` confiava em BodyPartExamined/SeriesDescription (tag vence a imagem) e só rodava o modelo de tórax se região in (None, CHEST).

## Mudanças
- `detect_view_region`: com modelos ligados, audita tags ABDOMEN/PELVIS/SPINE com o PSPNet de tórax; par pulmonar + coração (chest_frontal) => região=CHEST, `region_conflict`, aviso "tag DICOM diz X mas a imagem parece tórax". Perfil torácico sob tag abdominal => `region_uncertain`. Tag CHEST + modelo sem tórax + heurística abdome => `region_uncertain`.
- `region_uncertain`: análise abstém (sem segmentação/medidas/achados), warning na API.
- API: `RXRequest.region_overrides {instance_id: região}` reanalisa com a região escolhida (`analyze_image(region_override=)`); UI: aviso + seletor "Reanalisar" (RXViewer/StudyView).
- ViewPosition e polaridade: NÃO alterados (sem evidência de erro nos 10 casos; AP/PA não é distinguível pela imagem). Polaridade já arbitrada pelo modelo só sem tag PhotometricInterpretation.

## Tabela dos 10 DICOM (modo modelo, rodada antes → depois)
| caso | tag | antes | depois |
|---|---|---|---|
| abdome/1,2,5 | ABDOMEN | abdomen | abdomen |
| torax-tag-errada/3 | ABDOMEN | abdomen (ERRADO) | chest + aviso |
| torax-tag-errada/4 | ABDOMEN | abdomen (ERRADO) | chest + aviso |
| torax/1-5 | CHEST | chest | chest |

Bench (`python -m bench.rx_region_bench --mode model`): 10/10 corretos; 'tag divergente' 2/2 corretos, 2/2 com aviso. Modo heurístico (--mode heur, sem modelo): 8/10 (os 2 mal-etiquetados continuam abdome: detecção exige o modelo; limitação).

## Comandos
`cd backend && MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -p no:cacheprovider` (suíte completa sem falhas; 14 testes novos em tests/test_rx_tag_divergence.py); `python -m bench.rx_region_bench --mode model|heur`; `npx tsc --noEmit` no frontend (0 erros).

## Dados
DICOM NÃO copiados para tests/data: PatientName/ID são pseudônimos TCIA (ex. MIDRC-RICORD-1C-SITE2-000204), StudyDate preenchida (datas deslocadas) e arquivos de 6-17 MB. Testes referenciam por caminho com skip.

## Não feito
abdomen_bench/rx_bench --source dicom-exemplos não rodados (orçamento crítico; rx_bench não tem essa fonte, criado rx_region_bench); vitest do frontend não rodado; sem verificação visual do seletor no navegador; sem push.

## Commits
c93e430 fix(rx) região; 7262755 feat(ui); 6aae79a test(rx)+bench; (+ este log)
