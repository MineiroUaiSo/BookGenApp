# Bibliografia de referência para o leitor de RX do MedLens

Pesquisa feita em 2026-11-24. Objetivo: escolher livros, atlas e padrões de terminologia para a base `knowledge/`. Ela deve apoiar uma IA que identifica cada estrutura em radiografias simples (PA e perfil), descreve de forma sistemática e depois faz análise crítica com diagnósticos diferenciais.

**Política de copyright.** O repositório guarda apenas citações (livro, edição, capítulo) e critérios reescritos com palavras próprias. Os PDFs licenciados ficam em `knowledge/private/`, fora do git, só para RAG local.

**Convenção de verificação.**
- **[V]** = dado confirmado em página de editora ou catálogo nesta pesquisa.
- **[NV]** = não confirmado. Conferir antes de citar formalmente.
- Datas de publicação variam em um ano entre catálogos (data de lançamento x ano de copyright). Quando houve divergência, ela está indicada.

---

## 1. Padrões de terminologia e ontologias

| Item | Detalhes | Uso no MedLens | Acesso |
|---|---|---|---|
| **Fleischner Society: Glossary of Terms for Thoracic Imaging** [V] | Bankier AA et al. *Radiology* 2024;310(2):e232558. DOI 10.1148/radiol.232558. É a 4ª edição e substitui as de 1984, 1996 e 2008. Reduz o número de "sinais" e os epônimos, e acrescenta mais imagens de RX e TC. PMCID PMC10902601. | **Vocabulário canônico dos achados** (consolidação, opacidade em vidro fosco, nódulo, massa, atelectasia, derrame etc.). Usar como campo `term` controlado nos achados. Os termos mais radiográficos (sinal da silhueta, broncograma aéreo) vêm do glossário. A explicação de como aplicá-los vem de Felson e Webb. | **Acesso aberto** (PMC). https://pmc.ncbi.nlm.nih.gov/articles/pmid/38411514 e https://pubmed.ncbi.nlm.nih.gov/38411514/ |
| **Fleischner Glossary 2008** [V] | Hansell DM et al. *Radiology* 2008;246(3):697-722. PMID 18195376. | Apenas histórico. Preferir a versão 2024. | Acesso restrito, mas indexado. |
| **RadLex** (RSNA) [V parcial] | Léxico de radiologia em ontologia. BioPortal mostra a versão 4.3 (dez/2025). **Confirmar a versão corrente em radlex.org**, pois o BioPortal é um espelho. Licença pública RSNA, gratuita para uso comercial e não comercial. | **Backbone de IDs** para estruturas anatômicas e achados (anatomia: pulmão, hilo, ápice, cúpula diafragmática, traqueia, carina, aorta etc.). Cada item de `knowledge/*.yaml` deve ter um campo `radlex_id` quando existir. | Gratuito. https://www.rsna.org/practice-tools/data-tools-and-standards/radlex-radiology-lexicon e https://bioportal.bioontology.org/ontologies/RADLEX |
| **Consenso brasileiro ilustrado sobre terminologia da TC de tórax** [NV, apenas referência indireta] | Silva CIS, Marchiori E, Souza Júnior AS, Müller NL, Comissão de Imagem da SBPT. Publicado no *J Bras Pneumol* (2010), com versão em português do glossário Fleischner. Os resultados da busca só mostraram uma página agregadora. **Localizar o DOI antes de citar.** | **Termos em pt-BR** para a saída ao usuário (por exemplo, "vidro fosco", "consolidação", "padrão em árvore em brotamento"). Fonte para a tradução oficial da terminologia. | Provavelmente aberto (SciELO/J Bras Pneumol). |
| **ACR** (Practice Parameter for Communication of Diagnostic Imaging Findings; Appropriateness Criteria; Reporting & Data Systems) [NV] | A busca não retornou as páginas do ACR. Conferir em acr.org. | Estrutura do laudo (técnica, achados, impressão, recomendação), linguagem de certeza e comunicação de achados críticos. **Apenas para o formato do laudo**, não para anatomia. | Parte aberta. |

---

## 2. Tórax

| Item | Detalhes | Excelente para | Acesso |
|---|---|---|---|
| **Felson's Principles of Chest Roentgenology: A Programmed Text** [V] | Lawrence R. Goodman. **5ª ed., Elsevier, 2021** (lançamento ago/2020). ISBN 978-0-323-62567-8 (brochura), eBook 978-0-323-62568-5. 288 p. **A 6ª ed. está anunciada pela Elsevier (ISBN 978-0-443-28709-1)**, e as fontes divergem na data (mai/2026 x mar/2027). Verificar disponibilidade antes de fixar a edição. | **Método sistemático de leitura da RX de tórax.** Anatomia normal PA e perfil, sinal da silhueta, sinal do broncograma aéreo, localização de lesões por lobo/segmento, padrões básicos (alveolar, intersticial, atelectasia). É o livro mais próximo do que o MedLens quer ensinar a IA a fazer. | Comercial. https://shop.elsevier.com/books/felsons-principles-of-chest-roentgenology/goodman/978-0-443-28709-1 |
| **Thoracic Imaging: Pulmonary and Cardiovascular Radiology** (Webb & Higgins) [V] | Henry TS, Ordovás KG (eds.); fundadores W. Richard Webb e Charles B. Higgins. **4ª ed., Wolters Kluwer/LWW, out/2024** (título da capa: *Webb & Higgins' Thoracic Imaging*). ISBN 978-1-9751-9938-8 (impresso + eBook). 1168 p. 3ª ed. (2016): 978-1-4963-2104-6. | Referência abrangente de RX + TC, com **diferenciais por padrão** e capítulos de dispositivos/tubos, cardíaco e mediastino. Bom para a camada crítica. | Comercial. https://shop.lww.com/p/9781975199388 |
| **Fraser and Paré's Diagnosis of Diseases of the Chest** [NV] | Müller NL, Colman N, Paré PD et al. **A última edição que consegui confirmar indiretamente é a 4ª (Saunders, 1999, 4 vols.)**. A busca não achou ISBN nem edição posterior. Existe a versão condensada *Synopsis of Diseases of the Chest* (Saunders, 2005, ISBN 978-0-7216-0445-9, [V]). | Enciclopédia de correlação radiológico-patológica. Fonte profunda para fisiopatologia e diferenciais. É livro de **consulta**, não de uso para ensino. | Comercial, esgotado em grande parte. |
| **Imaging of the Chest** (Müller & Silva) [V] | Nestor L. Müller, C. Isabela S. Silva (eds.). Saunders/Elsevier, **2008**, 2 vols., 1608 p. ISBN 978-1-4160-4048-4. Série Expert Radiology. Fora de estoque em alguns revendedores. | Ênfase em TC de alta resolução. Útil para sinais e padrões de doença parenquimatosa e vias aéreas. | Comercial. |
| **Imaging of Diseases of the Chest** (Hansell et al.) [NV] | Hansell DM, Lynch DA, McAdams HP, Bankier AA. Edição não confirmada nesta busca (a página da Elsevier apareceu sem dados claros). Conferir se existe a 6ª edição. | Alternativa de estilo europeu, ótima para TC e padrão de doença. | Comercial. |
| **Diagnostic Imaging: Chest** (Amirsys/Elsevier) [V] | Rosado-de-Christenson ML, Martínez-Jiménez S. **3ª ed., Elsevier, 20/12/2021**, 1104 p. ISBN 978-0-323-79663-7. | Formato de **checklist por diagnóstico** (achados-chave, diferencial, pontos-chave). **É o mais fácil de converter em regras estruturadas** para o YAML, porque cada capítulo tem a mesma forma. | Comercial. https://shop.elsevier.com/books/diagnostic-imaging-chest/rosado-de-christenson/978-0-323-79663-7 |
| **Chest X-Ray Made Easy** (Corne & Au-Yong) [V] | Jonathan Corne, Iain Au-Yong. **5ª ed., Elsevier, 2022** (lançamento mai/2022; algumas listas indicam 2023). ISBN 978-0-7020-8234-4; eBook 978-0-7020-8236-8. Inclui seções sobre dose e aparências na COVID-19. | Rotina de leitura passo a passo para iniciante (A-B-C-D-E), com boa lista de tubos e dispositivos. Modelo para o **roteiro de descrição** que o MedLens deve seguir. | Comercial. |

---

## 3. Radiologia geral (textos de base)

| Item | Detalhes | Excelente para | Acesso |
|---|---|---|---|
| **Squire's Fundamentals of Radiology** [V] | Robert A. Novelline. **7ª ed., Harvard University Press, 2018** (29/01/2018), 688 p. ISBN 978-0-674-05795-1. **Nota: a editora é Harvard UP, não Elsevier.** | Base de **leitura sistemática de RX** (tórax, abdome, osso), com pontos de partida didáticos. Ótimo para sinais clássicos (silhueta, ar livre). | Comercial. |
| **Brant and Helms' Fundamentals of Diagnostic Radiology** [V] | Klein JS, Brant WE, Helms CA, Vinson EN (eds.). **5ª ed., LWW/Wolters Kluwer, 2018**, ISBN 978-1-4963-6738-9. Há indícios de uma **6ª ed. (nov/2024, Klein & Mellnick)**, mas o ISBN que apareceu (978-1-4963-6739-6) conflita com a 5ª edição. **Conferir.** | Amplo e uniforme: tórax, abdome, músculo-esquelético, pediatria. Boa fonte para tabelas de diferencial. | Comercial. |
| **Grainger & Allison's Diagnostic Radiology** [V] | Adam A, Dixon AK, Gillard JH, Schaefer-Prokop CM (eds.). **7ª ed., Elsevier, 2020** (jun/2020), 2 vols., ~2400 p. ISBN 978-0-7020-7524-7. Existe a "Essentials" (978-0-323-93605-7), mais enxuta. | Tratado de referência com versão do Reino Unido. Para consulta aprofundada, não para regras básicas. | Comercial. |

---

## 4. Abdome

| Item | Detalhes | Excelente para | Acesso |
|---|---|---|---|
| **Abdominal X-Rays Made Easy** [V, com correção de autoria] | **O título correto é no plural e o autor é James D. Begg** (não Gunn/Nicholson). 2ª ed., Churchill Livingstone/Elsevier, **2006**. ISBN 978-0-443-10257-8. | Roteiro de leitura da radiografia simples de abdome (gás intestinal, calibre das alças, ar livre, cálculos, calcificações, corpos estranhos). | Comercial. |
| **Textbook of Gastrointestinal Radiology** (Gore & Levine) [V] | Richard M. Gore, Marc S. Levine. **5ª ed., Elsevier, 25/08/2021**, 1104 p. ISBN 978-0-323-64082-4; eBook 978-0-323-64083-1. | Referência de **doença do trato gastrointestinal**, para diferenciais de obstrução, megacólon, pneumatose etc. | Comercial. |
| **Baker's Abdominal Plain Film** [NV] | Não encontrei esse título exato nesta pesquisa. Há referências de Stephen R. Baker sobre a radiografia simples do abdome (*The Abdominal Plain Film*). **Verificar título e edição antes de usar.** | Radiografia simples do abdome em profundidade. | NV |

---

## 5. Músculo-esquelético

| Item | Detalhes | Excelente para | Acesso |
|---|---|---|---|
| **Orthopaedic Imaging: A Practical Approach** (Greenspan & Beltran) [V] | Adam Greenspan, Javier Beltran. **7ª ed., LWW/Wolters Kluwer, 2020 (alguns catálogos: 2021)**, ISBN 978-1-9751-3647-5. **8ª ed. publicada em jun/2025** (ISBN 978-1-9752-1681-8). **O título atual usa "Orthopaedic"**, não "Orthopedic". | Abordagem de lesões ósseas por padrão (lítica, esclerótica, periostal, matriz), tumores e artrites. Útil para a lista de causas de alteração óssea na RX. | Comercial. |
| **Atlas of Normal Roentgen Variants That May Simulate Disease** (Keats & Anderson) [V] | Theodore E. Keats, Mark W. Anderson. **9ª ed., Elsevier, 2012** (copyright 2013 em alguns catálogos), ISBN 978-0-323-07355-4. Aparece uma edição nova (Anderson, ISBN 978-0-323-93141-0), **a conferir** como possível 10ª edição. | **O melhor livro de variantes normais** para evitar falsos-positivos (costela cervical, osso acessório, calcificação fisiológica, sobreposições). Peça-chave para a etapa "isto é normal?". | Comercial. |
| **Rockwood and Green's Fractures** [NV] | Não verificado nesta pesquisa. Conferir a edição vigente. | Classificação de fraturas e luxações em adultos e crianças. | NV |

---

## 6. Anatomia e posicionamento

| Item | Detalhes | Excelente para | Acesso |
|---|---|---|---|
| **Weir & Abrahams' Imaging Atlas of Human Anatomy** [V] | Spratt JD et al. **6ª ed., Elsevier, 2020 (copyright 2021)**, ISBN 978-0-7020-7926-9. Há edição em espanhol. | **Correlação anatômica com RX, TC e RM**, com ótimas legendas. Base para rótulos de estruturas. | Comercial. |
| **Merrill's Atlas of Radiographic Positioning and Procedures** [V] | Rollins JH et al. **15ª ed., Elsevier/Mosby, 2022**, 3 vols., ISBN 978-0-323-83279-3. Volumes: 978-0-323-83280-9, -83281-6, -83282-3. **Há edição futura listada** (ISBN 978-0-443-12041-1). | Incidências, técnica, critérios de qualidade por projeção. Ajuda a **reconhecer PA x AP x perfil** e rotação/inspiração. | Comercial. |
| **Bontrager's Textbook of Radiographic Positioning and Related Anatomy** [V] | **10ª ed., Elsevier, 2020**, ISBN 978-0-323-65367-1 (Handbook: 978-0-323-69422-3). Edição mais recente não verificada. | Posicionamento com anatomia correlata, em linguagem didática. | Comercial. |
| **Netter's Atlas of Human Anatomy / Gray's Anatomy** [NV] | Não pesquisados em detalhe. São referências de anatomia clássicas, úteis para nomenclatura (Terminologia Anatomica). | Nomes e relações anatômicas. | Comercial. |
| **Caffey's Pediatric Diagnostic Imaging** [NV] | Opcional, pediatria. Não pesquisado. | Radiografia pediátrica. | Comercial. |

---

## 7. Referências em português (Brasil)

**Ressalva.** A busca web não localizou fichas editoriais para os livros brasileiros pedidos. Os itens abaixo são, portanto, **[NV]** e precisam ser conferidos no catálogo da Elsevier Brasil, da Guanabara Koogan (Grupo GEN) e no site do CBR.

- **Série CBR "Tórax"** (Colégio Brasileiro de Radiologia e Diagnóstico por Imagem / Elsevier). Título, organizadores e edição não confirmados.
- **Marchiori E, Santos ML. *Introdução à Radiologia*.** Guanabara Koogan. Edição e ano não confirmados. A busca só mostrou um título diferente (Stimac, *Introdução ao Diagnóstico por Imagens*, 1992).
- **Revista *Radiologia Brasileira*** (órgão oficial do CBR, SciELO, ISSN 0100-3984) [V]. **Acesso aberto.** https://www.scielo.br/journal/rb/about/?ilang=en. Boa fonte de artigos em português para citações.
- **Consenso brasileiro de terminologia de TC de tórax** (ver Seção 1).

---

## 8. Classificação por camadas

**Tier 1 (núcleo da base de conhecimento).**
1. Fleischner Glossary 2024 (aberto)
2. RadLex (aberto)
3. Felson's Principles of Chest Roentgenology
4. Webb & Higgins' Thoracic Imaging
5. Diagnostic Imaging: Chest (Rosado-de-Christenson)
6. Keats & Anderson, Atlas of Normal Roentgen Variants

**Tier 2 (complementos e outras regiões).**
- Chest X-Ray Made Easy
- Squire's Fundamentals of Radiology
- Brant & Helms
- Weir & Abrahams
- Abdominal X-Rays Made Easy (Begg)
- Gore & Levine
- Greenspan (Orthopaedic Imaging)
- Merrill's Atlas (reconhecer incidência e qualidade)
- Consenso brasileiro de terminologia (para pt-BR)

**Tier 3 (consulta profunda ou não verificados).**
- Müller & Silva, Imaging of the Chest
- Fraser & Paré
- Hansell
- Grainger & Allison
- Bontrager, Netter, Gray's
- Caffey (pediatria)
- Rockwood (fraturas)
- Baker (abdome)
- Livros do CBR e Marchiori/Santos
- ACR (apenas para o formato do laudo)

## 9. Recomendação: 6 principais para a base `knowledge/`

| # | Item | Por quê |
|---|---|---|
| 1 | **Fleischner Glossary 2024** | Define os termos oficiais dos achados. É aberto, então pode ser citado e parafraseado com segurança. |
| 2 | **Felson's Principles (Goodman, 5ª ed.; 6ª em lançamento)** | Ensina o método de leitura e os sinais (silhueta, broncograma aéreo) em PA e perfil. |
| 3 | **Diagnostic Imaging: Chest (3ª ed.)** | Estrutura uniforme por diagnóstico, fácil de converter em critérios YAML com diferenciais. |
| 4 | **Webb & Higgins' Thoracic Imaging (4ª ed.)** | Cobertura ampla, incluindo dispositivos, mediastino e cardíaco, para a camada crítica. |
| 5 | **Keats & Anderson, Atlas of Normal Roentgen Variants** | Reduz falsos-positivos e cobre ossos e tecidos moles. |
| 6 | **RadLex** | Vincula cada estrutura e achado a um ID, o que dá consistência entre a segmentação, o laudo e as referências. |

**Lacunas para abdome e MSK.** Para abdome, adicionar Abdominal X-Rays Made Easy e Gore & Levine. Para ossos, adicionar Greenspan. Para pt-BR, o consenso brasileiro de terminologia e artigos da *Radiologia Brasileira*.

## 10. Como citar no YAML (modelo)

```yaml
- id: silhouette_sign
  term_fleischner: "silhouette sign"
  radlex_id: null          # preencher
  criterion_pt: "Perda do contorno de uma borda mediastinal ou diafragmática normal por opacidade contígua do mesmo plano."
  references:
    - "Goodman LR. Felson's Principles of Chest Roentgenology. 5th ed. Elsevier; 2021. Cap. 'Silhouette sign'."
    - "Bankier AA et al. Fleischner Society glossary 2024. Radiology 2024;310(2):e232558."
```

(O capítulo exato de cada citação deve ser conferido com o exemplar licenciado.)

## 11. Pendências a verificar

- Edição vigente do Felson (5ª x 6ª).
- Se a nova edição do Keats (ISBN 978-0-323-93141-0) é a 10ª.
- ISBN e ano da 6ª edição do Brant & Helms.
- Edição atual de Fraser & Paré e de Hansell.
- Título e ano de Baker, Rockwood, Netter, Gray's.
- Fichas dos livros do CBR e de Marchiori/Santos.
- DOI do consenso brasileiro de terminologia.
- Versão corrente do RadLex em radlex.org.
- Documentos do ACR.
