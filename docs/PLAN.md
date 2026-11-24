# MedLens — Leitor de ECG e RX com IA (plano mestre)

> Ferramenta de **apoio à decisão / ensino**. Não é dispositivo médico certificado (ANVISA/FDA).
> Todo laudo gerado é rascunho que exige revisão por médico.

## 1. Objetivo

Dois leitores numa só aplicação web:

| Leitor | Entradas | Saída principal |
|---|---|---|
| **ECG** | DICOM (12-lead Waveform IOD, pasta inteira), HL7 aECG XML, CSV/WFDB, **foto/print de alta resolução** | Cada onda identificada (P, Q, R, S, T, U) em cada derivação, intervalos e durações medidos, eixo, destaque visual por onda, animação da condução cardíaca (SA → átrios → AV → His → ramos → Purkinje → ventrículos) isolada e em conjunto, descrição minuciosa, análise crítica com literatura |
| **RX** | DICOM (pasta inteira, várias séries/incidências), PNG/JPG/print | Segmentação e legenda de cada estrutura (ossos, pulmões, coração, traqueia, diafragma, mediastino, aorta, clavículas, escápulas, coluna, alças intestinais...), medidas (índice cardiotorácico etc.), **reconstrução 3D aproximada a partir de PA + Perfil**, descrição sistemática, análise crítica com diferenciais da literatura |

## 2. Arquitetura

```
frontend/  React 18 + Vite + TypeScript
  ├─ Upload (arquivos, pasta inteira via webkitdirectory, foto da câmera)
  ├─ ECG Viewer (SVG em papel milimetrado, 12 derivações, toggles por onda/intervalo,
  │              régua de medida, animação da condução sincronizada ao batimento)
  ├─ RX Viewer (canvas + máscaras coloridas, legenda clicável, janela/nível)
  ├─ 3D Viewer (three.js / @react-three/fiber, glTF com uma malha por estrutura)
  └─ Painel de laudo (descrição → achados → análise crítica → referências)

backend/   Python 3.11+ FastAPI
  app/main.py            — app, CORS, rotas
  app/schemas.py         — CONTRATO (pydantic) — fonte da verdade, ver docs/CONTRACTS.md
  app/store.py           — armazenamento de estudos/jobs em disco (data/)
  app/dicom/             — ingestão de pasta, agrupamento Study/Series, render (VOI LUT, MONOCHROME1)
  app/ecg/ingest/        — DICOM waveform, aECG XML, CSV, WFDB
  app/ecg/digitize/      — foto → sinal: perspectiva, grade (px/mm), layout 3x4+ritmo, extração do traçado
  app/ecg/analysis/      — delineação por derivação, batimento mediano, medidas, ritmo, critérios
  app/rx/                — incidência (PA/AP/Perfil), segmentação de estruturas, classificação, medidas
  app/recon3d/           — reconstrução biplanar (casco visual + prior anatômico) → glTF
  app/llm/               — Claude (visão + saídas estruturadas): descrição, análise crítica, citações
  app/knowledge/         — carregador da base de critérios (knowledge/*.yaml)

knowledge/  critérios diagnósticos e sinais radiológicos em YAML, cada item com citação
            (livro/diretriz, edição, capítulo). Sem texto protegido por copyright copiado.
docs/research/  pesquisa bibliográfica e de ferramentas/modelos/datasets
```

### Princípio central: medir primeiro, interpretar depois
1. **Camada determinística** (sinal/imagem) mede tudo que é mensurável: ondas, intervalos, eixos, máscaras, ICT.
2. **Camada de descrição** (Claude com visão) recebe imagem + medidas e descreve estrutura a estrutura, sem diagnosticar.
3. **Camada crítica** (Claude) cruza descrição + medidas com a base `knowledge/` e produz hipóteses e diferenciais, cada uma com referência e grau de confiança, apontando discordâncias entre medida e impressão visual.

## 3. ECG — pipeline

1. **Ingestão**: DICOM `WaveformSequence` (pydicom `waveform_array`), aECG XML, CSV, WFDB.
   Pasta DICOM: varrer todos os arquivos, agrupar por StudyInstanceUID/SeriesInstanceUID, separar ECG de imagem pelo SOP Class/Modality.
2. **Digitalização de foto**: correção de perspectiva (bordas da folha), detecção da grade (FFT/Hough → px/mm, 25 mm/s, 10 mm/mV, confirmação pelo pulso de calibração), detecção do layout (3x4 + D2 longo, 6x2, 12x1), segmentação do traçado por cor/intensidade, vetorização por coluna, conversão para mV × s, reamostragem a 500 Hz. Retorna índice de qualidade por derivação.
3. **Pré-processamento**: remoção de baseline (passa-alta 0,5 Hz), notch 50/60 Hz, passa-baixa 40–150 Hz.
4. **Delineação**: picos R (consenso entre derivações), NeuroKit2 DWT por derivação + refinamento próprio; onset/pico/offset de P, QRS (Q, R, S, R'), T, U; batimento mediano por derivação; ponto J.
5. **Medidas**: FC, RR (média/DP), duração P, PR, QRS, QT, QTc (Bazett, Fridericia, Framingham, Hodges), eixos P/QRS/T (método das derivações dos membros), amplitudes, ST em J, J+60, J+80 por derivação, Sokolow-Lyon, Cornell, índice de Lewis, transição precordial, deflexão intrinsecoide.
6. **Ritmo/condução**: regularidade, relação P:QRS, presença de P sinusal (positiva em D1/D2/aVF), BAV 1º/2º/3º, BRD/BRE/BDAS/BDPI, pré-excitação, QT longo/curto etc. — regras em `knowledge/ecg_criteria.yaml`.
7. **Condução cardíaca**: linha do tempo por batimento (ativação atrial = P, retardo AV = segmento PR, despolarização ventricular = QRS, repolarização = ST-T) mapeada em diagrama anatômico animado, por derivação e global.

## 4. RX — pipeline

1. **Ingestão**: DICOM (VOI LUT/janela, MONOCHROME1 invertido, PixelSpacing/ImagerPixelSpacing para mm) ou imagem.
2. **Incidência**: tag ViewPosition/BodyPartExamined + classificador heurístico (PA/AP/Perfil, tórax/abdome/extremidade).
3. **Segmentação**: tórax — torchxrayvision PSPNet (ChestX-Det, 14 estruturas: clavículas, escápulas, pulmões, hilos, coração, aorta, diafragma, mediastino, traqueia, coluna); opcional TotalSegmentator-style/CXAS para mais classes. Abdome/outras regiões: segmentação genérica + descrição guiada por visão do Claude. Modelos pesados opcionais; com fallback.
4. **Classificação**: torchxrayvision DenseNet (18 patologias) como sinal auxiliar, nunca como laudo.
5. **Medidas**: índice cardiotorácico, desvio traqueal, ângulos costofrênicos, altura das cúpulas, contagem de arcos costais (inspiração), rotação (clavículas × processos espinhosos), penetração.
6. **3D (PA + Perfil)**: alinhar as duas incidências por pontos de referência verticais (ápices, cúpulas, carina); para cada estrutura, extrudar a máscara PA no eixo AP e a máscara do Perfil no eixo LL, intersectar (casco visual), regularizar com prior anatômico (elipsoides/atlas) e suavizar; marching cubes → malha → glTF com nome e cor por estrutura. Deixar explícito na UI que é **reconstrução aproximada**, não tomografia.

## 5. IA (Claude)

- Modelo padrão `claude-opus-5-5` (configurável), visão + `output_config.format` (JSON schema).
- Prompts versionados em `backend/app/llm/prompts/`.
- Entrada: imagem(ns), medidas determinísticas, trechos relevantes de `knowledge/`.
- Saída estruturada: `description` (estrutura a estrutura / onda a onda), `findings`, `differentials` (com `references` e `confidence`), `limitations`, `disagreements_with_measurements`.
- Sem chave de API: o sistema continua funcionando com medidas + regras e marca a parte de IA como indisponível.

## 6. Bibliografia

Ver `docs/BIBLIOGRAFIA.md` (resultado da pesquisa em `docs/research/`).
Livros protegidos por copyright: o usuário fornece os PDFs licenciados localmente (`knowledge/private/`, fora do git) para RAG; o repositório guarda só citações e critérios reescritos.

## 7. Divisão do trabalho (agentes)

| Agente | Diretórios que possui |
|---|---|
| backend-core | `backend/app/main.py`, `store.py`, `app/dicom/`, `backend/pyproject.toml`, `backend/tests/test_core*` |
| ecg-ingest-digitize | `backend/app/ecg/ingest/`, `backend/app/ecg/digitize/`, testes correspondentes |
| ecg-analysis | `backend/app/ecg/analysis/`, `backend/app/ecg/conduction.py`, testes |
| rx-analysis | `backend/app/rx/`, testes |
| recon3d | `backend/app/recon3d/`, testes |
| llm-knowledge | `backend/app/llm/`, `backend/app/knowledge/`, `knowledge/*.yaml`, testes |
| frontend-core | `frontend/` (shell, upload, API client, RX viewer, laudo) exceto pastas abaixo |
| frontend-ecg | `frontend/src/features/ecg/` |
| frontend-3d | `frontend/src/features/recon3d/` |
| research ×4 | `docs/research/*.md` |

Contrato compartilhado: `backend/app/schemas.py` e `frontend/src/types/api.ts` (escritos pelo orquestrador; agentes não mudam sem necessidade e documentam qualquer acréscimo).
