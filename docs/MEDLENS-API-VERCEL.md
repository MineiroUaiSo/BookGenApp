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
| `layout` | Opcional (ECG): `auto`, `strips`, `3x4`, `3x4+1`, `6x2`, `12x1` |

Resposta 200 (`Cache-Control: no-store`), chaves em snake_case:
`tipo`, `modo` (`pediatrico`), `idade_meses` (int ou null), `incidencia?` e `regiao?` (só RX), `medidas[]` (`codigo`, `rotulo`, `valor`, `unidade`, `confiavel`, `nota?`), `qualidade[]` (`codigo`, `texto`, `nivel` = `info|alerta`), `descricao_tecnica`, `avisos[]`, `versao_motor`.

- ECG: medidas `fc`, `rr`, `pr`, `qrs`, `qt`, `qtc_bazett` (sempre com a nota de Bazett), `eixo_qrs`. Medida ausente é omitida, nunca inventada.
- RX v1: `medidas` sempre vazio (ICT suprimido), `incidencia`/`regiao` (ou `indeterminada` sob dúvida) e qualidade técnica.
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
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/api/oneshot/ecg" -F "file=@ecg-sintetico.png"   # esperado 401
curl -s "$URL/api/health"                                                                                # esperado {"status":"ok",...}
```

## Limites conhecidos

- Cold start: import do app ~0,2 s; a primeira análise importa scipy/opencv (~2 s com imagem real). Meta do plano: < 10 s.
- RX sem modelo: a incidência e a região de projeções atípicas (perfil) podem errar; o serviço devolve `indeterminada` quando a heurística acusa fora de escopo ou região incerta, e o aviso diz que a estimativa é de baixa confiança.
- Entrada DICOM/WFDB/PDF fora do v1 (o navegador converte DICOM em PNG antes de enviar).
- O multipart é lido pelo Starlette, que pode usar arquivo temporário do sistema (apagado ao fim da requisição) para partes acima de 1 MB; o limite de `Content-Length` barra corpos acima de 4,5 MB antes de ler.
