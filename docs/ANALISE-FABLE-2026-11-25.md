# Análise crítica MedLens — Fable, 2026-11-25

Branch `claude/ecg-rx-ai-reader-nd20rs`, HEAD `5b9b1c1`. Somente leitura: nenhum código editado, nada commitado, nenhum bench reexecutado. O marcador `data/bench/ecg/code_test.RUN` não foi tocado.
Público: Opus orquestrador (monta lotes) e Sonnets (executam). Decisões clínicas ficam com o médico.

Convenções: `arquivo:linha` refere-se ao HEAD acima. "Sonda" = script de leitura rodado nesta sessão; os comandos estão no Apêndice A para reprodução. Python: `cd backend && PYTHONPATH=. .venv/bin/python`.

Ressalva de método: as contagens sobre `data/bench/ecg/code_test.jsonl` são **re-tabulação do cache já gravado** (sem reexecutar regras). São descritivas e pós-hoc. Não podem ser usadas para ajustar limiar; todo ajuste proposto aqui se apoia no PTB-XL dev, onde o mesmo defeito aparece.

---

## 0. Resumo executivo

1. O texto de IA do **ECG** (caminho padrão, v1) não tem barreira qualitativa. Sonda: 9 frases sem lastro ("sem sinais de isquemia aguda", "Brugada tipo 1", "dentro dos limites da normalidade") passaram intactas, 0 discordâncias. O RX recebeu a barreira; o ECG não.
2. A barreira do **RX** (`claim_check`) é uma lista de negação e vaza: 23 de 30 frases adversariais sem lastro passaram (tuberculose, aneurisma de aorta, pneumomediastino, TEP, "hipotransparência", "condensação", "sem particularidades"). Há ainda um atalho de abstenção e o ICT heurístico é aceito como lastro.
3. No ECG, a regra de **sobrecarga ventricular direita é, na prática, um detector de BRD mal rotulado**: no PTB-XL dev, 171 de 247 disparos (69%) são BRD completo no gold e só 47 são SVD (VPP 17,8%). Isso explica a maior parte da sensibilidade baixa de BRD, não o "incompleto".
4. O **CODE-test pode não ser válido para regras de amplitude**: o app dispara HVE em 64,8% dos 827 traçados e SAD em 30,1% (PTB-XL NORM: 3,2% e 0,9%). Ou a unidade do sinal está errada no harness, ou o app degrada muito fora do PTB-XL. As duas hipóteses são graves e nenhuma foi investigada.
5. Não há autenticação, nem exclusão, nem retenção de estudos. Qualquer publicação com exame real é bloqueada por isso.

---

## 1. Onde o MedLens ainda pode prejudicar um médico (por gravidade)

### R1 — CRÍTICO — Texto de IA do ECG sem barreira qualitativa
- Caminho: `llm/__init__.py:248-278` (`ecg_report`). Com `MEDLENS_LAUDO_V2` desligado (padrão), usa `_two_stage("ecg")` e `validate_report` (`llm/validate.py:347`). Esse validador confere números e 5 tópicos críticos, e só **marca**; nunca remove. A checagem semântica (`claim_semantics.semantic_issues`) só é chamada no v2 (`validate.py:549`).
- `says_normal` só gera alerta se houver regra **crítica** disparada (`validate.py:419-425`). Com `ecg.st_not_assessable` (BRE, marca-passo, QRS largo) presente, a IA pode escrever "sem sinais de isquemia" sem nenhum aviso.
- Sonda (Apêndice A.1): resumo com ritmo sinusal + `ecg.st_not_assessable`. Texto com "Sem sinais de isquemia aguda", "Ausência de supradesnivelamento de ST", "Não há bloqueio atrioventricular", "Padrão de Brugada tipo 1", "Sinais de hipercalemia", "S1Q3T3 sugestivo de embolia pulmonar", "dentro dos limites da normalidade" e um achado `ia.brugada` crítico. Resultado: descrição idêntica, `disagreements = []`, todos os contadores em 0, achado sem flag.
- Agravantes na tela (`frontend/src/features/report/ReportPanel.tsx`): com lista vazia a UI escreve "Nenhuma discordância identificada." (linha ~190), o que lê como "validado"; há botão "Copiar versão curta" para prontuário (linhas 157-158) sobre texto do laudo v1, cujo validador (`laudo.py:217`) também só confere números e supressão por digitalização.
- A IA do ECG recebe o plot renderizado (`llm/__init__.py:265-267`), então descreve morfologia "vista" sem que nada confira.
- Correção mínima: no caminho v1, remover (não marcar) frases com (a) negação de isquemia/IAM/BAV/bloqueio, (b) "normal/sem alterações", (c) diagnóstico não presente em `achados_por_regras`. Reusar o desenho do `rx/claim_check.py` com tópicos de ECG, ou reusar `semantic_issues`. Alternativa mais barata: desligar a narrativa livre do ECG por padrão até o v2 ser avaliado (decisão D-A).

### R2 — CRÍTICO/ALTO — Barreira do RX vaza (lista de negação)
Arquivo `backend/app/rx/claim_check.py`. Só é barrado o que casa com `TOPICOS` (linhas 45-93). Frase que não cita tópico conhecido passa por definição (`problema_da_frase` devolve `None`, linhas 193-216).

Sonda (Apêndice A.2), fatos: ICT 0,46, escores baixos, nenhuma regra. Foram 31 frases: 30 sem lastro e 1 legítima ("Área cardíaca normal.", sustentada pelo ICT medido). **23 das 30 sem lastro passaram**:

| Passou (sem lastro) | Por quê |
|---|---|
| "Hipotransparência em base direita." / "Condensação em base pulmonar esquerda." / "Hipertransparência difusa bilateral." | sinônimos pt-BR usuais ausentes dos regex de opacidade/consolidação/enfisema (linhas 51-66) |
| "Pneumomediastino." / "Cavitação em ápice direito sugestiva de tuberculose." / "Tuberculose pulmonar ativa." / "Abscesso pulmonar." / "Bronquiectasias em bases." / "Calcificações pleurais." | tópico inexistente |
| "Aneurisma de aorta torácica." / "Aorta alongada e ateromatosa." / "Tromboembolismo pulmonar." / "Sinais de insuficiência cardíaca descompensada." / "Neoplasia pulmonar provável." / "Metástases pulmonares múltiplas." / "Achados compatíveis com DPOC." / "… COVID-19." / "Escoliose torácica." | diagnóstico fora da lista |
| "Radiografia de tórax sem particularidades." / "Tórax sem evidências de doença cardiopulmonar aguda." / "Nada digno de nota." / "Parênquima pulmonar com transparência conservada." | normalidade global fora de `_NORMAL_GLOBAL` (linhas 104-107) |
| "Derrame pleural volumoso à direita limitando avaliação do parênquima." | atalho de abstenção: `_ABST` casa "limitando avaliação" e a cláusula inteira é liberada (linhas 194-196), mesmo afirmando derrame volumoso |

Outros três defeitos no mesmo arquivo:
- **ICT heurístico vale como lastro.** `Fatos.de` (linhas 130-145) lê a medida sem olhar a origem. `_afirmacao_ok` aceita "cardiomegalia" com ICT > 0,50 (linha 162) e `_negacao_ok` aceita "área cardíaca normal" com ICT ≤ 0,50 (linha 174). A ficha trata o mesmo ICT heurístico como `NAO_AVALIADO` (`rx/ficha.py:135`). Sonda: ICT 0,62 heurístico, sem regra, "Cardiomegalia importante." passa. O caminho heurístico tem viés +0,109 e concordância ICT>0,5 de 0,35 (`docs/benchmarks/rx.md:105`). O mesmo vale para incidência AP.
- **Falha aberta.** Exceção em `sanitize_report` devolve o texto cru (`llm/__init__.py:335-338`); idem `validate_report` (`llm/__init__.py:153-156`). Uma barreira de segurança deve falhar fechada: em exceção, descartar a narrativa e manter só regras.
- **Janela de negação de 45 caracteres** (linha 188): negação longa vira afirmação. Só importa quando o modelo está em zona "sugestivo" (a negação sobreviveria como afirmação com lastro).

Correção de desenho (o que resolve de fato): inverter para **lista de permissão**. Uma frase da IA só fica se (a) não contém termo clínico, ou (b) todo termo clínico pertence a um tópico com fato. Aproximação barata: léxico de "termo clínico desconhecido" (sufixos e raízes: -ite, -ose, -oma, -megalia, -ectasia, aneurisma, neoplas-, metást-, embol-, tubercul-, cavit-, calcific-, aorta, etc.) cujo casamento sem tópico correspondente remove a frase. O contrato do laudo novo (`rx/laudo_validate.py`, ids de fato obrigatórios) já é lista de permissão; o texto livre de `rx_report` é que ficou no modelo antigo.

### R3 — ALTO — Rótulo de SVD em quem tem BRD (ECG)
Detalhe e números na seção 2.1. Risco clínico: "Sobrecarga ventricular direita" (severidade `abnormal`) em paciente com BRD leva a investigação errada (TEP, hipertensão pulmonar) e esconde o bloqueio.

### R4 — ALTO — Comportamento fora do PTB-XL desconhecido e possivelmente ruim
Re-tabulação do cache do CODE-test (Apêndice A.3), taxa de disparo por registro:

| código | CODE-test (N=827) | PTB-XL dev (N=9183) | PTB-XL só NORM (N=2815) |
|---|---|---|---|
| `ecg.lvh` | 64,8% | 21,3% | 3,2% |
| `ecg.rae` | 30,1% | 1,6% | 0,9% |
| `ecg.lae` | 17,3% | 5,7% | 2,0% |
| `ecg.st_elevation_*` | 13,5% | 4,1% | 0,7% |
| `ecg.rvh` | 7,1% | 2,7% | 0,0% |
| `ecg.within_normal_limits` | 13,2% | 35,5% | 74,6% |

O CODE-test é atenção primária por telessaúde: 681 de 827 registros são negativos para os 6 rótulos. HVE em dois terços e supra de ST em 13,5% dessa população não é plausível.
- Hipótese H1 (harness): unidade errada. `bench/code_test.py:39` fixa `UNIT_TO_MV = 1.0` contra o README do dataset ("escala 1e-4 V"), com base em um percentil. Estatística bruta desta sessão (Apêndice A.4, sem rótulos, sem regras): SV1+RV5 aproximado tem mediana 3,76 "mV" e 57% dos registros ≥ 3,5; pico a pico de D2 tem mediana 1,85. Valores fisiológicos esperados ficam perto da metade. Estimativa grosseira (percentis, sem filtro de linha de base), mas na mesma direção.
- Hipótese H2 (produto): o app degrada com 400 Hz, linha de base ou filtragem diferentes do PTB-XL. Nesse caso a especificidade real de HVE/SAD/supra em exame de rotina é muito pior que a publicada.
- Consequência imediata: a tabela de `docs/benchmarks/code_test.md` vale para rótulos de ritmo/frequência; para BRD/BRE (limiares em mV em `rules.py:128-172`) e para qualquer leitura de amplitude, fica sob suspeita até H1/H2 ser resolvida.
- Como separar sem tocar no teste: teste metamórfico no PTB-XL dev (seção 2.4).

### R5 — ALTO — Falsa certeza por VPP fixo na tela
`ReportPanel.tsx:69-71` mostra "VPP 84,7% [82,4–86,8] (PTB-XL dev, N=1002)" ao lado de fibrilação atrial (`backend/app/knowledge/rule_ppv.json`). No CODE-test, com especificidade igual (98,8% vs 98,1%), o VPP foi 54,5% porque a prevalência é 1,6% e não 11%. VPP não é propriedade da regra. Em pronto-socorro ou ambulatório o número exibido engana para cima.
Correção mínima: trocar por sensibilidade/especificidade (ou razão de verossimilhança), ou manter o VPP com a prevalência da base escrita ("em base com 11% de FA").

### R6 — ALTO — Medida exibida diferente da medida que decide
As regras decidem com medianas por derivação; a tabela mostra o valor global, que é enviesado (PR +11,6 ms, QRS +25,3 ms vs 12SL; `RETOMADA.md:35`; QT: comentário em `rules.py:517-519`). Sonda no cache PTB-XL dev (Apêndice A.5), entre 3257 registros com "Nenhuma regra automática disparou":
- 414 mostram PR global > 200 ms (37 deles são BAV1 no gold);
- 986 mostram QTc Bazett global > 470 ms; no gold QT longo, 33 de 94 (35%) saem com o rótulo neutro;
- 1303 mostram QRS global ≥ 120 ms (este é o caso já decidido pelo dono como "limítrofe").
O médico vê "QTc 480" e, ao lado, nenhuma regra. Ou ele desconfia do app, ou confia no rótulo e ignora o número. Correção: exibir o valor usado na decisão como principal e o global como secundário rotulado ("global, tende a superestimar"). Não muda regra nem bench.

### R7 — ALTO — "Dentro do limite" do ICT com viés negativo
`rx/findings.py:100-102` emite `rx.cardiothoracic_ratio_normal` (severidade `normal`) para qualquer ICT ≤ 0,50, inclusive do caminho heurístico. O caminho com modelo subestima: viés −0,026 (JSRT) e −0,033 (PA outros), concordância ICT>0,5 de 0,89 e 0,80 (`rx.md:104,106`); piores casos 0,22 vs 0,53 e 0,40 vs 0,68 (`rx.md:109`). Um ICT real de 0,52 sai como "dentro do limite". Além disso `findings.py:97` ainda rotula "Cardiomegalia (ICT > 0,50 em PA)", contrariando a decisão D2 já tomada ("sugere aumento da silhueta cardíaca"); o laudo estruturado usa a frase nova, então a mesma tela mostra as duas.
Proposta (limiar é decisão clínica, D-C): faixa cinzenta 0,47–0,53 como "limítrofe/indeterminado pela medida automática"; ICT heurístico nunca gera achado normal nem anormal.

### R8 — ALTO (bloqueia uso real) — PHI: sem autenticação, sem exclusão, sem retenção
- `backend/app/main.py:9-18` não tem autenticação. `GET /api/studies` lista todos os estudos; `GET /api/instances/{id}/render.png` (`api/studies.py:26`) devolve a imagem original, com eventual texto queimado.
- `backend/app/store.py` não tem método de exclusão nem expiração: todo DICOM enviado fica em disco para sempre.
- `_LAST` (`api/analysis.py:70`) é um dicionário em memória sem limite: cresce indefinidamente, some no reinício (o `/ai` passa a responder 409) e quebra com mais de um worker.
- Positivo conferido: `usage_log.py` só grava campos em lista de permissão e hash salgado do estudo; o texto do RX passa por `assert_text_only` em todo caminho (`llm/__init__.py:328-333`); a imagem só sai com consentimento.
- Lacuna: a foto do ECG não vai ao provedor, mas o plot renderizado vai sempre que a IA está ligada, sem consentimento na tela. Não contém cabeçalho; é dado biométrico de baixo risco. Registrar na nota LGPD da UI.

### R9 — MÉDIO — Estados de erro que enganam ou somem (seção 4)

### R10 — MÉDIO — Achados que saem só de escore de modelo
Derrame, consolidação, nódulo dependem só do DenseNet (nódulo AUC 0,628). O laudo estruturado os isola em caixa própria (correto), mas o `ReportPanel` continua listando `rx.model.*` na lista principal de achados, com o mesmo peso visual das regras medidas.

---

## 2. ECG: maior valor por menor custo

### 2.1 BRD — o problema não é o "incompleto", é a regra de SVD
Fatos:
- CODE-test (re-tabulação, Apêndice A.3): dos 17 FP de `RBBB_any`, 14 são só `ecg.irbbb`. Com predicado "só completo": TP 11, FP 3, **sens 32,4%, VPP 78,6%**. Trocar o mapeamento melhora o VPP e derruba a sensibilidade; não é correção.
- Dos 23 BRD do gold não detectados como completo: **18 saíram como `ecg.rvh`**, 13 como `ecg.ivcd`, 7 como `ecg.irbbb`.
- PTB-XL dev (Apêndice A.5): gold BRD completo N=432; detectados 250; perdidos 182, dos quais **119 com `ecg.rvh`**, 79 com `ecg.ivcd`, 71 com `ecg.irbbb`. A mesma informação já estava em `docs/benchmarks/ecg.md:265` ("FN our findings -> rvh:119").
- `ecg.rvh` dispara 247 vezes: gold SVD 47, **gold BRD completo 171**, gold BRD incompleto 46; **230 têm QRS global ≥ 120 ms**. VPP exibido na UI: 17,8% (`rule_ppv.json`).

Causa (regra, não dado):
- `rules.py:507`: a SVD só é inibida quando `c["bbb"] == "rbbb"`. Se o classificador de bloqueio falha, R alto em V1 com QRS largo vira SVD.
- `rules.py:137-153`: BRD exige que a **última** deflexão de V1 seja R/R' (`v1["last"]`) e S larga em D1/V5/V6, ou R' ≥ 5 mm com QRS ≥ 130. O próprio comentário (linhas 399-400) admite que as letras do delineador são ruidosas; um "s" terminal minúsculo derruba `rb_v1`.

Correção mínima (2 mudanças, 1 arquivo):
1. SVD exige QRS de decisão (`dur`) < 120 ms, salvo eixo > 110° (critério já citado no comentário da linha 501-503).
2. QRS de decisão ≥ 120 ms + R dominante em V1 (`r_max > |s_min|`, a mesma condição que hoje dispara SVD) + ausência de padrão de BRE: classificar como BRD. Onde não houver S lateral, rotular "BRD provável".

Efeito estimado no PTB-XL dev (limite superior, se todos os 230 disparos migrarem): sens BRD completo 58,0% → até 85% (369/432), VPP ~69% → ~68%; `ecg.rvh` cai de 247 para ~17 disparos.
Como medir (sem CODE-test): `cd backend && PYTHONPATH=. MEDLENS_BENCH=../data/bench python -m bench.ecg_bench --source ptbxl --split dev --set large --tag E1rvh --workers 4` e comparar as linhas `RBBB_complete`, `RBBB_any`, `RVH` com `docs/benchmarks/ecg.md:194-196`.
Aceite: RBBB_complete sens ≥ 75% com VPP ≥ 65%; RVH VPP ≥ 40%; NORM→normal sem queda > 0,5 pp (hoje 74,6%); LBBB_complete sem mudança.

Sobre BRD incompleto: é limitação combinada. O gold do CODE não separa completo de incompleto e trata incompleto como negativo; no PTB-XL o nosso `irbbb` tem sens 18,9% e VPP 59,0%. Já sai como `borderline`. Não mexer agora; só deixar o texto do `code_test.md` dizer "14 dos 17 FP são bloqueio incompleto (re-tabulação pós-hoc do cache)".

### 2.2 FA — VPP 54,5% é prevalência + um defeito de detecção de QRS
- Parte de dado: especificidade 98,8% no CODE (10 FP em 814) contra 98,1% no PTB-XL. Com 13 positivos (1,6%) o VPP só pode ser baixo; o IC [33,3–75,0] não permite concluir piora. Não é regressão.
- Parte de regra (re-tabulação, Apêndice A.3): dos 10 FP, **5 têm FC calculada de 152, 167, 187, 206 e 222 bpm** em registros sem FA e sem taquicardia sinusal no gold. Co-achados: `ecg.short_qt` em 5, `ecg.lvh` em 6, `ecg.hcm_pattern` em 4. Leitura: onda T alta contada como R (dupla contagem), RR passa a "irregular" e a FC dobra. Esse erro ainda rende "taquicardia" e "QT curto" falsos.
- Limitação para medir: no PTB-XL dev só 1 dos 153 FP de FA tem FC > 150. O dev não contém esse modo de falha, então não há como calibrar nele. E não se pode calibrar no CODE.
- Proposta mínima: guarda de plausibilidade antes de classificar ritmo: se FC > 150 e os picos alternam amplitude/morfologia (padrão R-T-R-T) ou QT de decisão > ~0,9·RR, redetectar com período refratário maior; se persistir, emitir "detecção de QRS não confiável: ritmo não classificado" em vez de FA.
- Como medir: (a) teste unitário sintético (batimento com T = 0,8·R a 75 bpm; esperado FC 75 e nenhum `ecg.atrial_fibrillation`); (b) teste metamórfico no PTB-XL NORM: multiplicar a onda T por 2 em 200 registros e exigir FC inalterada (±5 bpm) em ≥ 98%; (c) bench dev: FA sens ≥ 83% e espec ≥ 98,0% (sem regressão).
- No PTB-XL, 40 dos 153 FP têm PACE no gold. FA com marca-passo ventricular é comum e o gold pode rotular só PACE; não tratar como erro de regra sem revisão de traçado.

### 2.3 BAV1 — sens 46% é metade regra, metade dado
Decomposição dos 370 FN no PTB-XL dev (Apêndice A.5):
- 155 (42%) têm **nosso PR global > 200 ms** e a regra não disparou: a conjunção é estrita demais (`rules.py:339-340`: mediana por batimento > 200 E ≥ 60% dos batimentos E pico P–QRS ≥ 165 ms E ritmo sinusal).
- 62 sem PR medido; 83 com ritmo classificado como flutter/FA/ectópico (erro de ritmo a montante).
- 110 com PR ≤ 180 ms e 43 entre 180 e 200: ou erro de medida, ou rótulo ruidoso (o 1AVB do PTB-XL não é todo validado por cardiologista). No CODE, com gold de cardiologistas, o VPP é 92,9% (1 FP); no PTB-XL é 54,3%. A diferença sugere ruído do gold PTB-XL, não regra frouxa.
- Afrouxar pela medida global não serve: PR global > 220 em ritmo sinusal sem BAV1 atual soma 610 registros, 94 TP e 516 FP (sens 40% → 55%, VPP 54% → 32%).

Proposta mínima, em dois passos:
1. Sem mudar a classificação: quando o PR exibido passa de 200 ms e a regra não dispara, emitir achado `borderline` "PR medido acima de 200 ms sem critério completo de BAV de 1º grau: conferir no traçado". Resolve a incoerência de R6 (414 registros) sem inflar o rótulo `abnormal`.
2. Medir contra medida, não contra rótulo: usar o PR do 12SL (PTB-XL+, já usado em `r2_base.md` para o viés) como referência. Métrica: sensibilidade da regra para "PR 12SL > 200 ms" e erro do nosso PR mediano por batimento. Só depois decidir se relaxa `AV1_PEAK_MS` (165) ou `AV1_BEAT_FRAC` (0,6).
Aceite do passo 1: nenhum registro com PR exibido > 200 ms sai sem achado de PR; NORM→normal inalterado (achado `borderline` não tira do neutro, `rules.py:690-696`).

### 2.4 Medir sem tocar no CODE-test
- **Regra geral**: todo ajuste é medido no PTB-XL dev large (N=9183) e LUDB; o CODE-test não é reexecutado. O cache `code_test.jsonl` pode ser re-tabulado para descrição, sempre rotulado "pós-hoc".
- **Teste de invariância (novo, barato)**: 1000 registros do PTB-XL dev, três transformações: reamostrar 500 → 400 Hz; somar deriva de linha de base (0,3 Hz, 0,2 mV); multiplicar amplitude por 0,5 e por 2. Aceite: concordância de códigos com o original ≥ 95% nas duas primeiras; taxa de `ecg.lvh` varia ≤ 2 pp nas duas primeiras. A terceira serve para ler R4: se ×2 no PTB-XL NORM reproduzir ~65% de HVE e ~30% de SAD, a hipótese H1 (unidade do CODE) ganha força.
- **Unidade do CODE (H1)**: resolver por documentação do Zenodo e pela estatística bruta do Apêndice A.4 comparada à mesma estatística no PTB-XL NORM. Isso lê o sinal, não os rótulos, e não roda regras. Se a unidade estiver errada, o resultado publicado para BRD/BRE é inválido por erro de harness; reexecutar é decisão do dono (D-B).
- **Tamanho de amostra**: com 13 a 37 positivos por rótulo no CODE, nenhum IC de sensibilidade tem menos de ±15 pp. Não comparar pontos percentuais entre PTB-XL e CODE como se fossem regressão.

---

## 3. RX

### 3.1 Sobreposição de rótulos em 390 px
`frontend/src/features/rx/labelLayout.ts:37-54`: `placeLabel` posiciona cada rótulo de forma independente (direita do âncora, senão esquerda, depois limita à viewport). Não recebe os retângulos já ocupados. `ViewerPane.tsx:200-204` chama uma vez por medida. ICT e cúpulas têm âncoras na mesma faixa vertical, então colidem em tela estreita.
Correção mínima: `placeLabel` recebe `ocupados: Bounds[]` e, havendo interseção, desloca em passos de `lineHeight` (para cima, depois para baixo) até livrar ou esgotar 4 tentativas; o chamador ordena por `y` do âncora. Função pura, testável em Vitest sem navegador.
Aceite: teste unitário com dois âncoras a 4 px de distância devolve retângulos sem interseção; Playwright em 320 e 390 com ICT + cúpulas sem sobreposição (comparar `getBoundingClientRect` não se aplica a canvas: validar por captura e pelo teste unitário).

### 3.2 Erro de console não investigado
Não reproduzido nesta sessão (sem navegador). Hipótese mais provável: `GET /favicon.ico` → 404. `frontend/index.html` não tem `<link rel="icon">` e não existe `frontend/public/`; servido pelo `StaticFiles` (`main.py:17`) o navegador registra "Failed to load resource: 404". A rodada R4 no Vite dev relatou console limpo; o erro apareceu na rodada do bundle (porta 8030), o que combina.
Verificar: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8030/favicon.ico`, e no Playwright listar `console` + `requestfailed` com URL. Se confirmado, adicionar ícone (SVG inline em `data:`), esforço P. Se não for isso, registrar a mensagem exata antes de qualquer correção.

### 3.3 Laudo estruturado vs spec (§2–§4)
| Item da spec | Estado | Evidência |
|---|---|---|
| §2 seções, nível por frase, bloco crítico fixo | feito | `rx/laudo.py:152-200` |
| §2 item 5: Impressão inclui `MEDIDO` fora da faixa | **a verificar** | `_impressao` (`laudo.py:169-180`) filtra só `Nivel.REGRA`; depende de a ficha promover medida fora da faixa a REGRA. Teste pedido: ficha com `mediastinal_width_ratio` fora da faixa e sem regra → Impressão deve citá-la |
| §2 item 7: Concordo/Discordo persistido | não | `LaudoEstruturado.tsx:26-34`: estado local, some ao recarregar; não chama `/api/feedback` |
| §2 item 7: comentário por região não avaliada | parcial | `LaudoEstruturado.tsx:36-44`: `useState` sem persistência e **fora do texto copiado/impresso** (`no-print`) |
| §2 item 7: assinatura e status rascunho → revisado | não | só exibe `laudo.status`; não há ação de revisar |
| Fontes consultáveis | parcial | só `title` no `<sup>` (`LaudoEstruturado.tsx:21`): inacessível em toque e teclado; mostra "Fonte S1" sem o título |
| Copiar/exportar o laudo determinístico | **não** | `laudo_rx_markdown` existe na API e em `types/api.ts:222`, mas nenhum componente o usa. O único "copiar" da tela é o do texto de IA |
| §2.2 frases D2 ("sugere aumento…") | parcial | laudo sim; `findings.py:97` ainda diz "Cardiomegalia", na mesma tela |
| §3 contrato da IA + validador | feito, desligado | `rx/laudo_validate.py`; não ligado em `rx_report` (correto, D3) |
| §3.1 barreira no texto livre | feito, com vazamentos | R2 acima |
| §4.1 suíte adversarial ≥ 60 | feito (77) | mas as frases de A.2 não estão nela |
| §4.1 propriedade "região sem fato → não avaliado" | feito | `tests/test_rx_laudo.py` |
| §4.2 casos-ouro | bloqueado | HTTP 429 no Commons; `data/gold_rx/` vazio |
| §4.3 revisão médica de 30 laudos | não feito | é o aceite para uso |
| §6/§7 fontes | parcial | S3 só título lido; N1–N10 pendentes |

### 3.4 Calibração e gate fora de escopo (4,4%)
- O número 4,4% **não tem definição nem comando reproduzível no repositório versionado**: não aparece em `docs/benchmarks/rx.md` (só "não rerodado", linha 139) e `bench/rx_bench.py` não avalia escopo (`grep -n "scope\|out_of_scope" backend/bench/rx_bench.py` não retorna nada). Sem saber o denominador (tórax real rejeitado? não-tórax aceito?), o número não serve para decidir.
- `rx/scope.py` (47 linhas) barra imagem pequena, uniforme, com aparência de documento, ou não-tórax. Os dois erros têm custo diferente: rejeitar tórax real é incômodo; **aceitar não-tórax gera medidas sem sentido**. Só o segundo é risco clínico.
- Pedido: adicionar `--source scope` ao bench com duas taxas separadas e IC: (a) tórax rejeitado, sobre JSRT 247 + PA 400; (b) não-tórax aceito, sobre o conjunto de abdome/outros já usado no `tagfix` e os 400 perfis. Aceite sugerido: (b) ≤ 1% com IC superior ≤ 3%; (a) reportado.
- Reconhecimento de tórax sem tags em perfil: 84,3% (`rx.md:97`); 15,7% dos perfis não geram nada, o que é falha segura.
- Calibração: ECE medido só no IU, e o DenseNet foi treinado também com IU (`rx.md:131`, "risco de vazamento"). As zonas "sugestivo/indeterminado" estão calibradas numa base otimista. Sem VinDr/BRAX (credencial) não há como corrigir. Reexecutar 16 h no mesmo IU não agrega (seção 5). Enquanto isso o texto da caixa do modelo deveria dizer "calibrado em base que participou do treino".

### 3.5 O que falta para o laudo ser usável por um médico
Em ordem:
1. Copiar/imprimir o laudo determinístico com os comentários do médico incluídos (hoje não dá).
2. Uma só voz na tela: hoje há três textos (achados por regra, texto de IA, laudo estruturado) com termos diferentes para o mesmo fato. Para RX, o laudo estruturado deveria ser o principal e o texto de IA, recolhido.
3. Persistir parecer e status (rascunho → revisado) no servidor, sem texto livre no log.
4. ICT com faixa cinzenta e sem achado a partir de segmentação heurística (R7).
5. Revisão médica de 30 laudos (§4.3), que depende dos casos-ouro.
6. Honestidade de cobertura já está boa: pleura, pulmões, ossos e dispositivos saem como "não avaliado". O efeito colateral é um laudo que, na maioria dos exames, só afirma ICT e técnica. Isso é aceitável como apoio, mas deve estar dito no topo ("esta análise mede silhueta, mediastino, traqueia, cúpulas e técnica; não avalia parênquima, pleura, ossos nem dispositivos").

---

## 4. UX e estabilidade

Verificado por leitura de código; o que depende de navegador está marcado "não testado".

| # | Problema | Evidência | Gravidade |
|---|---|---|---|
| U1 | IA indisponível por bloqueio LGPD, recusa ou erro do provedor mostra "sem chave de API ou desativada" e **esconde o motivo real** | `ReportPanel.tsx`: ramo `ai?.available` falso cai no texto genérico; `ai.limitations` (onde `llm/__init__.py:166,173,333` põem o motivo) só é renderizado quando `available` é verdadeiro | ALTO |
| U2 | "Falha ao reanalisar" (confirmar região) **nunca aparece** em estudo de uma incidência | `StudyView.tsx:42` grava `error`, que só é renderizado na linha 80, dentro do bloco `recon3d_available` (linha 75) | ALTO |
| U3 | Diferenciais mostram barra "0%" | `validate.py:406` zera `confidence` e põe `confidence_display`; a UI ignora o campo e imprime `Math.round(d.confidence*100)%` | MÉDIO |
| U4 | POST `/ai` duplicado e sem cancelamento | `StudyView.tsx:24-33` usa flag `cancelled`, sem `AbortController`; `client.ts:93` não aceita `signal`. Em StrictMode (dev) são 2 chamadas pagas; em produção, cada troca do consentimento ou de região dispara nova chamada e a anterior segue cobrando. O servidor não tem cache por (estudo, tipo, consentimento) | MÉDIO (custo: saldo OpenRouter ~US$ 2,65) |
| U5 | `/ai` responde 409 após reinício do backend ou com 2 workers | `_LAST` em memória (`api/analysis.py:70-81`); a UI mostra a mensagem em inglês "analyze first…" | MÉDIO |
| U6 | Botão 3D usa a análise original, não a reanalisada | `StudyView.tsx:75` lê `result.rx.recon3d_available` em vez de `rx` | BAIXO |
| U7 | Alvos de toque < 44 px | `global.css:47` `.btn.small { min-height: 32px }` (Copiar laudo, Concordo/Discordo do `ReportPanel`, "← Novo estudo"); `global.css:71` `.tab` 36 px. Só o laudo estruturado e os switches foram corrigidos | BAIXO |
| U8 | 320/768/1024 do laudo estruturado | **não testado** (`RETOMADA.md:137`). Risco por código: de 961 a 1024 px a grade tem 2 colunas com mínimo de 300 px na segunda (`global.css:74`) e 3 filhos; o laudo cai sozinho na coluna larga, abaixo do visor. Em 320, `pre` do laudo de ECG usa `pre-wrap` (ok) | a medir |
| U9 | Sem `ErrorBoundary` | `grep ErrorBoundary frontend/src` vazio; um erro de renderização em `ViewerPane`/`Recon3DViewer` (carregados com `Suspense`) derruba a tela inteira | MÉDIO |

Aceite comum para U1/U2: teste Vitest que monta o componente com `ai = {available:false, limitations:["Envio à IA bloqueado pela barreira LGPD (…)"]}` e exige o texto na tela; e com `analyzeRX` rejeitando em estudo de uma incidência, exige `role="alert"` visível.

---

## 5. O que NÃO vale fazer agora (custo > valor)

- **Implementar Sgarbossa/Smith.** Exige medida de ST confiável em QRS largo, que hoje tem viés conhecido; o aviso "ST não interpretável" já cobre o risco.
- **Corrigir o viés de +25 ms do QRS global.** O dono manteve "limítrofe"; a correção só importaria para promover a anormal. Basta exibir a medida de decisão (R6).
- **Trocar o mapeamento do CODE para "só BRD completo".** Sobe o VPP para 78,6% e derruba a sensibilidade para 32,4%. Não é correção, e é escolha pós-hoc sobre o teste externo.
- **Afinar BAV2/BAV3.** N=12 positivos cada no dev; qualquer ganho é ruído.
- **Reexecutar a calibração do RX (~16 h) no mesmo IU.** Mesma base com vazamento; sem dado externo o resultado não muda de natureza.
- **Ligar a IA no laudo do RX, rodar 60 laudos (~US$ 11), CXAS, DRR/abdome, reconstrução 3D.** Nenhum reduz risco; todos dependem de decisão ou licença pendente.
- **Melhorar a segmentação heurística.** Dice 0,45 e ICT com concordância 0,35: melhor impedir que gere achado do que consertá-la.
- **Melhorar o detector de nódulo (AUC 0,63).** Sem dado e sem modelo novo não há ganho; manter rebaixado na caixa do modelo.
- **Matriz Safari/Firefox e digitalização de aVL/V4 do caso 1.** Valor baixo enquanto R1–R4 estão abertos.

---

## 6. Decisões que só o dono toma (3)

**D-A. Narrativa livre de IA no ECG enquanto não há barreira qualitativa.**
Opções: (1) desligar por padrão a "Descrição minuciosa" e o laudo v1 do ECG, mantendo regras e medidas; (2) manter ligada e aplicar a barreira de remoção (item 1 da lista); (3) manter como está.
Recomendação: (1) agora e (2) em seguida. O texto atual passa "sem sinais de isquemia" em traçado com ST não interpretável e tem botão de copiar para prontuário.

**D-B. CODE-test: o que fazer se a unidade do sinal estiver errada no harness.**
Opções: (1) não reexecutar; publicar errata em `code_test.md` (rótulos de amplitude e BRD/BRE sob suspeita; 14 dos 17 FP de BRD são incompletos; HVE em 64,8%) e tratar o resultado atual como definitivo com ressalva; (2) autorizar **uma** reexecução declarada "execução 2, não cega, correção de harness", publicada ao lado da primeira; (3) ignorar.
Recomendação: (1) já. (2) só se o teste de invariância no PTB-XL e a documentação do dataset confirmarem erro de unidade, e somente depois de as regras estarem congeladas de novo. Nunca usar o CODE para ajustar limiar.

**D-C. ICT: faixa cinzenta e linguagem.**
Proposta: 0,47–0,53 = "limítrofe/indeterminado pela medida automática" (em vez de "dentro do limite" até 0,50 e "cardiomegalia" acima); ICT de segmentação heurística não gera achado; rótulo "sugere aumento da silhueta cardíaca" também na lista de achados (D2 já decidida, falta aplicar em `findings.py`).
Recomendação: aprovar. O erro médio do ICT com modelo é 0,027–0,041 com viés negativo; um corte seco em 0,50 produz falso "dentro do limite" exatamente onde a decisão importa. Os limites 0,47/0,53 são sugestão a partir do erro medido; o médico define.

---

## 7. Lista ordenada (máx. 10)

| id | Item | Risco / valor | Esforço | Evidência | Aceite objetivo |
|---|---|---|---|---|---|
| F1 | ECG: barreira qualitativa no texto de IA v1 (remover, não marcar), ou desligar a narrativa (D-A) | CRÍTICO: IA afirma "sem isquemia", Brugada, "normal" sem lastro e o texto é copiável | M (P se só desligar) | R1; sonda A.1: 9/9 frases passam, 0 discordâncias | Teste RED→GREEN com as frases de A.1: 0 sem lastro permanecem; "FC 72 bpm" e "ritmo sinusal" (com regra) permanecem; suíte ECG atual verde |
| F2 | RX: fechar vazamentos do `claim_check` (termo clínico desconhecido = remove; atalho `_ABST`; origem/incidência do ICT; falha fechada nas duas barreiras) | CRÍTICO/ALTO: diagnósticos graves inventados passam | M | R2; sonda A.2: 23/30 sem lastro passam; `llm/__init__.py:153-156,335-338` | As 30 frases sem lastro de A.2 entram em `test_rx_validator_qualitative.py`: 0 passam; "Área cardíaca normal." com ICT de modelo em PA continua passando; as 31 legítimas de `test_rx_laudo_validate.py` continuam passando; exceção simulada no validador devolve relatório sem narrativa |
| F3 | ECG: SVD não dispara com QRS ≥ 120 ms (salvo eixo > 110°); R dominante em V1 + QRS ≥ 120 vira BRD | ALTO: rótulo errado em 171 de 247 disparos; maior ganho de sensibilidade disponível | P | 2.1; `rules.py:137-153,507`; `ecg.md:265`; A.5 | PTB-XL dev large: RBBB_complete sens ≥ 75% e VPP ≥ 65%; RVH VPP ≥ 40%; NORM→normal ≥ 74,1%; LBBB inalterado |
| F4 | ECG: teste de invariância (400 Hz, deriva, escala) + apurar unidade do CODE-test; errata em `code_test.md` | ALTO: validade do teste externo e comportamento fora do PTB-XL desconhecidos | P/M | R4; tabela CODE vs PTB-XL; A.3, A.4 | Relatório com concordância de códigos ≥ 95% (ou lista do que quebra); unidade do CODE determinada por documento + estatística; `code_test.md` com ressalva; marcador `.RUN` intacto |
| F5 | PHI antes de qualquer uso real: autenticação, exclusão de estudo, retenção com prazo, `_LAST` limitado | ALTO: bloqueia publicação | M | R8; `main.py:9-18`; `store.py` sem delete; `api/analysis.py:70` | `GET /api/studies` sem credencial = 401; `DELETE /api/studies/{id}` remove arquivos e artefatos (teste); estudos expiram em N horas configuráveis; `_LAST` com teto |
| F6 | Coerência medida × conclusão no ECG: exibir a medida de decisão; achado `borderline` para PR > 200 ms sem critério completo; não exibir QTc global isolado | ALTO: 414 (PR) e 986 (QTc) registros neutros com número fora da faixa na tela | M | R6, 2.3; A.5 | No cache dev reprocessado: 0 registros com PR exibido > 200 ms sem achado de PR; QTc exibido = QTc da decisão; NORM→normal inalterado |
| F7 | UI: mostrar o motivo real quando a IA está indisponível; erro de reanálise visível; VPP com prevalência ou trocado por sens/espec; confiança "0%" dos diferenciais | ALTO/MÉDIO: erro silencioso e falsa certeza | P | U1, U2, U3, R5 | Vitest dos dois estados de erro (seção 4); nenhum "VPP x%" sem a prevalência da base; Playwright 320/768/1024/1440 |
| F8 | RX: ICT com faixa cinzenta e sem achado heurístico; rótulo D2 em `findings.py`; modelo fora da lista principal de achados | ALTO: falso "dentro do limite" | P | R7, R10; `findings.py:86-102`; `rx.md:104-109` | Depende de D-C. Teste: ICT 0,49 (modelo) → limítrofe; ICT heurístico → nenhum achado normal/anormal; nenhuma ocorrência de "Cardiomegalia (" nos rótulos |
| F9 | RX: laudo utilizável — copiar/imprimir `laudo_rx_markdown` com comentários, parecer/status persistidos, fontes acessíveis por toque, anti-colisão de rótulos, causa do erro de console | MÉDIO: sem isso o laudo não sai da tela | M | 3.1, 3.2, 3.3 | Botão copia markdown com comentários; parecer sobrevive a recarregar; teste unitário de colisão; Playwright 320/390/768/1024 sem sobreposição e console sem erro (mensagem registrada) |
| F10 | FA: guarda contra dupla contagem de QRS (FC > 150 com T alta) + `AbortController` e cache do `/ai` | MÉDIO: FA/taquicardia falsas fora do PTB-XL; custo de chamadas duplicadas | M | 2.2 (5 de 10 FP com FC 152–222); U4 | Teste sintético T = 0,8·R: FC correta, sem FA; metamórfico T×2 em 200 NORM: FC ±5 bpm em ≥ 98%; bench dev FA sens ≥ 83% e espec ≥ 98,0%; em StrictMode, 1 chamada concluída ao provedor por estudo |

Ordem sugerida de lotes: F1 e F2 primeiro (independentes, arquivos distintos: `llm/` e `rx/claim_check.py`); F3 isolado (toca `rules.py`, exige bench); F4 em paralelo (só bench e docs); F7 e F9 no frontend; F5 antes de qualquer uso com exame real. F6, F8 e F10 depois das decisões D-A a D-C.

---

## Apêndice A — Comandos das sondas

Todos somente leitura. Diretório: `backend/`. Interpretador: `PYTHONPATH=. .venv/bin/python`.

**A.1 ECG, validador v1**
```python
from app.schemas import AIReport, Finding
from app.llm.validate import validate_report
s={"medidas_globais":{"heart_rate_bpm":72,"pr_ms":160,"qrs_ms":96,"qt_ms":400,"qtc_bazett_ms":430},"medidas_por_derivacao":[],
   "achados_por_regras":[{"code":"ecg.sinus_rhythm","label":"Ritmo sinusal","severity":"normal","evidence":[]},
                         {"code":"ecg.st_not_assessable","label":"ST não interpretável","severity":"borderline","evidence":[]}],"avisos":[]}
t=("Ritmo sinusal. Sem sinais de isquemia aguda. Ausência de supradesnivelamento de ST. Não há bloqueio atrioventricular. "
   "Onda T invertida difusa sugestiva de isquemia subendocárdica. Padrão de Brugada tipo 1 em V1-V2. Sinais de hipercalemia. "
   "Padrão S1Q3T3 sugestivo de embolia pulmonar. Eletrocardiograma dentro dos limites da normalidade.")
r=validate_report(AIReport(description=t,findings=[Finding(code="ia.brugada",label="Padrão de Brugada tipo 1",severity="critical",evidence=[])]),s,[])
print(r.description==t, r.disagreements_with_measurements, r.validation)   # True [] todos 0
```

**A.2 RX, `claim_check`**
```python
from app.rx import claim_check as C
S=lambda ict=0.46:{"imagens":[{"medidas":[{"key":"cardiothoracic_ratio","value":ict}],
   "probabilidades_modelo_auxiliar":{"Effusion":0.1,"Pneumothorax":0.1},"zonas_modelo_auxiliar":{"Effusion":"nao_sugerido"}}],"achados_por_regras":[]}
f=C.Fatos.de(S())
for x in ["Derrame pleural volumoso à direita limitando avaliação do parênquima.","Hipotransparência em base direita.",
          "Condensação em base pulmonar esquerda.","Pneumomediastino.","Tuberculose pulmonar ativa.","Aneurisma de aorta torácica.",
          "Tromboembolismo pulmonar.","Metástases pulmonares múltiplas.","Radiografia de tórax sem particularidades.","Nada digno de nota."]:
    print(C.problema_da_frase(x,f) is None, x)          # True = passou
print(C.problema_da_frase("Cardiomegalia importante.", C.Fatos.de(S(0.62))))   # None = passou com ICT sem origem
```
As 23 frases que passaram estão na tabela de R2. Barradas corretamente (7): pneumotórax hipertensivo, consolidação lobar, linfonodomegalia hilar, "exame radiográfico sem achados agudos", negação longa de derrame, "mediastino sem alterações" (sem medida no resumo) e "cardiomegalia" com ICT 0,46.

**A.3 CODE-test, re-tabulação do cache (não reexecuta nada)**
```python
import json, collections
from bench import code_test as ct
gold=ct.load_labels(); L=ct.LABELS
rows={int(json.loads(l)["id"].split("-")[1]):json.loads(l) for l in open("../data/bench/ecg/code_test.jsonl")}
i=L.index("RBBB")
for nome,p in (("any",lambda c:"ecg.rbbb" in c or "ecg.irbbb" in c),("completo",lambda c:"ecg.rbbb" in c)):
    tp=sum(1 for j,r in rows.items() if p(r["codes"]) and gold[j][i]); fp=sum(1 for j,r in rows.items() if p(r["codes"]) and not gold[j][i])
    print(nome,tp,fp)                                    # any 18 17 ; completo 11 3
print(collections.Counter(c for j,r in rows.items() if gold[j][i] and "ecg.rbbb" not in r["codes"] for c in r["codes"]).most_common(4))
k=L.index("AF"); print(sorted(round(r["hr"]) for j,r in rows.items() if "ecg.atrial_fibrillation" in r["codes"] and not gold[j][k]))
print({c:round(100*sum(c in r["codes"] for r in rows.values())/827,1) for c in ("ecg.lvh","ecg.rae","ecg.within_normal_limits")})
```

**A.4 CODE-test, amplitude bruta (sem rótulos, sem regras)**
```python
import numpy as np; from bench import code_test as ct
X=ct.load_tracings(); s=[]
for x in X:
    x=ct.trim_padding(x); x=x-np.median(x,axis=0)
    s.append(abs(np.percentile(x[:,6],0.5))+np.percentile(x[:,10],99.5))     # ~S V1 + R V5
print(np.percentile(s,[10,50,90]), np.mean(np.array(s)>=3.5))                # [2.1 3.76 6.0] 0.571
```

**A.5 PTB-XL dev, cache `data/bench/ecg/ptbxl.jsonl`**
```python
import json
px=[r for r in map(json.loads,open("../data/bench/ecg/ptbxl.jsonl")) if r.get("ok")]
C=lambda r:[f["code"] for f in r["data"]["findings"]]; G=lambda r,k:r["data"]["gm"].get(k) or 0; P=lambda r,l:l in r["data"]["scp"]
rv=[r for r in px if "ecg.rvh" in C(r)]
print(len(rv),sum(P(r,"RVH") for r in rv),sum(P(r,"CRBBB") for r in rv),sum(G(r,"qrs_ms")>=120 for r in rv))   # 247 47 171 230
cr=[r for r in px if P(r,"CRBBB") and "ecg.rbbb" not in C(r)]; print(len(cr),sum("ecg.rvh" in C(r) for r in cr))  # 182 119
w=[r for r in px if "ecg.within_normal_limits" in C(r)]
print(len(w),sum(G(r,"pr_ms")>200 for r in w),sum(G(r,"qtc_bazett_ms")>470 for r in w),sum(G(r,"qrs_ms")>=120 for r in w))  # 3257 414 986 1303
fn=[r for r in px if P(r,"1AVB") and "ecg.av_block_1" not in C(r)]; print(len(fn),sum(G(r,"pr_ms")>200 for r in fn))   # 370 155
```
Observação: o cache conta 618 registros com 1AVB e 432 com CRBBB; `ecg.md` reporta 616 e 431 (diferença de 1–2 registros por critério de inclusão do bench). Não altera as conclusões.

## Apêndice B — Limites desta análise
- Nada foi rodado em navegador: 3.1, 3.2 e U8 são leitura de código e hipótese.
- O bench não foi reexecutado; os números do PTB-XL vêm do cache `ptbxl.jsonl` de 2026-11-25 17:39 e de `docs/benchmarks/ecg.md`.
- Os efeitos estimados em 2.1 são limite superior, não medição.
- Não foram lidos: `ecg/digitize/*`, `recon3d/*`, `rx/measure.py`, `rx/seg_*`, `llm/client.py`, `llm/anon.py`, `dicom/burned_text.py`. Riscos nessas áreas não foram avaliados.
- A estatística de amplitude do CODE (A.4) é grosseira; serve para levantar a hipótese, não para fixar o fator de escala.
- No diretório de trabalho há itens não rastreados que não são desta sessão (`.claude/worktrees/`, `CLAUDE.md`); não foram tocados.
