# Trilha r2-laudo (laudo de ECG completo, ecg_laudo_v1) - log

Worktree wt/r2-laudo (a partir de wt/r2-llm). Python: venv do servidor, sem pip install. Env: MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=<wt>/data/bench.

## Entregas
- J1 docs/research/laudo_ecg_estrutura.md; backend/app/llm/prompts/ecg_laudo_v1.md; backend/app/llm/laudo.py (schema LaudoECG, gate de
  digitalização PR/QRS/QT vs cabeçalho impresso, supressão por regex de achados dependentes, conferência de números, achados críticos sem lastro).
- J2 render_markdown / render_short (1 parágrafo); AIReport.laudo/laudo_markdown/laudo_curto (campos novos; contrato antigo intacto);
  ecg_report(..., printed_header=None, sexo=None) chama o laudo (3a chamada, só texto/medidas, sem imagem); MEDLENS_LAUDO=0 desliga;
  frontend (ReportPanel + types) exibe e copia. npm run build OK (node_modules do repo principal ligado por symlink temporário, não versionado).
- J3 backend/tests/laudo_fixtures.py + test_llm_laudo.py (17 testes offline): few-shot normal/IAM/FA; caso1 errada (abre com discordância, sem
  pré-excitação/isquemia; LLM mal comportada é limpa pelo validador) e caso1 correta (HVE + CMH, strain, Peguero não preenchido, sem desvio de eixo).
- J4 backend/bench/llm_laudo_bench.py + bench/llm_laudo_ids.json (10 ECG PTB-XL folds 1-8 = primeiros 10 de bench/llm_eval_ids.json congelado em wt/r2-llm,
  + caso1-ok e caso1-errada estruturados com gabarito de fatos).

## Correção de Peguero-Lo Presti
Primeira versão usava S de V3 e cortes invertidos. Conferido (busca web, resumo ACC e JACC 2017;69(13):1694): S mais profunda em qualquer
derivação + S de V4; >= 28 mm (2,8 mV) homens, >= 23 mm (2,3 mV) mulheres. Corrigido em laudo.py, docs e teste. Índices prontos em
summary["indices_calculados"] têm precedência (ponto de entrada para futuro analysis/indices.py).

## Benchmark (comandos)
    cd backend; export MEDLENS_DATASETS=... MEDLENS_BENCH=<wt>/data/bench PYTHONPATH=.
    python -m bench.llm_laudo_bench --run --budget 0.10 --tag haiku                       # 10 ECG + caso1 (modelo anthropic/claude-haiku-5.5, OpenRouter)
    python -m bench.llm_laudo_bench --run --only caso1 --budget 0.04 --tag haiku_caso1    # após correção do prompt (6b/6c) e do Peguero
    python -m bench.llm_laudo_bench --run --only caso1 --budget 0.06 --model anthropic/claude-sonnet-5.5 --tag sonnet_caso1

| Execução | Laudos | Números checados | Fora das medidas | % nas medidas | caso1 gabarito |
|---|---|---|---|---|---|
| haiku-5.5, 10 ECG PTB-XL + caso1 (prompt v1 inicial) | 12/12 | 548 | 2 (ptbxl-04359 "210"; ptbxl-13217 "80 ms") | 99,6 | 1/2 (caso1-ok falhou: sem CMH, sem "sem desvio de eixo", sem "Peguero não preenche") |
| haiku-5.5, caso1 (prompt 6b/6c + Peguero V4) | 2/2 | 89 | 0 | 100 | 2/2 |
| sonnet-5.5, caso1 | 2/2 | 57 | 0 | 100 | 2/2 |

Críticos sem lastro: 0. O contador "validador_divergentes" (validate._check_text) tem falsos positivos conhecidos quando uma frase lista
vários valores com uma só unidade (ex. "PR e QRS ... 148 ms e 112 ms" atribui 148 a outra chave): 7 nos 12 laudos iniciais, 2 nos caso1-errada; ficam marcados com [⚠] no texto.
Classes cobertas pelos 10 ECG: normal x2, FA, BAV x2, BRE, BRD, IAM, HVE, QT longo. Não houve revisão médica dos 10 laudos (checagem é só de números/gabarito caso1).

## Custo OpenRouter (soma de usage.cost medido pelo bench)
haiku 12 chamadas US$ 0,0353; haiku caso1 US$ 0,0048; sonnet caso1 US$ 0,0783; total US$ 0,118 (limite da trilha 0,30; J4 0,15). Saldo da conta
é compartilhado com outras sessões, então delta de saldo não é atribuível. Cache das respostas: data/bench/llm_laudo/ (fora do git).

## Não feito
- Laudo com citações de fatos [F..]/critérios [C..], cartões de critérios, qualidade inválida => sem laudo, supressão de WPW por confiança de PR < 0,6.
- Remoção do envio de imagem original ao provedor no ecg_report (estágios 1-2 existentes) e redução dos tetos de tokens dessas etapas (o laudo novo é só texto, 8000 tokens).
- Rodar os 30 ECG; revisão médica; push.
