# Trilha F — RX segmentação / latência / caso real

Commits: ver `git log` (fix DICOM real f1f348c, R4 40d8625, R6 678efdb).

## Caso real (TCIA COVID-19-AR, tórax AP portátil)
Causa: no venv do servidor faltavam torch/torchxrayvision (modelos indisponíveis) e o fallback heurístico não achava o par
de pulmões (Otsu junta pulmão com ar/fundo em filme de baixo contraste; pulmões fundidos ao ar lateral). Correção:
`seg_heuristic.find_lung_pair` tenta Otsu e, se falhar, multi-Otsu (limiar mais baixo) com aberturas maiores; fallback de
coração pelo vão inter-pulmonar. Mensagem de erro de decode agora diz "codec DICOM não suportado (instale pylibjpeg)".
JPEG Lossless (RICORD, 5/10 arquivos) exige pylibjpeg (já em requirements-optional.txt).

Comando: `MEDLENS_RX_MODELS=0|1 PYTHONPATH=. python -m bench.rx_bench --source dicom-exemplos --models on|off|both`
Regressão: `tests/test_rx_real_dicom.py` (pytest.skip se ausentes).

## Tabela 10 DICOM (antes -> depois; sem modelos = o caso do usuário)
| arquivo | antes (sem modelos) | depois (sem modelos) | depois (modelo PSPNet) |
|---|---|---|---|
| torax/1,2,3 COVID-19-AR | "segmentação indisponível", 0 medidas | pulmões heurísticos + ICT (baixa confiança) | PSPNet, 14 estruturas, ICT 0.46/0.46/0.52 |
| torax/4,5 RICORD (JPEG Lossless) | n/d (sem decoder neste venv na época) | pulmões heurísticos + ICT | PSPNet, ICT 0.51/0.52 |
| abdome/1..5 | região abdome (heurística) | igual (abdome 1 sem tag de incidência: OTHER) | igual |
Todos os 10: polaridade MONOCHROME1/2 tratada corretamente, região correta (tórax x5, abdome x5), incidência AP (exceto abdome/1 sem tag).

## R4
`analyze.supported_structures(mode, view)`; bench marca "não suportado" (esterno/costelas com PSPNet, aorta/clavícula em perfil)
em vez de Dice 0. Shenzhen: nomes por lado da imagem ('lung_image_left') agora mapeados para o lado do paciente (invertido).
Dataset Shenzhen/Montgomery/PAX-Ray não estava disponível na hora: não revalidado com dados (testes unitários apenas).

## R6 latência
PSPNet: 1 passada (já compartilhada entre detecção de vista e segmentação). MPS: 0.6 s vs 6.7 s CPU (max |dp| 2e-6, 0 pixels diferentes).
Medido com carga da máquina ~100 (outras trilhas): analyze_image completo 2.5-3.3 s (PSP 0.6 s; resto: DenseNet 0.3 s, PNG/contornos ~1.5 s);
bench jsrt N=15 modelo: mediana 3.3 s, p95 4.7 s (2 workers, inclui warm-up MPS ~7 s por worker). Meta <2 s: PSP ok; resto depende de máquina ociosa.
Dice jsrt (N=15) inalterado: lungs 0.855, heart 0.933.

## Pendências
- Spike R3 (cxas em venv separado): não feito (instalação de pacotes bloqueada; tempo).
- Reexecutar latência com máquina ociosa; reexecutar bench masks completo quando manifests montgomery/shenzhen/paxray existirem.
- "Estruturas não segmentadas" no output da API: só são emitidas as segmentadas (sem mudança necessária).

## Atualização (após merge do main; bench masks --limit 100, workers 2, jsrt + PAX-Ray++ test, 2 trilhas ECG em paralelo)
Comando: `PYTHONPATH=. python -m bench.rx_bench --source masks --limit 100 --workers 2 --models both --out <tmp>` (NÃO regenerou rx.md).
Antes = docs/benchmarks/rx.md publicado (N=120 jsrt; PAX-Ray N=56 PA); depois = código atual (N=100 jsrt; PA N=49).

| métrica | antes | depois |
|---|---|---|
| jsrt pulmões, heurística (Dice) | 0.205 | 0.636 |
| jsrt coração, heurística | 0.153 | 0.444 |
| PAX-Ray PA pulmões, heurística | 0.025 | 0.336 |
| PAX-Ray PA coração, heurística | 0.021 | 0.372 |
| jsrt pulmões/coração, modelo | 0.863 / 0.926 | 0.864 / 0.928 (inalterado) |
| ICT MAE jsrt, heurística | n/d | 0.168 (modelo 0.027) |
| latência modelo p50 / p95 | 6.26 / 7.32 s | 3.44 / 9.17 s (inclui aquecimento MPS por worker, máquina compartilhada) |
| latência heurística p50 / p95 | 0.16 / 0.91 s | 1.20 / 24.9 s  (REGRESSÃO de cauda) |

Montgomery/Shenzhen indisponíveis: correção de lado do Shenzhen só com teste unitário.
Latência: meta <2 s NÃO confirmada (p50 3.4 s com 2 workers + 2 trilhas ECG; PSP isolada = 0.6 s). Heurística ficou mais lenta
porque `find_lung_pair` agora tenta até 9 estratégias nas imagens em que a primeira falha: PENDENTE otimizar (limitar tentativas/reduzir resolução).

## ICT heurístico (commit separado)
`analyze.HEUR_CTR_RANGE=(0.30,0.70)`: ICT heurístico fora da janela some das medidas e vira quality["ICT"]="não confiável...".
Limite: phantoms verídicos chegam a 0.64, então a janela não pega valores inflados 0.56-0.70; nos 5 tóraces de exemplo,
2 de 3 COVID-19-AR deixam de mostrar ICT; RICORD 4/5 e COVID 3 ainda mostram 0.56-0.65 (modelo: 0.46-0.52). Solução melhor =
validar a máscara cardíaca (não só o valor) — pendente.
