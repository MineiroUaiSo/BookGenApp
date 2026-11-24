# Bibliografia de referência para o leitor de ECG do MedLens

Pesquisa feita em 2026-11-24 (web). Objetivo: fundamentar uma IA que (a) identifica cada onda do ECG em cada derivação, mede durações e intervalos e explica a condução cardíaca (nó SA, átrios, AV, His, ramos, Purkinje), e (b) faz análise crítica e diagnóstico diferencial a partir dessa descrição.

**Política de direitos autorais.** A base `knowledge/*.yaml` guarda só citações (autor, edição, capítulo/tabela) e critérios reescritos com palavras próprias. Nenhum texto, figura ou tabela protegido é copiado.

**Legenda de verificação.**
- **[V]** confirmado em busca (título, edição, ano e ISBN).
- **[V-parcial]** o livro existe, mas algum dado (ISBN, edição mais recente, autores de capítulo) não foi confirmado.
- **[A verificar]** vem da memória do pesquisador ou de fonte secundária e precisa ser conferido antes de citar.

**Limitações desta pesquisa.**
- Os sites acc.org e escardio.org não resolveram (rede bloqueada). Detalhes da 5ª Definição Universal de IM e dos Critérios Internacionais de 2025 vieram só de resultados de busca.
- Os números de tolerância da IEC 60601-2-25 vieram de fonte secundária (artigo arXiv) e não do texto da norma, que é paga.

---

## 1. Top 5 recomendados para a base de conhecimento

| # | Referência | Por que está no Top 5 |
|---|---|---|
| 1 | **Diretriz da SBC sobre a Análise e Emissão de Laudos Eletrocardiográficos – 2022** (Samesima N et al.; Arq Bras Cardiol 2022;119(4):638-680; **acesso aberto**) | É a única fonte em pt-BR e define o formato do laudo e a terminologia. Cobre ritmo, onda P, FC, condução AV e intraventricular, sobrecargas, isquemia, atleta e pediatria. Tem erratas que precisam ser aplicadas. Os critérios de laudo viram direto o esquema de saída do app. |
| 2 | **AHA/ACCF/HRS Recommendations for the Standardization and Interpretation of the ECG, Partes I–VI** (Kligfield, Mason, Surawicz, Rautaharju, Hancock, Wagner e outros; Circulation 2007 e 2009; **acesso aberto**) | É o padrão internacional de **definições** de onda, ponto fiducial e medida. Cobre onset e offset de P, QRS e T, QT/QTc, critérios de BRE e BRD, hipertrofia e lista de termos diagnósticos. É a melhor fonte para a delineação de ondas. |
| 3 | **Marriott's Practical Electrocardiography, 13ª ed.** (Strauss DG, Schocken DD; Wagner GS como colaborador; Wolters Kluwer/LWW, 2020-21) | É o texto mais completo para **diagnóstico diferencial** e correlação clínica. Reúne todas as arritmias, bloqueios, isquemia e síndromes de pré-excitação num único volume. |
| 4 | **Bayés de Luna – Clinical Electrocardiography: A Textbook** (4ª ed. 2012; 5ª ed. 2021-22) | É a melhor fonte para **correlação eletrofisiológica**: sequência de ativação, vetores, bloqueios fasciculares e do septo, áreas de IM por correlação com ressonância. Alimenta a animação da condução e a explicação "por que a onda tem essa forma". |
| 5 | **Goldberger's Clinical Electrocardiography: A Simplified Approach, 10ª ed.** (Goldberger AL, Goldberger ZD, Shvilkin A; Elsevier, 2023) | É o melhor texto para **leitura sistemática e ensino**: FC, eixo, intervalos e interpretação por derivação. Funciona como roteiro da "descrição sistemática" e dá a ordem das etapas de análise. |

Âncoras de critério (obrigatórias, mas fora do Top 5 por serem documentos de critério e não livros): **5ª Definição Universal de IM (2026)**, **ESC 2021 Marcapasso/CRT** e **ESC 2022 Arritmias Ventriculares**. Entram no YAML de isquemia, condução e arritmias.

---

## 2. Tier 1 (núcleo, indispensável)

| Item | Edição, ano, autores, editora | ISBN / DOI | Uso no projeto | Acesso | URL | Status |
|---|---|---|---|---|---|---|
| **Diretriz da SBC sobre a Análise e Emissão de Laudos Eletrocardiográficos – 2022** | Arq Bras Cardiol 2022;119(4):638-680. Samesima N e colaboradores (SBC). Em inglês: "Brazilian Society of Cardiology Guidelines on the Analysis and Issuance of Electrocardiographic Reports – 2022". Há errata (dez/2022): o item 12.1.2 passa de QRS 160 ms para **140 ms** (PMC9814798). Há também carta com comentários sobre o ECG do atleta (PMC9833214). | DOI 10.36660/abc.20220623 | Estrutura do laudo (descritivo, conclusivo, automático), qualidade técnica do traçado, ritmo, onda P, FC, condução, sobrecargas, isquemia, atleta e pediatria. Fonte primária das regras em pt-BR. | **Aberto** (SciELO/PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC9563889 · SciELO: https://www.scielo.br/j/abc/a/4QcQvX3T6kZBjNQLzrt5cXj/ · Errata: https://pmc.ncbi.nlm.nih.gov/articles/PMC9814798 | [V] |
| **AHA/ACCF/HRS Recommendations for the Standardization and Interpretation of the ECG, Partes I–VI** | I: tecnologia do ECG (Kligfield et al., Circulation 2007;115:1306-1324). II: lista de termos diagnósticos (Mason et al., 2007). III: distúrbios de condução intraventricular (Surawicz, Childers, Deal, Gettes; Circulation 2009;119:e235-e240). IV: ST, T, U e QT (Rautaharju, Surawicz, Gettes; 2009;119:e241-e250). V: hipertrofia de câmaras (Hancock et al.; 2009;119:e251-e261). VI: isquemia aguda e infarto (Wagner et al.; 2009;119:e262-e270). Cópias paralelas em JACC 2009 e Heart Rhythm. Endossadas pela ISCE. | Parte I: JACC/HRJ/Circulation (DOI nos sites) | I: filtros, frequência de amostragem e padrões de medida. II: vocabulário do laudo. III: BRE, BRD, bloqueios fasciculares e critérios. IV: pontos de medida de ST/T/U e fórmulas de QTc. V: critérios de HVE, HVD e átrio. VI: critérios de elevação de ST por derivação. É o conjunto que mais ajuda na delineação das ondas. | **Aberto** (PDFs no HRS e na AHA) | Índice: https://hrsonline.org/guidance/clinical-resources/ahaaccfhrs-scientific-statement-recommendations-standardization-and-interpretation · Parte III: https://hrsonline.org/documents/interpretation-electrocardiogram-part-iii-intraventricular-conduction-disturbancespdf/download · Parte IV: https://hrsonline.org/documents/interpretation-electrocardiogram-part-iv-st-segment-t-and-u-waves-and-qt-intervalpdf/download · Parte VI: https://hrsonline.org/documents/standardization-and-interpretation-electrocardiogram-part-vipdf/download | [V] (autores da Parte VI conferir; a busca trouxe listas divergentes) |
| **Marriott's Practical Electrocardiography, 13ª ed.** | Strauss DG, Schocken DD; Wagner GS (colaborador). Wolters Kluwer / Lippincott Williams & Wilkins. 2020 na ficha do editor; 2021 em vários catálogos de biblioteca. | Impresso 9781496397454; e-book 9781496397461; VitalSource 9781496397478 | Diferencial de arritmias, bloqueios AV, pré-excitação, hipertrofia, isquemia. Correlação clínica e armadilhas. | Pago | https://shop.lww.com/p/9781496397454 | [V] |
| **Bayés de Luna – Clinical Electrocardiography: A Textbook** | 4ª ed. 2012, Wiley-Blackwell, Bayés de Luna A (com Bayés-Genís A): ISBN 978-0-470-65859-8 (impresso, 568 p.) e 978-1-118-39201-0 (e-book). Edição mais recente: 5ª ed., Wiley, 2021-22 (ed. Bayés de Luna, Fiol-Sala, Bayés-Genís, Baranchuk): ISBN 9781119536451. | ver à esquerda | Eletrofisiologia aplicada: sequência de ativação, vetorcardiograma, bloqueios fasciculares e septais, localização do IM, pré-excitação. Base da animação da condução. | Pago | https://www.wolterskluwer.com/en/solutions/ovid/clinical-electrocardiography-12654 | [V] (4ª ed.); [V-parcial] (5ª ed.: ISBN vem de resenha, ano 2021 ou 2022 a conferir) |
| **Goldberger's Clinical Electrocardiography: A Simplified Approach, 10ª ed.** | Goldberger AL, Goldberger ZD, Shvilkin A. Elsevier, 2023 (ficha do editor: 2 de fev; varejistas: 17 de abril de 2023). 320 p. | Impresso 9780323824750; e-book 9780323824767; VitalSource 9780323824774 | Roteiro de análise passo a passo (ritmo, FC, eixo, intervalos, hipertrofia, isquemia). Bom para a ordem das etapas da descrição. | Pago | https://shop.elsevier.com/books/goldbergers-clinical-electrocardiography/goldberger/978-0-323-82475-0 | [V] |
| **Quarta Definição Universal de IM (2018) e Quinta (2026)** | **5ª Definição**: Mills NL, Newby LK, Zaman S et al. Força-tarefa conjunta ESC/ACC/AHA/WHF, 2026. Citação JACC 88(11):1314-1368, DOI 10.1016/j.jacc.2026.07.025 (fonte UCL). Há publicação paralela no Eur Heart J / Circulation; a busca divergiu quanto ao periódico de referência. A 5ª substitui a de 2018 e classifica IM em primário, secundário e relacionado a procedimento. Define lesão miocárdica por troponina com limites sex-específicos. | DOI acima | Critérios de ECG para isquemia e IM. **Os limiares de ST e a parte de IM oclusivo não foram confirmados nesta pesquisa**: ler o texto completo antes de gravar no YAML. | **Aberto** (manuscrito em UCL Discovery; páginas ESC/AHA) | https://professional.heart.org/en/science-news/fifth-universal-definition-of-myocardial-infarction-2026 · https://discovery.ucl.ac.uk/id/eprint/10230734/ | [V-parcial] |
| **ESC 2021 – Diretrizes de marcapasso e CRT** | Glikson M et al. Eur Heart J 2021;42:3427-3520 (também EP Europace 2022;24:71-164). | DOI via PubMed 34455427 | Algoritmo de avaliação de bradicardia e doença de condução. Critério de QRS ≥150 ms com BRE para CRT. Reforça o pipeline de condução (BAV, BRE, BRD, fasciculares). | **Aberto** | https://pubmed.ncbi.nlm.nih.gov/34455427/ | [V] |

---

## 3. Tier 2 (alta utilidade, complementar)

| Item | Edição, ano, autores, editora | ISBN | Uso no projeto | Acesso | URL | Status |
|---|---|---|---|---|---|---|
| **Chou's Electrocardiography in Clinical Practice: Adult and Pediatric, 6ª ed.** | Surawicz B, Knilans T. Elsevier/Saunders, mar/2008, 752 p. A busca não achou edição mais nova. | Impresso 9781416037743; e-book 9781437711028 | Enciclopédia de morfologias: bloqueios, hipertrofia, repolarização, distúrbios eletrolíticos, pediatria. Surawicz é coautor das Partes III e IV da AHA. | Pago | https://shop.elsevier.com/books/chous-electrocardiography-in-clinical-practice/surawicz/978-1-4160-3774-3 | [V] |
| **Josephson's Clinical Cardiac Electrophysiology: Techniques and Interpretations** | 6ª ed. 2020 (Callans DJ), Wolters Kluwer. A 7ª ed. (2024) existe (ISBN 9781975201166 no site LWW). | 6ª: 9781975115562 (impresso), 9781975115593 (e-book). 7ª: 9781975201166 | Intervalos intracardíacos (AH, HV), localização de via acessória, mecanismos de taquicardia, Purkinje e His. Dá a base eletrofisiológica da animação SA→átrios→AV→His→ramos→Purkinje. | Pago | https://shop.lww.com/p/9781975115593 | [V] (6ª); [V-parcial] (7ª) |
| **Braunwald's Heart Disease, 12ª ed.** (capítulo de eletrocardiografia) | Editores incluem Bonow RO, Mann DL, Tomaselli GF, Bhatt DL, Solomon SD, Libby P, Braunwald E. Elsevier, 2022. **Os autores do capítulo de ECG não foram confirmados.** | 2 vol. 9780323722193; vol. único 9780323824675 | Visão resumida e bem referenciada, boa para citações cruzadas de fisiologia e de diretrizes. | Pago | https://shop.elsevier.com/books/braunwald-s-heart-disease-2-vol-set/bonow/978-0-323-72219-3 | [V-parcial] |
| **International Criteria for ECG Interpretation in Athletes** | 2017: Drezner JA, Sharma S, Baggish A et al. (Seattle 2015); JACC 2017 e Br J Sports Med 2017;51(9):704-731 (PubMed 28258178). **Atualização IC25** (Drezner, Sharma, Papadakis et al.; consenso em Br J Sports Med, online em 2026): foca em inversão de T, repolarização precoce anterior e extrassístoles ventriculares. **A busca não achou DOI nem a lista final de autores.** | n/a | Normal vs. anormal em atleta; evita falso-positivo de repolarização precoce e de aumento de voltagem. Complementa o capítulo de atleta da SBC. | **Aberto** (2017 em PMC) | PubMed 2017: https://pubmed.ncbi.nlm.nih.gov/28258178/ · Resumo ACC IC25: https://www.acc.org/Latest-in-Cardiology/Articles/2026/10/29/11/45/2026-International-Criteria-For-ECG-Interpretation-in-Athletes | [V] (2017); [A verificar] (IC25: citação completa) |
| **ESC 2022 – Diretrizes de arritmias ventriculares e morte súbita** | Zeppenfeld K et al. Eur Heart J 2022 (publicado online em ago/2022; volume e páginas a conferir). | n/a | ECG em canalopatias, cardiomiopatias, TV e extrassístoles ventriculares. Critérios diagnósticos e diferencial. | **Aberto** | Resumo ACC: https://www.acc.org/latest-in-cardiology/ten-points-to-remember/2022/09/02/14/23/2022-esc-guidelines-for-vas-esc-2022 | [V-parcial] |
| **Minnesota Code Manual of Electrocardiographic Findings, 2ª ed.** | Prineas RJ, Crow RS, Zhang ZM. Springer London, 2010. Reedição em brochura 2016. | Capa dura 978-1-84882-777-6; e-book 978-1-84882-778-3; brochura 978-1-4471-6883-6. DOI 10.1007/978-1-84882-778-3 | Classificação **codificada e repetível** (Minnesota e Novacode). Ideal para gerar o campo estruturado `codigos[]` e para validar o pipeline em estudos populacionais. | Pago | https://www.springer.com/us/book/9781848827776 | [V] |
| **Tranchesi – Eletrocardiograma Normal e Patológico (7ª ed.)** | Moffa PJ, Sánchez PCG (coord.). Editora Roca, São Paulo, 2001, 911 p. | 85-7241-323-5 (de fonte secundária) | Referência brasileira clássica. Terminologia usada por laudistas no Brasil. Capítulos de BRE, BRD, hemibloqueios, sobrecargas e arritmias. Não foi achada edição mais recente. | Pago | Resenha: https://www.medicinabuenosaires.com/demo/revistas/vol62-02/2/v62_n2_p205.pdf | [V-parcial] (ISBN a confirmar em catálogo de biblioteca) |
| **IEC 60601-2-25:2011 (eletrocardiógrafos) e 60601-2-47** | 2ª ed., IEC, publicada em 2011-10-19. Funde as 1ªs edições de 60601-2-25 e 60601-2-51. A 60601-2-47 cobre ECG ambulatorial. Testes de exatidão de medida usam as bases CTS (sinais artificiais) e CSE (sinais biológicos). | n/a | Define **como validar** a medição automática de P, PR, QRS e QT. É a régua do módulo `app/ecg/analysis`. | Pago (a base CSE está em CD-ROM do INSERM) | https://webstore.iec.ch/publication/2636 · Visão geral das bases: https://medteq.squarespace.com/article/iec-60601-2-25-overview-of-databases | [V] |

### Tolerâncias de medida (não confirmadas no texto da norma)

Fonte secundária (artigo arXiv sobre ECG pré-hospitalar, Tabela 201.105 da IEC 60601-2-25): diferença média ±10 ms para duração de P, duração de QRS e PQ, e ±25 ms para QT. O texto extraído estava truncado.

**[A verificar na norma]** antes de usar como meta de teste. Um estudo de 2024 com delineador por deep learning reporta no CSE: P 2,6 ± 11,0 ms, PQ 0,9 ± 5,8 ms, QRS -2,4 ± 5,4 ms, QT -0,7 ± 10,3 ms (https://pmc.ncbi.nlm.nih.gov/articles/PMC11280871). Note que o desvio-padrão da onda P (11,0) passa de 10 ms, então "dentro da tolerância" depende de a norma limitar o viés médio ou a dispersão.

---

## 4. Tier 3 (introdutórios e de consulta rápida)

| Item | Edição, ano, autores, editora | ISBN | Uso e ressalva | Acesso | Status |
|---|---|---|---|---|---|
| **The ECG Made Easy, 10ª ed.** | Hampton J, Adlam D. Elsevier, 2024 (cópia 2025), 210 p. | 9780323937665 (edição internacional 9780323937832; e-book 9780323938105) | Bom para texto de explicação ao usuário leigo. Pouca profundidade para diferencial. | Pago | [V] |
| **Rapid Interpretation of EKG's, 6ª ed.** | Dubin D. Cover Publishing, 2000 | 9780912912066 | Método visual simplificado (régua de leitura rápida). Menos rigor, edição antiga. | Pago | [V] |
| **Schamroth – An Introduction to Electrocardiography** | Obra clássica da série Blackwell/Wiley. **Edição e ISBN não foram confirmados.** | n/a | Valor didático e histórico para bloqueios e arritmias. | Pago | [A verificar] |
| **Hampton – The ECG in Practice** | Elsevier. Edição e ISBN não confirmados. | n/a | Casos clínicos. | Pago | [A verificar] |
| **Mirvis & Goldberger – capítulo de Eletrocardiografia, em Braunwald** | Foi atribuído nas edições antigas ao capítulo de ECG. A busca **não confirmou** a autoria na 12ª ed. | n/a | Substituído, para este projeto, pelo Goldberger (livro) e pelas partes AHA. | Pago | [A verificar] |

---

## 5. Mapa de uso por funcionalidade

| Funcionalidade do app | Fontes principais | Fontes de apoio |
|---|---|---|
| Delineação de ondas (onset e offset de P, QRS, T, U) | AHA Partes I, III, IV; IEC 60601-2-25 (validação) | SBC 2022; Chou |
| Intervalos (PR, QRS, QT, QTc, RR) | AHA Parte IV (QT e QTc); SBC 2022 | IEC 60601-2-25; Goldberger |
| Eixo elétrico | Goldberger; SBC 2022 | Marriott; Bayés de Luna (vetores) |
| Condução (SA, AV, His, ramos, Purkinje) | Bayés de Luna; Josephson; AHA Parte III | ESC 2021 Marcapasso; Marriott |
| Arritmias | Marriott; SBC 2022 | ESC 2022 Arritmias Ventriculares; Josephson |
| Isquemia e IM | AHA Parte VI; 5ª Definição Universal (2026) | Marriott; Bayés de Luna; Minnesota |
| Hipertrofia | AHA Parte V; SBC 2022 | Chou; Goldberger |
| Atleta | SBC 2022 (capítulo e carta de comentários); Critérios Internacionais 2017 e IC25 | Chou |
| Laudo em pt-BR | SBC 2022; Tranchesi/Moffa | n/a |
| Codificação estruturada | Minnesota Code | Parte II da AHA (lista de termos) |

---

## 6. Lacunas e próximos passos

1. Conferir o texto completo da 5ª Definição Universal de IM (limiares de ST, critério de IM oclusivo) e o periódico de referência.
2. Obter a citação completa de IC25 (DOI, autores) e checar se há versão em JACC.
3. Conferir a Tabela 201.105 da IEC 60601-2-25 no texto da norma.
4. Confirmar os autores dos capítulos de ECG em Braunwald 12ª ed.
5. Confirmar edição e ISBN de Schamroth e de Hampton (The ECG in Practice).
6. Confirmar o ISBN de Tranchesi/Moffa em catálogo de biblioteca e ver se há edição posterior a 2001.
7. Aplicar as erratas da SBC 2022 (item 12.1.2: QRS 140 ms) antes de gravar critérios.
8. Conferir volume e páginas da diretriz ESC 2022 de arritmias ventriculares.
