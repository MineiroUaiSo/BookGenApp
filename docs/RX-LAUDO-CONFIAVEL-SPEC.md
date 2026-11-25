# SPEC — Laudo de RX de tórax estruturado e confiável (MedLens)

Autor: arquiteto (Opus), 2026-11-25, branch `claude/ecg-rx-ai-reader-nd20rs`. Somente leitura no código; nada commitado.
Status: proposta para execução por Sonnet. O laudo é **rascunho de apoio à decisão que exige revisão médica**. Nunca é diagnóstico automático.

## 0. Resumo em 6 linhas
1. Hoje o RX tem medidas e regras boas (ICT, rotação, inspiração, penetração, seios, traqueia, mediastino), mas **não tem laudo estruturado**: só `findings` + texto livre da IA (`rx_report`).
2. **Bug CRÍTICO reproduzido no caminho RX**: `llm/validate.py::validate_report` aceita afirmação qualitativa falsa (consolidação, nódulo, fratura, derrame pequeno) e negação sem avaliação ("sem pneumotórax", "seios livres"). Só 5 tópicos "críticos" são checados, e mesmo assim só sinalizados, nunca removidos.
3. O laudo v2 com `[F]/[C]` existe só para ECG (`llm/laudo.py`, `claim_semantics.py`; T1-T3 mesclados). O RX não tem ficha de fatos.
4. Proposta: ficha `rx_ficha/v1` (fatos F com origem e confiança) + mapa de cobertura (o que foi e o que NÃO foi avaliado) + laudo **determinístico** por seções. A IA, se ligada, só reescreve frases a partir de ids. O validador remove o que não tiver lastro.
5. Regra de ouro: o que o app não avalia sai como **"não avaliado nesta análise"**, nunca como normal.
6. Primeira tarefa: teste RED com as 6 frases da sonda e correção só no caminho RX (sem tocar `backend/app/ecg`).

## 1. O que existe (mapa lido)
| Peça | Arquivo | O que faz |
|---|---|---|
| Medidas frontais | `backend/app/rx/measure.py::measure_frontal` | largura torácica, ICT (`cardiothoracic_ratio`), largura cardíaca, desvio traqueal (mm e %), ângulos costofrênicos D/E, diferença das cúpulas, largura do mediastino (mm e %), razão de área pulmonar E/D |
| Qualidade técnica | `measure.py::quality_frontal` | rotação (clavículas, com fallback coluna × campos), inspiração (arcos posteriores ≥ 9, mais razão altura/largura), penetração (contraste da coluna atrás do coração) |
| Regras | `backend/app/rx/findings.py` | cardiomegalia (ICT > 0,50 em PA; AP = borderline), ICT normal, alargamento mediastinal, desvio traqueal > 3 %, embotamento de seio ≥ 95° (rebaixado), elevação de cúpula, assimetria de volume, limitações técnicas, achados do modelo (zonas calibradas) |
| Calibração | `rx/calibration.py` | zonas `nao_sugerido`/`indeterminado`/`sugestivo`; Pneumothorax = `INSUFFICIENT_EVIDENCE` |
| Segmentação | `seg_model.py` (PSPNet), `seg_heuristic.py`, `seg_cxas.py` (flag off, licença) | Dice coração 0,926 e pulmões 0,864 (JSRT, modelo); heurística 0,45/0,64 |
| ICT vs referência | `docs/benchmarks/rx.md` | MAE 0,027 (JSRT, modelo) e 0,041 (PA outros); concordância ICT > 0,5 de 0,89 e 0,80; heurística MAE 0,123, sem ICT em 70/247 |
| Texto IA | `llm/__init__.py::rx_report` → `_two_stage` → `validate.py::validate_report` | imagem só com opt-in; texto anonimizado; validador numérico + 5 tópicos críticos |
| Cartões RX | `knowledge/rx_signs.yaml` (21 sinais), `knowledge/references.yaml` | paráfrase + referência; nenhum revisado por médico |
| Referências no código | `findings.py` | `felson_2025`, `fleischner_glossary`, `squire`, `xrv_cohen_2022` (edição/página não verificadas) |

### 1.1 O que o app SABE afirmar com evidência (medida + critério)
- Incidência PA/AP/perfil (tag ou classificador), região, e se a imagem está fora de escopo.
- ICT medido (só com segmentação por modelo) e a comparação com 0,50 em PA. Em AP vale só a ressalva de magnificação.
- Rotação, inspiração e penetração como **estimativas** (3 estados: adequada / possivelmente inadequada / indeterminada).
- Desvio traqueal, largura mediastinal, diferença das cúpulas e razão de área: valores medidos com faixa de referência.
### 1.2 O que NÃO sabe (só escore de modelo ou nada)
- Derrame, consolidação, atelectasia, edema, opacidade, nódulo/massa, enfisema, fibrose: **só escore do modelo** (DenseNet/torchxrayvision, calibrado no IU). Nódulo tem AUC 0,628 no JSRT, fraco.
- Pneumotórax: **evidência insuficiente**, nunca afastar.
- Ângulo costofrênico ≥ 95°: heurística local, sem fonte e rebaixada. Não sustenta "derrame".
- Ossos, partes moles, dispositivos (tubos, cateteres, marca-passo), ar livre subdiafragmático, hilos, trama vascular, linhas de Kerley, comparação com exame anterior: **não avaliados**.

### 1.3 Sonda (reproduzida, código atual)
Script em scratchpad (`probe_rx.py`). Resumo: ICT 0,46 normal; escores do modelo baixos; `validate_report` sobre `description`:
| Frase da IA | Resultado atual | Esperado |
|---|---|---|
| "Consolidação no lobo inferior direito com broncograma aéreo." | aceita, 0 discordâncias | rejeitar: sem fato |
| "Nódulo pulmonar de 12 mm no lobo superior esquerdo." | aceita (número só "não verificável") | rejeitar |
| "Sem pneumotórax. Seios costofrênicos livres. Pulmões sem opacidades." | aceita | rejeitar: tópico não avaliado / negação sem medida |
| "Pequeno derrame pleural à direita." | aceita (o regex só cobre derrame "volumoso") | rejeitar |
| "Pneumotórax à esquerda." | 1 discordância, **texto mantido** | remover e mostrar aviso |
| "Fratura do 6º arco costal direito." | aceita | rejeitar |
Bug extra: `is_supported` aceita escore **bruto** ≥ 0,5 como lastro, ignorando a zona calibrada e `INSUFFICIENT_EVIDENCE`.
Bug de terminologia: `PATHO_PT["Infiltration"] = "infiltrado"`. O glossário Fleischner 2024 chama "infiltrate" de termo obsoleto e não recomendado. Usar "opacidade".

## 2. Formato do laudo (`rx_laudo/v1`)
Cada frase é um objeto `{secao, texto, fatos:[F…], fontes:[S…], nivel}`. `nivel` ∈ {`MEDIDO`, `REGRA`, `SUGERIDO_MODELO`, `NAO_AVALIADO`, `QUALIDADE`}. A UI mostra o nível como etiqueta e as fontes ao passar o mouse.

Seções e ordem (alinhadas a ACR Communication §II.B: dados do exame, informação clínica, procedimento, achados, limitações, impressão, recomendações; e a ACR Chest Radiography quanto à técnica):
1. **Identificação e técnica**: incidência(s), número de imagens, posição (se tag). Nenhum dado pessoal no texto do laudo gerado; identificação fica com o sistema do médico.
2. **Qualidade técnica e limitações** (`QUALIDADE`): inclusão de ápices e seios; rotação (coluna centrada entre as clavículas, critério ACR); inspiração (arcos posteriores, estimativa); penetração (corpos vertebrais torácicos baixos e vasos retrocardíacos definidos, critério ACR). Toda limitação vira frase "limita a avaliação de …".
3. **Achados por região**. Toda região tem frase obrigatória, mesmo vazia:
   - Pleura (seios, derrame, pneumotórax)
   - Pulmões (opacidade/consolidação/atelectasia/nódulo/padrão intersticial/hiperinsuflação)
   - Mediastino e hilos (largura, traqueia)
   - Coração e vasos (ICT, contorno)
   - Diafragma (cúpulas, ar livre)
   - Ossos e partes moles
   - Dispositivos
4. **Sinais do modelo auxiliar** (caixa separada, `SUGERIDO_MODELO`): só zonas calibradas, com a frase fixa "escore de modelo; não confirma nem afasta". Ver decisão D1.
5. **Impressão**: só itens `REGRA`, ou `MEDIDO` fora da faixa, em ordem de gravidade. Mais o bloco fixo de achados críticos não avaliados (abaixo). Nunca "exame normal".
6. **Recomendações**: só genéricas e condicionais ("correlacionar com a clínica"; "se a dúvida persistir, considerar incidência em perfil ou PA", quando a imagem é AP). Sem conduta terapêutica.
7. **Revisão médica** (campos do médico): Concordo/Discordo por frase (já existe por achado; estender por seção), texto livre por região "não avaliada", campo "comunicação não rotineira" (data/hora, meio, destinatário; ACR §II.D.2.b) guardado só localmente, nunca em log; assinatura e status `rascunho → revisado`. Nota fixa de uso de IA (CFM 2.454/2026 via nota CBR; texto padronizado do CBR ainda em construção).

### 2.1 Frases-molde (determinísticas; paráfrase própria, sem texto protegido)
| Situação | Frase | nivel |
|---|---|---|
| ICT PA ≤ 0,50 (modelo) | "Índice cardiotorácico medido {v} (limite clássico 0,50 em PA)." | MEDIDO |
| ICT PA > 0,50 | "Índice cardiotorácico medido {v}, acima de 0,50: sugere aumento da silhueta cardíaca (critério de acurácia limitada; correlacionar)." | REGRA |
| ICT em AP | "ICT {v} em AP: a incidência magnifica o coração; não usar para afirmar cardiomegalia." | REGRA |
| ICT de heurística | "Silhueta cardíaca não medida com confiança (segmentação de baixa confiabilidade)." | NAO_AVALIADO |
| Região sem fato | "{Região}: não avaliado nesta análise automática." | NAO_AVALIADO |
| Modelo `sugestivo` | "Modelo auxiliar: possível {achado} (probabilidade calibrada ≈ {p}); não confirma." | SUGERIDO_MODELO |
| Modelo `indeterminado` | "Modelo auxiliar: indeterminado para {achado}; não permite afirmar nem afastar." | SUGERIDO_MODELO |
| Modelo `nao_sugerido` | não vira frase de ausência; a região fica `NAO_AVALIADO` (D1) | n/a |
| Crítico fixo | "Pneumotórax, pneumoperitônio e posição de tubos/cateteres NÃO são avaliados por esta análise: revisar a imagem." | NAO_AVALIADO |

### 2.2 Vocabulário de incerteza (escala fechada, inspirada em Panicek & Hricak, AJR 2016)
Só 5 graus, mapeados ao nível:
- "compatível com": proibido em achado diagnóstico. Só para a própria medida ("medida compatível com faixa de referência").
- "sugere": REGRA com medida e critério citável.
- "possível": SUGERIDO_MODELO zona `sugestivo`.
- "indeterminado": zona `indeterminado` ou qualidade limitante.
- "não avaliado": sem fato.

Proibidos em qualquer texto gerado: "normal", "sem alterações", "dentro da normalidade", "afasta", "descarta", "ausência de", "livre(s)", "diagnóstico de", "confirma". Exceção: "dentro da faixa de referência" junto a um fato MEDIDO. As porcentagens da escala original ficam em "a confirmar" (§7).

### 2.3 Proibições (testáveis)
Nada de diagnóstico definitivo automático; nada de promessa clínica; nada de PHI em log (vale o `usage_log` atual, sem texto do laudo); nada de imagem ao provedor sem opt-in (`rx_image_ai_mode`, já existe); termos Fleischner 2024 (sem "infiltrado").

## 3. Contrato com a LLM (só se a IA estiver ligada; flag `MEDLENS_RX_LAUDO_IA=0` por padrão)
- Entrada: a ficha anonimizada (`F1..Fn` com chave, valor, unidade, nível, região), a lista fechada de fontes `S1..Sk` e as frases determinísticas já prontas. Sem imagem, salvo opt-in.
- Saída (JSON schema): `{afirmacoes:[{secao, texto, fatos:[F…], fontes:[S…]}]}`. A LLM só **reescreve com fluidez**; não cria região nova nem achado novo.
- Validador determinístico `rx/laudo_validate.py`. Rejeita a frase (remove e registra em `rejeicoes`) quando:
  1. não cita fato, ou cita id fora da lista;
  2. traz número que não está nos fatos citados (reusar a lógica de `unmatched_numbers`);
  3. menciona um tópico RX (tabela `TOPICOS_RX`: derrame, pneumotórax, consolidação, atelectasia, opacidade, nódulo/massa, edema, enfisema, fratura, dispositivo, ar livre, cardiomegalia/silhueta, mediastino, traqueia, cúpula), **afirmado ou negado**, sem fato do mesmo tópico entre os citados;
  4. faz negação ou normalidade de tópico cujo fato é `NAO_AVALIADO` ou `SUGERIDO_MODELO` (negação só vale com fato MEDIDO na faixa);
  5. o grau de incerteza é mais forte que o nível do fato (ex.: "sugere" com fato de modelo; "compatível com" com diagnóstico);
  6. traz descritor visual (lobo, broncograma, contorno, "imagem mostra") sem imagem enviada;
  7. usa termo proibido (§2.2).
- Mais de 50 % de rejeição, ou rejeição em Impressão: **abstenção**. Vale o laudo determinístico, com o aviso "texto da IA descartado pelo validador".
- O laudo determinístico é sempre o padrão. A IA nunca é requisito para haver laudo.

### 3.1 Correção do bug CRÍTICO (antes de tudo)
- **Teste RED** `backend/tests/test_rx_validator_qualitative.py`: monta `summary` como na sonda (§1.3) e roda o caminho RX. Afirma que: (a) as 6 frases saem marcadas e **removidas** do texto exibido; (b) `Pneumothorax` 0,55 bruto com zona `nao_sugerido` ou `INSUFFICIENT_EVIDENCE` **não** sustenta "pneumotórax"; (c) "Cardiomegalia" com `rx.cardiomegaly` presente continua aceita (sem regressão); (d) uma frase numérica certa ("ICT 0,46") continua aceita.
- **Correção** só no caminho RX: novo `backend/app/rx/claim_check.py` (tópicos RX + negação + remoção), chamado em `rx_report` depois de `_two_stage`. `validate.py` não muda de comportamento para ECG: suíte ECG verde antes e depois. Não tocar `backend/app/ecg/`.

## 4. Plano de verificação
### 4.1 Automático
- Suíte adversarial RX: ≥ 60 frases (afirmações e negações por tópico × com/sem fato × com/sem imagem). Meta: **0 frases sem lastro passam**, e ≥ 95 % das frases com lastro passam.
- Propriedade: para qualquer ficha sem fato de uma região, o laudo contém "não avaliado" naquela região e nenhuma palavra proibida (teste parametrizado sobre fichas sintéticas).
- Regressão do bench: `rx.md` sem piora de ICT MAE nem de Dice (o laudo não muda as medidas).
### 4.2 Casos-ouro com imagens livres
- Wikimedia Commons, categoria "X-rays of the chest" (API consultada: dos 200 primeiros, 14 em domínio público e 5 CC0). Candidatos CC0: `File:Cardiothoracic ratio.jpg`, `File:Chest radiograph of a lung with Kerley B lines.jpg`, `File:Chest radiograph with signs of congestive heart failure - annotated.jpg`, `File:Chest Xray PA 3-8-2010 inverted.png`. Em domínio público: `File:Air crescent sign.jpg`, `File:6077 lores.jpg`. O executor confirma a licença na página de cada arquivo, baixa para `data/gold_rx/` (fora do git) e o teste dá `skip` se faltar.
- Já disponíveis no bench (só local, não versionar): JSRT e conjuntos de máscaras. Licenças em §7.
- O gabarito de cada caso-ouro é escrito pelo médico (achado presente/ausente por região). O app é cobrado só nas regiões que avalia.
### 4.3 Revisão médica (aceite para ligar por padrão)
- N = 30 laudos determinísticos (10 normais pelo gabarito, 20 com achado: cardiomegalia, derrame, consolidação, AP de leito, rotação) e mais 20 com IA ligada, se D3 aprovar.
- Por frase: Concordo/Discordo e gravidade do erro (0 nenhum, 1 menor, 2 enganoso, 3 perigoso).
- Aceite: **0 erros grau 3**; ≤ 2 % de frases grau 2; ≥ 90 % de concordância por frase; 100 % das regiões não avaliadas rotuladas assim. Registrar tempo de revisão por laudo.

## 5. Decisões que só o dono toma (máx. 3)
- **D1. Escore do modelo no laudo.** Recomendado: caixa separada "Sinais do modelo auxiliar", nunca na Impressão, e `nao_sugerido` sem frase de ausência. Alternativa: incluir "possível X" dentro de Achados.
- **D2. Linguagem do ICT > 0,50.** Recomendado: "sugere aumento da silhueta cardíaca (critério de acurácia limitada)", e não "cardiomegalia". Motivo: CMAJ 2021, sens/espec 72 %/72 % em PA. Alternativa: manter "Cardiomegalia (ICT > 0,50 em PA)" como em `findings.py`.
- **D3. IA no laudo RX.** Recomendado: só determinístico até a revisão §4.3 passar; depois IA só texto (sem imagem), atrás de flag. Alternativa: IA ligada desde já com validador novo.

## 6. Fontes verificadas (lidas nesta sessão)
| Id | Título / entidade / ano | URL (como lida) | O que foi lido de fato | Direitos | Seção do laudo |
|---|---|---|---|---|---|
| S1 | ACR–SPR–STR Practice Parameter for the Performance of Chest Radiography. ACR/SPR/STR. Revisado 2022 (Res. 11), emendado 2023 | https://gravitas.acr.org/PPTS/DownloadPreviewDocument?DocId=129 (o PDF em acr.org retornou HTML de bloqueio) | padrão PA + perfil esquerdo, em pé, inspiração plena; AP sentado/supino como substituto; incluir ápices e seios costofrênicos; coluna centrada entre as clavículas; corpos vertebrais torácicos baixos e vasos retrocardíacos definidos; parênquima em cinza médio | © ACR; uso educacional; só paráfrase + citação | Técnica e qualidade |
| S2 | ACR Practice Parameter for Communication of Diagnostic Imaging Findings. ACR. Revisado 2025 (Res. 9) | https://gravitas.acr.org/PPTS/DownloadPreviewDocument?DocId=74 | componentes do laudo (dados, clínica, procedimento, achados, limitações, questão clínica, comparação, impressão com diferencial e seguimento); laudo preliminar rotulado; comunicação não rotineira (pneumotórax, pneumoperitônio, tubo/cateter mal posicionado) documentada com data, hora, meio e destinatário | © ACR; paráfrase | Estrutura, Impressão, crítico, Revisão médica |
| S3 | ACR–SPR–STR Practice Parameter for Portable (Mobile Unit) Chest Radiography | https://gravitas.acr.org/PPTS/DownloadPreviewDocument?DocId=149 | **só título e cabeçalho** | © ACR | Técnica em AP (ler antes de citar) |
| S4 | Bankier AA et al. Fleischner Society: Glossary of Terms for Thoracic Imaging. Radiology 2024;310(2):e232558, doi:10.1148/radiol.232558 | PDF em https://car.ca/wp-content/uploads/2025/07/bankier-et-al-2024-fleischner-society-glossary-of-terms-for-thoracic-imaging.pdf; metadados via Europe PMC | substitui os glossários de 1984, 1996 e 2008; nódulo ≤ 30 mm, massa > 30 mm, micronódulo < 6 mm; consolidação e opacidade como descritores inespecíficos; "infiltrate" obsoleto; broncograma aéreo | © RSNA 2024; sem OA; só termos e paráfrase curta | Vocabulário de Achados |
| S5 | Panicek DM, Hricak H. How Sure Are You, Doctor? A Standardized Lexicon to Describe the Radiologist's Level of Certainty. AJR 2016;207(1):2-3, doi:10.2214/AJR.15.15895 | Europe PMC (resumo) | só o resumo: léxico padronizado de certeza (MSKCC, 2009), incluído em cada laudo | © ARRS; sem OA | Vocabulário de incerteza |
| S6 | Diagnostic performance of chest radiography measurements for the assessment of cardiac chamber enlargement. CMAJ 2021;193(44):E1683, doi:10.1503/cmaj.210083 | Europe PMC (resumo) | n = 152 com RM; ICT 0,50 em PA: sens 72 % e espec 72 %; diâmetro cardíaco máximo AUC 0,827; o corte 0,5 tem valor limitado | CC BY-NC-ND | Coração (D2) |
| S7 | Ignácio FCGR et al. Laudo radiológico: qual a opinião do médico solicitante? Radiol Bras 2018;51(5):308-312 | https://rb.org.br/export-pdf/3084/v51n5a08.pdf | o CBR criou grupo de trabalho com "recomendações mínimas" para laudo de qualidade (lista na ref. 3, **não lida**); solicitantes preferem laudo estruturado | acesso aberto (SciELO) | Justificativa da estrutura |
| S8 | CBR, Nota oficial sobre a Resolução CFM nº 2.454/2026 (uso de IA na medicina), 02/03/2026 | https://cbr.org.br/wp-content/uploads/2026/03/Normatizacao-do-Uso-da-Inteligencia-Artificial-na-Medicina.pdf | decisão final sempre do médico; sem aprovação automática de laudos; paciente informado do uso de IA; nota padronizada no laudo em construção pelo CBR; apoio diagnóstico = risco médio; vigência 180 dias após o DOU de 27/02/2026 | documento público institucional | Revisão médica, nota de IA, governança |
| S9 | Wikimedia Commons, Category:X-rays of the chest | API `commons.wikimedia.org/w/api.php` (extmetadata LicenseShortName) | contagem de licenças e nomes de arquivos CC0/PD (§4.2) | por arquivo | Casos-ouro |

## 7. Fontes NÃO verificadas / a confirmar
- RSNA RadReport: template de RX de tórax e licença (`reportingwiki.rsna.org/index.php/Template_License` respondeu "Site is down for maintenance"). Não usar os campos do template até ler.
- Fleischner 2008 (Hansell et al., Radiology 2008;246(3):697-722): só registro bibliográfico; substituído por S4.
- Percentuais da escala de certeza (> 90 %, ~75 %, ~50 %, ~25 %, < 10 %): vistos só no trecho de busca de um resumo ACR 2017 (Lakhani). Ler o texto completo de S5 antes de exibir percentuais.
- Felson's Principles of Chest Roentgenology (o código usa id `felson_2025`; edição e ano não confirmados) e Squire's Fundamentals of Radiology: confirmar edição e páginas; só paráfrase.
- Danzer 1919 (origem do ICT): só citação secundária.
- Limiares sem fonte primária lida: inspiração ≥ 9 arcos posteriores; mediastino < ~80 mm / < ~30 %; ângulo costofrênico ≥ 95°; desvio traqueal > 3 %/> 5 %; diferença das cúpulas (−5 %/+14 %); razão de área 0,55-1,3. Até haver fonte, a frase sai como REGRA "heurística local", ou fica fora da Impressão.
- Lista de "recomendações mínimas" do CBR (ref. 3 de S7) e texto integral da Resolução CFM 2.454/2026 (lida só a nota do CBR).
- Licenças de JSRT, Montgomery/Shenzhen (NLM), NIH ChestX-ray14 e IU/Open-i para uso em produto: não lidas nesta sessão.
- Radiopaedia: CC BY-NC-SA (não comercial; de memória, não lido). Não usar como fonte de texto.

## 8. Tarefas para executores Sonnet (ordem obrigatória; TDD; não tocar `backend/app/ecg/` nem `docs/benchmarks/`)
Comando de teste: `cd backend && PYTHONPATH=. .venv/bin/python -m pytest -q`.

1. **Validador RX: teste RED + correção.** Arquivos: `backend/tests/test_rx_validator_qualitative.py` (novo), `backend/app/rx/claim_check.py` (novo), chamada em `backend/app/llm/__init__.py::rx_report`. RED: casos (a)-(d) de §3.1 falham hoje. Aceite: (a)-(d) verdes; frase rejeitada some de `description`/`findings`/`differentials` e vai para `disagreements_with_measurements`; suporte por escore usa a zona calibrada e respeita `INSUFFICIENT_EVIDENCE`; suíte inteira verde, incluindo ECG.
2. **Terminologia Fleischner.** `rx/findings.py::PATHO_PT`: "infiltrado" vira "opacidade". RED: teste de que nenhum rótulo RX contém "infiltrad". Aceite: teste verde, sem mudar código de achado.
3. **Registro de fontes.** `knowledge/rx_report_sources.yaml` (S1-S9 de §6 com `verificado: true` e as de §7 com `verificado: false`), loader e teste de esquema (id, título, ano, url, direitos, seções). Aceite: o laudo só cita `verificado: true`; uma fonte não verificada usada pelo laudo falha o teste.
4. **Ficha `rx_ficha/v1`.** `backend/app/rx/ficha.py`: fatos F (chave, valor, unidade, nível, região, origem modelo/heurística, fontes) + `cobertura` por região (§2 item 3). RED: fixture sintética com segmentação heurística → ICT sai `NAO_AVALIADO`; AP → ressalva; sem dispositivos → `NAO_AVALIADO`. Aceite: modelos frozen; ids estáveis por ordem.
5. **Léxico de incerteza.** `backend/app/rx/lexico.py` (graus de §2.2 + termos proibidos). RED: o nível `SUGERIDO_MODELO` não pode gerar "sugere"/"compatível com"; texto com "sem alterações" é reprovado. Aceite: tabela única usada pelo laudo e pelo validador.
6. **Laudo determinístico.** `backend/app/rx/laudo.py` (`build_laudo(analysis) -> LaudoRX`) com as seções de §2 e as frases-molde de §2.1, mais `render_markdown`. RED: teste de propriedade (região sem fato = "não avaliado"; nenhuma palavra proibida; bloco crítico sempre presente; nunca "normal"). Aceite: teste verde para PA, AP, perfil, heurística e fora de escopo.
7. **API.** `backend/app/api/analysis.py`: campo `laudo_rx` na resposta do estudo RX (schema em `schemas.py`). RED: teste de integração com DICOM sintético (`fixtures_dicom.make_dx_dicom`). Aceite: sem PHI no laudo (rodar `guard.scan_text` no markdown).
8. **Contrato IA (atrás de `MEDLENS_RX_LAUDO_IA=0`).** Prompt `llm/prompts/rx_laudo_v1.md`, schema de saída e `backend/app/rx/laudo_validate.py` (regras 1-7 de §3, abstenção > 50 %). RED: suíte adversarial ≥ 60 frases (§4.1). Aceite: 0 sem lastro passam; ≥ 95 % das legítimas passam; sem chamada real à nuvem nos testes (cliente falso).
9. **UI.** Seção "Laudo estruturado" no frontend: etiqueta de nível por frase, fontes no hover, Concordo/Discordo por seção, texto livre para região não avaliada, campo de comunicação não rotineira (só local) e nota de IA. RED: vitest do componente. Aceite: Playwright em 320/768/1024/1440, alvo de toque ≥ 44 px, claro e escuro, sem overflow.
10. **Casos-ouro + kit de revisão.** `bench/rx_gold_fetch.py` (baixa os arquivos de §4.2 para `data/gold_rx/`, confere a licença pela API e grava o manifesto) e `bench/rx_review_kit.py` (exporta N laudos em markdown com planilha de gravidade 0-3). Testes dão `skip` sem as imagens. Aceite: o manifesto registra licença e URL de cada imagem; nada de imagem no git.
