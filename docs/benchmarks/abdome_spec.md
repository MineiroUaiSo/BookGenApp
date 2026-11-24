# Benchmark de abdome - especificacao (esqueleto)

Estado atual: so heuristica (`backend/app/rx/seg_heuristic.py::segment_abdomen`) e um achado de gas
(`backend/app/rx/findings.py::_abdomen_findings`, lumen gasoso >= 60 mm). Nao ha verdade de referencia.
Este documento define como medir. Implementacao: `backend/bench/abdomen_bench.py`.

## (a) Fluxo regiao / incidencia / polaridade (modo `flow`)
- Entrada: DICOM em `$MEDLENS_DICOM_EXAMPLES` (padrao `~/Downloads/dicom-exemplos`; subpastas `abdome/` e `torax/`). Nao copiar para o repo.
- Verdade de regiao: nome da subpasta (abdome -> abdomen ou pelvis aceitos; torax -> chest).
- Registra por arquivo: Modality, ViewPosition, BodyPartExamined, PhotometricInterpretation (MONOCHROME1 = polaridade invertida
  tratada pelo loader), regiao/incidencia detectadas por `analyze_image`, e se uma inversao extra foi aplicada (nota de polaridade).
- Metrica: acuracia de regiao (k/n com IC de Wilson). Amostra de 10 arquivos: indicativo, nao estatistica.

## (b) Segmentacao (modo `drr`)
- Verdade sintetica: TC abdominal + mascaras do TotalSegmentator (coluna, pelve, femures, rins, figado, gas intestinal).
- DRR AP: soma de atenuacao ao longo do eixo antero-posterior (HU -> mu linear, soma, Beer-Lambert normalizado);
  mascaras 3D projetadas com `any` no mesmo eixo.
- Metrica: Dice por estrutura entre a mascara da heuristica/modelo no DRR e a projecao da verdade.
- Limites: DRR nao tem a textura/ruido de RX real (gap de dominio); gas e femures podem sair do campo. Viabilidade: so TC
  real < 1 GB e sem credencial; nibabel e opcional (`requirements-optional`). Sem TC disponivel, so o teste unitario sintetico roda.

## (c) Gas / diametro de alca (modo `gas`)
- Pendencia do medico: 100-150 RX reais com o maior diametro de alca anotado (mm) em CSV
  (`image,diameter_mm[,pixel_spacing_mm]`; `image` = caminho DICOM/PNG, relativo ao CSV).
- Metrica: MAE (mm), vies, e sensibilidade/especificidade do limiar de 60 mm. Limiares ajustados so em dev; teste unico no fim.
- Enquanto nao houver CSV, o modo apenas valida o formato.

## (d) Politica de achados
- Nenhum achado de abdome alem do gas e emitido sem rotulo de radiologista.
- O achado de gas segue como "medida/sugestivo, nao validado" (borderline, confianca baixa) ate haver (c).
