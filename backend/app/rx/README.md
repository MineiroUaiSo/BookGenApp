# app/rx — análise de radiografias

Entrada: `analyze_image(img_uint8, instance_id, ds|None, *, use_model=None) -> RXImageAnalysis` e
`study_findings(list[RXImageAnalysis]) -> list[Finding]`. Dependências obrigatórias: numpy, scipy,
scikit-image, pillow (pydantic via schemas). Opcionais: `torch` + `torchxrayvision` (pesos baixados
em `~/.torchxrayvision/models_data` no primeiro uso). Variável `MEDLENS_RX_MODELS=0` desliga os modelos.

## Fluxo
1. `view.py` — região/incidência: tags DICOM (`BodyPartExamined`, `SeriesDescription`, `ProtocolName`,
   `ViewPosition`, `PatientOrientation`) e, na falta delas, heurísticas de imagem (par de campos escuros
   simétricos = tórax frontal; um campo escuro único = perfil; gás/sem ar ao redor = abdome; muito ar = extremidade).
   Sem tag, frontal assume PA (AP só é sugerida quando escápulas, via modelo, se projetam sobre os pulmões).
2. Segmentação do tórax frontal:
   - **Modelo**: `torchxrayvision.baseline_models.chestx_det.PSPNet` (14 classes: clavículas, escápulas, pulmões,
     hilos, coração, aorta, face diafragmática, mediastino, "Weasand"=traqueia, coluna), entrada 512x512, `sigmoid>0.5`,
     maior componente por classe. Aceito só se ambos os pulmões e o coração têm área plausível; senão cai no fallback.
   - **Fallback heurístico** (`seg_heuristic.py`, `origin="heuristic"`, confiança baixa): Otsu + morfologia para os dois
     pulmões; lacuna entre pulmões por linha → mediastino (acima) e coração (onde a lacuna alarga, até 88% da altura
     pulmonar); coluna por perfil de brilho; traqueia = tubo escuro vertical no mediastino superior; clavículas = cristas
     (Sato + orientação ~horizontal) no quinto superior; arcos costais (aproximado) por filtro de cristas dentro dos pulmões;
     diafragma = contorno inferior dos pulmões; "aorta" = zona do botão aórtico (muito aproximada).
   - Perfil: heurística (campo pulmonar único `lung_field`, `heart`, `spine`, `sternum`, `trachea`, `diaphragm`).
     O lado posterior vem de `PatientOrientation` ou do brilho da faixa externa; `quality["orientação"]` informa.
   - Abdome: gás intestinal (`bowel_gas`, "alças intestinais (gás)"), coluna, ossos da pelve; maior lúmen gasoso (mm se há spacing).
   - Outras regiões: ossos por limiar (`bones`).
3. Classificação auxiliar (`model_scores`): DenseNet121 `densenet121-res224-all` (18 patologias), só em tórax frontal, em try/except.
4. Medidas (`measure.py`), com `drawing` em pixels da imagem original: ICT (largura máx. do coração / largura dos campos pulmonares
   como proxy da largura torácica interna), largura torácica, desvio traqueal (mm ou px, e % da largura), ângulos costofrênicos,
   diferença de altura das cúpulas (+ = direita mais alta), largura do mediastino (nível do botão aórtico), razão de área E/D.
   Valores em mm só se houver `PixelSpacing`/`ImagerPixelSpacing` (senão `unit="px"`). `quality`: rotação, inspiração, penetração,
   incidência, segmentação, observações.
5. `findings.py`: regras pt-BR com evidência e referências (`felson_2025`, `fleischner_glossary`, `squire`, `xrv_cohen_2022`):
   `rx.cardiomegaly` (ICT>0,50 em PA; em AP só "borderline"), `rx.mediastinal_widening`, `rx.tracheal_deviation`,
   `rx.costophrenic_blunting_{right,left}`, `rx.hemidiaphragm_elevation_{left,right}`, `rx.lung_volume_asymmetry`,
   `rx.technique_limitations`, `rx.bowel_gas_distension`, e `rx.model.<patologia>` ("Sugestivo de ..."; `origin="model"`; escore >= 0,65).

Convenção: no frontal, pulmão direito do paciente = lado esquerdo da imagem (as medidas deduzem o lado pelos centróides, então
imagens espelhadas também funcionam com o modelo). Todas as máscaras são PNG binário (0/255) no tamanho da imagem renderizada.
Chaves de estruturas: `right_lung, left_lung, lung_field, right_hilum, left_hilum, heart, aorta, mediastinum, trachea, spine,
right_clavicle, left_clavicle, right_scapula, left_scapula, ribs, sternum, diaphragm, right_diaphragm, left_diaphragm,
bowel_gas, pelvis_bones, bones`.
