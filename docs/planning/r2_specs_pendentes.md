# Specs da rodada 2 (handoff do orquestrador)

Gerado em 2026-11-24. Trilhas ainda NÃO lançadas por orçamento: 5 (r2-ux), 6 (r2-e5), 7 (r2-e1), 8 (r2-e34), 9-E6 (r2-e6), e ondas 2-4 do plano ECG (ficha ecg_features/v1, cabeçalho, laudo v2 com [F]/[C], conjunto-ouro). Cada spec abaixo é o prompt exato para um executor Sonnet em worktree ~/medlens-wt/r2-<trilha> criado a partir da branch principal já mesclada.



## SPEC5

```text
Você é executor SONNET da trilha r2-ux (Ação 5: qualidade, fora de escopo, UX de confiança, monitoramento) do MedLens. Worktree: /Users/macbook/medlens-wt/r2-ux (branch wt/r2-ux). TRILHA=ux.

CONTEXTO COMUM (MedLens, ferramenta de apoio a laudo ECG/RX; NÃO é dispositivo certificado):
- Repositório principal: /Users/macbook/medlens (branch claude/ecg-rx-ai-reader-nd20rs). Você trabalha SÓ no seu worktree (indicado abaixo); não toque no repo principal nem em outros worktrees.
- Python: use /Users/macbook/medlens/backend/.venv/bin/python (venv do servidor: PROIBIDO pip install nele). Rode tudo a partir de <worktree>/backend com PYTHONPATH=. e exporte:
  MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets  MEDLENS_BENCH=<worktree>/data/bench
- Testes: cd <worktree>/backend && PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -p no:cacheprovider
- Bench (exemplos): python -m bench.ecg_bench --source ludb|ptbxl|qtdb [--split dev] --tag <TAG> --workers 3 ; python -m bench.rx_bench --source masks|dicom-exemplos|iu ... (leia --help).
- DICOM reais de exemplo: ~/Downloads/dicom-exemplos/{torax,abdome} (dados de paciente anonimizados: NUNCA versionar, nunca enviar a serviço externo).
- 
- REGRA DO USUÁRIO: modelos de IA de linguagem/embeddings/OCR NUNCA locais (sem Ollama, easyocr, tesseract etc.); se precisar de LLM, OpenRouter em nuvem dentro do orçamento. Ferramentas determinísticas locais ok. Os modelos de visão do leitor RX (TorchXRayVision/PSPNet) seguem como estão.
- REGRAS DURAS: não fazer git push; não reiniciar/usar a porta 8000 (se precisar de servidor, use porta 8100+ e mate ao fim); nunca 'git add -A' ou '-u' (add arquivo por arquivo); não versionar datasets/DICOM/dados (data/ está no .gitignore); não mexer em .env/segredos; PTB-XL folds 9-10 e LUDB 161-200 são TESTE: proibido usar para ajustar (só dev: PTB-XL folds 1-8, LUDB 1-160). Não imprima chaves de API.
- 1 commit por tarefa, mensagem conventional (feat/fix/test/docs/bench), terminando com a linha:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
- Ao final, escreva docs/benchmarks/trilha_r2_<TRILHA>_log.md (comandos exatos, números antes→depois, commits) e commite-o.
- Resposta final para mim: curta, com lista de commits (hash + assunto), métricas antes→depois, comandos de validação usados, e o que NÃO foi feito. Não invente números: só reporte o que você rodou.

Fatos (confira): ruído alto por derivação só gera aviso (backend/app/ecg/analysis/__init__.py ~163). A IA bloqueia a resposta (backend/app/api/analysis.py ~94-101, ~156-163). frontend ReportPanel.tsx ~58 mostra a confiança fixa das regras como "%"; "baixa confiabilidade" aparece como parágrafo comum (RXViewer.tsx ~110-111).
TAREFAS (1 commit cada):
T1 feat(ecg): abstenção ST/Q em derivação ruidosa: quando a derivação tem ruído alto (critério já existente), não emitir achados de ST (STE/STD) nem Q patológica baseados nela; registrar na qualidade "ST/Q não avaliados em <derivs> (ruído)". Se a abstenção remover o suporte de um achado contíguo, o achado cai. Teste sintético. Bench: PTB-XL dev (--source ptbxl --split dev, tags UX0 antes / UX1 depois): STD/STE sens/espec e FP de MI não podem piorar a sensibilidade mais de 2 pontos; reporte.
T2 feat(rx): gate fora de escopo. Use o autoencoder do TorchXRayVision (xrv.autoencoders, pesos já cacheados se houver; se exigir download > 200 MB registre e use só a sanidade) para erro de reconstrução + sanidade da área/par pulmonar: imagem que não é RX de tórax adulto frontal/perfil (abdome, extremidade, foto, ECG, imagem em branco) => sem achados torácicos, aviso "fora de escopo". Limiar calibrado em: IU dev/JSRT (in-scope) contra abdome (5 DICOM em ~/Downloads/dicom-exemplos/abdome, só local), PNGs de ECG/fotos dos benches e imagens sintéticas. Meta: 100% dos fora de escopo com aviso/abstenção e <= 2% de falso fora-de-escopo em JSRT+amostra IU dev (reporte N).
T3 feat(api+ui): regras primeiro, IA depois. Endpoint de análise devolve regras/medidas imediatamente; texto IA em chamada separada (ex. POST .../ai ou GET com polling) e a UI mostra "gerando texto da IA..." sem bloquear o laudo das regras. Mantenha compatibilidade dos testes existentes (ajuste testes se o contrato mudar).
T4 feat(ui): confiança medida. Troque a confiança fixa das regras exibida como "%" pelo PPV medido no bench por código (arquivo versionado gerado pelo bench, ex. backend/app/knowledge/rule_ppv.json com {codigo: {ppv, ic_inf, ic_sup, n, fonte:'PTB-XL dev'}}; script que o gera a partir do cache do bench dev). Código sem medida => "não medido". UI: "VPP 0,80 [0,74–0,85] (PTB-XL dev, N=...)".
T5 feat(ui): alerta de baixa confiabilidade (RX e ECG) como componente de alerta visível (cor/ícone, role="alert"), não parágrafo.
T6 feat(ui+api): botão concordo/discordo por achado; grava feedback localmente.
T7 feat(api): log JSONL local sem PHI (ex. MEDLENS_DATA/logs/usage.jsonl): hash do commit, versão, latência por etapa, flags de qualidade, códigos emitidos, provedor IA, feedback concordo/discordo; NUNCA nome, ID, data de nascimento, pixels, texto livre do laudo ou UIDs DICOM (use hash salgado aleatório por instalação se precisar correlacionar). Teste que verifica ausência de campos PHI. Conjunto de regressão: teste pytest rápido que roda ~10 casos sintéticos/fixtures e compara códigos com snapshot versionado.
Frontend: rode npm run build (ou o script existente) para verificar. Não sirva na 8000. Suíte completa sem falhas novas.
```


## SPEC6

```text
Você é executor SONNET da trilha r2-e5 (Ação 6: onda P global, BAV1, BAV3) do MedLens. Worktree: /Users/macbook/medlens-wt/r2-e5 (branch wt/r2-e5). TRILHA=e5.

CONTEXTO COMUM (MedLens, ferramenta de apoio a laudo ECG/RX; NÃO é dispositivo certificado):
- Repositório principal: /Users/macbook/medlens (branch claude/ecg-rx-ai-reader-nd20rs). Você trabalha SÓ no seu worktree (indicado abaixo); não toque no repo principal nem em outros worktrees.
- Python: use /Users/macbook/medlens/backend/.venv/bin/python (venv do servidor: PROIBIDO pip install nele). Rode tudo a partir de <worktree>/backend com PYTHONPATH=. e exporte:
  MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets  MEDLENS_BENCH=<worktree>/data/bench
- Testes: cd <worktree>/backend && PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -p no:cacheprovider
- Bench (exemplos): python -m bench.ecg_bench --source ludb|ptbxl|qtdb [--split dev] --tag <TAG> --workers 3 ; python -m bench.rx_bench --source masks|dicom-exemplos|iu ... (leia --help).
- DICOM reais de exemplo: ~/Downloads/dicom-exemplos/{torax,abdome} (dados de paciente anonimizados: NUNCA versionar, nunca enviar a serviço externo).
- 
- REGRA DO USUÁRIO: modelos de IA de linguagem/embeddings/OCR NUNCA locais (sem Ollama, easyocr, tesseract etc.); se precisar de LLM, OpenRouter em nuvem dentro do orçamento. Ferramentas determinísticas locais ok. Os modelos de visão do leitor RX (TorchXRayVision/PSPNet) seguem como estão.
- REGRAS DURAS: não fazer git push; não reiniciar/usar a porta 8000 (se precisar de servidor, use porta 8100+ e mate ao fim); nunca 'git add -A' ou '-u' (add arquivo por arquivo); não versionar datasets/DICOM/dados (data/ está no .gitignore); não mexer em .env/segredos; PTB-XL folds 9-10 e LUDB 161-200 são TESTE: proibido usar para ajustar (só dev: PTB-XL folds 1-8, LUDB 1-160). Não imprima chaves de API.
- 1 commit por tarefa, mensagem conventional (feat/fix/test/docs/bench), terminando com a linha:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
- Ao final, escreva docs/benchmarks/trilha_r2_<TRILHA>_log.md (comandos exatos, números antes→depois, commits) e commite-o.
- Resposta final para mim: curta, com lista de commits (hash + assunto), métricas antes→depois, comandos de validação usados, e o que NÃO foi feito. Não invente números: só reporte o que você rodou.

Referência de avaliação: docs/benchmarks/r2_base.md (dev PTB-XL ampliado, IC95%, medidas vs 12SL do PTB-XL+, subgrupos; comando de reprodução no topo). Rode o MESMO comando com tag <TRILHA>0 (código antes) e <TRILHA>1 (depois) e compare com IC. Ajuste só no dev (PTB-XL folds 1-8 / LUDB 1-160). Não rode o teste externo code_test nem PTB-XL folds 9-10.
Regra de regressão: qualquer métrica-chave do r2_base.md que piore além do IC (ou > 2 pontos em sensibilidade de achado crítico) deve ser corrigida ou a mudança revertida; reporte a tabela completa das métricas-chave antes/depois.
Leia docs/benchmarks/trilha_E5_log.md (rodada 1).
Fatos (confira): onset global de P = mínimo entre derivações (backend/app/ecg/analysis/delineate.py ~515) => viés de PR +~30 ms; regra de BAV1 compensa com AND triplo (backend/app/ecg/analysis/rules.py ~297, AV1_PEAK_MS ~158). BAV3: série de P de 1 derivação (analysis/__init__.py ~216-225), resíduo dá 30-60 picos/10 s; critérios em backend/app/ecg/analysis/rhythm.py ~203-207.
TAREFAS (1 commit cada):
T1 fix(ecg): onset global de P pela mediana ou 2º mais precoce entre derivações (como E2 fez no QRS), escolha pela calibração em LUDB dev (P onset vs anotação) e viés de PR vs 12SL do PTB-XL+ no dev. Meta: |viés PR| <= 8 ms. Depois simplifique a regra de BAV1 (PR > 200 ms com consistência por batimento) e calibre no dev. Meta: BAV1 sens >= 55% com espec >= 95% (IC reportado).
T2 feat(ecg): série atrial multiderivação: resíduo atrial (QRS-T cancelado) de D2 + V1 + aVF combinado, frequência atrial por autocorrelação, dissociação AV por teste de fase P-R (PR não constante e P marcha independente). Regra extra: FA com RR regular e lento (< 60 bpm, CV RR baixo) => "BAV total (sugestivo)". Meta: BAV3 sens >= 40% com IC (N pequeno: reporte N), sem FP novo relevante (espec >= 99,5%). Testes sintéticos (BAV3 com P a 75 e QRS a 40; sinusal normal; FA regularizada).
Mantenha BAV3 sempre rotulado '(sugestivo)'.
```


## SPEC7

```text
Você é executor SONNET da trilha r2-e1 (Ação 7: ST/STE/STD) do MedLens. Worktree: /Users/macbook/medlens-wt/r2-e1 (branch wt/r2-e1). TRILHA=e1.

CONTEXTO COMUM (MedLens, ferramenta de apoio a laudo ECG/RX; NÃO é dispositivo certificado):
- Repositório principal: /Users/macbook/medlens (branch claude/ecg-rx-ai-reader-nd20rs). Você trabalha SÓ no seu worktree (indicado abaixo); não toque no repo principal nem em outros worktrees.
- Python: use /Users/macbook/medlens/backend/.venv/bin/python (venv do servidor: PROIBIDO pip install nele). Rode tudo a partir de <worktree>/backend com PYTHONPATH=. e exporte:
  MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets  MEDLENS_BENCH=<worktree>/data/bench
- Testes: cd <worktree>/backend && PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -p no:cacheprovider
- Bench (exemplos): python -m bench.ecg_bench --source ludb|ptbxl|qtdb [--split dev] --tag <TAG> --workers 3 ; python -m bench.rx_bench --source masks|dicom-exemplos|iu ... (leia --help).
- DICOM reais de exemplo: ~/Downloads/dicom-exemplos/{torax,abdome} (dados de paciente anonimizados: NUNCA versionar, nunca enviar a serviço externo).
- 
- REGRA DO USUÁRIO: modelos de IA de linguagem/embeddings/OCR NUNCA locais (sem Ollama, easyocr, tesseract etc.); se precisar de LLM, OpenRouter em nuvem dentro do orçamento. Ferramentas determinísticas locais ok. Os modelos de visão do leitor RX (TorchXRayVision/PSPNet) seguem como estão.
- REGRAS DURAS: não fazer git push; não reiniciar/usar a porta 8000 (se precisar de servidor, use porta 8100+ e mate ao fim); nunca 'git add -A' ou '-u' (add arquivo por arquivo); não versionar datasets/DICOM/dados (data/ está no .gitignore); não mexer em .env/segredos; PTB-XL folds 9-10 e LUDB 161-200 são TESTE: proibido usar para ajustar (só dev: PTB-XL folds 1-8, LUDB 1-160). Não imprima chaves de API.
- 1 commit por tarefa, mensagem conventional (feat/fix/test/docs/bench), terminando com a linha:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
- Ao final, escreva docs/benchmarks/trilha_r2_<TRILHA>_log.md (comandos exatos, números antes→depois, commits) e commite-o.
- Resposta final para mim: curta, com lista de commits (hash + assunto), métricas antes→depois, comandos de validação usados, e o que NÃO foi feito. Não invente números: só reporte o que você rodou.

Referência de avaliação: docs/benchmarks/r2_base.md (dev PTB-XL ampliado, IC95%, medidas vs 12SL do PTB-XL+, subgrupos; comando de reprodução no topo). Rode o MESMO comando com tag <TRILHA>0 (código antes) e <TRILHA>1 (depois) e compare com IC. Ajuste só no dev (PTB-XL folds 1-8 / LUDB 1-160). Não rode o teste externo code_test nem PTB-XL folds 9-10.
Regra de regressão: qualquer métrica-chave do r2_base.md que piore além do IC (ou > 2 pontos em sensibilidade de achado crítico) deve ser corrigida ou a mudança revertida; reporte a tabela completa das métricas-chave antes/depois.
Leia docs/benchmarks/trilha_B_log.md e ecg_rules_log.md (rodada 1).
Decisões clínicas FIXAS: manter o limiar de STE UDMI-4 atual (inclusive mulher V2-V3 1,5 mm). STD 0,5–1 mm só pode virar "limítrofe" se o bench dev não piorar; senão não faça.
Fatos (confira): STE dispara com amplitude de J em 1 derivação (backend/app/ecg/analysis/rules.py ~493), sem morfologia, recíproca ou razão ST/S; com HVE só anexa texto (~510-511). J é lido em janela ±4 ms no offset da derivação (backend/app/ecg/analysis/measure.py ~96-104); offset precoce cai dentro do S/R'.
TAREFAS (1 commit cada):
T1 fix(ecg): medida ST-J validada contra o 12SL (PTB-XL+) ANTES de mexer em regra: J no offset global consolidado (não o da derivação) ou offset da derivação + correção, ST por batimento com consistência (mediana, MAD), J60 (J+60 ms) também medido. Meta: MAE ST-J <= 30 µV vs 12SL no dev (reporte por derivação e IC).
T2 fix(ecg): regra STE: exige J e J60 elevados em >= 2 derivações contíguas; rebaixar para "limítrofe/inespecífico" se QRS >= 120 ms ou HVE com ST/S < 25%; depressão recíproca aumenta a confiança. Gold de STE = STE_acute (infarction_stadium1) do r2_base. Meta: STE sens >= 50% em IAM agudo (STE_acute) com FP < 40 no dev (reporte N e IC).
T3 fix(ecg): STD: meta espec >= 85% com sens >= 55%; teste do "limítrofe" 0,5–1 mm conforme decisão acima.
Testes sintéticos (STE verdadeiro contíguo; BRE com ST discordante não vira IAM; HVE strain; J ruidoso).
Atenção: ST-T secundário a HVE com strain e a BRE/BRD não é isquemia (ver caso-ouro: CASO-OURO caso1 (gabarito de cardiologista, confirmado por eco): ritmo sinusal normocárdico; R > 20 mm em D1 e aVL; R > 30 mm em V3-V6; infra de ST pequeno com T invertida assimétrica nessas derivações (strain de VE); Romhilt-Estes 6 pontos (voltagem 3 + strain 3); Cornell do gabarito = 58 mm, que corresponde a R aVL ~21 + R V3 ~37 mm (soma de R, não é o Cornell clássico; o Cornell clássico R aVL + S V3 = ~21 + ~6 = ~27 mm, abaixo do limite de 28 mm em homem; nota R3-C1: remedido na imagem, S V3 ~6 mm); Sokolow-Lyon = 60 mm (limite 35); Peguero-Lo Presti NÃO preenchido (R cresce de V3 com S baixas nas precordiais: sugere hipertrofia focal); SEM desvio de eixo para a esquerda; P ~120 ms em D2 (aumento de AE). Eco: CMH septal assimétrica obstrutiva (septo 20 mm), FE preservada, AE 47 mm. Cabeçalho impresso (GE 12SL 241): PR 148 ms, QRS 112 ms, QT/QTcB 438/482 ms, eixos P/QRS/T 49/20/171, sexo masculino. LAUDO CORRETO: "Sobrecarga de câmaras esquerdas. Padrão eletrocardiográfico sugestivo de miocardiopatia hipertrófica (CMH)." Saída ERRADA atual do app: PR 88 ms, QRS 270 ms, "pré-excitação/onda delta", ST -4,9 mm em aVF, "infra de ST inferior/anterolateral extenso". Referências (cite só como referência, não copie texto): Samesima et al., Diretriz SBC de Laudos Eletrocardiográficos 2022, Arq Bras Cardiol 119(4):638-680; Peguero et al., JACC 2017;69(13):1694-1703; Makavos et al., Heart Fail Rev 2019;24(4):439-459.)
```


## SPEC8

```text
Você é executor SONNET da trilha r2-e34 (Ação 8: E3 FA/flutter + E4 NORM) do MedLens. Worktree: /Users/macbook/medlens-wt/r2-e34 (branch wt/r2-e34). TRILHA=e34.

CONTEXTO COMUM (MedLens, ferramenta de apoio a laudo ECG/RX; NÃO é dispositivo certificado):
- Repositório principal: /Users/macbook/medlens (branch claude/ecg-rx-ai-reader-nd20rs). Você trabalha SÓ no seu worktree (indicado abaixo); não toque no repo principal nem em outros worktrees.
- Python: use /Users/macbook/medlens/backend/.venv/bin/python (venv do servidor: PROIBIDO pip install nele). Rode tudo a partir de <worktree>/backend com PYTHONPATH=. e exporte:
  MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets  MEDLENS_BENCH=<worktree>/data/bench
- Testes: cd <worktree>/backend && PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -p no:cacheprovider
- Bench (exemplos): python -m bench.ecg_bench --source ludb|ptbxl|qtdb [--split dev] --tag <TAG> --workers 3 ; python -m bench.rx_bench --source masks|dicom-exemplos|iu ... (leia --help).
- DICOM reais de exemplo: ~/Downloads/dicom-exemplos/{torax,abdome} (dados de paciente anonimizados: NUNCA versionar, nunca enviar a serviço externo).
- 
- REGRA DO USUÁRIO: modelos de IA de linguagem/embeddings/OCR NUNCA locais (sem Ollama, easyocr, tesseract etc.); se precisar de LLM, OpenRouter em nuvem dentro do orçamento. Ferramentas determinísticas locais ok. Os modelos de visão do leitor RX (TorchXRayVision/PSPNet) seguem como estão.
- REGRAS DURAS: não fazer git push; não reiniciar/usar a porta 8000 (se precisar de servidor, use porta 8100+ e mate ao fim); nunca 'git add -A' ou '-u' (add arquivo por arquivo); não versionar datasets/DICOM/dados (data/ está no .gitignore); não mexer em .env/segredos; PTB-XL folds 9-10 e LUDB 161-200 são TESTE: proibido usar para ajustar (só dev: PTB-XL folds 1-8, LUDB 1-160). Não imprima chaves de API.
- 1 commit por tarefa, mensagem conventional (feat/fix/test/docs/bench), terminando com a linha:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
- Ao final, escreva docs/benchmarks/trilha_r2_<TRILHA>_log.md (comandos exatos, números antes→depois, commits) e commite-o.
- Resposta final para mim: curta, com lista de commits (hash + assunto), métricas antes→depois, comandos de validação usados, e o que NÃO foi feito. Não invente números: só reporte o que você rodou.

Referência de avaliação: docs/benchmarks/r2_base.md (dev PTB-XL ampliado, IC95%, medidas vs 12SL do PTB-XL+, subgrupos; comando de reprodução no topo). Rode o MESMO comando com tag <TRILHA>0 (código antes) e <TRILHA>1 (depois) e compare com IC. Ajuste só no dev (PTB-XL folds 1-8 / LUDB 1-160). Não rode o teste externo code_test nem PTB-XL folds 9-10.
Regra de regressão: qualquer métrica-chave do r2_base.md que piore além do IC (ou > 2 pontos em sensibilidade de achado crítico) deve ser corrigida ou a mudança revertida; reporte a tabela completa das métricas-chave antes/depois.
Leia docs/benchmarks/trilha_C_log.md e trilha_D_log.md (rodada 1).
Fatos (confira): FP de FA restantes ~6 flutter, ~10 bigeminismo/PAC, 4 PACE sem espícula; teste de FA vem antes do de flutter (backend/app/ecg/analysis/rules.py ~182-186). Bloqueios de NORM: T invertida (~558), HVE por voltagem (~431), QTc sem corte por sexo (~481).
TAREFAS (1 commit cada):
T1 fix(ecg): testar flutter antes de FA (ondas F em D2/D3/aVF/V1, frequência atrial 240-340), alternância de RR (autocorrelação lag-2 / bigeminismo) exclui FA, V1 para atividade atrial. Meta: PPV FA >= 0,85 com sens >= 0,83 (IC).
T2 fix(ecg): NORM por idade/sexo: Sokolow-Lyon em < 40 anos não basta para HVE (vira limítrofe); T invertida isolada em V1-V3 de mulher jovem (< 40) = variante/limítrofe; QTc com corte por sexo (homem > 450, mulher > 460 ms; QT longo grave > 500 ambos). Meta: NORM→normal >= 80% com IC inferior >= 76%, sem perder mais de 2 pontos em "non-NORM com >=1 achado" e LVH/LQT sens.
Testes sintéticos para cada regra.
```


## SPECE6

```text
Você é executor SONNET da trilha r2-e6 (Ação 9 parte E6: classificador em MODO SOMBRA, só bench offline) do MedLens. Worktree: /Users/macbook/medlens-wt/r2-e6 (branch wt/r2-e6). TRILHA=e6.

CONTEXTO COMUM (MedLens, ferramenta de apoio a laudo ECG/RX; NÃO é dispositivo certificado):
- Repositório principal: /Users/macbook/medlens (branch claude/ecg-rx-ai-reader-nd20rs). Você trabalha SÓ no seu worktree (indicado abaixo); não toque no repo principal nem em outros worktrees.
- Python: use /Users/macbook/medlens/backend/.venv/bin/python (venv do servidor: PROIBIDO pip install nele). Rode tudo a partir de <worktree>/backend com PYTHONPATH=. e exporte:
  MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets  MEDLENS_BENCH=<worktree>/data/bench
- Testes: cd <worktree>/backend && PYTHONPATH=. /Users/macbook/medlens/backend/.venv/bin/python -m pytest -q -p no:cacheprovider
- Bench (exemplos): python -m bench.ecg_bench --source ludb|ptbxl|qtdb [--split dev] --tag <TAG> --workers 3 ; python -m bench.rx_bench --source masks|dicom-exemplos|iu ... (leia --help).
- DICOM reais de exemplo: ~/Downloads/dicom-exemplos/{torax,abdome} (dados de paciente anonimizados: NUNCA versionar, nunca enviar a serviço externo).
- 
- REGRA DO USUÁRIO: modelos de IA de linguagem/embeddings/OCR NUNCA locais (sem Ollama, easyocr, tesseract etc.); se precisar de LLM, OpenRouter em nuvem dentro do orçamento. Ferramentas determinísticas locais ok. Os modelos de visão do leitor RX (TorchXRayVision/PSPNet) seguem como estão.
- REGRAS DURAS: não fazer git push; não reiniciar/usar a porta 8000 (se precisar de servidor, use porta 8100+ e mate ao fim); nunca 'git add -A' ou '-u' (add arquivo por arquivo); não versionar datasets/DICOM/dados (data/ está no .gitignore); não mexer em .env/segredos; PTB-XL folds 9-10 e LUDB 161-200 são TESTE: proibido usar para ajustar (só dev: PTB-XL folds 1-8, LUDB 1-160). Não imprima chaves de API.
- 1 commit por tarefa, mensagem conventional (feat/fix/test/docs/bench), terminando com a linha:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
- Ao final, escreva docs/benchmarks/trilha_r2_<TRILHA>_log.md (comandos exatos, números antes→depois, commits) e commite-o.
- Resposta final para mim: curta, com lista de commits (hash + assunto), métricas antes→depois, comandos de validação usados, e o que NÃO foi feito. Não invente números: só reporte o que você rodou.

Referência de avaliação: docs/benchmarks/r2_base.md (dev PTB-XL ampliado, IC95%, medidas vs 12SL do PTB-XL+, subgrupos; comando de reprodução no topo). Rode o MESMO comando com tag <TRILHA>0 (código antes) e <TRILHA>1 (depois) e compare com IC. Ajuste só no dev (PTB-XL folds 1-8 / LUDB 1-160). Não rode o teste externo code_test nem PTB-XL folds 9-10.
Regra de regressão: qualquer métrica-chave do r2_base.md que piore além do IC (ou > 2 pontos em sensibilidade de achado crítico) deve ser corrigida ou a mudança revertida; reporte a tabela completa das métricas-chave antes/depois.
REGRA ABSOLUTA: nada deste classificador vai para app/, API ou UI (decisão regulatória pendente, RDC 657/2022). Tudo em bench/ e num venv separado. Leia docs/research/e6_classificador_spec.md.
T0: Modelo de Ribeiro et al. 2020 (CODE; rótulos 1dAVb, RBBB, LBBB, SB, AF, ST; treinado no CODE, sem vazamento com PTB-XL): baixe os pesos públicos (Zenodo; confira licença e registre texto exato) para /Users/macbook/medlens/data/models/ribeiro/ (fora do git). Venv separado /Users/macbook/medlens-venvs/e6 (tensorflow/keras ou port PyTorch reconhecido; NÃO toque em backend/.venv).
T1 bench: script bench/e6_shadow.py que reamostra PTB-XL dev ampliado para 400 Hz / 4096 amostras (zero-pad), unidade conforme o modelo, roda no venv e2 por subprocesso, e reporta por rótulo AUC, sens a 90% espec e no limiar do artigo, com IC, lado a lado com as regras do MedLens (mesmos registros) e concordância (kappa). Para IAM o modelo não tem rótulo: registre "IAM não coberto pelo modelo" (meta do plano IAM sens >= 60% a 90% espec fica não aplicável) a menos que exista modelo público SEM treino em PTB-XL que cubra IAM; não use modelos treinados em PTB-XL (vazamento).
T2 docs: docs/benchmarks/e6_shadow.md com resultados e a frase "modo sombra: não exibido ao usuário".
NÃO rode code_test (é o teste externo final das regras).
```
