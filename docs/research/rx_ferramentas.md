# Pesquisa de ferramentas abertas para RX (MedLens)

Data: 2026-11-24. Legenda de confiança: **[V]** verificado nesta pesquisa (fonte aberta consultada), **[M]** conhecimento prévio do autor, não reconfirmado (checar LICENSE/model card antes de depender). Licenças de pesos costumam diferir da licença do código; sempre conferir.

## 0. Resumo executivo

- **Tórax frontal**: torchxrayvision PSPNet (14 estruturas) é a base, roda em CPU, pesos abertos. CXAS (PAX-Ray++, ~157-159 classes, frontal e lateral) é o upgrade opcional, mas licença dos pesos/dados provavelmente não comercial.
- **Perfil**: não existe segmentador de perfil leve e bem estabelecido em torchxrayvision. Opções: CXAS (inclui lateral), CheXmask/HybridGNet (apenas frontal), ou fallback geométrico/heurístico. Deixar o perfil como "melhor esforço" com qualidade sinalizada.
- **Classificação**: torchxrayvision DenseNet121 (pesos `densenet121-res224-all`) em CPU, só como sinal auxiliar.
- **VLM**: MAIRA-2 e CheXagent são pesados (7-8B), licenças restritivas/não comerciais [M]; em CPU são inviáveis na prática. Recomendação: Claude com visão (já no plano) + medidas determinísticas; modelos médicos opcionais em GPU futura.
- **3D**: nenhum modelo aberto (X2CT-GAN, PerX2CT) é confiável em RX clínicos reais (treinados em projeções sintéticas de CT; PerX2CT com pesos CC BY-NC 4.0 [V]). Abordagem recomendada e honesta: **casco visual por estrutura a partir das máscaras PA + Perfil, regularizado por prior elipsoidal**, rotulado "aproximação".
- **Viewer**: manter render no backend (pydicom, PNG 8-bit) para o MVP; cornerstone3D no frontend como evolução. three.js/glTF para 3D.

## 1. Segmentação anatômica de tórax

### 1.1 torchxrayvision PSPNet (ChestX-Det) [V]
- URL: https://github.com/mlmed/torchxrayvision (código Apache-2.0 [M]); pesos: https://github.com/mlmed/torchxrayvision/releases/download/v1/pspnet_chestxray_best_model_4.pth (baixados no 1º uso para `~/.torchxrayvision/`).
- **Lista exata (14, ordem da saída; `seg_model.targets`)**: Left Clavicle, Right Clavicle, Left Scapula, Right Scapula, Left Lung, Right Lung, Left Hilus Pulmonis, Right Hilus Pulmonis, Heart, Aorta, Facies Diaphragmatica, Mediastinum, Weasand (traqueia/esôfago), Spine.
  - Atenção: "Left/Right" é do **paciente** (conferir orientação na prática), "Facies Diaphragmatica" é uma única classe para diafragma, "Weasand" ≈ traqueia, e **não há classe separada de costelas**.
- API [V]:
  ```python
  import torchxrayvision as xrv
  seg = xrv.baseline_models.chestx_det.PSPNet()   # eval()
  out = seg(img)          # img: tensor [1,1,H,W], valores em [-1024,1024]
  # out: [1,14,512,512] logits; usa fix_resolution -> 512x512 internamente
  masks = (torch.sigmoid(out) > 0.5)   # multi-rótulo (estruturas se sobrepõem)
  ```
  Preparação de entrada: `xrv.datasets.normalize(img_uint8, 255)` leva uint8 para [-1024,1024]; redimensionar a máscara de volta ao tamanho original com nearest/bilinear no logit.
- CPU: viável (~1-3 s/imagem em CPU moderna, ~200-400 MB RAM) [M]. Dependência: torch (+torchvision). Peso do .pth na ordem de dezenas a ~100 MB [M].
- Uso: base de `rx/segment.py`; saída = máscaras por estrutura + legenda pt-BR (mapeamento nome → rótulo/cor).
- Limitações: treinado em ChestX-Det (PA adulto); baixa qualidade em AP deitado, pediátrico, próteses, perfil.

### 1.2 CXAS (Chest X-ray Anatomy Segmentation) [V parcial]
- URL: https://github.com/ConstantinSeibold/ChestXRayAnatomySegmentation, PyPI `cxas`. Dataset PAX-Ray++ (arXiv 2306.03934): **157 classes anatômicas, frontal e lateral**; o pacote anuncia 159 classes (versão posterior).
- Licença: **inconsistente/não confirmada** (libraries.io lista AFL-3.0; metadado do dataset em academictorrents aponta CC BY-NC-SA 4.0). Tratar como **não comercial até leitura do LICENSE e dos termos dos pesos**.
- Pesos: baixados automaticamente pelo pacote (backbone tipo nnU-Net/UNet-ResNet [M]). CPU: possível, mas mais lento (dezenas de s/imagem) [M].
- Uso: backend opcional `RX_SEG_BACKEND=cxas`; entrega costelas individuais (arcos), vértebras, estruturas do mediastino, e **perfil**. Mapear classes para os mesmos grupos de estrutura do contrato (ver 7).

### 1.3 CheXmask + HybridGNet [V parcial]
- CheXmask: https://www.physionet.org/content/chexmask-cxr-segmentation-data/ (657.566 máscaras de pulmões, coração e clavículas sobre CheXpert, MIMIC-CXR, PadChest, VinDr etc.; **sem imagens**; acesso via PhysioNet, licença citada como CC BY 4.0 em artigos, mas confirmar na página; exige conta credenciada PhysioNet). Paper: arXiv 2307.03293.
- HybridGNet: https://github.com/ngaggion/HybridGNet (segmentação baseada em grafo de landmarks: pulmões, coração, clavículas; saídas **anatomicamente plausíveis**). Licença do repo: GPL-3.0 sugerida em citação de terceiros para CheXmask-U, **confirmar** [M]. Pesos no Google Drive/Zenodo do autor [M]. CPU ok (modelo pequeno) [M].
- Uso: alternativa/validação cruzada para pulmões+coração (ICT mais robusto) ou dataset de treino; GPL é um risco se o projeto for distribuído fechado.

### 1.4 Perfil, costelas, supressão óssea
- **Perfil**: CXAS (PAX-Ray++) é a única opção aberta ampla que encontrei com classes laterais [V parcial]. Sem ela: fallback heurístico (limiar de intensidade + atlas de posição relativa). O contrato de `recon3d` deve aceitar máscaras do perfil de qualquer origem.
- **Costelas**: VinDr-RibCXR (https://physionet.org/content/vindr-ribcxr/ , 245 CXR com 20 costelas por lado, PhysioNet, uso científico; treinar U-Net é possível, sem pesos oficiais garantidos [M]). Alternativa pronta: classes de costela do CXAS. Uso: contagem de arcos posteriores (inspiração adequada: 9-10).
- **Supressão óssea**: modelos acadêmicos (ex.: ResNet-BS, métodos GAN/diffusion) com pesos esparsos/instáveis [M]; **não recomendado** no MVP. Alternativa barata para realce: CLAHE/unsharp no viewer.

## 2. Classificação de patologias e incidência

### 2.1 torchxrayvision classificadores [M, API conhecida]
- `xrv.models.DenseNet(weights="densenet121-res224-all")` (18 patologias: Atelectasis, Consolidation, Infiltration, Pneumothorax, Edema, Emphysema, Fibrosis, Effusion, Pneumonia, Pleural_Thickening, Cardiomegaly, Nodule, Mass, Hernia, Lung Lesion, Fracture, Lung Opacity, Enlarged Cardiomediastinum). Outros pesos: `-chex`, `-mimic_nb`, `-mimic_ch`, `-nih`, `-pc`, `-rsna`, `-kaggle`. Entrada 224x224, [-1024,1024].
- Licença: código Apache-2.0; pesos treinados em datasets públicos com termos próprios [M]. CPU: ~0,2 s/imagem. Uso: `rx/classify.py`, saída em probabilidades, sempre rotulada "auxiliar, não é laudo"; usar `xrv.models.ResNet` e `ae` (autoencoder, OOD) para sinalizar imagem fora de distribuição.
- Calibração fraca fora do domínio; evitar thresholds fixos.

### 2.2 Classificação de incidência (PA/AP/Perfil)
- Ordem de preferência: (1) tags DICOM `ViewPosition`, `PatientOrientation`, `SeriesDescription` (2) heurística de imagem: perfil tem escápulas/braços sobrepostos e assimetria com coluna na lateral, largura/altura do campo pulmonar, razão de simetria; (3) classificador CNN pequeno treinado em CheXpert (`Frontal/Lateral`, `AP/PA`) – não encontrei pesos abertos estáveis [M]. Recomendação: tags + heurística (simetria esquerda/direita da máscara pulmonar do PSPNet: simétrica → frontal; PSPNet com área pulmonar/hilos anômalos → perfil). Distinguir AP/PA só por tag + sinais (escápulas sobre campos pulmonares, magnificação cardíaca).
- Tipo de região (tórax/abdome/MSK): `BodyPartExamined`, `StudyDescription`; fallback: Claude com visão.

## 3. Abdome e musculoesquelético
- **Abdome (radiografia simples)**: não há segmentador aberto maduro. TotalSegmentator (https://github.com/wasserth/TotalSegmentator, Apache-2.0, pesos abertos; algumas tarefas com licença comercial separada [M]) é para **CT/MR**, não RX. Recomendação: sem segmentação abdominal automática; usar Claude visão para descrever alças, gás, níveis, calcificações, psoas, ossos; apenas medidas de qualidade (pixel spacing, janela). Possível futuro: CXAS cobre parte superior do abdome em CXR.
- **MSK**: MURA (Stanford, classificação normal/anormal em 7 regiões; dataset com termos de uso de pesquisa, modelos comunitários sem pesos oficiais) [M]; FracAtlas (CC BY 4.0 [M]); GRAZPEDWRI-DX (pediátrico punho, CC BY 4.0 [M], YOLOv8 comunitário); RSNA Bone Age (modelos comunitários). Recomendação: **descrição guiada pelo Claude + checagem de qualidade**, sem classificador MSK no MVP; deixar ponto de extensão `rx/msk.py`.

## 4. Modelos visão-linguagem médicos vs VLM geral
| Modelo | URL | Licença (confirmar) | Tamanho | CPU |
|---|---|---|---|---|
| MAIRA-2 (Microsoft; relatório com grounding, usa frontal + lateral + prior) | https://huggingface.co/microsoft/maira-2 | MSRLA (pesquisa, não clínica) [M] | ~7B (LLaVA-like, Vicuna-7B + RAD-DINO) | inviável em CPU prática |
| CheXagent (Stanford AIMI) | https://huggingface.co/StanfordAIMI/CheXagent-8b (e 2-3b) | CC BY-NC [M] | 8B / ~3B | muito lento |
| RadFM | https://github.com/chaoyi-wu/RadFM | pesos em HF, licença acadêmica [M] | 14B | inviável |
| MedGemma (Google; 4B multimodal; versão 1.5 adiciona 3D/CT) | https://huggingface.co/google/medgemma-4b-it | Health AI Developer Foundations terms (uso permitido com condições) [M] | 4B | possível, lento (minutos) |
| LLaVA-Med / Rad-DINO / BiomedCLIP | HF Microsoft | MIT/CC [M] | variado | Rad-DINO/BiomedCLIP viáveis (embeddings) |
- A busca no HF Hub por "chest x-ray report generation" só trouxe repositórios comunitários sem tração (0 downloads) [V]; os modelos acima precisam de verificação manual na página oficial.
- Comparação (literatura 2024-2026 [M]): modelos médicos específicos produzem laudos mais fiéis ao estilo radiológico e com menos erros de lateralidade em frontal, mas **ainda alucinam e não superam laudo humano**; VLMs gerais de ponta (Claude, GPT, Gemini) tendem a pontuar menos em métricas de laudo (RadGraph-F1) mas descrevem estruturas visíveis e raciocinam melhor com contexto/medidas. Para o MedLens a camada de descrição é "estrutura a estrutura" com medidas injetadas, então Claude visão (plano) é adequado; MAIRA-2/MedGemma entrariam apenas como segunda opinião opcional com GPU.

## 5. Reconstrução 3D a partir de PA + Perfil
| Método | Código / pesos | Licença | CPU | Observação |
|---|---|---|---|---|
| X2CT-GAN (arXiv 1905.06902) | https://github.com/kylekma/X2CT ; pesos de terceiros/escassos [V parcial: não confirmei pesos oficiais] | GPL-3.0 (código) [M] | lento, 128^3 | treinado em DRRs sintéticas (LIDC); falha em RX reais |
| PerX2CT (arXiv 2303.05297) | https://github.com/dek924/PerX2CT ; pesos https://huggingface.co/KAISTEdlab/PerX2CT [V] | **CC BY-NC 4.0** (pesos) [V] | inferência possível em CPU, minutos [M] | proj. em perspectiva; modelo avisa sem garantia em RX clínicos reais [V] |
| DX2CT (difusão, arXiv 2409.08850), CT-from-biplanar com atenção coarse-fine (2408.09736) | código/pesos escassos | n/c | GPU | pesquisa |
| NeRF/Gaussian splatting biplanar (ex.: NAF, SAX-NeRF) | repositórios de pesquisa, treino por caso | vários | treino pesado, 2 vistas é sub-determinado | não prático |
| EOS / SSM (modelo estatístico de forma ajustado a contornos biplanares) | EOS é comercial/fechado; SSM de coluna/pelve existem em pesquisa; para pulmão/coração, atlas abertos (ex.: SSM de pulmão do SPHARM, SMPL-like para tórax não padrão) | n/c | CPU ok (otimização leve) | exige atlas; não há atlas torácico aberto simples |
| **Casco visual por estrutura + prior** (recomendado) | implementar (numpy, scikit-image, trimesh) | nossa | CPU, segundos | determinístico, explicável |

Conclusão: modelos aprendidos não generalizam para RX reais e têm licença NC; entregariam textura plausível mas **inventada**. Para "reconstrução aproximada honesta" por estrutura:
1. Alinhar escala/altura: PA e perfil compartilham o eixo vertical (z). Usar landmarks: ápices pulmonares, cúpulas, carina/ponta da traqueia, topo da coluna. Escala mm via PixelSpacing (se ausente, usar altura pulmonar comum e marcar "sem escala").
2. Por estrutura e por fatia z: largura em x (PA) e profundidade em y (perfil). Preencher a seção axial com **elipse** (ou superelipse) de semi-eixos (largura/2, profundidade/2) centrada pela posição; para pulmões, separar esquerdo/direito por x do PA e limitar a profundidade pelo perfil (pulmões sobrepostos no perfil → dividir profundidade proporcional; a lateralidade é ambígua → regularizar com simetria e priors).
3. Casco visual clássico (interseção das extrusões) para estruturas com silhueta visível nas duas vistas (coluna, esterno, coração); elipsóide para as demais; suavização (Laplaciana/gaussiana no volume) e marching cubes (`skimage.measure.marching_cubes`) → `trimesh` → glTF por malha nomeada com cor.
4. Se não houver perfil: extrusão elíptica com profundidade nominal por estrutura (prior), marcada "baixa confiança".
5. Metadados `method` e confiança por malha; UI exibe aviso "aproximação, não é tomografia".
Dependências: numpy, scipy, scikit-image, trimesh (glb) — todas leves e CPU.

## 6. Viewers e DICOM
- **cornerstone3D** (https://github.com/cornerstonejs/cornerstone3D, MIT [M]) e **OHIF** (https://github.com/OHIF/Viewers, MIT [M]): excelentes para DICOM (WL/WW, zoom, medidas, WADO). Para o MVP, o backend renderiza PNG 8-bit (contrato `render.png?wc=&ww=`) e o frontend usa canvas + overlays; cornerstone3D (pacotes `@cornerstonejs/core`, `tools`, `dicom-image-loader`) pode ser adotado depois para régua/janela interativa. OHIF completo é pesado demais para embutir.
- **dcmjs** (https://github.com/dcmjs/dcmjs, MIT [M]): parsing/escrita DICOM no browser; útil se o frontend ler tags para pasta inteira antes do upload.
- **pydicom** (MIT [M]) no backend:
  - `pydicom.pixels.apply_voi_lut(arr, ds)` (v3: `pydicom.pixels.apply_voi_lut`; em v2 `pydicom.pixel_data_handlers.util.apply_voi_lut`) aplica VOI LUT/janela; se não houver, calcular janela por percentis 1-99.
  - `apply_modality_lut` antes (RescaleSlope/Intercept).
  - **MONOCHROME1**: inverter após a janela (`max - x`) para branco = osso/alta densidade.
  - Descompressão: JPEG2000/JPEG-LS/RLE exigem `pylibjpeg` ou `gdcm`/`pillow` (`pip install pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg`).
  - mm: `PixelSpacing` (campos do detector: `ImagerPixelSpacing`; projeção radiográfica difere por magnificação, `EstimatedRadiographicMagnificationFactor` quando existir). Se só `ImagerPixelSpacing`, rotular medidas em mm como estimadas.
  - Tags úteis: ViewPosition, PatientOrientation, BodyPartExamined, PhotometricInterpretation, Modality (CR/DX).
- **three.js/glTF**: `@react-three/fiber` + `GLTFLoader`; malhas nomeadas por estrutura (`node.name`), materiais com transparência para pulmões; DRACO/Meshopt não necessários no tamanho esperado. Backend exporta glb via `trimesh.Scene.export(file_type="glb")`.

## 7. Stack recomendada

### backend/app/rx
- Dependências opcionais (import preguiçoso, extras `rx` no pyproject): `torch` (CPU), `torchvision`, `torchxrayvision`, `scikit-image`, `opencv-python-headless`, `scipy`; extra `rx-cxas`: `cxas` (NC, opt-in).
- Módulos sugeridos:
  - `view.py`: tags DICOM → heurística de simetria (máscara pulmonar) → {PA, AP, LATERAL, ABDOME, EXTREMIDADE, DESCONHECIDO}.
  - `segment.py`: backend `xrv_pspnet` (padrão), `cxas` (opcional), `none`. Saída: dict estrutura → máscara bool no tamanho original, mais mapa pt-BR (ex.: Weasand → "Traqueia/esôfago", Facies Diaphragmatica → "Diafragma", Hilus → "Hilo"). Pós-processamento: maior componente conexo por pulmão, fechamento morfológico, checagem de plausibilidade (área mínima, Left/Right não trocados pela posição do coração).
  - `measure.py`: ICT (largura máxima do coração ÷ largura interna do tórax, a partir das máscaras de coração e pulmão), desvio traqueal (centroide de Weasand vs. linha média da coluna), cúpulas (topo da máscara do diafragma/pulmão), ângulos costofrênicos aproximados, rotação (clavículas × coluna), penetração (intensidade da coluna através do coração). Sempre com `confidence`.
  - `classify.py`: `densenet121-res224-all` + OOD (autoencoder) → probabilidades auxiliares.
  - `__init__.analyze_image` conforme contrato; falha dos modelos devolve estruturas vazias + `warnings`.
- Cache de modelos em `$MEDLENS_DATA/models` (definir `XRV_CACHE`/cache_dir) e `torch.set_num_threads`. Em testes, mocks sem torch.
- Licenciamento: manter o padrão 100% permissivo (PSPNet + DenseNet); NC apenas por opt-in documentado.

### backend/app/recon3d
- `numpy`, `scipy.ndimage`, `scikit-image` (marching_cubes), `trimesh` (glb). Sem PyTorch.
- Pipeline: landmarks verticais comuns → reamostragem das máscaras para grade z comum → modelo por estrutura (casco visual ∩ elipse prior) → suavização → malha → glb. Retorna `(glb, meshes, method)` com `method="visual_hull+ellipsoid_prior"` e aviso.
- Opcional futuro (não padrão): PerX2CT como "visualização de curiosidade" apenas com aviso de não comercial e de ausência de validação.

### Frontend
- RX: canvas + PNG do backend + máscaras (RLE ou PNG por estrutura), legenda clicável; migrar para cornerstone3D se precisar de medidas interativas. 3D: `@react-three/fiber` + glTF.

## 8. Riscos e pendências
- Verificar manualmente: licença dos pesos do CXAS, licença do HybridGNet, termos de MAIRA-2/CheXagent/MedGemma, acesso PhysioNet (credenciamento).
- Perfil: sem modelo leve e sólido; qualidade de 3D dependerá disso. Priorizar CXAS opt-in ou entrada manual de landmarks.
- Nada aqui é validado clinicamente; todo resultado deve ser apresentado como apoio ao ensino/decisão.

## Fontes consultadas
- https://raw.githubusercontent.com/mlmed/torchxrayvision/master/torchxrayvision/baseline_models/chestx_det/__init__.py
- https://pypi.org/project/cxas/ , https://arxiv.org/abs/2306.03934
- https://www.physionet.org/content/chexmask-cxr-segmentation-data/ , https://arxiv.org/abs/2307.03293
- https://huggingface.co/KAISTEdlab/PerX2CT , https://arxiv.org/abs/2303.05297 , https://arxiv.org/abs/1905.06902
