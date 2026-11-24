# Bibliografia-base do MedLens

Síntese da pesquisa em `docs/research/` (ecg_bibliografia.md, rx_bibliografia.md, ecg_ferramentas.md, rx_ferramentas.md).
[V] = edição confirmada em ficha de editora/catálogo durante a pesquisa · [NV] = conferir antes de citar formalmente.
O repositório guarda **só citações e critérios reescritos** (`knowledge/*.yaml`). PDFs licenciados do usuário ficam em `knowledge/private/` (fora do git).

## ECG — leitura, medidas e condução

| # | Obra | Edição | Para que serve no MedLens |
|---|---|---|---|
| 1 | **Diretriz da SBC sobre Análise e Emissão de Laudos Eletrocardiográficos** — Samesima N et al., Arq Bras Cardiol 2022;119(4):638-680 (acesso aberto) + errata dez/2022 | 2022 [V] | Formato e terminologia do laudo em pt-BR; critérios brasileiros (BRE/BRD, sobrecargas, BAV). |
| 2 | **AHA/ACCF/HRS Recommendations for the Standardization and Interpretation of the ECG**, Partes I–VI (Circulation 2007/2009, acesso aberto) | 2007–2009 [V] | Definição de ondas, pontos de medida, QT, bloqueios de ramo, hipertrofia, isquemia — referência da delineação. |
| 3 | **Marriott's Practical Electrocardiography** — Strauss DG, Schocken DD | 13ª ed., 2020/21 [V] | Raciocínio diagnóstico e diferenciais. |
| 4 | **Clinical Electrocardiography: A Textbook** — Bayés de Luna A | 4ª ed. 2012 [V]; 5ª ed. 2021/22 [NV] | Correlação eletrofisiológica e condução — base da animação SA→AV→His→ramos→Purkinje. |
| 5 | **Goldberger's Clinical Electrocardiography: A Simplified Approach** — Goldberger AL, Goldberger ZD, Shvilkin A | 10ª ed., 2023 [V] | Roteiro sistemático de leitura. |

Âncoras de critério: Definição Universal de IM (4ª, 2018; 5ª, 2026 [NV] — conferir limiares de ST), ESC 2021 Marcapasso/CRT, ESC 2022 Arritmias Ventriculares, Critérios Internacionais para atletas.
Tier 2: Chou's (Surawicz & Knilans, 6ª), Josephson's Clinical Cardiac Electrophysiology, Braunwald (cap. ECG), Minnesota Code, Tranchesi/Moffa (7ª), IEC 60601-2-25 (tolerâncias de medida).
Tier 3 (didáticos): Hampton, Dubin, Schamroth.

## RX — estruturas, sinais e diferenciais

| # | Obra | Edição | Para que serve no MedLens |
|---|---|---|---|
| 1 | **Fleischner Society: Glossary of Terms for Thoracic Imaging** — Bankier AA et al., Radiology 2024;310:e232558 (acesso aberto) | 4ª ed., 2024 [V] | Vocabulário oficial dos achados (consolidação, vidro fosco, sinal da silhueta…). |
| 2 | **Felson's Principles of Chest Roentgenology** — Goodman LR | 5ª ed., 2021 [V] (6ª anunciada) | Método de leitura PA/perfil, sinal da silhueta, lobos e segmentos. |
| 3 | **Diagnostic Imaging: Chest** — Rosado-de-Christenson ML, Martínez-Jiménez S | 3ª ed., 2021 [V] | Estrutura por diagnóstico → fácil de converter em critérios YAML. |
| 4 | **Webb & Higgins' Thoracic Imaging** — Henry TS, Ordovás KG | 4ª ed., 2024 [V] | Diferenciais, mediastino, dispositivos. |
| 5 | **Keats & Anderson — Atlas of Normal Roentgen Variants That May Simulate Disease** | 9ª ed., 2012 [V] | Variantes normais: evita falso-positivo (ossos, abdome, tórax). |
| 6 | **RadLex** (RSNA, gratuito) | v4.x [V] | IDs padronizados para estruturas e achados. |

Tier 2: Chest X-Ray Made Easy (5ª, 2022), Squire's Fundamentals of Radiology (7ª, 2018, Harvard UP), Brant & Helms (5ª, 2018), Weir & Abrahams' Imaging Atlas of Human Anatomy (6ª, 2020), Gore & Levine GI Radiology (5ª, 2021), Greenspan's Orthopaedic Imaging (7ª 2020 / 8ª 2025), Merrill's Atlas of Radiographic Positioning (15ª, 2022), Abdominal X-Rays Made Easy (Begg, 2ª, 2006).
Brasileiros a confirmar [NV]: série CBR "Tórax" (Elsevier), Marchiori & Santos "Introdução à Radiologia", consenso brasileiro de terminologia torácica (J Bras Pneumol 2010).

## Ferramentas e modelos usados (licenças abertas)
- ECG: implementação própria de delineação (NeuroKit2/wfdb opcionais), digitalizador próprio (OpenCV/scikit-image). Validar em **LUDB** e **PTB-XL** (próximo passo).
- RX: **torchxrayvision** (PSPNet ChestX-Det 14 estruturas + DenseNet 18 patologias; Cohen et al., MIDL 2022), fallback clássico.
- 3D: casco visual + prior anatômico (numpy/scikit-image/trimesh) — modelos X2CT/PerX2CT descartados (treinados em DRR sintético, licença NC).
- Evitar: HuBERT-ECG e CXAS (CC BY-NC), ECGdeli (GPL/MATLAB).
