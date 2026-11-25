# Trilha 5 (UX / qualidade / log) — rodada 3

Branch `wt/r3-t5`, base 4b13b7d. T1 (abstenção ST/Q por ruído) fora: já feita na trilha 7.

## Commits
- T2 `f66ed11` feat(rx): gate fora de escopo
- T3 `55c1dee` feat(api+ui): regras primeiro, IA depois
- T5 `546b282` feat(ui): alerta de baixa confiabilidade
- T7 `c0ac1bb` feat(api): log JSONL sem PHI + feedback + snapshot de regressão (10 casos)
- T6 `f3e45ff` feat(ui+api): concordo/discordo por achado
- T4 (este commit) rule_ppv.json + script + UI "VPP x [a–b] (PTB-XL dev, N=...)"

## T2 — gate fora de escopo (sem pesos novos)
Os pesos do autoencoder do TorchXRayVision NÃO estão em cache (só PSPNet e DenseNet) e o download não foi feito;
o gate usa a região/incidência já decididas por `app/rx/view.py` (tag DICOM + plausibilidade PSPNet) mais
estatísticas de pixel (imagem uniforme, traçado/documento com fundo dominante > 80%, entropia < 5,5 bits).
Mede-se (modelos ligados, `app.rx.analyze_image`):

| Conjunto | N | fora de escopo |
|---|---|---|
| JSRT (tórax PA) | 60 | 1 (1,7%) |
| IU dev amostra | 100 | 5 (5,0%): 4 perfis (sufixo -1) classificados como abdome/outra + 1 frontal |
| DICOM exemplos abdome | 3 legíveis | 3/3 fora de escopo |
| DICOM exemplos tórax | 5 | 0/5 (todos em escopo) |

Falso fora-de-escopo JSRT+IU = 6/160 = 3,75% (meta <= 2%: NÃO atingida; causa: detecção de perfil pré-existente
em `view.py`, que confunde perfis com abdome). Imagem em branco e traçado/documento sintéticos: 100% (testes).
Amostras: random.seed(3), `/Users/macbook/medlens/data/datasets/{jsrt_masks,iu_xray}`.

## T3 — regras primeiro, IA depois
`POST /api/ecg|rx/{id}/analyze` (ai=false por padrão no front) devolve regras na hora; `POST /api/ecg|rx/{id}/ai`
gera o texto (usa o último resultado em memória; 409 se não houve analyze). `?ai=true` segue funcionando.
UI: "Gerando texto da IA…" sem bloquear o laudo.

## T4 — VPP medido
`python -m bench.ecg_bench --source ptbxl --split dev --set large --tag R3T5L --workers 3` (HEAD 4b13b7d + T2/T3 que não tocam o ECG;
9183 registros dev, folds 1-8) e `python -m bench.rule_ppv --tag R3T5L` -> `backend/app/knowledge/rule_ppv.json`
(43 códigos, IC Wilson 95%). Código sem medida (ex.: ritmo irregular, RX) mostra "VPP não medido".
Endpoint `GET /api/rule-ppv`.

## T5/T6/T7
- Alerta: `components/ReliabilityAlert.tsx` (role="alert", ícone, cor; crítico para fora de escopo/região incerta) em RX e ECG.
- Feedback: `POST /api/feedback/{study}` {kind, code, verdict}; grava só código+veredito.
- Log: `<MEDLENS_DATA>/logs/usage.jsonl`: commit, versão, latência por etapa, flags de qualidade, códigos, provedor IA,
  feedback; campos por whitelist; study_id vira hash com sal aleatório por instalação. Teste verifica ausência de PHI.
- Regressão: `tests/test_ecg_regression_snapshot.py` (10 sintéticos, snapshot versionado; regenerar com MEDLENS_UPDATE_SNAPSHOT=1).

## Validação
Frontend: `npm run build` ok; `npx vitest run` 35 testes ok (node_modules por symlink do repo principal, não versionado).
