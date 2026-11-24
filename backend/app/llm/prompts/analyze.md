ETAPA 2 - ANÁLISE CRÍTICA.

Com base na descrição da etapa 1 (revise-a criticamente: corrija o que estiver incoerente com a imagem ou com as medidas), nos dados determinísticos e nos critérios do bloco de CONHECIMENTO, produza a saída estruturada exigida pelo esquema:
- `description`: a descrição final minuciosa (pode reaproveitar e corrigir a da etapa 1), organizada por estrutura/onda.
- `findings`: achados com `code` estável (ex.: ecg.av_block_1, rx.pleural_effusion, em minúsculas e com ponto), `label` em pt-BR, `severity` (normal, borderline, abnormal, critical), `evidence` (medidas e observações que sustentam, com derivação/zona), `references` (ids de REFERÊNCIAS que sustentam o critério usado), `confidence` de 0 a 1 calibrada. Inclua também achados normais relevantes. Reserve `critical` para achados que exigem ação imediata.
- `differentials`: diagnósticos diferenciais ordenados, com `rationale`, `supporting`, `against`, `references` e `confidence`.
- `disagreements_with_measurements`: divergências entre sua leitura e as medidas/segmentações automáticas, cada uma com justificativa.
- `limitations`: limites da imagem, calibração, incidência, ausência de dados clínicos ou de exame prévio e demais incertezas.
Seja específico e sucinto em cada campo. Não repita o aviso legal. Use apenas ids de referência existentes.
