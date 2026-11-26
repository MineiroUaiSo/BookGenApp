# MedLens dentro do AssistentePediatria: plano de integração (arquiteto, 2026-11-26)

Meta: até 07h de 2026-11-26, leitor de ECG/RX do MedLens online e funcionando na aba `/raio-x` do AssistentePediatria, renomeada para **"Exames de imagem (apoio) · BETA"**. Nenhum outro item do site muda.
Restrições: dono indisponível; PHI nunca em log, commit ou serviço externo novo; crédito OpenRouter curto (parar se saldo < US$ 2,00).

---

## 0. Fatos medidos (não são suposições)

| Item | Valor | Como foi medido |
|---|---|---|
| venv local do MedLens (macOS arm, py3.14, com extras) | 1,4 GB | `du -sh backend/.venv/lib/python3.14/site-packages` |
| torch sozinho | 649 MB | `du -sk .../torch` |
| pesos torchxrayvision (`~/.torchxrayvision`) | 287 MB | `du -sh` |
| Deps Linux x86_64 py3.12 **com** wfdb | 722 MB | `pip install --target --platform manylinux... --only-binary=:all:` em dir temporário |
| Deps Linux x86_64 py3.12 **mínimas** (fastapi, pydantic, pydicom, numpy, pillow, python-multipart, pyyaml, scipy, scikit-image, opencv-python-headless, pylibjpeg×3) | 501 MB brutos, dos quais 110 MB são pastas `tests/` | idem |
| Mínimas sem `tests/` | ~391 MB | 501 − 110 |
| Limite de bundle Python na Vercel | 500 MB (docs Vercel: "stay under the 500 MB bundle limit", usar `excludeFiles`) | `search_vercel_documentation` |
| Limite de corpo de requisição em Vercel Function | 4,5 MB | regra conhecida da plataforma |
| Código Python de ECG+RX+DICOM | 10.925 linhas | `wc -l app/ecg app/rx app/dicom` |
| torch/torchxrayvision/cv2/wfdb/anthropic/matplotlib no código | todos import **preguiçoso** (dentro de função) | `grep -n "^\s+import"` |
| RX sem modelo (`MEDLENS_RX_MODELS=0`) | segmentação heurística, Dice ~0,07–0,25; ICT heurístico 0,64–0,87 em filme normal. O próprio código marca ICT/desvio traqueal como "não confiável" | `app/rx/analyze.py:17-30` |
| neurokit2 | não é usado (implementação própria) | `app/ecg/analysis/__init__.py:15` |
| Barreira PHI | `phi_guard` em `app/main.py`: com `MEDLENS_API_TOKEN` exige Bearer (compare_digest); sem token só aceita loopback | leitura do código |
| Fluxo atual da API | **com estado**: `/api/ingest` grava no disco (`MEDLENS_DATA`), depois `/api/{ecg,rx}/{study_id}/analyze` lê. Em serverless, duas requisições podem cair em instâncias diferentes | `app/store.py`, `app/api/analysis.py` |
| IA no MedLens | `MEDLENS_DESCRICAO_IA` (padrão 1), `MEDLENS_RX_DESCRICAO_IA` (padrão 1), `MEDLENS_RX_IMAGE_AI` (padrão optin), `MEDLENS_RX_LAUDO_IA` (padrão 0); só chama LLM se existir `OPENROUTER_API_KEY` ou `ANTHROPIC_API_KEY` | `app/llm/*`, `app/rx/descricao_ia.py` |

### Produção do Pediatria (Vercel `prj_hO55OymjUt0x9JaDAwNtA1XTZEEs`)
- Último deploy de produção READY: `dpl_DwrUdGS6xXeJb9wSeavoBfi14cMg`, **Git main @ `c752268a`** ("fix: sticky, foco e escopo da coluna lateral do parecer"). Veio pela integração Git, então o Git **não está BLOCKED** neste momento (autor noreply `MineiroUaiSo`).
- Os dois deploys de produção anteriores (`dpl_BoqXiuSk…`, `dpl_tx33hozD…`) não têm metadado Git: foram via CLI, provavelmente a landing. O deploy `c752268a` substituiu esses dois.
- Prova HTTP: `GET /` → 307 `/login`, e também `/inicio` → 307 `/login`. Se a landing estivesse no ar, `/` seria pública. **A landing NÃO está em produção agora.**
- `origin/feat/pagina-inicial` (3b7ed70b) tem 14 commits que não estão na main. A main tem 5 commits que não estão nela (inclui o parecer em coluna lateral).
- **Base da feature: `origin/main` = `c752268a` = exatamente o que está no ar.** Não mesclar a landing: publicá-la seria uma mudança não pedida. A landing fica como pendência do dono.
- Env do projeto (só nomes): `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `AI_MODEL_DEEP`, `AI_MODEL_DOCS` (OpenRouter = `AI_API_KEY` + `AI_BASE_URL`). **`AI_MODEL_VISAO` não existe**, então o `/raio-x` atual responde "IA de visão não configurada": a aba hoje não laudava nada em produção.
- A faixa de idade do `/raio-x` é validada em `src/lib/rx/idade.ts`: só aceita 0 dias a 17a11m. **Portanto todo exame no Pediatria cai no modo pediátrico.** O caminho adulto (≥ 18 anos) não é exposto.
- Região da produção: `gru1` (São Paulo), pelo header `x-vercel-id`.

---

## 1. Hospedagem do back-end: decisão

**Escolha: (a) novo projeto Vercel `medlens-api` na mesma equipe (`team_5XiXyOxtAbJThCXfoJOcoUFM`).** FastAPI/ASGI, região `gru1`, perfil ECG + RX heurístico, sem torch e sem IA.

| Opção | Veredito | Motivo |
|---|---|---|
| (a) Vercel Python, sem torch | **ESCOLHIDA** | ~391 MB após `excludeFiles` (limite 500 MB, folga ~100 MB). Mesmo operador de dados que o app já usa, região BR, 24 h, sem login humano. Deploy por CLI/MCP. |
| (a') Vercel com torch | Inviável | torch 649 MB + pesos 287 MB, mais que o dobro do limite. |
| (b) HF Space Docker | Rejeitada | Novo operador de dados (EUA) recebendo imagem de criança: transferência internacional sem base no fluxo atual. Free tier hiberna (cold start de minutos). Space privado exige token: mais um segredo. Só reconsiderar com DPA e anonimização formal. |
| (c) Portar para TS | Rejeitada para hoje | 10,9 mil linhas Python numpy/scipy/cv2 (digitalização de ECG por foto, perspectiva, detecção de grade, morfologia). Semanas de trabalho, alto risco de divergência numérica. |
| (d) Mac + túnel | Rejeitada | Depende do Mac ligado. Só serve como contingência de 1 noite, nunca como entrega. |

Limites desta opção (honestos, e aparecem na tela):
- **RX roda sem modelo.** A segmentação é heurística, então ICT, desvio traqueal e áreas pulmonares saem marcados como não confiáveis. No modo pediátrico eles **não são exibidos**. O RX v1 entrega: incidência/região detectadas, qualidade técnica (exposição, rotação, corte, texto queimado), metadados úteis e a imagem conferida. É pouco, mas não é falso.
- **ECG é o ganho principal.** Digitalização de foto/print de ECG pelo opencv, mais medidas de FC, PR, QRS, QT, QTc e eixo, com qualidade de sinal.
- Entrada: imagem JPG/PNG, e DICOM convertido no navegador (já existe em `src/lib/rx/dicom`). WFDB e PDF ficam fora do v1: wfdb puxa pandas+matplotlib (+220 MB).
- O corpo tem limite de 4,5 MB. O cliente já redimensiona (`src/lib/rx/imagem/preparar-envio.ts`). O teto do proxy é 4 MB.

`vercel.json` do `medlens-api`, a ser criado em P1a:
```json
{
  "regions": ["gru1"],
  "functions": { "app/main.py": { "maxDuration": 60, "excludeFiles": "{tests/**,bench/**,data/**,medlens_data/**/*.dcm,**/tests/**,**/__pycache__/**,../frontend/**}" } }
}
```
O executor ajusta o glob e o entrypoint (zero-config FastAPI aceita `app/main.py`) e prova o tamanho com `vercel build` ou com um deploy de preview. **Critério:** bundle < 450 MB e cold start < 10 s.

Env do `medlens-api` (P4 cria; valores fora de commit e de log):
| Nome | Valor |
|---|---|
| `MEDLENS_API_TOKEN` | segredo aleatório de 48 bytes (`openssl rand -base64 48`), o mesmo valor que `MEDLENS_API_TOKEN` no Pediatria |
| `MEDLENS_DATA` | `/tmp/medlens` |
| `MEDLENS_RETENCAO_HORAS` | `0.1` |
| `MEDLENS_RX_MODELS` | `0` |
| `MEDLENS_DESCRICAO_IA` | `0` |
| `MEDLENS_RX_DESCRICAO_IA` | `0` |
| `MEDLENS_RX_IMAGE_AI` | `0` |
| `MEDLENS_RX_LAUDO_IA` | `0` |
| `MEDLENS_CORS` | vazio (só servidor a servidor) |
| **NÃO criar** | `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`. Sem chave, `ai_available()` é falso: trava dupla contra LLM |

Env novo no Pediatria (P4 cria): `MEDLENS_API_URL` (URL de produção do `medlens-api`) e `MEDLENS_API_TOKEN`. Sem `MEDLENS_API_URL`, a aba mostra "Leitor indisponível" (kill-switch natural). Nenhuma env existente é alterada.

Deployment Protection: no plano Hobby, a URL de produção é pública. A proteção vem do Bearer no `phi_guard`. Previews ficam protegidos por SSO; o smoke de preview usa `vercel curl` ou bypass. Se a equipe tiver proteção também em produção, P4 usa `x-vercel-protection-bypass` com `VERCEL_AUTOMATION_BYPASS_SECRET`, que entra só no env do Pediatria.

---

## 2. Desenho da integração

```
navegador (/raio-x, "Exames de imagem")
  │ arquivo → (DICOM→PNG no navegador) → máscara de texto + conferência (componentes existentes)
  │ → redimensiona ≤ 4 MB → POST multipart /api/exames/analisar {tipo, idade, imagem}
  ▼
Next route (Pediatria, runtime nodejs, maxDuration 60, region gru1)
  rxAbaAtiva() → origemValida → authenticateRequest → excedeuRateLimit(`exames:${userId}`, 20 / 10 min)
  → valida idade (validarIdadeRx) e tamanho → fetch(MEDLENS_API_URL + /api/oneshot/{ecg|rx},
     Authorization: Bearer MEDLENS_API_TOKEN, AbortSignal.timeout(55s))
  → Zod strict (whitelist do contrato) + filtro de vocabulário → JSON no-store
  ▼
medlens-api (Vercel Python): phi_guard (Bearer) → oneshot: TemporaryDirectory + Store(root=tmp)
  → ingest → analyze → aplicar_modo_pediatrico → apaga tmp → JSON (sem PHI, sem imagem)
```

Regras:
- A imagem não é gravada: só existe em memória e no `TemporaryDirectory` do oneshot, apagado no `finally`. Nada de corpo, imagem ou resultado em `console.*` ou `log.*`. O `usage_log` do MedLens grava só códigos e latência, com hash salgado do id; fica em `/tmp`, efêmero.
- `phi_guard` continua ativo. Texto queimado é mascarado no navegador (conferência obrigatória, já existente) e de novo no servidor (`MEDLENS_BURNED_TEXT` padrão ligado). Tags DICOM nunca saem do navegador: só pixels vão.
- **Sem cota de plano** (`consumirQuota` não é chamado): não há custo de LLM. Usa só o rate limit.
- **IA de texto: DESLIGADA no v1.** Nenhuma chamada a OpenRouter no fluxo padrão, nem em teste, nem no smoke. A descrição é determinística. Fase 2 (só se o dono pedir): botão opt-in "Redigir descrição com IA" no Pediatria, que manda **só os fatos estruturados** (nunca imagem) por `AI_API_KEY`/`AI_BASE_URL` com modelo barato. Teto de 3 chamadas por usuário por dia e 30 por dia no total, kill-switch `EXAMES_IA_ATIVA` (padrão off), mesmo filtro de vocabulário na saída. Não implementar agora.
- `/api/rx/laudo` (rota antiga de visão) **fica intacta e sem uso pela UI**, sem remoção. Ela já responde 503 em produção por falta de `AI_MODEL_VISAO`.

### Contrato de resposta (Pediatria `src/lib/exames/tipos.ts` + Zod `.strict()`)
```ts
export type TipoExame = 'ecg' | 'rx'
export interface MedidaExame { codigo: string; rotulo: string; valor: number; unidade: string; confiavel: boolean; nota?: string }
export interface QualidadeExame { codigo: string; texto: string; nivel: 'info' | 'alerta' }
export interface ResultadoExame {
  tipo: TipoExame
  modo: 'pediatrico'
  idadeMeses: number
  incidencia?: string          // RX: PA/AP/perfil detectado
  regiao?: string              // RX: tórax/abdome/...
  medidas: MedidaExame[]       // ECG: fc, pr, qrs, qt, qtc_bazett, rr, eixo_qrs; RX: nenhuma no v1 (ICT suprimido)
  qualidade: QualidadeExame[]
  descricaoTecnica: string     // determinística, sem normal/anormal
  avisos: string[]             // inclui o aviso pediátrico fixo
  versaoMotor: string          // commit curto do medlens-api
}
```
O oneshot do MedLens devolve as chaves em snake_case (`idade_meses`, `descricao_tecnica`, `versao_motor`). A rota do Pediatria converte. Campo desconhecido é descartado. `findings`, `laudo`, `classificacao`, `diagnostico` **nunca** passam no modo pediátrico.

### UI: reaproveitar × trocar
- **Reaproveitar** (sem alterar): `EntradaArquivo`, `carregar-arquivos`, `src/lib/rx/dicom/*`, `src/lib/rx/imagem/*` (máscara, detectar-texto, preparar-envio, redimensionar), `EditorMascara`, `ConferenciaEnvio`, `PreVisualizacao`, `JanelaControles`, `EstadoPedido`, `copiar-texto`, `validarIdadeRx`.
- **Trocar** (novos arquivos em `src/components/exames/`): `ExamesImagemClient`, com seletor ECG | RX. Para ECG não há janela DICOM nem projeção. O formulário pede idade (obrigatória) e o tipo. `useExameMedlens` + `api-exames.ts` substituem `useLaudoRx`/`api-laudo`. `ResultadoExame` + `MedidasTabela` substituem `ResultadoRx`/`LaudoSecoes`.
- **Frontend React/Vite do MedLens: não copiar.** Ele tem outro sistema de estilo, rótulos adultos e estado de estudo com várias instâncias. A UI nova segue o padrão do Pediatria, mobile-first.
- Menu: `src/components/consulta/MenuApp.tsx:60`, só o rótulo muda para `"Exames de imagem (apoio) · BETA"`. A rota `/raio-x` é mantida, para não quebrar links e testes de rota. `metadata.title` muda para `'Exames de imagem (apoio)'`.

---

## 3. Segurança clínica pediátrica

Todo exame no Pediatria é de paciente com menos de 18 anos (validador 0d–17a11m). Comportamento único: **modo pediátrico**.

### Regra mínima (implementada nos DOIS lados)
1. **Nenhuma classificação diagnóstica adulta.** O oneshot com `modo=pediatrico` não devolve `findings`, laudo, conclusões, nem rótulos "normal/anormal/aumentado/prolongado/desvio".
2. **ECG:** devolve só medidas com unidade e flag de confiabilidade do sinal: FC (bpm), RR (ms), PR (ms), QRS (ms), QT (ms), QTc Bazett (ms) e eixo do QRS (graus). Também devolve a qualidade do sinal e da digitalização (derivações legíveis, calibração detectada, ruído). Junto do QTc vai a nota: "Bazett superestima o QTc com FC alta, comum em lactentes; compare QT e RR". Nenhum valor é colorido nem sinalizado.
3. **RX:** devolve incidência, região e qualidade técnica. **ICT não é exibido**, por dois motivos: o limiar 0,50 é de adulto (`ficha.py:LIMITE_ICT`), e a medida heurística desta hospedagem não é confiável. O mesmo vale para desvio traqueal e áreas. Texto fixo: "Índice cardiotorácico não exibido: o limite de adulto não vale para criança e a medida automática desta versão não é confiável."
4. **Descrição técnica determinística**, gerada por template só com as medidas e a qualidade. Exemplo de ECG: "ECG digitalizado de imagem. FC 128 bpm; PR 110 ms; QRS 70 ms; QT 290 ms; QTc (Bazett) 423 ms; eixo do QRS +75°. Qualidade: 12 derivações legíveis, calibração 10 mm/mV detectada."
5. **Filtro de vocabulário** (teste e runtime, nos dois lados). Se `descricaoTecnica`, `avisos` ou `qualidade[].texto` contiverem `/\b(normal|anormal|aumentad|reduzid|prolongad|curto|hipertrofi|sobrecarga|cardiomegalia|bloqueio|desvio do eixo|isquemi|infarto|pneumonia|derrame|consolida)/i`, a rota do Pediatria responde 502 `resultado_bloqueado` ("Resultado indisponível com segurança"). **Exceção:** os avisos fixos 6 e 3 citam "limite de adulto" e "normais por idade". Eles entram por constante do Pediatria e não passam pelo filtro.
6. **Aviso fixo na tela**, em destaque acima do resultado, nos dois tipos: "Apoio técnico, não é laudo. Os valores normais do ECG e do raio-X mudam com a idade da criança. Esta ferramenta mostra medidas e qualidade da imagem e não classifica o exame como normal ou alterado. Compare com uma tabela por faixa etária e confirme com o radiologista ou o cardiologista pediátrico."

### Fontes pediátricas: o que poderia entrar e o que entra hoje
- ECG: Rijnbeek PR et al., "New normal limits for the paediatric electrocardiogram", *Eur Heart J* 2001;22:702-711, **PMID 11286528** (verificado no PubMed). Davignon A et al., *Pediatr Cardiol* 1979/80;1:123-131 (**PMID não localizado** pela busca por citação; precisa conferir). Os percentis 2–98 por faixa (FC, PR, QRS, QTc, eixo) poderiam virar sinalização "fora do P2–P98 para a idade".
- RX/ICT: nenhuma fonte pediátrica de ICT no repo. `docs/research/rx_bibliografia.md` lista Caffey como "não pesquisado".
- **Hoje entra apenas a citação de Rijnbeek como referência de consulta no aviso, sem nenhum valor numérico.** Nenhuma tabela foi transcrita e conferida contra o texto integral nesta sessão. Pela regra "sem fonte citável e verificável não entra", os percentis vão para a pendência do médico (P-CLIN-1).

### Pendências do médico (não bloqueiam as 7h)
- P-CLIN-1: aprovar a transcrição dos percentis de Rijnbeek 2001 (tabelas por faixa), conferida contra o PDF, antes de qualquer sinalização por idade.
- P-CLIN-2: decidir se o QTc deve usar Fridericia/Hodges em vez de Bazett na pediatria, ou exibir os dois.
- P-CLIN-3: fonte de ICT pediátrico (ex.: Caffey) e retorno do ICT quando houver segmentação por modelo (fase 2).
- P-CLIN-4: liberar ou não a IA de texto opt-in (fase 2, crédito OpenRouter).

---

## 4. Pacotes paralelos (executores Sonnet)

Worktrees:
- MedLens: `git -C /Users/macbook/medlens worktree add ../medlens-ped -b feat/oneshot-pediatria claude/ecg-rx-ai-reader-nd20rs`
- Pediatria: `git -C /Users/macbook/Documents/Projetos/AssistentePediatria worktree add ../AssistentePediatria-exames -b feat/exames-imagem-medlens origin/main`

**Nunca tocar** no working tree principal do Pediatria (`feat/pipeline-dash-futurista`, sujo de outra sessão). Um commit por tarefa. Nenhum teste chama a rede, OpenRouter ou Anthropic.

Ordem: P1a/P1b, P2 e P3 rodam em paralelo. P4 é sequencial e vem depois.

### P1a: oneshot sem estado + empacotamento Vercel (MedLens, Python)
- Arquivos permitidos: `backend/app/api/oneshot.py` (novo), `backend/app/api/__init__.py` (registrar router), `backend/vercel.json` (novo), `backend/.python-version` (novo, `3.12`), `backend/pyproject.toml` e `backend/requirements.txt` (só adicionar `opencv-python-headless` ao core), `backend/tests/test_oneshot.py` (novo). Refatorar `app/api/analysis.py` só se for preciso extrair funções que recebam o `store` como parâmetro, sem mudar o comportamento das rotas existentes.
- Endpoint: `POST /api/oneshot/{ecg|rx}`, multipart com `file`, `idade_meses:int (0..215)`, `modo:'pediatrico'|'adulto'` (padrão `pediatrico`) e `layout` opcional (ECG). Usa `TemporaryDirectory` + `Store(root=tmp)`, `ingest_files`, a análise com `ai=False` e, no `finally`, apaga o diretório. Chama `aplicar_modo_pediatrico` (P1b) e devolve o contrato da §2 em snake_case. Limite de 4 MB no arquivo. Rejeita ZIP e mais de 1 arquivo.
- Aceite: `pytest -q` verde (os 116 arquivos de teste atuais, mais os novos). Teste prova que (i) sem Bearer → 401 quando `MEDLENS_API_TOKEN` está definido, (ii) `/tmp` fica vazio após a chamada, (iii) com `monkeypatch` que faz `app.llm.client` levantar exceção a chamada passa (nenhum LLM é chamado), (iv) uma imagem sintética de ECG (gerar no teste, ex.: o fantasma de `bench/`) devolve FC dentro de ±5 bpm do valor gerado. Venv limpo py3.12 só com as deps do Vercel (sem torch, wfdb, matplotlib ou anthropic) roda `pytest tests/test_oneshot.py` verde: prova que nenhum import preguiçoso pesado é exigido no caminho. Medir o tamanho do bundle (`vercel build` ou deploy de preview) < 450 MB e registrar o número no commit.

### P1b: filtro pediátrico (MedLens, Python)
- Arquivos permitidos: `backend/app/pediatric.py` (novo), `backend/tests/test_pediatric_mode.py` (novo).
- Interface fixa: `aplicar_modo_pediatrico(kind: Literal['ecg','rx'], analise: ECGAnalysis | RXAnalysis, idade_meses: int) -> dict` no formato do contrato. Ela faz o whitelist das medidas da §3.2 e §3.3, monta a qualidade, gera a descrição por template e aplica o regex de vocabulário. Se o template produzir termo vetado, levanta `ValueError`.
- Aceite: testes com análises fixture (sem imagem) provam que o resultado não tem `findings`/`laudo`, não tem ICT no RX, e não tem termo vetado em 50 combinações aleatórias de medidas. QTc sempre vem acompanhado da nota de Bazett. P1a importa esta função; para não bloquear, P1a usa um stub com a mesma assinatura até o merge.

### P2: rota proxy (Pediatria, TS)
- Arquivos permitidos: `src/lib/exames/tipos.ts`, `src/lib/exames/resultado-schema.ts` (Zod strict + filtro de vocabulário), `src/lib/exames/medlens-client.ts` (fetch com Bearer, timeout 55 s, mapeamento de snake para camel), `src/lib/exames/flag.ts` (`examesMedlensConfigurado()` = há `MEDLENS_API_URL` e `MEDLENS_API_TOKEN`; devolve só o booleano), `src/app/api/exames/analisar/route.ts`, e os testes `*.test.ts` correspondentes.
- Padrão idêntico ao de `src/app/api/rx/laudo/route.ts`: `rxAbaAtiva`, `origemValida`, `authenticateRequest`, `excedeuRateLimit`, leitura de corpo com limite real (4 MB), `validarIdadeRx`, `Cache-Control: no-store`, `runtime='nodejs'`, `maxDuration=60`. **Sem `consumirQuota`.** Nenhum `console.*` com corpo ou resultado.
- Erros: 503 `leitor_indisponivel` (sem env, ou MedLens fora/timeout), 413, 400, 429, 401/403 e 502 `resultado_bloqueado` (falha no Zod ou no vocabulário).
- Aceite: `npx tsc --noEmit` e `npx vitest run src/lib/exames src/app/api/exames` verdes. `fetch` mockado. Testes cobrem cada código de erro, o descarte de campo desconhecido, o bloqueio por vocabulário e a ausência de log (spy em `console`). `git diff --stat origin/main` só lista arquivos permitidos.

### P3: UI "Exames de imagem" (Pediatria, React)
- Arquivos permitidos: `src/components/exames/*` (novos: `ExamesImagemClient.tsx`, `FormularioExame.tsx`, `ResultadoExame.tsx`, `MedidasTabela.tsx`, `AvisoPediatrico.tsx`, `useExameMedlens.ts`, `api-exames.ts`, `descricao-copia.ts`, mais testes), `src/app/raio-x/page.tsx` (render de `ExamesImagemClient` com `leitorAtivo={examesMedlensConfigurado()}`; o title muda; gate de login e `rxAbaAtiva` ficam iguais), `src/app/raio-x/page.test.tsx`, `src/components/consulta/MenuApp.tsx` (só o rótulo da linha 60) e os testes de menu que conferem o texto. Importa `src/lib/exames/tipos.ts` (contrato da §2; se P2 ainda não mergeou, criar com conteúdo idêntico, e o merge resolve igual).
- Aceite: `tsc` e `vitest` verdes. A suíte completa (`npx vitest run`) fica sem regressão, comparando o número de falhas com a linha de base de `origin/main`. Playwright em 320/768/1024/1440 sem overflow horizontal, com screenshots salvas em `test-results/exames/`. Em todas as larguras o aviso pediátrico aparece antes das medidas. ECG não mostra janela DICOM. RX não mostra ICT. Botão "Copiar descrição" funciona. Quando `leitorAtivo=false`, aparece "Leitor indisponível no momento". Os dados de teste são sintéticos, nunca imagem real.

### P4: deploy e integração (sequencial, um executor só, depois de P1–P3 verdes)
Ver §5.

---

## 5. Deploy seguro

**Linha de base, ANTES de qualquer deploy.** Salvar em `/private/tmp/.../baseline-rotas.txt`. Rotas: `/`, `/login`, `/cadastro`, `/inicio`, `/consulta`, `/raio-x`, `/pipeline`, `/curso`, `/hoje`, `/api/rx/laudo` (POST sem auth). Para cada uma, `curl -s -o /dev/null -w "%{http_code} %{redirect_url}"`. Salvar também `git rev-parse origin/main` (= c752268a) e o id do deploy de produção atual (`dpl_DwrUdGS6xXeJb9wSeavoBfi14cMg`), que é o alvo de rollback.

1. **medlens-api.** Criar o projeto `medlens-api` na equipe (root `backend`, região `gru1`) e as envs da §1, com o token gerado localmente e sem eco no terminal (`vercel env add ... < arquivo` e apagar o arquivo depois). Deploy de produção por CLI a partir de `feat/oneshot-pediatria`. Smoke: `GET /api/health` → 200. `POST /api/oneshot/ecg` sem token → 401. Com token e imagem **sintética** (ECG fantasma gerado pelo próprio repo, ou figura CC0/domínio público, ex.: ECG ilustrativo da Wikimedia com licença conferida) → 200 com FC coerente. RX com fantasma sintético → 200 sem ICT. Medir a latência fria e a quente.
2. **Env do Pediatria.** Criar `MEDLENS_API_URL` e `MEDLENS_API_TOKEN` em Production e Preview. Não alterar nenhuma outra env.
3. **Preview do Pediatria.** Push de `feat/exames-imagem-medlens` (base `origin/main`): o Git gera o preview. Smoke no preview, logado com a conta de teste do dono, e com a mesma imagem sintética nas duas abas ECG/RX. Fazer a checagem "nada mais mudou" no preview (abaixo).
4. **Produção.** Fazer fast-forward de `main` para a branch da feature (ela contém `c752268a` + só os commits da feature). Isso dispara o deploy Git de produção. Se aparecer BLOCKED ou "Building…" eterno, usar o fallback: `vercel deploy --prod` pela CLI a partir do mesmo commit no worktree, conferindo o autor noreply, conforme a memória `feedback_vercel_blocked_autor_github_noreply.md`.
5. **Smoke em produção.** Repetir o 3, só com imagem sintética. **Nunca dado de paciente.** Conferir `get_runtime_errors` dos dois projetos (15 min).

Checklist "nada mais do site mudou":
- [ ] `git diff --stat origin/main..feat/exames-imagem-medlens` lista só os arquivos permitidos de P2 e P3.
- [ ] Rotas da linha de base: mesmo status e redirect após o deploy. `/` continua 307 → `/login` (a landing não entrou).
- [ ] `.next/server/app-paths-manifest.json`: a única entrada nova é `/api/exames/analisar/route`, e nenhuma some.
- [ ] Menu: só o rótulo "Raio-X (apoio) · BETA" mudou para "Exames de imagem (apoio) · BETA" (diff do teste do MenuApp).
- [ ] Envs do Pediatria: só 2 nomes novos (diff de `filter_project_envs` só com os nomes).
- [ ] O parecer em coluna lateral continua no ar (abrir `/consulta` no desktop, conta de teste).

Rollback:
- Rápido (segundos): remover `MEDLENS_API_URL` do Pediatria e fazer redeploy. A aba mostra "indisponível" e o resto não muda.
- Total: `request_rollback`/promover `dpl_DwrUdGS6xXeJb9wSeavoBfi14cMg` e reverter o ff na main (`git push origin c752268a:main --force-with-lease`). **Este último só se o rollback de deploy não bastar**, porque reescreve a main.
- Back-end: pausar o projeto `medlens-api` (`pause_project`).

Linha do tempo alvo: P1–P3 em paralelo (~2 h) → P4 (~1 h) → folga até 07h.

---

## 6. O que exige Fable (escalada)
- **F1, fase 2 do RX:** exportar a segmentação do torchxrayvision (PSPNet) para ONNX + `onnxruntime` e quantizar, para caber em ~500 MB junto do resto. Isso devolve ICT e áreas confiáveis. Envolve decisão de ML e validação de Dice contra o benchmark existente: não é mecânico.
- **F2, se P1a estourar 500 MB** ou o caminho exigir matplotlib/wfdb em runtime: Fable decide o corte (ex.: trocar funções do scikit-image por scipy, ou separar ECG e RX em duas funções).
- **F3, tabelas pediátricas (P-CLIN-1):** conferir a transcrição dos percentis de Rijnbeek contra o texto integral, junto com o médico, antes de qualquer sinalização por idade.

## 7. Riscos
- Cold start do Python com scipy+cv2 (estimado 3–8 s). Aceitável com o spinner existente; P4 mede.
- Digitalização de foto de ECG torta ou com reflexo pode falhar. Nesse caso a resposta traz a qualidade com alerta e nenhuma medida (falha fechada), nunca um número inventado.
- RX v1 tem pouco valor clínico (sem modelo). Isso fica explícito na tela, para não haver falsa confiança.
- Vercel Hobby: limites de uso de função. O volume esperado é baixo; o rate limit é 20 por 10 min por usuário.
- O dono pode ter esperado a landing no ar: ela não está, e continua fora por decisão deliberada (ver §0).
