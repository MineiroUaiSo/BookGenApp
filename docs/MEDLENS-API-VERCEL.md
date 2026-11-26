# medlens-api: back-end MedLens hospedado na Vercel (oneshot pediátrico)

Projeto Vercel Python **`medlens-api`** (equipe `team_5XiXyOxtAbJThCXfoJOcoUFM`, região `gru1`), raiz do projeto = `backend/`.
Expõe só `GET /api/health` e `POST /api/oneshot/{ecg|rx}`. Sem estado, sem IA, sem modelo. Plano: `docs/PEDIATRIA-INTEGRACAO-PLANO.md`.

## O que existe no repositório

| Arquivo | Função |
|---|---|
| `backend/api/index.py` | Entrypoint ASGI (`app`). **Força** `MEDLENS_*_IA=0`, `MEDLENS_LAUDO=0`, `MEDLENS_RX_MODELS=0` e monta só health + oneshot (`create_app(oneshot_only=True)`) |
| `backend/app/api/oneshot.py` | Rota. Bearer em tempo constante, validação, `TemporaryDirectory` apagado no `finally` |
| `backend/app/pediatric.py` | Filtro pediátrico (whitelist de medidas, qualidade, descrição por template, filtro de vocabulário) |
| `backend/vercel.json` | Região `gru1`, `maxDuration` 60, `excludeFiles`, rewrite `/(.*)` para `/api/index` |
| `backend/.python-version` | `3.12` |
| `backend/requirements.txt` | Deps de produção, sem torch/onnx/wfdb/matplotlib/anthropic |
| `backend/.vercelignore` | Não sobe `.venv`, `tests`, `bench`, `data`, `docs` |

## Contrato

`POST /api/oneshot/ecg` ou `/rx`, `multipart/form-data`, header `Authorization: Bearer <MEDLENS_API_TOKEN>`.

| Campo | Regra |
|---|---|
| `file` | Exatamente 1. PNG, JPG ou JPEG (extensão e assinatura de bytes devem concordar). Até 4 MB. Corpo total até 4,5 MB e `Content-Length` obrigatório |
| `idade_meses` | Inteiro 0..215 (até 17a11m). Ausente ou vazio continua pediátrico, com `idade_meses: null` e aviso. 216 ou mais: 400 `idade_fora_da_faixa` |
| `sexo` | Opcional, `M` ou `F`. Validado e **não usado** (não aparece na resposta) |
| `modo` | Opcional, só `pediatrico`. Qualquer outro valor: 400 `modo_invalido` |
| `regiao_declarada` | Opcional (RX): `torax`, `abdome` ou `outro`. Outro valor: 400 `regiao_declarada_invalida`. Vazio conta como ausente |
| `incidencia_declarada` | Opcional (RX): `pa`, `ap`, `perfil` ou `outro`. Outro valor: 400 `incidencia_declarada_invalida`. Vazio conta como ausente |
| `layout` | Opcional (ECG): `auto`, `strips`, `3x4`, `3x4+1`, `6x2`, `12x1` |

Resposta 200 (`Cache-Control: no-store`), chaves em snake_case:
`tipo`, `modo` (`pediatrico`), `idade_meses` (int ou null), `incidencia?` e `regiao?` (só RX), `medidas[]` (`codigo`, `rotulo`, `valor`, `unidade`, `confiavel`, `nota?`), `qualidade[]` (`codigo`, `texto`, `nivel` = `info|alerta`), `descricao_tecnica`, `avisos[]`, `versao_motor`.

- ECG: medidas `fc`, `rr`, `pr`, `qrs`, `qt`, `qtc_bazett` (sempre com a nota de Bazett), `eixo_qrs`. Medida ausente é omitida, nunca inventada. Como a entrada é sempre imagem, toda medida traz a nota fixa "estimada a partir de imagem; conferir no traçado". `confiavel` é `false` em todas as medidas quando a calibração não foi verificada (pulso de calibração não achado na imagem ou grade com pouca confiança; item de qualidade `calibracao` com nível `alerta`). QRS >= 200 ms ou eixo fora de -90..180 graus saem sempre com `confiavel: false`, a nota e um aviso "valor extremo: pode ser artefato".
- RX v1: `medidas` sempre vazio (ICT suprimido) e qualidade técnica. `incidencia` e `regiao` são o que o usuário declarou (`PA|AP|perfil|outro` e `tórax|abdome|outro`) ou `indeterminada` quando não declarou; a detecção do motor nunca é apresentada como fato. Só quando a detecção é confiante (sem aviso de baixa confiança, sem região incerta, sem fora de escopo) e contradiz a declaração sai o item de qualidade `divergencia_regiao` ("região detectada diverge da declarada: conferir") ou `divergencia_incidencia`. Os critérios de rotação, inspiração e exposição só aparecem com PA ou AP declarado.
- Nunca saem `findings`, laudo, índices de voltagem, imagem, nome de arquivo ou texto livre do motor.

Erros (`{"detail": {"codigo", "mensagem"}}`): 401 `nao_autenticado`, 503 `nao_configurado` (sem `MEDLENS_API_TOKEN` no ambiente), 400 (`idade_invalida`, `idade_fora_da_faixa`, `modo_invalido`, `sexo_invalido`, `layout_invalido`, `um_arquivo`, `arquivo_vazio`, `corpo_invalido`), 404 tipo desconhecido, 411, 413 (`arquivo_grande`, `corpo_grande`, `imagem_grande`), 415 `tipo_nao_permitido`, 422 (`imagem_invalida`, `imagem_nao_analisavel`), 500 `analise_falhou`, 502 `resultado_bloqueado`.

## Variáveis de ambiente

| Nome | Valor | Obrigatória |
|---|---|---|
| `MEDLENS_API_TOKEN` | segredo de 48 bytes (`openssl rand -base64 48`), o mesmo do Pediatria | sim (sem ele: 503) |
| `MEDLENS_RETENCAO_HORAS` | `0.1` | não (já é o padrão do entrypoint) |
| `MEDLENS_DATA` | `/tmp/medlens` | não (nunca é usado pelo oneshot) |
| `MEDLENS_CORS` | vazio | não |
| `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY` | **NÃO criar** | não |

As travas de IA (`MEDLENS_DESCRICAO_IA`, `MEDLENS_RX_DESCRICAO_IA`, `MEDLENS_RX_IMAGE_AI`, `MEDLENS_RX_LAUDO_IA`, `MEDLENS_LAUDO`, `MEDLENS_RX_MODELS`) são forçadas a `0` em `api/index.py`; não precisam de env.

## Deploy (comandos exatos, rodados dentro de `backend/`)

Escopo: `--scope team_5XiXyOxtAbJThCXfoJOcoUFM`. Valores de segredo nunca vão a commit nem a log.

```bash
cd backend
SCOPE=team_5XiXyOxtAbJThCXfoJOcoUFM

# 1. cria/vincula o projeto (só na primeira vez; é o passo do P4, não foi feito)
vercel link --yes --project medlens-api --scope $SCOPE

# 2. token: gere e guarde o MESMO valor para o Pediatria (MEDLENS_API_TOKEN)
TOKEN=$(openssl rand -base64 48)
printf '%s' "$TOKEN" | vercel env add MEDLENS_API_TOKEN production --scope $SCOPE
printf '%s' "$TOKEN" | vercel env add MEDLENS_API_TOKEN preview --scope $SCOPE
printf '%s' '0.1' | vercel env add MEDLENS_RETENCAO_HORAS production --scope $SCOPE
vercel env ls --scope $SCOPE            # confere só os NOMES; não deve haver OPENROUTER_/ANTHROPIC_

# 3. preview e checagem do tamanho do bundle (limite 500 MB; medido ~397 MB)
vercel deploy --scope $SCOPE            # imprime a URL de preview
vercel inspect <url-do-deploy> --scope $SCOPE

# 4. produção (só depois do smoke do preview)
vercel deploy --prod --scope $SCOPE
```

Região `gru1` vem de `vercel.json`. Preview com proteção SSO: use `vercel curl /api/health --deployment <url> --scope $SCOPE` ou o header `x-vercel-protection-bypass`.

Rollback: `vercel rollback <url-anterior> --scope $SCOPE`, ou pause o projeto (`pause_project`). Sem `MEDLENS_API_URL` no Pediatria a aba mostra "indisponível".

## Como testar

Local (qualquer venv com `requirements.txt` + `pytest httpx`):
```bash
cd backend
PYTHONPATH=. MEDLENS_DATASETS= python -m pytest -p no:cacheprovider -W ignore tests/test_oneshot.py tests/test_pediatric_mode.py
PYTHONPATH=. MEDLENS_API_TOKEN=teste uvicorn api.index:app --port 8010      # servidor local, mesmo entrypoint da Vercel
```

Smoke em preview/produção (imagem sintética ou pública anonimizada; **nunca paciente real**):
```bash
curl -s -X POST "$URL/api/oneshot/ecg" -H "Authorization: Bearer $TOKEN" \
  -F "file=@ecg-sintetico.png" -F "idade_meses=30" -F "sexo=F" | jq .
curl -s -X POST "$URL/api/oneshot/rx" -H "Authorization: Bearer $TOKEN" \
  -F "file=@rx-publico.png" -F "idade_meses=60" -F "regiao_declarada=torax" -F "incidencia_declarada=pa" | jq .
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/api/oneshot/ecg" -F "file=@ecg-sintetico.png"   # esperado 401
curl -s "$URL/api/health"                                                                                # esperado {"status":"ok",...}
```

## Limites conhecidos

- Cold start: import do app ~0,2 s; a primeira análise importa scipy/opencv (~2 s com imagem real). Meta do plano: < 10 s.
- RX sem modelo: a detecção de incidência e região erra em perfis (medido no OpenI: perfis de tórax lidos como abdome ou extremidade). Por isso a saída usa só a declaração do usuário; sem modelo, a detecção nunca é confiante e não gera item de divergência. Medido em 11 imagens OpenI (5 perfis): nenhuma saída contém "abdome" sem declaração.
- Entrada DICOM/WFDB/PDF fora do v1 (o navegador converte DICOM em PNG antes de enviar).
- O multipart é lido pelo Starlette, que pode usar arquivo temporário do sistema (apagado ao fim da requisição) para partes acima de 1 MB; o limite de `Content-Length` barra corpos acima de 4,5 MB antes de ler.

## Deploy 2026-11-26

Projeto `medlens-api` (id `prj_l1x5dSvlk0R3Yub55sSXYGWvKFrC`, equipe `mviniciusses-1874s-projects` = `team_5XiXyOxtAbJThCXfoJOcoUFM`). Deploy de produção `dpl_7QeKmCdP3a62oYZRXm88rzWdjfrQ`, função `api/index.py` em `gru1`, Python 3.12.

- **URL estável de produção (usar como `MEDLENS_API_URL`):** `https://medlens-api-nu.vercel.app` (alias extra: `https://medlens-api-mviniciusses-1874s-projects.vercel.app`).
- **Bundle:** 407,88 MB brutos no build (abaixo de 500 MB); a Vercel otimiza e a função sai com 43,12 MB (`vercel inspect`). As dependências são instaladas no runtime a cada cold start (~2,5 a 3 s, visto nos logs).
- **Diretório de deploy limpo** (fora do repo): cópia de `backend/api`, `backend/app`, `requirements.txt`, `.python-version`, `.vercelignore` e um `vercel.json` próprio. Sem `.venv`, `tests`, `bench`, `data`, `medlens_data`, imagens.
- **Env (production, tipo Sensitive):** `MEDLENS_API_TOKEN` (`openssl rand -hex 32`; valor só em arquivo 0600 fora do repo, nunca impresso), `MEDLENS_RETENCAO_HORAS=0.1`, e `MEDLENS_DESCRICAO_IA`, `MEDLENS_RX_DESCRICAO_IA`, `MEDLENS_RX_IMAGE_AI`, `MEDLENS_RX_LAUDO_IA`, `MEDLENS_LAUDO`, `MEDLENS_RX_MODELS` todos `0` (redundante com `api/index.py`). Sem `OPENROUTER_API_KEY` e sem `ANTHROPIC_API_KEY`. Não há env em Preview (o Pediatria usa só Production no medlens-api).
- **Proteção de deployment:** `ssoProtection` do projeto `medlens-api` foi posta em `null` via `PATCH /v9/projects/{id}` (só este projeto; o `assistente-pediatria` não foi tocado). A segurança passa a ser só o Bearer do `phi_guard` (falha fechada: 401 sem token, 503 se o token faltar no ambiente).

### Correção necessária no `vercel.json` (importante)

O `backend/vercel.json` do repo (com `rewrites` para `/api/index` e `functions`) **não serve** no projeto com preset FastAPI:
1. Com o rewrite, a Vercel roteia pelo destino reescrito e toda rota vira 404.
2. Sem o rewrite, o preset FastAPI detecta `app/main.py` como entrypoint (candidato padrão) e sobe o **app completo** (`app = create_app()` no fim do módulo, com `/api/studies`, `/api/ingest` etc. e os flags de IA sem a trava de `api/index.py`). Foi o que apareceu no primeiro deploy; foi removido.
3. `pyproject.toml` com `[project.scripts]` não foi respeitado e ainda tira o `requirements.txt` do caminho.

Solução aplicada: builder explícito `@vercel/python` com rota que preserva o caminho. `vercel.json` realmente em produção:

```json
{
  "regions": ["gru1"],
  "builds": [{
    "src": "api/index.py",
    "use": "@vercel/python",
    "config": {
      "maxLambdaSize": "500mb",
      "excludeFiles": "{tests/**,bench/**,data/**,docs/**,medlens_data/**,frontend/**,**/tests/**,**/test/**,**/__pycache__/**,**/*.pyc,**/*.dcm,.venv/**}"
    }
  }],
  "routes": [{ "src": "/(.*)", "dest": "/api/index.py" }]
}
```

Pendente: copiar este arquivo para `backend/vercel.json` (ainda não feito, fora do escopo do P4a). Os 3 deploys anteriores (app completo / 404 / falha de import) foram removidos.

### Smoke em produção (imagens públicas/sintéticas, nenhum LLM)

| Teste | Resultado |
|---|---|
| `GET /api/health` com token | 200 `{"status":"ok","modo":"oneshot-pediatrico"}` (sem token: 401, o `phi_guard` cobre todas as rotas) |
| `POST /api/oneshot/ecg` sem token | 401 |
| `POST /api/oneshot/ecg` token errado | 401 |
| `POST /api/oneshot/rx`, RX público NLM Open-i CXR1521, `idade_meses=60`, `torax`, `pa` | 200, `medidas: []`, sem "cardiomegalia", "normal" ou ICT numérico; avisos dizem que o ICT não é exibido |
| `POST /api/oneshot/ecg`, ECG sintético do repo (`tests/synth_ecg.py`, FC real 100 bpm), `idade_meses=60` | 200, FC 100 bpm, 7 medidas, todas com a nota "estimada a partir de imagem; conferir no traçado" |
| `POST /api/oneshot/ecg`, `idade_meses=216` | 400 `idade_fora_da_faixa` |

Latência (do Mac, ida e volta): 401 sem corpo ~0,25 a 0,4 s; health quente ~0,12 s; RX primeira chamada (inclui cold start) 3,1 s, quente 0,74 s; ECG primeira chamada 5,3 s, quente ~5,0 s (CPU, imagem 2144x1232). Três ECGs simultâneos: 13,5 a 14,4 s cada, ou seja, a análise de ECG contende por CPU quando concorrente; o Pediatria deve enviar uma por vez e usar timeout >= 30 s.

Logs (`vercel logs --deployment dpl_7QeKmCdP3a62oYZRXm88rzWdjfrQ`): só método e caminho de cada requisição e a instalação de dependências; nenhuma ocorrência de nome de arquivo, extensão de imagem ou conteúdo.

O doc acima (seção "Deploy (comandos exatos)") sugere `openssl rand -base64 48`; o token real foi gerado com `-hex 32`. O valor não é registrado aqui.
