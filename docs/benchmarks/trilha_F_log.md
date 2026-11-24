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
