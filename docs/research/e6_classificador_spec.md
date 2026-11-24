# E6 — Segunda opinião por classificador (spec, sem código de produção)

Status: proposta. Trilha H. Nada aqui altera `app/ecg/analysis/*`.

## 1. Objetivo

Hoje a análise de ECG é 100% baseada em regras explicáveis. Dois pontos fracos medidos no bench PTB-XL (folds de desenvolvimento):

- IAM (qualquer infarto, ondas Q / supra ST): sensibilidade ~33%.
- HVE (critério Peguero-Lo Presti): PPV ~26%.

Proposta: um classificador treinado como **segunda opinião** que roda em paralelo às regras e só **adiciona** um aviso (“o modelo sugere revisar IAM”) quando discorda delas. Ele nunca substitui, nunca suprime e nunca altera um achado de regra.

## 2. Modelos candidatos

| Opção | Descrição | Prós | Contras |
|---|---|---|---|
| A. Ribeiro et al. (CODE, Nat Commun 2020) | ResNet 1D de 12 derivações, pesos públicos pré-treinados (6 classes: 1AVB, BRD, BRE, BS, FA, TS) | Peso pronto, bem citado | Não cobre IAM/HVE; precisa de fine-tuning; dados CODE são de telemedicina brasileira (viés de população) |
| B. xresnet1d101 (benchmark Strodthoff et al., PTB-XL) | Treinar do zero em PTB-XL **folds 1-8** (fold 9 validação, fold 10 teste) | Cobre IAM/HVE com rótulos SCP; reprodutível; liberdade de licença (CC BY 4.0) | Treino em GPU; PTB-XL é alemão, 1 aparelho, calibração para população brasileira desconhecida |

Recomendação: **B** como base (rótulos IAM/HVE existem), com **A** como comparação. Treino só em folds 1-8; fold 9 para escolher limiar; fold 10 usado **uma única vez** no final. Os folds 9-10 já foram consultados para ajustar regras (“queimados” para as regras); para o classificador, usar adicionalmente validação externa (ver 4).

## 3. Metas (go/no-go)

| Alvo | Meta | Conjunto |
|---|---|---|
| IAM | sensibilidade >= 60% com especificidade >= 90% | fold 10 + externo |
| HVE (Peguero-Lo Presti como referência de regra) | PPV >= 35% | fold 10 + externo |
| Calibração | ECE <= 0,05 por classe | fold 9/10 |
| Foto de ECG | queda de AUROC <= 0,05 vs sinal limpo (usa o bench E7) | imagens renderizadas |
| Latência | <= 300 ms CPU por exame | M5 |

Se qualquer meta primária falhar, o modelo não entra em produção.

## 4. Validação

- Treino em PTB-XL folds 1-8; limiar em fold 9; teste final em fold 10, 1 vez.
- Validação externa independente: CODE-15% / SaMi-Trop ou CPSC2018 (rotular por conversão de SCP quando possível), para checar generalização entre aparelhos e populações.
- Intervalos de confiança por bootstrap; reportar por sexo e faixa etária.
- Teste de robustez com o digitalizador (E7): modelo roda no sinal digitalizado de foto, não apenas no sinal original.

## 5. Riscos regulatórios (SaMD, ANVISA RDC 657/2022)

- Software que sugere diagnóstico a partir de ECG é provável **SaMD** (RDC 657/2022; classe de risco a definir, provavelmente II-III pela regra de gravidade da condição). Exige notificação/registro antes de uso clínico real e um sistema de qualidade (RDC 665/2022 / ISO 13485), gestão de risco (ISO 14971) e ciclo de vida de software (IEC 62304).
- Uso hoje é apoio ao médico, sem finalidade de diagnóstico autônomo; manter o texto de finalidade de uso coerente em UI, README e API.
- LGPD: dados de treino públicos e anonimizados; se for feito fine-tuning com dados locais, exige base legal, DPIA e anonimização (skill/plano `lgpd`).
- Plano de monitoração pós-mercado: deriva de distribuição, taxa de discordância, feedback do médico.
- Versionamento do modelo (hash, dados de treino, métricas) registrado em cada laudo gerado.

## 6. Explicabilidade

- Saída: classe, probabilidade calibrada, e **onde** (mapa Grad-CAM 1D sobre as derivações e batimento mediano) — exibido junto ao traçado.
- Texto padrão: “Segunda opinião automática sugere possível IAM (probabilidade calibrada X%). Achado NÃO confirmado pelas regras. Revisão médica necessária.” Achados críticos (STE, pneumotórax, BAV3, etc.) permanecem sempre como **sugestivo**.
- Quando o modelo e as regras concordam, nada é exibido além do achado de regra (evita ruído e falsa convicção).
- Não exibir probabilidade bruta sem calibração.

## 5b. Política de integração (nunca substituir regras)

1. Regras continuam como fonte primária e única de achados estruturados.
2. Classificador publica um campo separado `second_opinion` (nunca em `findings`).
3. Kill-switch por variável de ambiente; default desligado até a decisão go/no-go.
4. Qualquer discordância é registrada para auditoria (sem dados de paciente identificáveis).
5. Em qualidade de sinal baixa (ruído, foto ruim, < 2 batimentos), o classificador se abstém.

## 7. Plano de execução (se aprovado)

1. Preparar splits e rótulos (SCP -> classes alvo) com script reprodutível.
2. Treinar xresnet1d (GPU GHOSTLOOK ou MacBook M5/MLX), avaliar em fold 9.
3. Calibrar (temperature scaling) e fixar limiar para espec 90%.
4. Avaliar fold 10 uma vez + validação externa + robustez em foto (E7).
5. Revisão clínica dos falsos positivos/negativos com o médico responsável.
6. Decisão go/no-go; só então integração atrás de flag.

## 8. Fora de escopo

Substituir regras; diagnóstico autônomo; alterar `app/ecg/analysis/*`; treino com dados de pacientes reais sem base legal.
