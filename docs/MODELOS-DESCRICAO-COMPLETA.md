# Modelos de descrição completa — ECG e RX (parágrafo único)

Data: 2026-11-25. Autor: analista Fable (pesquisa + redação). Estado: proposta para revisão do médico responsável.

Objetivo: dar ao MedLens um padrão para que o laudo de ECG e o de RX terminem com **um parágrafo único, coeso e completo**, que percorra o exame inteiro na ordem em que um leitor treinado o lê. "Completo" aqui quer dizer **cobertura completa**: todo item do roteiro aparece no parágrafo, como medida, como achado com grau de certeza permitido ou como abstenção explícita. Não quer dizer afirmar mais do que a ficha de fatos sustenta.

Avisos de escopo:

- Todos os números e casos deste documento são **fictícios**, criados para ilustrar a redação. Nenhum dado de paciente foi usado.
- Os parágrafos-modelo são redação própria. Há uma única citação literal curta, identificada na seção 1.1.
- O OpenEvidence não foi consultado (exige login). Só fontes públicas, listadas na seção 7, com a indicação do que foi de fato lido.
- Faixas de referência citadas aqui vêm das fontes indicadas e servem para a redação. Limiar novo só entra no código depois de conferido na fonte primária e aprovado pelo médico.

---

## 1. Ordem de leitura e vocabulário (resumo das fontes)

### 1.1 ECG

A Diretriz da SBC de 2022 (item 1.2.1, laudo descritivo) define o conteúdo mínimo do laudo descritivo em cinco blocos, nesta ordem: ritmo e frequência cardíaca; onda P (duração, amplitude, morfologia) e intervalo PR; eixo elétrico de P, QRS e T; QRS (duração, amplitude, morfologia); repolarização ventricular (ST-T, QT e U, quando presentes). O laudo conclusivo é a síntese dos diagnósticos. Sobre o laudo automatizado, a diretriz exige conferência médica das medidas, porque, nas palavras do texto, "o laudo é um ato médico" (SBC 2022, item 1.2.3). Antes de tudo vem a qualidade técnica (seção 2 da diretriz): calibração de 1 mV = 10 mm, troca de eletrodos, tremor, oscilação da linha de base, interferência elétrica e falhas de software de aquisição.

Valores de referência lidos na diretriz SBC 2022 (adulto):

| Item | Referência lida | Onde |
|---|---|---|
| Ritmo sinusal | P positiva em D1, D2 e aVF; eixo de P entre 0° e +90° | 3.1.1 |
| Onda P | amplitude até 2,5 mm; duração até 110 ms | 3.1.1 |
| Frequência sinusal | bradicardia abaixo de 50 bpm; taquicardia a partir de 100 bpm | 3.2.3.2 e 3.2.3.5 |
| PR | 120 a 200 ms (para FC até 90 bpm) | seção 4 |
| QRS | duração abaixo de 120 ms; eixo no plano frontal entre −30° e +90° | 5.1.1 e 5.1.2 |
| QTc | até 450 ms em homens e 470 ms em mulheres | 9.1.1.5 |
| Fórmula do QTc | Bazett tem limitação com FC abaixo de 60 ou acima de 90 bpm; nesses casos, fórmula linear (Framingham ou Hodges) | 9.1.1.5 |

A LITFL (PR, eixo, QT) traz as mesmas faixas para PR (120 a 200 ms) e eixo (−30° a +90°) e lista as quatro fórmulas de QTc (Bazett, Fridericia, Framingham, Hodges). A série AHA/ACCF/HRS de 2007 a 2009 tem seis partes: I tecnologia, II lista de enunciados diagnósticos, III distúrbios de condução intraventricular, IV ST, T, U e QT, V hipertrofia de câmaras, VI isquemia e infarto. Da parte II foi lido o resumo: ela organiza o vocabulário em enunciados primários, enunciados secundários, modificadores e enunciados de comparação entre ECGs. É esse desenho que justifica, no parágrafo, separar "o que foi medido" de "como qualifico" e de "comparado ao anterior".

### 1.2 RX de tórax (PA e perfil)

O parâmetro de prática do ACR para radiografia de tórax (fonte S1 da spec do repositório, PDF relido nesta sessão) pede, na PA ou AP: inclusão dos dois ápices e dos seios costofrênicos, coluna centrada entre as clavículas (rotação) e visibilização dos corpos vertebrais torácicos baixos e das estruturas retrocardíacas (penetração). O roteiro ABCDEFGHI do Radiopaedia ordena a leitura assim: qualidade e via aérea; ossos e partes moles; coração; diafragma; derrames; campos pulmonares, fissuras e corpos estranhos (tubos, cateteres, marca-passo, material cirúrgico); grandes vasos e bolha gástrica; hilos e mediastino; impressão. Para a qualidade, o mesmo roteiro usa posição, inspiração, exposição e rotação.

Vocabulário: o repositório já adota o glossário da Fleischner Society de 2024 (S4), que substitui o de 2008 (o resumo de 2008 foi relido; ele próprio substituía os de 1984 e 1996). Regra prática herdada da spec: **não usar "infiltrado"**; preferir opacidade, consolidação, atelectasia, opacidade reticular, nódulo, massa, derrame pleural, pneumotórax. Atenção: o roteiro do Radiopaedia ainda usa "infiltrates"; não importar esse termo.

Colégio Brasileiro de Radiologia: **não foi encontrado modelo oficial de laudo estruturado de RX de tórax do CBR** em fonte aberta. O que existe e já está na spec é S7 (artigo da Radiologia Brasileira sobre a opinião do médico solicitante, que menciona recomendações mínimas do CBR) e S8 (nota do CBR sobre IA). A busca apontou ainda um consenso de terminologia torácica em português e um artigo de revisão da USP que sugere usar o laudo de exame sem achados como roteiro de análise; ambos apareceram só em resultado de busca e **não foram lidos**, então não sustentam nenhuma frase daqui.

### 1.3 Ordem adotada para o parágrafo

A ordem do parágrafo segue a ordem das seções que o código já produz, para que cada trecho tenha um campo de origem:

- ECG (`LaudoECG`): `qualidade_tecnica` → `ritmo_frequencia` → `onda_p` → `intervalos` (PR, QRS, QT) com `qtc_formula` → `eixos` → `complexo_qrs` → `st_t` → `comparacao` → `impressao` e `limitrofes` → `recomendacao`.
- RX (`rx_laudo/v1`): identificação e técnica → qualidade e limitações → achados por região (pleura, pulmões, mediastino e hilos, coração e vasos, diafragma, ossos e partes moles, dispositivos) → sinais do modelo auxiliar → impressão (com o bloco crítico fixo) → recomendações → revisão médica.

---

## 2. ECG

### 2.1 Checklist ordenado

1. **Técnica e qualidade.** Origem do traçado (aparelho, PDF, foto digitalizada), número de derivações, velocidade e ganho informados, qualidade da digitalização, ruído, linha de base, suspeita de troca de eletrodos. Se houver divergência entre a medida digitalizada e o cabeçalho impresso, dizer isso logo no início.
2. **Ritmo.** Origem (sinusal ou não) com o critério observado (P antes de cada QRS, polaridade de P), regularidade.
3. **Frequência cardíaca.** Valor em bpm e como foi obtida.
4. **Onda P.** Duração, amplitude, eixo, morfologia, quando medidos.
5. **Intervalo PR.** Valor e posição em relação à faixa do critério citado.
6. **QRS.** Duração, eixo no plano frontal, morfologia (padrão de bloqueio de ramo, ondas Q, progressão de R nas precordiais), voltagem.
7. **ST.** Desnível por derivação ou parede, só se medido; caso contrário, abstenção.
8. **Onda T e onda U.** Polaridade e distribuição, só se medidas.
9. **QT e QTc.** Valor, fórmula usada e por que essa fórmula (FC fora de 60 a 90 bpm pede fórmula linear); ressalva quando o QRS é largo.
10. **Comparação.** Com ECG anterior, só se existir fato; sem fato, não afirmar nada sobre exame prévio.
11. **Síntese.** Regras atingidas, em ordem de relevância; achados limítrofes à parte.
12. **Fecho.** O que não foi avaliável e a necessidade de conferência no traçado original e de revisão médica.

### 2.2 Parágrafos-modelo (valores fictícios)

**A. Caso com achados**

> Traçado de 12 derivações recebido como arquivo digital, com velocidade e ganho informados na ficha e qualidade técnica boa, sem divergência entre as medidas digitalizadas e o cabeçalho impresso. O ritmo é sinusal, com onda P positiva em D1, D2 e aVF antes de cada QRS, regular, com frequência de 96 bpm. O intervalo PR mede 216 ms, acima do limite de 200 ms do critério citado, achado que corresponde a atraso da condução atrioventricular de primeiro grau. O QRS dura 138 ms, acima de 120 ms, com eixo em −40° e morfologia que atende à regra de bloqueio do ramo esquerdo registrada na ficha. As alterações de ST e T em V5 e V6 são discordantes do QRS e ficam descritas como alteração secundária da repolarização no contexto do distúrbio de condução; com esse padrão, a presença de isquemia não é avaliável com segurança por este traçado. O QT mede 400 ms e o QTc 463 ms pela fórmula de Hodges, escolhida porque a frequência está acima de 90 bpm; como o QRS é largo, parte desse valor decorre da despolarização, e a leitura do QTc fica limitada. Onda U e amplitude da onda P não foram medidas. A ficha não traz ECG anterior, de modo que nada se afirma sobre mudança em relação a exames prévios. Em síntese, ritmo sinusal com PR acima da faixa de referência e QRS largo com padrão de bloqueio do ramo esquerdo, a correlacionar com a clínica; rascunho automático que exige conferência no traçado original e revisão médica.

**B. Caso sem achados automáticos (com as abstenções corretas)**

> Traçado de 12 derivações recebido como arquivo digital, com velocidade e ganho informados na ficha e qualidade técnica boa. O ritmo é sinusal, com onda P positiva em D1, D2 e aVF antes de cada QRS, regular, com frequência de 78 bpm, dentro da faixa do critério citado. A onda P dura 96 ms, com eixo em +55°. O intervalo PR mede 164 ms, dentro da faixa de 120 a 200 ms. O QRS dura 92 ms, abaixo de 120 ms, com eixo em +45°, dentro da faixa de −30° a +90°; nenhuma regra automática de bloqueio de ramo, de onda Q ou de voltagem foi atingida. Nas derivações medidas, nenhuma regra automática de desnível de ST foi atingida; a morfologia fina de ST e T e a onda U não foram avaliadas automaticamente. O QT mede 380 ms e o QTc 433 ms pela fórmula de Bazett, aplicável porque a frequência está entre 60 e 90 bpm, abaixo do limite do critério citado. A ficha não traz ECG anterior para comparação. Em síntese, nenhum critério automático foi atingido nas medidas feitas; isso descreve o alcance da análise e não equivale a declarar o exame sem alterações, porque os itens não avaliados dependem da leitura do médico no traçado original.

**C. Caso com limitação técnica (foto de ECG em papel, com ruído)**

> Traçado de 12 derivações digitalizado a partir de fotografia de papel, com ruído e oscilação da linha de base em derivações dos membros e qualidade da digitalização baixa; a frequência e o intervalo PR digitalizados divergem dos valores impressos no cabeçalho, e por isso todas as medidas abaixo têm incerteza. O ritmo parece regular, com frequência estimada de 84 bpm; a origem sinusal não é avaliável com segurança, porque a onda P não foi delimitada de forma confiável. O intervalo PR e a duração da onda P não são avaliáveis com segurança neste traçado. O QRS foi estimado em 104 ms, medida com incerteza, e o eixo em +30°. Segmento ST, onda T e onda U não são avaliáveis com segurança, dado o ruído de linha de base; nada se afirma sobre isquemia, pré-excitação ou bloqueios. O QT não foi medido e o QTc não foi calculado. A ficha não traz ECG anterior. Em síntese, traçado de qualidade insuficiente para laudo automático confiável: recomenda-se conferir as medidas no traçado original e, se a dúvida persistir, repetir o registro, a critério do médico.

### 2.3 Banco de frases por item

Em todas as frases, `{…}` é valor da ficha. Não escrever número que não esteja na ficha.

| Item | Achado presente (medido ou regra) | Não avaliado | Medida com incerteza |
|---|---|---|---|
| Qualidade | "Traçado de {n} derivações, qualidade técnica {nivel}." | "Qualidade técnica não avaliada." | "Qualidade da digitalização {nivel}: as medidas abaixo têm incerteza." |
| Ritmo | "Ritmo sinusal, com P positiva em D1, D2 e aVF antes de cada QRS." / "Ritmo irregular, sem onda P identificável, que atende à regra de {regra}." | "Origem do ritmo não avaliável com segurança." | "O ritmo parece regular; a origem sinusal não é avaliável com segurança." |
| Frequência | "Frequência de {fc} bpm, {acima/abaixo/dentro} da faixa do critério citado." | "Frequência não medida." | "Frequência estimada de {fc} bpm, divergente do valor impresso ({fc_imp} bpm)." |
| Onda P | "Onda P com duração de {p} ms e eixo em {eixo_p}°." | "Onda P não avaliada automaticamente." | "Onda P de delimitação incerta; duração não informada." |
| PR | "PR de {pr} ms, {dentro da faixa de 120 a 200 ms / acima de 200 ms / abaixo de 120 ms}." | "PR não avaliável com segurança." | "PR estimado em {pr} ms, medida com incerteza; conferir no traçado." |
| QRS | "QRS de {qrs} ms, {abaixo de / acima de} 120 ms, com morfologia que atende à regra de {regra}." | "Morfologia do QRS não avaliada automaticamente." | "QRS estimado em {qrs} ms, medida com incerteza." |
| Eixo | "Eixo do QRS em {eixo}°, {dentro da faixa de −30° a +90° / desviado para a esquerda / desviado para a direita}." | "Eixo não calculado." | "Eixo estimado em {eixo}°, calculado sobre derivações com ruído." |
| ST-T | "Desnível de ST de {mm} mm em {derivacoes}, que atende à regra {regra}." / "Alteração de ST-T discordante do QRS, descrita como secundária ao distúrbio de condução." | "ST e T não avaliáveis com segurança; nada se afirma sobre isquemia." | "Desnível de ST estimado em {mm} mm em {derivacoes}, sobre linha de base instável; conferir no traçado." |
| QT | "QT de {qt} ms e QTc de {qtc} ms pela fórmula de {formula}." | "QT não medido; QTc não calculado." | "QTc de {qtc} ms ({formula}), de leitura limitada porque {fc fora de 60 a 90 bpm / QRS largo / fim da T incerto}." |
| Comparação | "Em relação ao ECG de {data}, {mudanca}." (só com fato) | "A ficha não traz ECG anterior." | não se aplica |

Conectivos úteis: "com" e "que" para encadear medida e qualificação; "achado que corresponde a" para ligar medida e regra; "de modo que" e "por isso" para ligar limitação e abstenção; "em síntese" para abrir a síntese; "a correlacionar com a clínica" para fechar.

---

## 3. RX de tórax

### 3.1 Checklist ordenado

1. **Identificação e técnica.** Incidência (PA, AP, perfil), número de imagens, posição se houver tag. Sem dado pessoal no texto.
2. **Qualidade técnica.** Inclusão de ápices e seios, rotação, inspiração, penetração; cada limitação diz o que ela limita.
3. **Pleura.** Seios costofrênicos, derrame, pneumotórax.
4. **Pulmões.** Volumes e simetria; opacidade, consolidação, atelectasia, nódulo, massa, padrão intersticial, hiperinsuflação.
5. **Mediastino e hilos.** Largura do mediastino, posição da traqueia, hilos.
6. **Coração e vasos.** Índice cardiotorácico, contorno cardíaco, aorta e vasos.
7. **Diafragma.** Altura e contorno das cúpulas, ar livre subdiafragmático.
8. **Ossos e partes moles.** Arcos costais, clavículas, coluna, ombros; enfisema subcutâneo, partes moles.
9. **Dispositivos.** Tubos, cateteres, sondas, eletrodos, fios e clipes cirúrgicos, com posição.
10. **Perfil, se houver.** Espaços retroesternal e retrocardíaco, seios posteriores, coluna. No estado atual do código, perfil não tem medida automática.
11. **Sinais do modelo auxiliar.** Em trecho próprio, com a frase fixa de escore de modelo.
12. **Síntese.** Só regras atingidas ou medidas fora da faixa, mais o bloco crítico fixo.
13. **Fecho.** Recomendações genéricas e condicionais; rascunho para revisão médica.

O que o MedLens mede hoje (e portanto pode entrar como medida): ICT, largura do mediastino (% ou mm), desvio traqueal, diferença de altura das cúpulas, razão de área pulmonar E/D, e as estimativas de rotação, inspiração e penetração. Todo o resto é abstenção ou sinal do modelo auxiliar.

### 3.2 Parágrafos-modelo (valores fictícios)

Cada frase traz entre colchetes, só neste documento, o nível do fato que a sustenta. Os colchetes não vão para o texto exibido.

**A. Caso com achados**

> Radiografia de tórax em PA, uma imagem, com rotação e penetração em estimativa automática adequada e inspiração indeterminada, o que limita a avaliação de volumes pulmonares e cúpulas. [QUALIDADE] Na região do coração e vasos, o índice cardiotorácico medido foi 0,56, acima de 0,50, o que sugere aumento da silhueta cardíaca (critério de acurácia limitada; medida com incerteza de ±0,05, que pode estar subestimada), enquanto o contorno cardíaco e os vasos não foram avaliados. [REGRA] No mediastino, a largura medida foi 27% da largura torácica e o desvio traqueal medido foi +0,8% da largura torácica; os hilos não foram avaliados. [MEDIDO] A razão de área pulmonar E/D medida foi 0,94 e a diferença de altura das cúpulas medida foi +3,1% da altura pulmonar; opacidades, nódulos, padrão intersticial e ar livre subdiafragmático não foram avaliados. [MEDIDO] Em trecho separado, o modelo auxiliar indica possível derrame pleural (probabilidade calibrada ≈ 0,71), escore de modelo que não confirma nem afasta o achado; a pleura não foi medida. [SUGERIDO_MODELO] Ossos, partes moles e dispositivos não avaliados nesta análise automática. [NAO_AVALIADO] Pneumotórax, pneumoperitônio e posição de tubos e cateteres não são avaliados por esta análise e exigem revisão da imagem. [NAO_AVALIADO] Rascunho automático para revisão médica, a correlacionar com a clínica. [QUALIDADE]

**B. Caso sem achados automáticos (com as abstenções corretas)**

> Radiografia de tórax em PA, uma imagem, com rotação, inspiração e penetração em estimativa automática adequada. [QUALIDADE] O índice cardiotorácico medido foi 0,46, com incerteza de ±0,05 (pode estar subestimado), valor que não exclui aumento da silhueta cardíaca; o contorno cardíaco e os vasos não foram avaliados. [MEDIDO] A largura do mediastino medida foi 25% da largura torácica e o desvio traqueal medido foi −0,4% da largura torácica, sem avaliação dos hilos. [MEDIDO] A razão de área pulmonar E/D medida foi 1,02 e a diferença de altura das cúpulas medida foi +2,0% da altura pulmonar; opacidades, nódulos, padrão intersticial e ar livre subdiafragmático não foram avaliados. [MEDIDO] Pleura, ossos, partes moles e dispositivos não avaliados nesta análise automática. [NAO_AVALIADO] Nenhum critério automático foi atingido nas medidas feitas, o que descreve o alcance da análise e não o estado do exame: as regiões não avaliadas dependem da leitura do médico. [NAO_AVALIADO] Pneumotórax, pneumoperitônio e posição de tubos e cateteres não são avaliados por esta análise e exigem revisão da imagem. [NAO_AVALIADO] Rascunho automático para revisão médica, a correlacionar com a clínica. [QUALIDADE]

**C. Caso com limitação técnica (AP, rodado, inspiração ruim)**

> Radiografia de tórax em AP, uma imagem, com rotação possivelmente inadequada (estimativa automática), que limita a avaliação de mediastino, traqueia e silhueta cardíaca, inspiração possivelmente inadequada, que limita a avaliação de volumes pulmonares e cúpulas, e penetração indeterminada, que limita a avaliação de parênquima e estruturas retrocardíacas. [QUALIDADE] O ICT foi 0,58 em AP, incidência que magnifica o coração, e por isso o valor não deve ser usado para afirmar cardiomegalia. [REGRA] A largura do mediastino e o desvio traqueal não foram medidos com confiança (segmentação de baixa confiabilidade). [NAO_AVALIADO] Pulmões, pleura, diafragma, ossos, partes moles e dispositivos não avaliados nesta análise automática. [NAO_AVALIADO] Pneumotórax, pneumoperitônio e posição de tubos e cateteres não são avaliados por esta análise e exigem revisão da imagem. [NAO_AVALIADO] Se a dúvida persistir, considerar incidência em PA ou perfil; as limitações técnicas listadas podem justificar nova radiografia, a critério do médico. [QUALIDADE]

### 3.3 Banco de frases por região

| Região | Achado presente (com lastro) | Não avaliado | Medida com incerteza |
|---|---|---|---|
| Técnica | "Radiografia de tórax em {incidencia}, {n} imagem(ns)." | "Incidência não informada." | "{Rotação/Inspiração/Penetração} possivelmente inadequada (estimativa automática): limita a avaliação de {alvo}." |
| Pulmões | "Razão de área pulmonar E/D medida {v}." / com regra: "…, acima do limiar local (heurística local, sem fonte primária; correlacionar)." | "Pulmões: opacidades, nódulos e padrão intersticial não avaliados nesta análise automática." | "Razão de área pulmonar não medida com confiança (segmentação de baixa confiabilidade)." |
| Pleura | só modelo: "Modelo auxiliar: possível derrame pleural (probabilidade calibrada ≈ {p}); escore de modelo; não confirma nem afasta." | "Pleura: não avaliado nesta análise automática." | "Modelo auxiliar: indeterminado para derrame pleural; não permite afirmar nem afastar." |
| Mediastino e hilos | "Largura do mediastino medida {v}% da largura torácica." / "Desvio traqueal medido {±v}% da largura torácica." | "Mediastino e hilos: hilos não avaliados nesta análise automática." | "Largura do mediastino não medida com confiança (segmentação de baixa confiabilidade)." |
| Silhueta cardíaca | "Índice cardiotorácico medido {v}, acima de 0,50: sugere aumento da silhueta cardíaca (critério de acurácia limitada; correlacionar)." | "Coração e vasos: contorno cardíaco e vasos não avaliados nesta análise automática." | "Índice cardiotorácico medido {v}, com incerteza (±0,05; pode estar subestimado): não exclui aumento da silhueta cardíaca." / "ICT {v} em AP: a incidência magnifica o coração; não usar para afirmar cardiomegalia." |
| Diafragma e seios | "Diferença de altura das cúpulas medida {±v}% da altura pulmonar." | "Diafragma: ar livre subdiafragmático não avaliado nesta análise automática." | "Diferença de altura das cúpulas não medida com confiança (segmentação de baixa confiabilidade)." |
| Ossos | sem lastro automático hoje; só o médico descreve | "Ossos e partes moles: não avaliado nesta análise automática." | "Modelo auxiliar: indeterminado para fratura; não permite afirmar nem afastar." |
| Partes moles | sem lastro automático hoje | (mesma frase de ossos e partes moles) | não se aplica |
| Dispositivos | sem lastro automático hoje | "Dispositivos: não avaliado nesta análise automática." | não se aplica |
| Crítico (fixo) | não se aplica | "Pneumotórax, pneumoperitônio e posição de tubos/cateteres NÃO são avaliados por esta análise: revisar a imagem." | não se aplica |

Conectivos úteis: "Na região de…", "No mediastino…", "enquanto… não foram avaliados", "sem avaliação de…", "em trecho separado", "o que limita a avaliação de…", "e por isso". Evitar "não é possível" e "não foi possível" em frase de RX: o léxico lê "possível" como grau de certeza de modelo (ver 5.2).

---

## 4. Outras incidências e regiões (só estilo)

O MedLens hoje só analisa tórax; abdome e coluna caem em `fora_de_escopo`. Esta seção serve de guia de estilo para o médico e para uma eventual expansão. **O sistema não deve gerar descrição automática dessas regiões.** Se a imagem não for de tórax, o parágrafo automático se resume a: "Imagem fora do escopo desta análise automática (tórax): nenhuma região foi avaliada."

### 4.1 RX de abdome

Ordem (roteiro ABDO X do Radiopaedia): ar (onde deveria e onde não deveria estar); alças (posição, calibre, parede); estruturas densas, calcificações e ossos; órgãos e partes moles; objetos externos e artefatos. O mesmo roteiro lembra que o RX de tórax em pé é mais sensível que o de abdome para ar livre intraperitoneal.

Esqueleto de parágrafo para o médico preencher (não é saída do sistema):

> Radiografia de abdome em {incidência e posição}, {n} imagem(ns), com inclusão {das cúpulas diafragmáticas à sínfise púbica / incompleta, o que limita…}. Distribuição do gás intestinal {descrição}, com alças de delgado de calibre {valor ou descrição} e cólon {descrição}; {níveis hidroaéreos, se em pé ou decúbito lateral}. {Sinais de gás fora da luz intestinal: descrição ou "não identificados nesta incidência, que tem sensibilidade limitada para esse fim"}. Calcificações {localização e aspecto}. Contornos de fígado, baço, rins e psoas {descrição}. Estruturas ósseas incluídas {descrição}. Dispositivos e corpos estranhos {descrição}. {Síntese em uma oração e recomendação condicional}.

### 4.2 RX de coluna (exemplo: lombar)

Projeções lidas no Radiopaedia (série da coluna lombar): frente (AP ou PA) com inclusão de T11-T12 ao sacro; perfil para corpos vertebrais, pedículos e facetas; oblíquas para facetas e pars interarticularis; flexão e extensão para instabilidade. A ordem de leitura abaixo (alinhamento, ossos, espaços discais, partes moles) é conhecimento geral de ensino e **não foi conferida em fonte nesta sessão**.

Esqueleto de parágrafo para o médico preencher:

> Radiografia da coluna {segmento} em {frente e perfil}, com inclusão de {níveis}, {adequada / limitada por…}. Alinhamento {descrição das linhas vertebrais e da curvatura}. Corpos vertebrais com altura {descrição por nível}, contornos e pedículos {descrição}. Espaços discais {descrição por nível}. Articulações facetárias e elementos posteriores {descrição}. Partes moles paravertebrais {descrição}. {Material de síntese, se houver, com posição}. {Síntese e recomendação condicional, lembrando o limite da radiografia para lesão de partes moles e de canal}.

---

## 5. Armadilhas: o que o sistema nunca afirma sem lastro

### 5.1 Expressões vetadas e a abstenção correta

A lista de RX é a de `backend/app/rx/lexico.py` (`PROIBIDOS`), que vale para o laudo determinístico e para o validador da IA. Para o ECG, o validador (`backend/app/llm/validate.py`) já alerta quando o texto diz "normal" com regra crítica disparada e remove afirmações sobre achado suprimido; a recomendação aqui é aplicar ao parágrafo de ECG a mesma disciplina de RX.

| Nunca escrever | Por que é armadilha | Abstenção correta |
|---|---|---|
| "normal", "exame normal", "dentro da normalidade" | declara o exame inteiro com base em poucas medidas | "Nenhum critério automático atingido nas medidas feitas; regiões não avaliadas listadas em Achados." |
| "sem alterações" | nega tudo, inclusive o que não foi olhado | "{Região}: não avaliado nesta análise automática." |
| "afasta", "descarta", "exclui" como conclusão | nenhum fato do sistema tem poder de exclusão | "não confirma nem afasta" (frase-molde isenta); "não exclui {achado}" para medida na faixa |
| "ausência de {achado}" | negação de achado sem fato MEDIDO do mesmo tópico | "{achado} não avaliado nesta análise automática." |
| "livre", "seios livres", "campos livres" | idem; única exceção é o nome do sinal "ar livre" | "Pleura: não avaliado nesta análise automática." |
| "pulmões limpos", "campos pulmonares limpos" | o sistema não avalia parênquima | "Pulmões: opacidades, nódulos e padrão intersticial não avaliados nesta análise automática." |
| "sem isquemia", "sem sinais de isquemia" | ST-T nem sempre é avaliável; ECG sem desnível não encerra a questão | "Nenhuma regra automática de desnível de ST foi atingida nas derivações medidas." ou "ST e T não avaliáveis com segurança." |
| "diagnóstico de…", "confirma…" | diagnóstico é ato médico | "sugere…" (só com regra e critério) ou "achado que atende à regra de…" |
| "infiltrado" | termo abandonado no glossário Fleischner adotado (S4) | "opacidade" (e só com lastro) |
| "sem pneumotórax", "tubo bem posicionado" | itens críticos que o sistema não avalia | bloco crítico fixo (`CRITICO` em `rx/laudo.py`) |
| "sem mudança em relação ao anterior" | não há fato de exame prévio | "A ficha não traz exame anterior." |

### 5.2 Armadilhas de grau de certeza (tabela `GRAUS_PERMITIDOS`)

- "sugere" e "sugestivo" só em frase de nível REGRA. A zona do modelo se chama `sugestivo`, mas o texto da frase de modelo usa "possível", nunca "sugestivo".
- "possível" e "possivelmente" só em frase de SUGERIDO_MODELO ou QUALIDADE. Efeito colateral: "não é possível avaliar" numa frase MEDIDO, REGRA ou NAO_AVALIADO é lido como grau `possivel` e a frase é recusada. Escrever "não avaliado" ou "não há como afirmar".
- "compatível com" só para a própria medida, na mesma frase que contenha "medida" ou "faixa de referência"; nunca com nome de doença.
- "dentro da faixa de referência" exige fato MEDIDO.
- "indeterminado" não pode aparecer em frase de nível NAO_AVALIADO; ali o único grau aceito é "não avaliado".
- Frase isenta que contém palavra vetada: "não confirma nem afasta", "nem afastar", "não confirma", "ar livre". Fora desses moldes, a palavra vetada derruba a frase.

### 5.3 Armadilhas de construção do parágrafo

- **Completude por omissão.** Parágrafo fluido tende a pular o que não tem achado. Aqui é o contrário: item sem fato vira abstenção escrita. Conferir que os itens do checklist aparecem todos.
- **Número novo.** Não somar, converter, arredondar nem calcular. O número do texto é o número da ficha, com o mesmo valor.
- **Descritor visual sem imagem.** Sem imagem enviada à IA, nada de lobo, lado, contorno, broncograma ou "a imagem mostra".
- **Modelo auxiliar na síntese.** Escore de modelo fica em trecho próprio e não entra na síntese.
- **Zona `nao_sugerido` do modelo.** Não vira frase de ausência; a região continua "não avaliado".
- **Conduta.** Só recomendações genéricas e condicionais; sem tratamento.
- **Excesso de ressalva.** A abstenção é dita uma vez por item, em oração curta. Agrupar regiões não avaliadas numa mesma frase mantém o parágrafo legível.
- **Mistura de níveis na mesma frase.** Cada frase do parágrafo tem um nível só (o do fato mais fraco que ela cita). É isso que permite validar frase a frase.

---

## 6. Como usar no prompt do LLM

Desenho proposto, coerente com o contrato já existente (`{"afirmacoes":[…]}` validado frase a frase):

1. O LLM devolve o parágrafo como **lista ordenada de frases**, cada uma com os fatos que cita. O servidor valida cada frase com as regras atuais e só então junta as aprovadas com um espaço, formando o parágrafo único.
2. As frases fixas (bloco crítico, nota de rascunho) são acrescentadas pelo servidor, não pelo LLM.
3. Se houver abstenção do validador, o parágrafo é montado com as frases determinísticas, na mesma ordem. Sempre existe parágrafo; a IA nunca é requisito.

Pontos que exigem mudança de código (não feitos aqui): aceitar a seção nova `descricao_completa` no validador de RX e no de ECG; decidir se a frase de abstenção de região sem fato pode sair do LLM (hoje a regra 1 do prompt de RX exige ao menos um fato por afirmação) ou se fica sempre a cargo do servidor. A recomendação é a segunda opção.

### 6.1 RX — trecho de prompt

```text
TAREFA ADICIONAL: DESCRIÇÃO COMPLETA EM PARÁGRAFO ÚNICO
Além das afirmações por seção, produza a seção "descricao_completa": uma sequência ordenada de frases
que, lidas em seguida, formem um único parágrafo coeso descrevendo o exame inteiro.

Ordem obrigatória: técnica e qualidade; coração e vasos; mediastino e hilos; pulmões; diafragma; pleura;
ossos, partes moles e dispositivos; sinal do modelo auxiliar; síntese.

Regras:
1. Uma frase por fato ou por grupo de fatos da MESMA região e do MESMO nível. Cite os ids em "fatos".
2. Todo número vem dos fatos citados, com o mesmo valor. Não calcule nem arredonde.
3. Grau de certeza pelo nível do fato: REGRA usa "sugere"; SUGERIDO_MODELO usa "possível" ou
   "indeterminado" e termina com "escore de modelo; não confirma nem afasta"; MEDIDO descreve a medida;
   QUALIDADE descreve a técnica e o que ela limita.
4. Dentro da frase de uma região medida, diga o que NÃO foi avaliado nela, copiando o campo "escopo"
   da cobertura. Não escreva frase para região sem nenhum fato: o servidor acrescenta essas abstenções.
5. Proibido: normal, sem alterações, dentro da normalidade, afasta, descarta, exclui como conclusão,
   ausência de, livre(s), limpo(s), diagnóstico de, confirma, infiltrado. Não use "não é possível".
6. Não mencione pneumotórax, pneumoperitônio nem posição de tubos e cateteres: o servidor acrescenta
   o aviso fixo. Não descreva a imagem. Não escreva conduta.
7. Use conectivos para dar fluidez ("na região de", "enquanto", "o que limita"), sem criar conteúdo.

Saída: JSON {"afirmacoes":[{"secao":"descricao_completa","texto":"...","fatos":["F1"],"fontes":["S1"]}]}
```

Entrada de exemplo (fictícia, no formato da ficha `rx_ficha/v1`):

```json
{
  "versao": "rx_ficha/v1",
  "incidencias": ["PA"],
  "fatos": [
    {"id": "F1", "chave": "incidencia", "valor": "PA", "nivel": "QUALIDADE", "regiao": "tecnica"},
    {"id": "F2", "chave": "rotacao", "valor": "adequada", "nivel": "QUALIDADE", "regiao": "tecnica"},
    {"id": "F3", "chave": "inspiracao", "valor": "indeterminada", "nivel": "QUALIDADE", "regiao": "tecnica"},
    {"id": "F4", "chave": "penetracao", "valor": "adequada", "nivel": "QUALIDADE", "regiao": "tecnica"},
    {"id": "F5", "chave": "ict", "valor": 0.56, "nivel": "REGRA", "regiao": "coracao_vasos", "fontes": ["S6"]},
    {"id": "F6", "chave": "mediastino_largura_pct", "valor": 27, "unidade": "%", "nivel": "MEDIDO", "regiao": "mediastino_hilos"},
    {"id": "F7", "chave": "traqueia_desvio_pct", "valor": 0.8, "unidade": "%", "nivel": "MEDIDO", "regiao": "mediastino_hilos"},
    {"id": "F8", "chave": "pulmoes_razao_area_E_D", "valor": 0.94, "nivel": "MEDIDO", "regiao": "pulmoes"},
    {"id": "F9", "chave": "cupulas_diferenca_pct", "valor": 3.1, "unidade": "%", "nivel": "MEDIDO", "regiao": "diafragma"},
    {"id": "F10", "chave": "modelo.effusion", "valor": 0.71, "nivel": "SUGERIDO_MODELO", "regiao": "pleura", "zona": "sugestivo"}
  ],
  "cobertura": [
    {"regiao": "pleura", "avaliada": false, "sinal_modelo": true},
    {"regiao": "pulmoes", "avaliada": true, "escopo": "somente assimetria de área pulmonar; opacidades, nódulos e padrão intersticial não avaliados"},
    {"regiao": "mediastino_hilos", "avaliada": true, "escopo": "largura do mediastino e desvio traqueal; hilos não avaliados"},
    {"regiao": "coracao_vasos", "avaliada": true, "escopo": "índice cardiotorácico; contorno e vasos não avaliados"},
    {"regiao": "diafragma", "avaliada": true, "escopo": "diferença de altura das cúpulas; ar livre subdiafragmático não avaliado"},
    {"regiao": "ossos_partes_moles", "avaliada": false, "sinal_modelo": false},
    {"regiao": "dispositivos", "avaliada": false, "sinal_modelo": false}
  ]
}
```

Saída esperada do LLM:

```json
{"afirmacoes": [
  {"secao": "descricao_completa", "fatos": ["F1", "F2", "F3", "F4"], "fontes": ["S1"],
   "texto": "Radiografia de tórax em PA, com rotação e penetração em estimativa automática adequada e inspiração indeterminada, o que limita a avaliação de volumes pulmonares e cúpulas."},
  {"secao": "descricao_completa", "fatos": ["F5"], "fontes": ["S6"],
   "texto": "Na região do coração e vasos, o índice cardiotorácico medido foi 0,56, acima de 0,50, o que sugere aumento da silhueta cardíaca (critério de acurácia limitada; correlacionar), enquanto o contorno e os vasos não foram avaliados."},
  {"secao": "descricao_completa", "fatos": ["F6", "F7"], "fontes": [],
   "texto": "No mediastino, a largura medida foi 27% da largura torácica e o desvio traqueal medido foi +0,8% da largura torácica; os hilos não foram avaliados."},
  {"secao": "descricao_completa", "fatos": ["F8", "F9"], "fontes": [],
   "texto": "A razão de área pulmonar E/D medida foi 0,94 e a diferença de altura das cúpulas medida foi +3,1% da altura pulmonar; opacidades, nódulos, padrão intersticial e ar livre subdiafragmático não foram avaliados."},
  {"secao": "descricao_completa", "fatos": ["F10"], "fontes": ["S5"],
   "texto": "Em trecho separado, o modelo auxiliar indica possível derrame pleural (probabilidade calibrada ≈ 0,71); escore de modelo; não confirma nem afasta."}
]}
```

Parágrafo final montado pelo servidor (frases aprovadas + abstenções de região sem fato + bloco crítico + nota de rascunho): é o parágrafo-modelo A da seção 3.2.

Observação: a quarta frase junta pulmões (F8) e diafragma (F9), duas regiões de mesmo nível. Se o validador exigir uma região por frase, separar em duas.

### 6.2 ECG — trecho de prompt

```text
TAREFA ADICIONAL: DESCRIÇÃO COMPLETA EM PARÁGRAFO ÚNICO
Além das afirmações por seção, produza a seção "descricao_completa": uma sequência ordenada de frases
que, lidas em seguida, formem um único parágrafo coeso descrevendo o traçado inteiro.

Ordem obrigatória: qualidade técnica; ritmo e frequência; onda P; PR; QRS (duração, eixo, morfologia);
ST e T; QT e QTc com a fórmula; comparação; síntese.

Regras:
1. Cada frase cita em "fatos" os F que a sustentam e em "criterios" os C aplicáveis. Nunca escreva
   identificadores dentro do texto.
2. Todo número vem dos fatos ou critérios citados na mesma frase, com o mesmo valor. Não calcule.
3. Percorra TODOS os itens da ordem. Para item cujo fato está "não avaliável" ou "suprimido", escreva
   "não avaliável com segurança" e nada mais sobre ele. Para item sem fato nenhum, escreva
   "não medido" ou "não avaliado automaticamente", citando o fato de qualidade.
4. Diga a posição da medida em relação à faixa do critério citado ("dentro da faixa de", "acima de",
   "abaixo de"). Não use "normal", "sem alterações", "sem isquemia", "afasta", "descarta", "exclui".
5. Se a qualidade da digitalização for baixa ou houver divergência com o cabeçalho impresso, diga isso
   na primeira frase e trate as medidas como estimativas ("estimado em", "medida com incerteza").
6. Só afirme comparação com ECG anterior se houver fato. Sem fato: "A ficha não traz ECG anterior."
7. A síntese repete apenas as regras atingidas, em ordem de relevância. Se nenhuma foi atingida,
   escreva que nenhum critério automático foi atingido nas medidas feitas e que isso não equivale a
   declarar o exame sem achados.
8. Sem conduta terapêutica. Tom de rascunho para revisão médica.

Saída: JSON {"afirmacoes":[{"secao":"descricao_completa","texto":"...","fatos":["F1"],"criterios":["C1"]}]}
```

Entrada de exemplo (fictícia; o formato real é o texto de `user_message_v2`, mostrado aqui como JSON equivalente):

```json
{
  "ficha": "ecg_features/v1",
  "qualidade": "boa",
  "fatos": [
    {"id": "F1", "texto": "Digitalização de qualidade boa; 12 derivações; sem divergência com o cabeçalho impresso."},
    {"id": "F2", "texto": "Ritmo sinusal: P positiva em D1, D2 e aVF antes de cada QRS; regular."},
    {"id": "F3", "texto": "Frequência cardíaca 78 bpm."},
    {"id": "F4", "texto": "Onda P: duração 96 ms; eixo +55 graus."},
    {"id": "F5", "texto": "Intervalo PR 164 ms."},
    {"id": "F6", "texto": "QRS: duração 92 ms; eixo +45 graus."},
    {"id": "F7", "texto": "QT 380 ms; QTc 433 ms (Bazett)."},
    {"id": "F8", "texto": "ST: nenhuma regra de desnível atingida nas derivações medidas."},
    {"id": "F9", "texto": "Morfologia de ST-T e onda U: não avaliável."}
  ],
  "criterios": [
    {"id": "C1", "nome": "Convenções de medida"},
    {"id": "C2", "nome": "Ritmo sinusal e frequência", "limiares": {"bradicardia": "< 50 bpm", "taquicardia": ">= 100 bpm"}},
    {"id": "C3", "nome": "Intervalo PR", "limiares": {"faixa": "120 a 200 ms"}},
    {"id": "C4", "nome": "QRS", "limiares": {"duracao": "< 120 ms", "eixo": "-30 a +90 graus"}},
    {"id": "C5", "nome": "QTc", "limiares": {"homens": "<= 450 ms", "mulheres": "<= 470 ms", "Bazett": "FC 60 a 90 bpm"}}
  ]
}
```

Saída esperada do LLM:

```json
{"afirmacoes": [
  {"secao": "descricao_completa", "fatos": ["F1"], "criterios": ["C1"],
   "texto": "Traçado de 12 derivações com qualidade técnica boa, sem divergência entre as medidas digitalizadas e o cabeçalho impresso."},
  {"secao": "descricao_completa", "fatos": ["F2", "F3"], "criterios": ["C2"],
   "texto": "O ritmo é sinusal, com onda P positiva em D1, D2 e aVF antes de cada QRS, regular, com frequência de 78 bpm."},
  {"secao": "descricao_completa", "fatos": ["F4"], "criterios": ["C2"],
   "texto": "A onda P dura 96 ms, com eixo em +55 graus."},
  {"secao": "descricao_completa", "fatos": ["F5"], "criterios": ["C3"],
   "texto": "O intervalo PR mede 164 ms, dentro da faixa de 120 a 200 ms."},
  {"secao": "descricao_completa", "fatos": ["F6"], "criterios": ["C4"],
   "texto": "O QRS dura 92 ms, abaixo de 120 ms, com eixo em +45 graus, dentro da faixa de -30 a +90 graus."},
  {"secao": "descricao_completa", "fatos": ["F8", "F9"], "criterios": ["C1"],
   "texto": "Nenhuma regra automática de desnível de ST foi atingida nas derivações medidas; a morfologia de ST-T e a onda U não são avaliáveis com segurança."},
  {"secao": "descricao_completa", "fatos": ["F7"], "criterios": ["C5"],
   "texto": "O QT mede 380 ms e o QTc 433 ms pela fórmula de Bazett."},
  {"secao": "descricao_completa", "fatos": ["F1"], "criterios": ["C1"],
   "texto": "A ficha não traz ECG anterior para comparação."},
  {"secao": "descricao_completa", "fatos": ["F3", "F5", "F6", "F7", "F8"], "criterios": ["C2", "C3", "C4", "C5"],
   "texto": "Em síntese, nenhum critério automático foi atingido nas medidas feitas, o que não equivale a declarar o exame sem achados; conferir no traçado original."}
]}
```

Dois cuidados antes de ligar: (a) o validador de ECG confere se cada número está nos fatos ou critérios citados; os limiares do exemplo (120, 200, −30, +90) só passam se constarem do cartão citado; (b) a frase de comparação cita o fato de qualidade por falta de fato melhor; se o validador recusar, essa frase deve ser fixa do servidor.

---

## 7. Fontes consultadas

Lidas nesta sessão (texto aberto):

- Diretriz da SBC sobre a Análise e Emissão de Laudos Eletrocardiográficos, 2022 (Arq Bras Cardiol 2022;119(4):638-680). Texto integral via Europe PMC: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9563889/fullTextXML (mesmo artigo em https://pmc.ncbi.nlm.nih.gov/articles/PMC9563889/ e https://www.scielo.br/j/abc/a/4QcQvX3T6kZBjNQLzrt5cXj/). Lidos: itens 1.1, 1.2.1 a 1.2.4, 2.1.1, 3.1.1, 3.2.3.2, 3.2.3.5, PR (seção 4), 5.1.1, 5.1.2, critério de BRE, 9.1.1.5.
- LITFL ECG Library (CC BY-NC-SA 4.0; só paráfrase, sem reúso de texto): https://litfl.com/pr-interval-ecg-library/ , https://litfl.com/ecg-axis-interpretation/ , https://litfl.com/qt-interval-ecg-library/ , https://litfl.com/ecg-library/basics/ (índice).
- AHA/ACCF/HRS, Recommendations for the Standardization and Interpretation of the Electrocardiogram, Part II (2007), **só o resumo**, via Europe PMC (PMID 17322456): https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:17322456&resultType=core&format=json . Das partes I e III a VI foram lidos só os títulos (PMIDs 17322457, 19228822, 19228821, 19228820, 19228819).
- ACR–SPR–STR Practice Parameter for the Performance of Chest Radiography (S1 da spec): https://gravitas.acr.org/PPTS/DownloadPreviewDocument?DocId=129 . Relido o trecho de critérios de posicionamento (ápices, seios, coluna centrada, vértebras torácicas baixas).
- Radiopaedia (CC BY-NC-SA 3.0, não comercial; só paráfrase, sem reúso de texto): https://radiopaedia.org/articles/chest-radiograph-assessment-using-abcdefghi , https://radiopaedia.org/articles/abdominal-x-ray-review-abdo-x , https://radiopaedia.org/articles/lumbar-spine-series , https://radiopaedia.org/licence .
- Fleischner Society: Glossary of Terms for Thoracic Imaging, 2008 (Radiology 2008;246:697-722), **só o resumo**, via Europe PMC (PMID 18195376). A versão em uso no repositório é a de 2024 (S4).
- Do próprio repositório: `docs/RX-LAUDO-CONFIAVEL-SPEC.md`, `backend/app/rx/laudo.py`, `backend/app/rx/lexico.py`, `backend/app/rx/ficha.py`, `backend/app/llm/laudo.py`, `backend/app/llm/prompts/ecg_laudo_v2.md`, `backend/app/llm/prompts/rx_laudo_v1.md`.

Tentadas e **não lidas** (não sustentam nenhuma afirmação deste documento):

- StatPearls/NCBI Bookshelf (https://www.ncbi.nlm.nih.gov/books/NBK553874/ e https://www.ncbi.nlm.nih.gov/books/NBK2214/): o site respondeu com verificação reCAPTCHA; não foi contornada.
- Heart Rhythm Society, página e PDF da parte II (https://hrsonline.org/guidance/clinical-resources/2007-ahaacchrs-scientific-statement-recommendations-standardization-and-interpretation): HTTP 403.
- CBR: nenhum modelo oficial de laudo estruturado de RX de tórax localizado. Vistos só em resultado de busca, sem leitura: consenso de terminologia torácica em português e artigo de revisão da USP sobre radiografia de tórax.
- OpenEvidence: exige login; não consultado.

Pendências para o médico responsável: aprovar os parágrafos-modelo e as faixas da tabela 1.1 antes de qualquer uso em prompt de produção; decidir se o parágrafo único substitui ou acompanha a seção Impressão; decidir quem escreve as abstenções de região sem fato (recomendado: o servidor).
