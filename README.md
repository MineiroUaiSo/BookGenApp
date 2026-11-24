# MedLens — Leitor de ECG e RX com IA

> Apoio à decisão e ensino. **Não é dispositivo médico certificado.** Todo laudo é rascunho e exige revisão médica.

- **ECG**: DICOM (pasta inteira), HL7 aECG XML, CSV, WFDB e **foto/print de alta resolução** (digitalização automática: perspectiva, grade, calibração, layouts 3x4+1 / 6x2 / 12x1). Identifica P, Q, R, S, R', T, U em cada derivação; mede P, PR, QRS, QT, QTc (4 fórmulas), eixos, ST (J/J+60/J+80), Sokolow, Cornell; ritmo e bloqueios; **animação da condução cardíaca** isolada ou em conjunto.
- **RX**: DICOM (pasta inteira) ou imagem. Segmenta e **legenda cada estrutura** (pulmões, coração, traqueia, clavículas, escápulas, hilos, aorta, mediastino, diafragma, coluna, esterno, alças intestinais…), mede ICT, desvio traqueal, seios costofrênicos etc. e faz **reconstrução 3D aproximada a partir de PA + Perfil**.
- **IA (Claude)**: descrição minuciosa → análise crítica com diferenciais citando a bibliografia (`knowledge/`), destacando discordâncias com as medidas.

## Rodar

```bash
# backend (Python 3.11+)
cd backend
pip install -e '.[dev,ecg,recon,ai]'          # + '.[rx]' para torch/torchxrayvision
export ANTHROPIC_API_KEY=...                   # opcional (sem chave: medidas + regras)
# ou: export OPENROUTER_API_KEY=...  [MEDLENS_OR_MODEL=anthropic/claude-sonnet-5.5]  (fallback via OpenRouter)
# DICOM JPEG Lossless (ex.: MIDRC-RICORD) exige: pip install -e '.[dicom-compressed]'
uvicorn app.main:app --port 8000

# frontend
cd frontend && npm install && npm run build    # o backend serve frontend/dist em http://localhost:8000
# ou, em desenvolvimento: npm run dev  (http://localhost:5173)
```

Testes: `cd backend && pytest` (113) · `cd frontend && npm test -- --run` (27).

Imagens enviadas juntas (ex.: PA + Perfil em PNG) formam um único estudo — necessário para o 3D.

## Documentação
- `docs/PLAN.md` — arquitetura · `docs/CONTRACTS.md` — API
- `docs/BIBLIOGRAFIA.md` — livros e diretrizes-base · `docs/research/` — pesquisa completa
- `knowledge/` — critérios reescritos + referências (revisão clínica pendente)
- `.claude/skills/` — skills para agentes (pydicom, neurokit2, pensamento crítico, leitura ECG/RX)

## Benchmarks
- Resultados: `docs/benchmarks/` (ecg.md, rx.md e logs por trilha `trilha_*_log.md`). Estado e pendências: `RETOMADA.md`.
- Dados (fora do git): `data/datasets/` (LUDB, PTB-XL 3000, QTDB, IU X-ray via espelho HF, JSRT, PAX-Ray++ test). Splits congelados em `backend/bench/splits.json`; `tests/test_no_test_leak.py` falha se id de teste aparecer em `backend/bench/tuning/`.
- Regressão em DICOM real: `tests/test_rx_real_dicom.py` e `python -m bench.rx_bench --source dicom-exemplos` (pasta `MEDLENS_DICOM_EXAMPLES`).

## Limitações conhecidas
- Validação em bases reais em andamento (ver RETOMADA.md); achados críticos (STE, pneumotórax, BAV3) sempre "sugestivo".
- Limiares de `knowledge/*.yaml` escritos de memória pelos agentes — precisam de revisão por especialista.
- Segmentação de perfil, abdome e ossos é heurística; 3D é aproximação (casco visual), não tomografia.
- IA (Claude) testada com cliente simulado; requer chave de API para uso real.
