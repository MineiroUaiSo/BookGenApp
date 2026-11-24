# Plano MedLens ECG: ficha de medidas determinística + critérios citáveis + digitalização por derivação

Reproduzi o erro no caso-ouro com o código atual: sai layout `6x2`, PR 88, QRS 270, QTc 616, pré-excitação e infra/T invertida inferior e anterolateral. A causa é a digitalização: o código não conhece 3x4+3, corta toda amplitude em ±1,77 mV e nenhuma barreira impede o laudo.

Rodei só leitura (`.venv`, sem escrita). Nada foi editado. Os worktrees `r2-*` foram apenas lidos.

## 1. Diagnóstico (file:line, base `/Users/macbook/medlens/backend/app/`)

### Digitalização

| # | Falha | Onde |
|---|---|---|
| D1 | Layout decidido só pelo número de linhas; 6 linhas viram `6x2`, 4–5 viram `3x4+1`. Não há 3x4+3. | `ecg/digitize/__init__.py:139-147`, `ecg/digitize/trace.py:8-15` |
| D2 | Faixa de ritmo sempre gravada como `II`. Em página com V1/II/V5, a primeira faixa (V1) sobrescreve D2. | `ecg/digitize/__init__.py:234-239` |
| D3 | Rótulos impressos nunca são lidos; `clean_ink` apaga o texto. | `ecg/digitize/trace.py:18-37` |
| D4 | Checagem física (Einthoven/Goldberger) desligada em página de 10 s (`std_ok = wide`). | `ecg/digitize/__init__.py:215-216` |
| D5 | Banda vertical de 0,75 × distância entre linhas corta R/S. No caso1 todas as derivações saturam em ±1,77 mV, e o R real de V4–V6 passa de 40 mm (estimativa visual). | `ecg/digitize/__init__.py:88`, `ecg/digitize/trace.py:123-124` |
| D6 | O rastreador troca de traço quando a R da linha vizinha invade a banda; só marca `valid=False` se o salto passa de 3 mm. | `ecg/digitize/trace.py:156-194` |
| D7 | Pulso de calibração lido como 6,5 mm; o código assume 10 mm/mV e segue sem baixar a confiança. | `ecg/digitize/__init__.py:118-121`, `ecg/digitize/trace.py:70-118` |
| D8 | Colunas divididas em partes iguais do tempo, sem usar rótulo nem marcador de troca de derivação. | `ecg/digitize/__init__.py:171-172` |
| D9 | `quality` mede só a fração de colunas válidas (0,95–0,99 no caso1, com tudo errado). `grid_confidence` saiu 1,0. | `ecg/digitize/__init__.py:200,232` |
| D10 | Cabeçalho impresso (PR/QRS/QT/eixos) não é lido em lugar nenhum do repositório principal. | ausente |

### Medidas: por que QRS 270 e PR 88

- **Derivações trocadas:** com `6x2`, cada linha é partida em 5,21 s. A derivação "I" passa a ser I+aVR, e "V1" passa a ser V1+V4.
- **QRS global é união de derivações desalinhadas:** a velocidade vetorial soma todas as derivações (`ecg/analysis/delineate.py:120-138`) e as bordas são o início mais cedo e o fim mais tarde (`delineate.py:465-468`). As medianas são montadas por derivação em modo segmentado (`ecg/analysis/__init__.py:89-103`).
- **Platôs de corte (D5)** alargam o QRS.
- **PR 88:** o início da P é procurado antes de um início de QRS já adiantado (`ecg/analysis/measure.py:120-122`).
- **Sem checagem de plausibilidade:** QRS 270 com ritmo sinusal a 70 bpm passa direto.
- **Imagem pequena:** 1113×727 px dá cerca de 4,2 px/mm, ou ~9,5 ms por pixel. O erro mínimo de intervalo fica em ±10 ms mesmo com tudo certo.

### Regras (`ecg/analysis/rules.py`)

| Critério | Estado |
|---|---|
| Sokolow-Lyon | Existe (`measure.py:143-145`, `rules.py:425`). Usa só S de V1, sem R de V5/V6 separados na saída. |
| Cornell | Existe (`measure.py:146-147`, `rules.py:429-431`). Só vira HVE com strain; sem sexo usa 24 mm. Falta o produto de Cornell. |
| R em aVL > 11 mm | Existe, peso fraco (`rules.py:432`). Falta R em D1 e a soma R D1 + S D3. |
| Romhilt-Estes | Ausente; só aparece como texto em `knowledge/ecg_criteria.yaml`. |
| Peguero-Lo Presti | Ausente no principal. Em `r2-laudo/backend/app/llm/laudo.py:81-89` está com defeito (ver abaixo). |
| Strain / repolarização secundária | Parcial: `strain_l` (`rules.py:421-423`) só reforça o Cornell. Infra de ST e T invertida continuam saindo como achados próprios, com uma nota de cautela (`rules.py:506-517, 561-564`). `ecg.secondary_repolarization` só existe para bloqueio de ramo (`rules.py:499, 556-560`). |
| Sobrecarga atrial esquerda | Exige P > 120 ms **e** bífida, ou Morris (`rules.py:387-393`). P de 120 ms isolada não sinaliza. |
| Padrão de CMH | Ausente; aparece só como diferencial no YAML. |
| Pré-excitação | Dispara com PR < 120 e razão de inclinação inicial < 0,45 (`rules.py:307-312`), sem checar a qualidade da digitalização. |

**Defeito no Peguero do `r2-laudo`:** o código soma o S mais profundo com S de **V3** e usa limites 23 (homem) / 28 (mulher). O critério publicado é S mais profundo + S de **V4**, com ≥ 28 mm em homem e ≥ 23 mm em mulher. Confirmar na fonte (JACC 2017) antes de corrigir.

### LLM

- **Fluxo atual:** duas chamadas com imagem (`llm/__init__.py:100-124`). A foto original vai inteira ao provedor (`api/analysis.py:80-81,100`; `llm/__init__.py:162-163`), com o cabeçalho e seus dados de identificação.
- **Prompt:** `prompts/ecg_system.md:6` pede "leitura visual" e registro de divergência. Isso convida o modelo a medir no olho.
- **Custo:** modelo `claude-opus-5-5`, esforço alto, tetos de 32k e 48k tokens (`llm/client.py:12-15`).
- **Esquema:** `description`, `findings`, `differentials`, `disagreements`, `limitations` (`llm/schema.py:22-42`). Não há aviso no topo, seções da SBC nem validação de números.
- **Seleção de critérios:** o YAML inteiro (33 itens) vai no bloco de sistema; a escolha dos "pertinentes" é por sobreposição de palavras (`knowledge/__init__.py:76-112`).
- **Em andamento em `r2-laudo` (não integrado):** `laudo.py` com LLM só de texto, bloqueio por divergência com o cabeçalho, validador de números e `ecg_laudo_v1.md`. É a base certa para este plano.
- **Em andamento em `r2-ecgk` (não integrado):** `digitize/layout.py` com casamento de moldes dos rótulos e `3x4+3`. A janela `UP_PITCH = 1.5` dá ~33 mm e ainda corta o R de V4–V6 deste caso.

## 2. Ficha de medidas (`ecg_features/v1`)

Arquivo novo `ecg/features.py`, com modelos Pydantic imutáveis. Toda medida carrega valor, unidade, origem, confiança e estado.

```json
{
 "schema": "ecg_features/v1",
 "aquisicao": {"fonte": "image", "layout": "3x4+3", "layout_conf": 0.93,
   "rotulos_lidos": 14, "velocidade_mm_s": 25, "ganho_mm_mv": 10,
   "pulso_mm": {"altura": 10.1, "largura": 5.0, "n": 6},
   "px_por_mm": 4.2, "resolucao_ms_px": 9.5, "filtro_impresso_hz": 40},
 "qualidade": {"global": "ok|suspeita|invalida", "motivos": [],
   "por_derivacao": {"V5": {"cobertura": 0.97, "saturou_banda": false,
     "trocas_de_traco": 0, "sobreposicao_vizinha": true, "snr": 14,
     "n_batimentos": 3, "corr_com_faixa_ritmo": 0.98, "status": "ok"}},
   "einthoven_residuo": 0.08, "goldberger_residuo": 0.06},
 "cabecalho_impresso": {"fonte": "leitura|manual|ausente", "pr_ms": 148,
   "qrs_ms": 112, "qt_ms": 438, "qtc_ms": 482, "qtc_formula": "Bazett",
   "eixo_p": 49, "eixo_qrs": 20, "eixo_t": 171},
 "concordancia": [{"medida": "qrs_ms", "algoritmo": 114, "impresso": 112,
   "delta": 2, "tolerancia": 20, "status": "concorda"}],
 "globais": {
   "fc_bpm": {"v": 73, "conf": 0.9},
   "rr": {"media_ms": 825, "dp_ms": 12, "cv": 0.015, "rmssd_ms": 14, "n": 11},
   "ritmo": {"codigo": "sinus", "p_antes_de_cada_qrs": 1.0},
   "p_ms": {"v": 120, "conf": 0.6, "derivacao": "II"},
   "pr_ms": {"v": 150, "conf": 0.7, "mediana_derivacoes": 148},
   "qrs_ms": {"v": 114, "conf": 0.7, "mediana_derivacoes": 110},
   "qt_ms": {"v": 436, "conf": 0.6},
   "qtc_ms": {"bazett": 480, "fridericia": 465, "framingham": 463, "hodges": 459},
   "eixos_graus": {"p": 50, "qrs": 22, "t": 170, "angulo_qrs_t": 148},
   "transicao_precordial": "V3"},
 "derivacoes": {"V5": {"origem": "coluna4/linha2", "janela_s": [7.5, 10.0],
   "p": {"amp_mm": 1.0, "dur_ms": 100, "morf": "positiva"},
   "q": {"amp_mm": 0, "dur_ms": 0},
   "r": {"amp_mm": 47, "pico_ms": 45}, "s": {"amp_mm": 2},
   "r_linha": null, "qrs_ms": 108, "morf_qrs": "Rs",
   "st_mm": {"j": -1.5, "j60": -2.0, "j80": -2.2, "inclinacao": "descendente"},
   "t": {"amp_mm": -6, "morf": "invertida_assimetrica", "simetria": 0.35},
   "qt_ms": 430, "discordancia_qrs_t": true, "conf": 0.8}},
 "indices": {
   "sokolow_lyon_mm": {"v": 60, "limiar": 35, "preenche": true, "componentes": {"S_V1": 18, "R_V5": 42}},
   "cornell_mm": {"v": 58, "limiar": {"M": 28, "F": 20}, "preenche": true},
   "cornell_produto_mm_ms": {"v": 6500, "limiar": 2440, "preenche": true},
   "peguero_mm": {"v": 25, "limiar": {"M": 28, "F": 23}, "preenche": false, "componentes": {"S_max": "V3", "S_V4": 3}},
   "r_avl_mm": {"v": 21, "limiar": 11, "preenche": true},
   "r_d1_mm": {"v": 22}, "r_max_precordial_mm": {"v": 47, "derivacao": "V5"},
   "romhilt_estes": {"pontos": 6, "itens": [
      {"item": "voltagem", "pts": 3, "evidencia": "R V5 47 mm"},
      {"item": "strain_sem_digital", "pts": 3, "evidencia": "infra ST + T invertida assimétrica em I, aVL, V4-V6"}],
      "classe": "definida>=5"},
   "morris_v1_mm_ms": {"v": 0.04}},
 "padroes": [{"codigo": "strain_lateral", "derivacoes": ["I","aVL","V4","V5","V6"],
   "regra": "R dominante + ST j60 <= -0,5 mm descendente + T invertida assimétrica"}],
 "achados_regras": [{"codigo": "ecg.lvh", "gravidade": "abnormal", "conf": 0.8,
   "evidencia_ids": ["indices.sokolow_lyon_mm", "indices.cornell_mm", "padroes.strain_lateral"],
   "criterio_ids": ["lvh.sokolow", "lvh.cornell", "lvh.romhilt_estes", "repol.strain"]}],
 "suprimidos": [{"codigo": "ecg.preexcitation", "motivo": "PR do algoritmo diverge do impresso"}],
 "contexto": {"sexo": "M|F|null", "idade": null}
}
```

Os números do exemplo são ilustrativos, não medidas reais do caso1.

**Formato enviado à LLM**, só texto, nesta ordem:

1. **Resumo narrativo determinístico** (`features_narrative.py`): 25 a 40 linhas, uma frase por fato, cada uma com identificador `[F12]`. Exemplo: `[F12] V5: R 47 mm, S 2 mm, ST J60 -2,0 mm descendente, T -6 mm invertida assimétrica (conf 0,8)`. A primeira linha é sempre o estado da digitalização e a concordância com o cabeçalho.
2. **JSON compacto**, sem nulos, em mm e ms, arredondado.
3. **Cartões de critério selecionados** (seção 3).

Regras que cortam alucinação:

- Toda frase do laudo cita `[F..]` e `[C..]`. O validador remove qualquer frase sem lastro e qualquer número ausente da ficha, generalizando o `unverified_numbers` do `r2-laudo`.
- Os índices chegam prontos. A LLM não soma, não mede e não vê imagem.
- Medida com confiança abaixo de 0,5 ou derivação com estado diferente de `ok` aparece como "não avaliável".

## 3. Critérios citáveis: tabela determinística + busca lexical, sem vetores

### Comparação

| Opção | Custo | Determinismo | Privacidade | Veredito |
|---|---|---|---|---|
| A. Tabela de cartões (YAML) escolhida por mapa código→cartão | zero | total | nada sai da máquina | base |
| B. A + SQLite FTS5 (BM25, biblioteca padrão) para perguntas livres | zero | total | local, sem modelo | **recomendado** |
| C. Embeddings em nuvem via OpenRouter + sqlite-vec | centavos | menor | só o texto do corpus sai, nunca a ficha | só se o corpus passar de ~2 mil trechos |
| D. YAML inteiro no prompt (como hoje) | tokens a cada chamada | total | sem problema | limite ~40 cartões |

**Recomendo B.** Com 150 a 300 cartões, o mapa por código recupera exatamente o critério certo e a busca lexical cobre o modo explicação. Vetores não trazem ganho mensurável nesse tamanho e somam dependência e um ponto de falha. Não verifiquei se o OpenRouter oferece endpoint de embeddings hoje; conferir antes de considerar C.

**OpenEvidence:** a busca indica que não existe API pública de autoatendimento em 2026. A documentação de desenvolvedor fica atrás de login e há apenas um formulário de acesso para pesquisa/institucional. Uma fonte secundária cita uma "versão de API" sem detalhes. Não é utilizável aqui; o caminho continua sendo o OpenRouter.

### Corpus

Um cartão = um critério, em `knowledge/ecg/cards/*.yaml`:

```yaml
id: lvh.peguero
versao: 1
nome_pt: Peguero-Lo Presti
criterio: "S mais profundo em qualquer derivação + S de V4"
limiares: {M: ">= 28 mm", F: ">= 23 mm"}
medidas: [indices.peguero_mm]
gatilhos: [ecg.lvh, ecg.lvh_voltage]
armadilhas: ["HVE focal/apical pode ter Peguero negativo com Sokolow/Cornell positivos"]
nao_confundir: [repol.strain_vs_isquemia]
fonte: {ref: peguero_2017, local: "JACC 2017;69:1694", tipo: paráfrase}
revisado_por_medico: false
```

Famílias de cartões:

- Intervalos normais e fórmulas de QTc.
- HVE: Sokolow, Cornell (voltagem e produto), R de aVL, Romhilt-Estes item a item, Peguero.
- Strain versus isquemia.
- CMH: voltagem extrema, T gigante apical, Q septais estreitas e profundas, sobrecarga atrial esquerda.
- Sobrecargas atriais, HVD.
- BRE, BRD, bloqueios divisionais, BAV de 1º a 3º grau.
- WPW, com exigência de onda delta visível e PR confiável.
- IAM com supra, limiares da 4ª Definição Universal, Sgarbossa, Q patológica.
- QT longo/curto, Brugada, pericardite, repolarização precoce, distúrbios de potássio, baixa voltagem, troca de eletrodos, marca-passo, FA e flutter.

### Licenças (não verifiquei nenhuma; confirmar antes de indexar)

| Fonte | Uso proposto |
|---|---|
| SBC 2022, laudos de ECG (Arq Bras Cardiol) | Provável acesso aberto CC BY: parafrasear e citar com seção. Confirmar a licença no PDF. |
| AHA/ACCF/HRS 2009 partes I–VI, 4ª Definição Universal de IAM, diretriz AHA/ACC de CMH 2024 | Direitos reservados: não copiar texto. Limiares são fatos; escrever com palavras próprias e citar. |
| Goldberger (Elsevier) | Só citação; nenhum texto indexado. |
| LITFL (CC BY-NC-SA 4.0) | Não indexar se o app puder virar comercial. Usar como link de leitura. |
| ECGpedia (CC BY-NC-SA) e Wikipedia (CC BY-SA) | Mesma restrição de compartilhamento; evitar no corpus, só link. |
| Artigos originais (Sokolow 1949, Casale 1985, Romhilt-Estes 1968, Peguero 2017) | Citar o critério e a referência. |

Regra única: o corpus é 100% paráfrase própria com referência primária, e cada cartão passa por revisão do médico (`revisado_por_medico`).

### Recuperação e uso

- **Recuperação:** `select_cards(features)` une os cartões ligados aos achados, aos índices calculados (inclusive os que não preenchem), aos padrões e os cartões "não confundir". Limite de 20. A imagem nunca entra na consulta.
- **Ordem da resposta:**
  1. Avisos de digitalização.
  2. Pontos críticos, apenas os que têm regra de apoio.
  3. Achados principais, cada um com `[F]` e `[C]`.
  4. Diferenciais, a favor e contra.
  5. Explicação didática curta.
  6. Laudo formal.
- **Citação obrigatória:** o esquema de saída exige `fatos: [F..]` e `criterios: [C..]` por afirmação, com lista fechada dos identificadores enviados.

## 4. Laudo e guarda-corpos

**Laudo formal (SBC 2022):** manter os campos do `LaudoECG` do `r2-laudo`. Acrescentar `pontos_criticos`, `indices_hve` (tabela preenchida por código, não pela LLM), `diferenciais` e `citacoes`.

**Explicação:** dois níveis. O de estudante lista critério, valor e limiar, cinco itens no máximo. O de leigo tem três a cinco frases, sem siglas, sempre com "rascunho, não substitui o médico".

**Guarda-corpos, todos em código:**

| Regra | Implementação |
|---|---|
| LLM não inventa números | Validador contra a ficha; tabelas de números vêm de molde fixo. |
| Divergência entre algoritmo, cabeçalho e física vira aviso no topo | `concordancia[]` e resíduo de Einthoven alimentam `aviso_topo` antes da LLM. |
| Strain não é isquemia | Com HVE por voltagem, ST-T discordante nas derivações de R alta vira `ecg.secondary_repolarization_lvh` e remove os achados de infra de ST e T invertida dessas derivações. Supra de ST em V1–V3 com S profundo recebe cartão de cautela. Achado só fica como isquemia se aparecer fora do padrão. |
| Abstenção | Qualidade `invalida`: sem laudo, só o motivo e o pedido de correção manual. Qualidade `suspeita`: laudo parcial, com os achados dependentes suprimidos. |
| Crítico sem regra | Marcado ou removido, como no `r2-laudo`. |
| WPW | Suprimido se o PR divergir do impresso, se a confiança do PR for menor que 0,6 ou se a digitalização não estiver `ok`. |
| CMH | Sempre "padrão sugestivo, correlacionar com ecocardiograma ou ressonância"; nunca diagnóstico. |

## 5. Digitalização por derivação

Sequência, tendo o `layout.py` do `r2-ecgk` como base:

1. **Retificação e grade** (já existe). Acrescentar um piso de resolução: abaixo de 5 px/mm, baixar a confiança dos intervalos e avisar.
2. **Linhas de base** pelo perfil horizontal, mais os pulsos de calibração na margem esquerda. O número de pulsos confirma o número de linhas.
3. **Rótulos** por casamento de moldes (já no `r2-ecgk`, sem modelo). Escolher o layout pelo acordo entre rótulos, incluindo `3x4+3`, `3x4+2`, `6x2+1` e formato Cabrera.
4. **Colunas** pela posição do rótulo e pelo marcador vertical de troca de derivação do GE. Divisão em partes iguais fica como reserva.
5. **Extração por derivação com banda larga**, de −2,5 a +1,5 distâncias entre linhas. O rastreador roda linha a linha de cima para baixo e subtrai da máscara a tinta já atribuída à linha vizinha. Nos cruzamentos, preferir continuidade de inclinação. Marcar `saturou_banda` e `trocas_de_traco`.
6. **Sincronização pela faixa de ritmo:** correlacionar cada trecho de 2,5 s com a faixa da mesma derivação (V1, II, V5) para corrigir o deslocamento da coluna. Os picos de R das faixas longas viram referência de tempo para todas as derivações.
7. **Checagens físicas sempre ligadas:** II = I + III, soma das aumentadas igual a zero, faixa versus trecho da mesma derivação com correlação ≥ 0,9, progressão de R, pulso entre 9 e 11 mm.
8. **Cabeçalho impresso:** recortar só o bloco numérico (PR/QRS/QT/eixos).
   - (a) moldes de dígitos da fonte GE, sem modelo;
   - (b) Tesseract local, que é OCR clássico e não LLM, mas precisa de instalação;
   - (c) digitação manual de seis números na interface.
   - Nunca usar OCR em nuvem, porque o cabeçalho traz dados de identificação.
9. **Checagem cruzada** entre algoritmo e impresso alimenta `concordancia[]`. Tolerâncias: PR e QRS ±20 ms, QT ±30 ms, eixos ±20°.
10. **Reserva manual na interface:** o usuário escolhe o layout, arrasta as caixas das 12 derivações e das faixas, confirma os rótulos e digita o cabeçalho. O servidor aceita `layout_boxes`.

**Dados de teste** (nada foi baixado; conferir licenças e `docs/DATASETS.md`):

- PTB-XL renderizado em 3x4+1, 3x4+3 e 6x2 com gerador próprio (`tests/synth_ecg.py` já existe).
- ECG-Image-Kit para dobras, sombra e rotação.
- ECG-Image-Database, com fotos reais e sinal de referência.
- PTB-XL+ para as medidas 12SL (o `r2-eval` já tem o carregador).
- Fotos reais do usuário, anonimizadas.

**Métricas:**

- acerto de layout ≥ 98% no sintético e ≥ 90% em fotos;
- acerto de rótulo por derivação;
- correlação de Pearson por derivação ≥ 0,95 (mediana);
- erro de amplitude de R e S ≤ 1 mm (mediana);
- erro absoluto médio de PR ≤ 12 ms, QRS ≤ 10 ms, QT ≤ 20 ms;
- taxa de saturação igual a zero;
- taxa de abstenção correta.

## 6. Avaliação

**Conjunto-ouro** em `backend/tests/gold/`: o caso1 mais 30 ECGs. Distribuição sugerida:

| Grupo | n |
|---|---|
| Normais | 6 |
| HVE com strain | 4 |
| Bloqueio de ramo | 4 |
| IAM com supra | 4 |
| FA / flutter | 3 |
| BAV | 3 |
| WPW | 2 |
| QT longo | 2 |
| Ilegíveis de propósito | 2 |

Cada caso tem imagem, `gold.yaml` (medidas, achados obrigatórios, achados proibidos, pontos críticos) e o laudo do cardiologista.

**Métricas e portões:**

| Métrica | Alvo |
|---|---|
| Fidelidade de números (todo número do laudo existe na ficha) | 100% |
| Erro da ficha contra o cabeçalho impresso ou 12SL | Limites da seção 5 |
| Cobertura de achados críticos | Sensibilidade ≥ 95% |
| Achados proibidos (caso1: WPW, isquemia extensa) | 0 |
| Concordância com o cardiologista por achado | kappa ≥ 0,7 |
| Abstenção correta nos ilegíveis | 100% |
| Abstenção indevida nos bons | ≤ 10% |
| Cobertura de citação (afirmações com `[F]` e `[C]` válidos) | 100% |

**Teste de alucinação:**

- ficha com campos removidos: o laudo não pode citá-los;
- ficha com números trocados: o laudo segue a ficha;
- instrução maliciosa dentro de um campo de texto;
- ficha normal: nenhum achado patológico.

**Integração contínua:**

- `pytest` sem rede cobre ficha, regras, validador e digitalização do caso1, com LLM simulada por respostas gravadas.
- Um alvo manual `make eval-llm` roda os 31 casos com LLM real e teto de custo.
- Asserções do caso1: layout `3x4+3`; QRS 112 ± 20; PR 148 ± 20; Sokolow ≥ 50; Cornell ≥ 45; Romhilt-Estes ≥ 5; Peguero negativo; `ecg.lvh` presente; sem `ecg.preexcitation`; sem `st_depression_*` em derivações de strain.

## 7. Riscos

| Risco | Mitigação |
|---|---|
| **LGPD:** hoje a foto com cabeçalho (sexo, técnico, número do pedido, EID) vai ao provedor externo | Laudo só com texto e ficha sem identificadores. Remover o envio de `image_png` em `llm/__init__.py:162-163`. Sexo e idade só se o usuário digitar. Se algum dia enviar imagem, recortar só o traçado e mascarar cabeçalho e rodapé, reaproveitando `burned_text.py` do `r2-llm`. Usar a skill `lgpd` na onda 0. |
| **Regulatório:** apoio à decisão sem registro | Rótulo "rascunho para revisão médica", registro de vers��es (ficha, prompt, cartões), sem laudo automático final. Enquadramento na RDC 657/2022 a confirmar; não verifiquei. |
| **Custo:** saldo de ~US$ 3 | Uma chamada só de texto, cerca de 6–8 mil tokens de entrada e 1,5 mil de saída. Reduzir os tetos (hoje 32k/48k). Modelo barato para o laudo, com subida de modelo só se o validador reprovar. Cache por hash da ficha. Avaliação com respostas gravadas. Preços por modelo não verificados. |
| **Latência** | Digitalização e ficha rodam localmente em 1–3 s (não medido). Uma chamada de LLM leva 5–20 s. Entregar ficha e índices primeiro e o laudo depois. |
| **Corte de amplitude não resolvido** em traços muito sobrepostos | Sinalizar e abster; oferecer a correção manual. |
| **Conflito com `r2-ecgk`, `r2-laudo`, `r2-llm`** | A onda 0 integra esses worktrees antes de qualquer edição. |

## 8. Ondas

O Opus orquestra e revisa a clínica. O Sonnet executa. O Haiku faz o trabalho mecânico.

| Onda | Tarefa | Arquivos | Aceite | Esforço | Modelo |
|---|---|---|---|---|---|
| **0** | Integrar `r2-ecgk`, `r2-laudo`, `r2-llm`; congelar o caso1 como teste que falha | `tests/gold/caso1/`, `tests/test_gold_caso1.py` | Teste falha pelos motivos desta análise | 0,5 dia | Sonnet |
| 0 | Parar de enviar a foto original | `llm/__init__.py`, `api/analysis.py` | Teste prova que nenhum bloco de imagem sai | 1 h | Sonnet |
| **1A** | Layout por rótulos integrado, `3x4+3`, nomes corretos das faixas | `digitize/__init__.py`, `layout.py`, `trace.py` | Caso1 dá `3x4+3`; sintético ≥ 98% | 1 dia | Sonnet |
| 1A | Banda larga com subtração de traços vizinhos e sinalização de saturação | `trace.py`, `digitize/__init__.py` | Caso1: R de V5 ≥ 40 mm; saturação zero | 1,5 dia | Sonnet, revisão Opus |
| 1A | Calibração robusta e qualidade física (Einthoven, faixa versus trecho) | `layout.py`, novo `digitize/quality.py` | Pulso entre 9 e 11 mm no caso1; páginas embaralhadas saem `invalida` | 1 dia | Sonnet |
| **1B** (paralela) | Índices: Peguero corrigido, Romhilt-Estes, produto de Cornell, R de D1 e aVL, ângulo QRS-T | novo `analysis/indices.py`, `measure.py` | Testes unitários com valores de tabela | 0,5 dia | Sonnet |
| 1B | Regras: strain secundário à HVE, sobrecarga atrial esquerda, padrão de CMH, bloqueios da pré-excitação, checagens de plausibilidade | `analysis/rules.py` (592 linhas; separar `rules_lvh.py`) | Caso1 em sinal sintético correto: HVE, strain, sem isquemia | 1 dia | Sonnet, limiares pelo Opus |
| **1C** (paralela) | Cartões de critério (~150), carregador, busca FTS5, `select_cards` | `knowledge/ecg/cards/`, `knowledge/__init__.py` | Todo código de achado tem ao menos um cartão; esquema validado | 1,5 dia | Haiku redige, Opus revisa, médico aprova |
| **2** | Ficha v1 e resumo narrativo | novos `ecg/features.py`, `ecg/features_narrative.py`, `schemas.py` | Instantâneo do caso1; sem nulos; identificadores estáveis | 1 dia | Sonnet |
| 2 | Leitura do cabeçalho e concordância | novo `digitize/header.py` | Caso1 lê 148/112/438/482/49/20/171 | 1 dia | Sonnet |
| **3** | Laudo v2 com citações `[F]`/`[C]`, validador generalizado, abstenção | `llm/laudo.py`, `prompts/ecg_laudo_v2.md`, `llm/validate.py` | Testes de alucinação da seção 6 passam com LLM simulada | 1,5 dia | Sonnet, prompt pelo Opus |
| 3 | Interface: aviso no topo, tabela de índices, correção manual de layout e cabeçalho | `frontend/src/features/report/`, novo `features/ecg-layout/` | Fluxo de correção manual funciona de ponta a ponta | 2 dias | Sonnet |
| **4** | Conjunto-ouro de 30 casos, alvo `eval-llm`, relatório | `tests/gold/`, `bench/` | Portões da seção 6 | 2 dias + médico | Sonnet e Haiku |

As trilhas 1A, 1B e 1C rodam em paralelo, em worktrees separados e sem arquivos em comum. A onda 2 depende de 1A e 1B. A onda 3 depende de 2 e 1C.

### Decisões que dependem do médico

1. Leitura do cabeçalho: moldes de dígitos, Tesseract local (OCR clássico, mas exige instalação) ou só digitação manual.
2. Limiares: Sokolow por idade, Cornell sem sexo informado, duração de P para sobrecarga atrial (≥ 120 ou > 120 ms), pontuação exata do Romhilt-Estes.
3. Gatilhos do "padrão sugestivo de CMH".
4. Uso comercial do app, que define se LITFL e ECGpedia podem entrar no corpus.
5. Modelo de LLM e teto de gasto por laudo.
6. Os 30 ECGs do conjunto-ouro e seus gabaritos.
7. Tolerâncias de concordância com o cabeçalho.

### Não verificado

- Por que o relato fala em "3x4 + 1 ritmo"; a reprodução no repositório principal deu `6x2`.
- Escala real em px/mm (estimativa visual de 4,2 contra 4,0 do código) e amplitudes reais do caso1.
- Estado funcional do `layout.py` do `r2-ecgk`; não executei.
- Licenças do corpus e dos conjuntos dedados.
- Endpoint de embeddings e preços do OpenRouter.
- Critério exato de Peguero e Romhilt-Estes na fonte primária.
- Enquadramento na Anvisa.