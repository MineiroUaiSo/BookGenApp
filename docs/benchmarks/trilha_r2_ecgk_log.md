# Trilha r2-ecgk (Trilha K: digitalização derivação a derivação), log

Worktree /Users/macbook/medlens-wt/r2-ecgk, branch wt/r2-ecgk. Ferramenta de apoio a laudo, não é dispositivo certificado.

## Comandos
- Testes: `cd backend && MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_header_ocr.py tests/test_plausibility.py tests/test_caso1_regression.py tests/test_digitize.py tests/test_digitize_real.py tests/test_ecg_analysis.py`
- Bench de fotos (antes = HEAD extraído com git archive; depois = worktree): `python -m bench.ecg_photo_bench --tag k0 --limit 40 --workers 3`

## Caso1 (antes -> depois), imagem redigida em backend/tests/data/caso1_ecg.jpg (adicionada com git add -f; tests/data é ignorado)
- Layout: 6x2 (errado) -> 3x4+3 com ritmos V1/II/V5 confirmados por 5 rótulos.
- PR 94 -> 152 ms; QRS 266 -> 116 ms (mediana por derivação; união das bordas dava 170); FC 70 bpm.
- Sem pré-excitação, sem ST crítico (achados de ST retidos: ST > 4 mm isolado em V6, artefato do fim do segmento).
- R (mm): D1 33,6; aVL 11,3; V3 40,7; V4 18,3; V5 43,2; V6 34,0. Metas D1>20, aVL>20, V3-V6>30: aVL e V4 NÃO atingem (xfail).
- Cabeçalho lido: QRS 112, QT 438, QTc 482, eixos 49/20/171. PR 148 não legível (linha cortada pela borda superior; fica None de propósito). Sexo não lido.

## Bench ecg_photo_bench (40 imagens PTB-XL dev, tag k0), HEAD vs worktree
- utilizável 100% -> 100%; Pearson mediano 0,8414 -> 0,8414 (idêntico: o novo caminho só liga quando os rótulos confirmam um layout; imagens do bench não ativam).

## Commits
- K1 feat(digitize): detecção automática de layout por rótulos
- K2 feat(digitize): leitura do cabeçalho impresso
- K3 feat(ecg): plausibilidade fisiológica e checagem cruzada com o impresso
- K5 test(ecg): regressão do caso1

## Pendente (próximos passos exatos)
1. K4 (UI fallback manual por derivação + API de recortes): NÃO feito.
2. Recall de rótulos: só 5 de ~19 rótulos reconhecidos (os que tocam o traçado somem); melhorar com recorte local + remoção do traçado, ou rótulos por posição vertical de troca de derivação.
3. Separação de traços fundidos entre linhas (V4/V5/V6 na mesma coluna de pixels): rastreador linha a linha subtraindo tinta já atribuída; flags saturou_banda/trocas_de_traco.
4. Banda vertical: usado 2,0 acima / 1,0 abaixo da distância entre linhas (2,5/1,5 inflou V1 e V5).
5. Pulso de calibração: detector próprio em layout.py devolve 10 mm/mV e 25 mm/s; o legado ainda avisa 6,5 mm (ignorado).
6. Checagem faixa x trecho da mesma derivação (corr >= 0,9) não implementada; Einthoven (razão 0,69) e Goldberger (0,16) ativos só na plausibilidade.
7. Falhas pré-existentes no worktree (fixtures ausentes por tests/data ignorado): test_collector_litfl (2) e test_rx_real_dicom torax (2).
