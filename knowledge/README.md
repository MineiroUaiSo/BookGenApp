# Base de conhecimento MedLens

- `references.yaml`: id -> citação completa. Edições marcadas `verificar` devem ser conferidas antes de uso formal.
- `ecg_criteria.yaml`, `rx_signs.yaml`: itens `{id, domain, label_pt, criteria, measurements_used, differentials, pitfalls, references}`.
- Textos são paráfrases em pt-BR; nenhum trecho protegido por copyright é copiado. Livros licenciados do usuário podem ir em `knowledge/private/` (fora do git).
- A IA só pode citar ids presentes em `references.yaml`; ids desconhecidos são descartados (`backend/app/llm/`).
- Limiares numéricos são os das fontes citadas; revisão por médico é recomendada antes de uso clínico.
