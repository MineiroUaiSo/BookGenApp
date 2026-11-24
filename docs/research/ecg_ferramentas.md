# Ferramentas, modelos e datasets open-source para o leitor de ECG (MedLens)

Data da pesquisa: 2026-11-24. Escopo: `backend/app/ecg/{ingest,digitize,analysis}`.

**Legenda de confiança.** [V] = verificado nesta sessão (página do projeto ou Hugging Face Hub). [M] = vem de conhecimento prévio e deve ser reconferido antes de adotar. Os hosts `arxiv.org` e `moody-challenge.physionet.org` estavam fora da allowlist de rede da sessão, então detalhes de papers e do site do Challenge 2024 ficaram [M].

> Aviso: licença de código não implica licença de pesos nem de dados. Os três precisam ser checados separadamente. Nada abaixo é dispositivo médico certificado.

---

## 1. Digitalização de ECG a partir de foto/scan

| Projeto | URL | Licença | Maturidade | Uso no MedLens | Riscos |
|---|---|---|---|---|---|
| **ECG-Image-Kit** (Kiyasseh/Sameni/Reyna, Emory) | github.com/alphanumericslab/ecg-image-kit | BSD-3-Clause [V] | Média-alta; 157 commits, artigo revisado por pares (PubMed 39150768) [V]. Sem pacote PyPI visível [V] | Gerar imagens sintéticas (ruído, dobras, perspectiva, texto manuscrito) para testar e calibrar nosso `digitize`. A pasta `codes/ecg-image-digitizer` traz uma referência de digitalização | Não é pip-instalável, então vendorizar ou clonar em `tools/`. Código de pesquisa com pouca documentação |
| **ECG-Image-Database** (PhysioNet) | physionet.org (buscar "ECG-Image-Database") | Dados abertos PhysioNet (checar termo exato) [M] | 35.595 imagens geradas a partir de 1.977 registros [V] | Teste de regressão do digitalizador, comparando com o sinal original | Imagens sintéticas ou semissintéticas, então a generalização para foto de celular real é otimista |
| **Challenge PhysioNet/CinC 2024** (Reyna et al.) | github.com/physionetchallenges/python-example-2024 e evaluation-2024 [V] | BSD-3 nos exemplos [M] | Referência de avaliação (SNR) | Reaproveitar o scorer de SNR e o formato de submissão como métrica interna | Exemplo é baseline fraco |
| **SignalSavants (Oxford), 1º lugar em digitalização** | arXiv 2410.14185 "Combining Hough Transform and Deep Learning Approaches" [V] | Não confirmada | Código não localizado nesta busca [V] | Receita: Hough para grade e orientação, U-Net para segmentar o traçado, vetorizar. Replicar a arquitetura, não depender do repo | Procurar o repo na página do paper antes de decidir; sem licença clara, só usar a ideia |
| **Artigo "Digitizing Paper ECGs at Scale: An Open-Source Algorithm"** | arXiv 2510.19590 [V, só título] | ? | Recente (out/2025) | Candidato a baseline; ler o paper e o repo | Não abri o paper (host bloqueado) |
| **ECGtizer** | github.com/UMMISCO/ecgtizer; arXiv 2412.12139 [V] | ? [M] | Pipeline ponta a ponta com recuperação de sinal | Candidato a comparação | Licença e qualidade a verificar |
| **Digitização de ECG sobrepostos (código Python aberto)** | arXiv 2506.10617 [V] | ? | Pesquisa | Útil para derivações que se sobrepõem na foto | Idem |
| **WAVIE** (CinC 2024) | CinC 2024 [V] | ? | Pesquisa | Referência de arquitetura | Idem |

Métodos de grade/papel (para `app/ecg/digitize`): detectar a grade por FFT/autocorrelação na imagem em tons de cinza e obter px/mm (25 mm/s, 10 mm/mV, quadrado pequeno de 1 mm, grande de 5 mm). Corrigir perspectiva com homografia a partir dos cantos do papel ou da grade (OpenCV). Remover a grade por limiarização de cor (vermelho/rosa) ou U-Net. Detectar a linha de calibração (pulso de 1 mV) quando existir.

**Conclusão da seção.** Nenhum digitalizador open-source é maduro e pip-instalável. Recomendo implementar o nosso com OpenCV/scikit-image e, como segundo estágio opcional, um U-Net pequeno treinado com ECG-Image-Kit. Usar ECG-Image-Database e o scorer do Challenge 2024 para medir SNR.

---

## 2. Delineação (P, QRS, T), batimento mediano e intervalos

| Ferramenta | URL | Licença | Maturidade | Uso | Riscos |
|---|---|---|---|---|---|
| **NeuroKit2** (`ecg_peaks`, `ecg_delineate` com métodos `peak`, `dwt`, `cwt`) | github.com/neuropsychology/NeuroKit | MIT [M] | Alta, ativo, pip | Padrão do backend: detecção de R, delineação por derivação, `ecg_clean` | Os métodos DWT/CWT têm erro de fronteira maior que os padrões de referência em T/P de baixa amplitude. Falham em ruído, bloqueios e arritmias. Validar contra LUDB, nunca assumir |
| **wfdb-python** | github.com/MIT-LCP/wfdb-python | MIT [M] | Alta, pip | Ler WFDB (PTB-XL, LUDB, QTDB), anotações, `processing.gqrs/xqrs` | Delineação própria é só QRS |
| **ECGdeli** (MATLAB) | github.com/KIT-IBT/ECGdeli | GPL-3 [M] | Boa em artigos | Referência de algoritmo (wavelet e regras) | MATLAB e GPL, então só como inspiração |
| **Delineadores DL em LUDB/QTDB** (U-Net, `ecg_segmentation`, Seq2Seq) | PMC11175442; arXiv 2304.06237 [V] | Variam [M] | U-Net com F1 de P/QRS/T próximos de 0,97-0,98 em LUDB [V]; generaliza mal em arritmias sub-representadas [V] | Segundo estágio opcional para refinar fronteiras. Treinar nosso U-Net 1D com LUDB mais QTDB (pesos próprios, licença limpa) | Poucos pesos prontos com licença clara; LUDB tem só 200 registros de 10 s |
| **ecg-plot / scipy** | pip | BSD/MIT | Alta | Auxiliares de renderização e filtros | n/a |

Batimento mediano: alinhar batimentos pelo pico R por derivação, rejeitar ectópicos e ruidosos (correlação com a mediana menor que 0,9), tomar a mediana ponto a ponto. Medir QRS, PR, QT e QTc (Bazett, Fridericia, Framingham) na forma de onda mediana, e usar o início/fim global como a primeira deflexão/última deflexão em qualquer derivação (convenção do CSE). Isso reduz o erro frente ao batimento isolado.

Acurácia: a norma IEC 60601-2-25 e os critérios CSE aceitam desvios médios de até cerca de 10 ms (QRS e QT) e desvio padrão de até cerca de 10-30 ms conforme a fronteira [M]. Algoritmos clássicos em sinais limpos ficam perto disso. Em foto digitalizada espere pior, principalmente pelo limite de resolução temporal (1 px a 25 mm/s em foto de 300 dpi é cerca de 3 ms, aceitável). Reportar sempre as medidas com um nível de confiança e marcar ausência de onda P.

---

## 3. Classificação de 12 derivações

| Modelo | URL | Licença (código/pesos) | Pesos | Uso | Riscos |
|---|---|---|---|---|---|
| **ECG-FM** (Bo Wang Lab, UHN) | github.com/bowang-lab/ECG-FM; HF `wanglab/ecg-fm` [V] | Código MIT [V]; licença dos pesos a confirmar no model card | Sim: `mimic_iv_ecg_pretrained` e `mimic_iv_ecg_finetuned` (HF) [V] | Melhor candidato permissivo. Pré-treinado em MIMIC-IV-ECG + PhysioNet 2021 [V], ajustado para diagnóstico | Depende do framework **fairseq_signals** (instalação pesada, não pip simples) [V]. Treinado com dados MIMIC (termos PhysioNet credenciado) |
| **HuBERT-ECG** (Coppola et al.) | HF `Edoardo-Coppola/hubert-ecg-{small,base,large}`; ajustados `HuBERT-ECG-SFT-CardioLearning-*` [V] | **CC BY-NC 4.0** [V] | Sim, `transformers` com `custom_code` [V] | Só para pesquisa/protótipo | **Não comercial**, incompatível com produto. Exige `trust_remote_code` |
| **ECGFounder** (PKU Digital Health) | HF `PKUDigitalHealth/ECGFounder`, arXiv 2410.04133; ONNX `ghirani33/ecgfounder-onnx` [V] | MIT [V] | Sim | Candidato para tags de diagnóstico e embeddings; ONNX facilita CPU | Reconferir licença dos dados de treino (Harvard-Emory ECG database). Cobertura de rótulos (150 classes) pode não casar com o nosso schema |
| **Modelos PTB-XL pequenos no HF** (Keras ResNet etc.) | `Steenslid/ecg-ptbxl-classification` (MIT), `MHkhan50/ptbxl-ecg-resnet` (CC-BY-4.0, "research-only") [V] | MIT / CC-BY | Sim | Só como baseline de teste | Procedência e qualidade desconhecidas; downloads altos não validam o modelo. Não usar como diagnóstico |
| **Benchmark PTB-XL** (Strodthoff et al.) | github.com/helme/ecg_ptbxl_benchmarking [M] | BSD-2 [M] | Sem pesos prontos | Receita: xresnet1d101 com AUC macro de cerca de 0,93 em superclasses | Treinar nós mesmos |
| **Modelos Ribeiro et al. (CODE, Nature Comms 2020, "CODE-15%")** | github.com/antonior92/automatic-ecg-diagnosis [M] | MIT (código) [M] | Pesos no Zenodo (necessário checar licença) [M] | ResNet 1D para 6 anormalidades (BAV1, BRD, BRE, FA, BS, TS) com treinamento em 2,3 milhões de ECGs de Minas Gerais | Dataset CODE completo é restrito; CODE-15% é público (CC BY 4.0, Zenodo) [M]. Pesos não pip. Bom ajuste para população brasileira |
| **MCore-ECG-0.8B** | HF `MCORE-HEALTH/MCore-ECG-0.8B-v0.1` (Apache-2.0) [V] | Apache-2.0 | Sim (GGUF) | Observação apenas | Piloto recente e sem validação; LLM de ECG pode alucinar |

Recomendação: o diagnóstico automático **não** deve ser a fonte principal. O pipeline determinístico (medidas e regras com critérios em `knowledge/*.yaml`) vem primeiro, o LLM redige. Um classificador é apenas uma segunda opinião, claramente rotulada, ligado por feature flag. Escolha inicial: **ECG-FM finetuned** ou **ECGFounder**, após confirmar a licença dos pesos, e os pesos do Ribeiro para as 6 anormalidades clássicas. Evitar HuBERT-ECG em produto (CC BY-NC).

---

## 4. Leitura de formatos (ingest)

| Formato | Biblioteca | Licença | Notas |
|---|---|---|---|
| **DICOM Waveform (12-lead ECG, SOP `1.2.840.10008.5.1.4.1.1.9.1.1`)** | **pydicom** (`ds.waveform_array(index)`, desde 2.1; `pydicom.waveforms`) | MIT [M] | `WaveformSequence` com `ChannelDefinitionSequence`, `WaveformSampleInterpretation`, `ChannelSensitivity`, `ChannelSensitivityCorrectionFactor`, `ChannelBaseline`. `waveform_array` aplica ganho e baseline? Confirmar: em pydicom 2.x devolve amostras brutas e é preciso escalar por sensibilidade e fator de correção (µV). Rótulos de derivação em `ChannelSourceSequence.CodeMeaning`. Multiplex group: um para ritmo e outro para 10 s são comuns |
| **HL7 aECG (XML, v3)** | `lxml` ou `xml.etree` | BSD/PSF | Sem biblioteca madura em Python. Extrair `SequenceSet`/`SLIST_PQ` (`digits`, `origin`, `scale`), `MDC_ECG_LEAD_*`. Escrever parser próprio (cerca de 100 linhas) |
| **SCP-ECG** | **wfdb não lê**. `scp-ecg` / `pyscp` / `ecgtools` dispersos [M] | variam | Raro no Brasil. Baixa prioridade; parsear só se surgir arquivo real. Alternativa: `ecg-converter`/`Biosig` (BioSig, GPL, via `biosig` pip) para converter |
| **WFDB, CSV, EDF, MIT-BIH** | `wfdb`, `pandas`, `pyedflib`/`mne` | MIT/GPL | WFDB cobre PTB-XL, LUDB e QTDB |
| **GE MUSE XML, Philips XML, Mortara** | parsers próprios | n/a | Comum no hospital; XML simples com amostras em base64 (int16). Adicionar depois |

Observação: a conversão para µV e a taxa de amostragem (`SamplingFrequency` ou `1/ChannelSamplingFrequency`) devem entrar no `ECGSignal`, pois as medidas em mm dependem delas.

---

## 5. Datasets para teste

| Dataset | URL | Licença | Conteúdo | Uso |
|---|---|---|---|---|
| **PTB-XL** | physionet.org/content/ptb-xl | CC BY 4.0 [M] | 21.799 ECGs de 12 derivações, 10 s, rótulos SCP e laudo | Teste de classificação, ingest WFDB, 100/500 Hz |
| **PTB-XL+** | physionet.org/content/ptb-xl-plus | CC BY 4.0 [M] | Características e delineação algorítmica (Unipolar, ECGdeli etc.) sobre PTB-XL | Comparar nossas medidas com medidas de referência (não de especialistas) |
| **LUDB** | physionet.org/content/ludb | ODC-By [M] | 200 registros de 12 derivações com início/pico/fim de P, QRS, T anotados por cardiologistas | **Padrão-ouro** para delineação e medida de erro |
| **QTDB** | physionet.org/content/qtdb | ODC-By [M] | 105 registros de 2 derivações, onda e fim de T anotados | Validar QT e fim de T |
| **CSE** (CTS) | não é livre | Comercial | Referência da IEC | Não disponível; usar LUDB como substituto |
| **CODE-15%** | zenodo.org (buscar "CODE-15%") | CC BY 4.0 [M] | 345.779 exames de 233.770 pacientes, 12 derivações, 7 a 10 s, rótulos para 6 anormalidades; população brasileira | Teste de classificação e de domínio brasileiro |
| **ECG-Image-Database** | PhysioNet | ver acima | 35.595 imagens a partir de 1.977 registros [V] | Teste de digitalização |
| **MIMIC-IV-ECG** | physionet.org/content/mimic-iv-ecg | PhysioNet Credentialed [M] | ~800 mil ECGs | Só se treinar/ajustar; credenciamento obrigatório |
| **PhysioNet/CinC 2021** | physionet.org/content/challenge-2021 | CC BY 4.0 [M] | 88 mil ECGs de 12 derivações com SNOMED | Teste multirrótulo |

Cuidado: nunca commitar dados de pacientes. Baixar sob demanda para `data/` (ignorada pelo git) com um script `scripts/fetch_test_data.py`.

---

## 6. Pilha recomendada para `backend/app/ecg`

```
ingest/      pydicom (waveform_array + escala por sensibilidade) | wfdb | lxml (aECG) | pandas (CSV)
             parsers próprios para MUSE/Philips XML depois; SCP-ECG só sob demanda
digitize/    OpenCV + scikit-image + numpy
             1) detectar papel e corrigir perspectiva (homografia)
             2) grade: autocorrelação -> px/mm; remover grade por cor
             3) layout (3x4+ritmo, 6x2, 12x1) por template e detecção de rótulos de derivação
             4) traçado: U-Net opcional (treinado com ECG-Image-Kit) ou
                limiarização + caminho mínimo por coluna; reamostrar a 500 Hz; escala 25 mm/s e 10 mm/mV
             5) validar SNR no ECG-Image-Database; devolver confiança e avisos
analysis/    scipy (filtros) + NeuroKit2 (R, dwt/cwt/peak) + batimento mediano próprio
             medidas na mediana (FC, PR, QRS, QT, QTc), eixo por área QRS em I e aVF
             teste de regressão em LUDB (erro médio e DP de início/fim de P, QRS, T)
             segundo estágio opcional: U-Net 1D treinado em LUDB+QTDB
classif.     (opcional, feature flag) ECG-FM finetuned ou ECGFounder (ONNX), pesos do Ribeiro
             sempre rotulado "segunda opinião automática"
llm/         Claude redige a partir de medidas e achados estruturados, não decide sozinho
```

Dependências pip (todas permissivas): `pydicom`, `wfdb`, `neurokit2`, `scipy`, `numpy`, `opencv-python-headless`, `scikit-image`, `lxml`, `onnxruntime` (opcional). Evitar GPL (ECGdeli, BioSig) e CC BY-NC (HuBERT-ECG) no produto.

## 7. Riscos e próximos passos

1. **Qualidade da foto** é o gargalo. Medir erro de intervalo na imagem digitalizada contra o sinal original (ECG-Image-Database) e mostrar incerteza na UI.
2. **Validação**: criar `tests/ecg/` com LUDB (delineação), PTB-XL (ingest) e imagens sintéticas (digitalização). Metas iniciais: erro médio de QRS e QT menor que 15 ms em LUDB.
3. **Licença dos pesos**: abrir os model cards de ECG-FM e ECGFounder e confirmar. Registrar a licença em `docs/`.
4. **Lacunas desta pesquisa** (rede bloqueada): repositório do vencedor SignalSavants, resultados oficiais do Challenge 2024, conteúdo dos papers arXiv 2510.19590, 2506.10617 e 2412.12139, e licenças de ECGtizer e WAVIE. Liberar `arxiv.org` e `moody-challenge.physionet.org` para completar.
5. Tudo é apoio à decisão e ao ensino; laudo exige revisão médica.

## Fontes consultadas
- ECG-Image-Kit: https://github.com/alphanumericslab/ecg-image-kit e https://pubmed.ncbi.nlm.nih.gov/39150768/
- ECG-FM: https://github.com/bowang-lab/ECG-FM e https://huggingface.co/wanglab/ecg-fm-preprint
- HuBERT-ECG: https://huggingface.co/Edoardo-Coppola/hubert-ecg-base
- ECGFounder: https://huggingface.co/PKUDigitalHealth/ECGFounder
- SignalSavants: https://arxiv.org/html/2410.14185v1
- ECGtizer: https://arxiv.org/html/2412.12139v1
- Digitização com sobreposição: https://arxiv.org/html/2506.10617v1
- Delineação em LUDB: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11175442/ e https://arxiv.org/pdf/2304.06237
- Challenge 2024: https://moody-challenge.physionet.org/2024/ (via resultados de busca)
