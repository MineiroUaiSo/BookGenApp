# Skills (Agent Skills / Claude Code) para o MedLens — pesquisa nov/2026

Busca feita no GitHub (repositórios e código `SKILL.md`), no catálogo de plugins/skills do claude.ai e no registro de conectores MCP.
Repositórios lidos localmente antes de qualquer adoção (conteúdo e scripts; nenhum script faz chamada de rede).

## Instaladas no projeto (`.claude/skills/`)

| Skill | Origem | Licença | Por quê |
|---|---|---|---|
| `pydicom` | K-Dense-AI/scientific-agent-skills (~58 mil ★, mantido) | MIT | Transfer syntaxes, compressão, VOI LUT, multi-frame, de-identificação — base de `app/dicom` e ingestão de pasta |
| `neurokit2` | idem | MIT | APIs atuais do NeuroKit2 0.2.13 (delineação DWT/CWT, limpeza, HRV) com validação de método — base de `app/ecg/analysis` |
| `scientific-critical-thinking` | idem | MIT | Hierarquia de evidência, vieses, GRADE — apoia a etapa de "análise crítica" e a revisão dos critérios |
| `ecg-expert-reading` | **própria** | — | Método MedLens: medir → descrever → interpretar, ordem de leitura, condução cardíaca, formato de laudo SBC/AHA |
| `rx-systematic-reading` | **própria** | — | Leitura sistemática PA/AP, perfil, abdome; legendas; limites do 3D; Fleischner/RadLex |

Commit de origem do K-Dense em `.claude/skills/UPSTREAM_COMMIT_kdense.txt`; licença MIT copiada em cada pasta.

## Avaliadas e não instaladas

| Skill / repo | Motivo |
|---|---|
| FreedomIntelligence/OpenClaw-Medical-Skills (869 skills) | Maioria cópia de K-Dense ou bioinformática; `radgpt-radiology-reporter` tem cabeçalho "All Rights Reserved / proprietary" conflitando com MIT — evitar |
| kavanthompson/radiology-ai-skills `core-radiology-cardiac` | Declara conteúdo "extraído de Core Radiology 2ª ed." — risco de copyright; foco em TC/RM cardíaca |
| yamz8/dicom-mri-skill (MIT) | Voltado a RM/TC de CD do paciente; sobrepõe nosso render DICOM. Útil só como referência |
| K-Dense `clinical-reports`, `clinical-decision-support` (MIT) | Restritas a pesquisa/dados agregados; boas ideias de governança, mas não de leitura de exame. Candidatas a adoção futura |
| K-Dense `imaging-data-commons` (MIT) | Útil para baixar DICOM públicos de teste (NCI IDC); instalar quando formos montar o conjunto de validação |
| Aperivue/medsci-skills (MIT) | Escrita/auditoria de artigos; fora do escopo |
| Amirsaj/YouOwnECG (sem licença declarada) | Não é skill, mas arquitetura muito parecida (pipeline de sinal → features → agentes LLM + RAG de livros). Referência de design apenas; sem licença, não copiar código |

## Catálogo claude.ai / conectores
- Nenhuma skill de ECG/radiologia no catálogo oficial.
- Conectores úteis: **PubMed** (já conectado — usar para manter `knowledge/references.yaml` atualizado), **SNOMED CT Terminology** (códigos de achados), **ICD-10** (já conectado). Não há conector DICOM/PACS oficial.

## Conclusão
Não existe hoje uma skill pronta e confiável de "leitor de ECG/RX". As melhores peças públicas são as de ferramentas (pydicom, NeuroKit2, pensamento crítico, todas do K-Dense, MIT). O conhecimento clínico fica nas duas skills próprias + `knowledge/*.yaml`, com critérios reescritos e citados.
