# Trilha r2-cards (Onda 1C): cartões de critério ECG + busca lexical

Worktree: /Users/macbook/medlens-wt/r2-cards (branch wt/r2-cards). Sem push.

## Entregas
- C1 backend/app/knowledge/cards.py: esquema pydantic Cartao (id, versao, nome_pt, criterio, limiares, medidas, gatilhos, armadilhas, nao_confundir, fonte{ref,local,tipo=paráfrase}, revisado_por_medico=false, verificar, leitura) + carregador/validador (ids únicos, nao_confundir existente, fonte.ref em references.yaml). Gatilho "ecg.x*" = prefixo.
- C2 knowledge/ecg/cards/*.yaml: 141 cartões em 25 arquivos de família (lista "cartoes:" por arquivo). Referências primárias novas em knowledge/references.yaml (Sokolow 1949, Casale 1985, Okin 1995, Romhilt-Estes 1968, Peguero 2017, Sgarbossa 1996, Smith 2012, Morris 1964, Strauss 2011, AHA/ACC CMH 2024, Brugada/Shanghai, Macfarlane 2015, Haïssaguerre 2008, Schwartz 2011, ESC VA 2022, ESC FA 2024, Brugada 1991, Ginzton 1982). Texto é paráfrase própria; nenhum cartão usa LITFL/ECGpedia/Wikipedia.
- C3 backend/app/knowledge/search.py: FTS5 em memória (sqlite3 stdlib, BM25, unicode61 sem acento), search_cards(consulta), select_cards(findings_codes, indices_keys, padroes, limite=20) (gatilhos > padrões > medidas > nao_confundir; ordem determinística por score e id), format_cards. API antiga (select_relevant, format_items) intocada; prompt ainda não migrado para os cartões.

## Comandos de validação
cd /Users/macbook/medlens-wt/r2-cards/backend
export MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=/Users/macbook/medlens-wt/r2-cards/data/bench PYTHONPATH=.
/Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_knowledge_cards_schema.py tests/test_knowledge_cards_cobertura.py tests/test_knowledge_search.py

Resultado: 21 passed. Antes: nenhum cartão (33 itens monolíticos em ecg_criteria.yaml, seleção por tokens). Teste de cobertura: todo código ecg.* de rules.py casa >=1 gatilho.

## Notas
- Famílias de id: lvh.* (HVE), af.* (FA/flutter), repol.*, iam.*, etc.
- Todos os cartões revisado_por_medico: false. Locais de fonte são seção/tema, não página exata, exceto onde a citação do periódico é conhecida.
- O teste de cobertura (exige os cartões) entrou no commit C2, não no C1.
- references.yaml foi sobrescrito por engano durante a sessão e restaurado via git checkout antes de reaplicar o apêndice (sem perda).

## Cartões com 'verificar' (59)
- qtc.framingham_hodges: coeficientes das fórmulas conferidos de memória; confirmar na fonte
- qtc.valores_limite: cortes variam entre fontes; confirmar o adotado pela SBC
- lvh.r_avl: limiar de R aVL conferido de memória; confirmar na Parte V
- lvh.cornell_produto: corte 2440 e ajuste de +6 mm em mulheres confirmar na fonte
- lvh.gubner_ungerleider: critério e corte conferidos de memória
- lvh.sbc_interpretacao: redação exata da recomendação conferir na diretriz
- cmh.voltagem_extrema: sem limiar numérico confirmado
- cmh.t_gigante_apical: corte de 10 mm conferido de memória
- cmh.q_septais: limiar de largura/profundidade confirmar
- cmh.atleta: achados distintivos conferir na seção de atletas
- atrial.ae_morris: cortes atuais da força terminal conferir na Parte V
- atrial.biatrial: confirmar critérios exatos
- atrial.atraso_interatrial: referência de livro; confirmar o critério em artigo primário
- hvd.criterios_r_v1: conjunto exato de critérios conferir
- hvd.s_profunda_lateral: conferir limiar
- bloqueio.trifascicular: definição de trifascicular tem variações
- bloqueio.bsvdr: critério controverso; não confirmado
- conducao.disfuncao_sinusal: verificar seção exata
- ritmo.bradicardia_sinusal: corte 50 ou 60 varia
- wpw.fa_preexcitada: confirmar localização na diretriz
- isquemia.infra_st_subendocardica: achado de aVR descrito em diretrizes ESC/ACC; confirmar texto
- iam.t_hiperaguda: sem limiar numérico
- isquemia.sgarbossa_marcapasso: extensão ao marca-passo vem de outro trabalho; confirmar
- isquemia.wellens: achado descrito por de Zwaan 1982; confirmar na fonte primária
- isquemia.de_winter: fonte primária (de Winter 2008) não confirmada
- isquemia.aneurisma_ve: ver evolução
- isquemia.avr_supra: ainda debatido
- qt.curto: cortes variam entre consensos
- brugada.tipo1: consensos recentes (Shanghai) mantêm; confirmar
- brugada.tipo2: critérios de tipo 2/3 foram revisados; confirmar
- brugada.shanghai: pontuações não detalhadas
- pericardite.tipica: critério consolidado, citação específica a conferir
- pericardite.estagios: conferir
- pericardite.razao_st_t: citação e corte não confirmados
- pericardite.derrame_alternancia: conferir
- repol.repolarizacao_precoce_atleta: conferir
- repol.hiperpotassemia: faixas de K por alteração a conferir
- repol.digital: conferir
- repol.hipotermia: conferir
- voltagem.baixa_voltagem: conferir cortes na Parte V
- voltagem.baixa_amiloidose: conferir
- eletrodos.perna: detalhes conferir
- mp.ritmo_estimulado: conferir
- mp.falha_captura: conferir
- mp.falha_sensibilidade: conferir
- mp.fusao: conferir
- mp.bivent: conferir
- af.resposta_ventricular: cortes dependem da diretriz
- af.bloqueio_associado: conferir
- af.flutter: faixa de frequência conferir
- af.flutter_atipico: conferir
- taq.tsv: conferir
- taq.tv: conferir
- arr.extrassistole: conferir
- arr.escape: conferir
- pulmonar.tep: conferir
- pulmonar.dpoc_padrao: conferir
- misc.alternancia_eletrica: conferir
- misc.sobrecarga_biventricular: conferir
