# Coleta de dados de validação

Dados ficam em `data/datasets/<fonte>/` (fora do git). Cada fonte tem `manifest.jsonl` (formato `Record` em `backend/medlens_data/__init__.py`) e um script em `backend/medlens_data/collectors/<fonte>.py`.

## Regras
1. Só fontes com licença/termos que permitem uso não comercial de pesquisa/ensino; licença e atribuição gravadas por item.
2. Respeitar robots.txt e termos; ≥1 s entre requisições por host; cache; identificação no User-Agent.
3. **Não raspar Google Imagens** (termos proíbem; licença desconhecida) nem Radiopaedia (termos proíbem coleta automatizada).
4. Legendas/laudos originais guardados *verbatim* apenas para avaliação; nada disso entra no repositório nem nos prompts da IA como texto copiado.
5. Peneira (`score_caption`, `dedupe`) grava notas em `quality`; o filtro é aplicado na hora de usar, não apagando dados.

## Fontes
| Fonte | Modalidade | Licença | O que fornece |
|---|---|---|---|
| LITFL ECG Library | ECG (imagem) | CC BY-NC-SA 4.0 | ECGs com interpretação de especialista |
| ECG Library (ecglibrary.com) | ECG (imagem) | verificar termos | Casos clássicos (site instável) |
| LUDB (PhysioNet) | ECG (sinal) | ODC-By | Onsets/offsets de P, QRS, T anotados por cardiologistas (padrão-ouro de delineação) |
| PTB-XL (PhysioNet) | ECG (sinal) | CC BY 4.0 | 21.799 ECGs com códigos SCP diagnósticos |
| ECG-Image-Database / Challenge 2024 (PhysioNet) | ECG (foto/scan) | ver página | Fotos/scans reais com sinal de referência |
| Wikimedia Commons | ECG e RX | CC/PD por arquivo | Imagens com descrição |
| Open-i / IU Chest X-ray (NLM) | RX PA + Perfil | CC BY-NC-ND 4.0 | ~7.4 mil imagens com laudo (pares PA+Perfil) |
| Europe PMC (artigos open access) | RX | CC BY / CC0 por artigo | Figuras com legenda dos autores ("peneira") |
| MedPix (NLM) | RX | ver termos | Casos didáticos com descrição |
| Hugging Face (espelhos JSRT/Montgomery/Shenzhen etc.) | RX | por dataset | Máscaras de pulmão/coração para Dice |

## Estado do download (trilha A, 2026-11-24)
Diretório compartilhado: `/Users/macbook/medlens/data/datasets` (`MEDLENS_DATASETS`). Não há `wget` nesta máquina: os collectors PhysioNet agora baixam em Python (lista de `SHA256SUMS.txt`, paralelo, retomável).

| Fonte | Registros (manifest) | Tamanho | Licença | Comando |
|---|---|---|---|---|
| LUDB 1.0.1 | 200 | 36 MB | ODC-By 1.0 | `physionet_ecg ludb-download`, `ludb-build` |
| PTB-XL 1.0.3 (seleção estratificada) | 3000 de 21.799 (500 Hz) | 381 MB | CC BY 4.0 | `ptbxl-select`, `ptbxl-download`, `ptbxl-build` |
| QTDB 1.0.0 | 105 (anot. q1c/q2c/pu, manifest com `annotations_json`) | 101 MB | ODC-By 1.0 | `qtdb-download`, `qtdb-build` |
| SCR/JSRT (Zenodo 7056076) | 247 (imagens 256 px + contornos) | 21 MB | CC BY 4.0 | `rx_masks fetch_jsrt`, `rx_masks jsrt` |
| IU X-Ray (espelho HF abdulhaseeb1308/IU-Xray) | 5910 imagens (~3,9 mil estudos; sem MeSH, rótulos por heurística de texto com negação) | 2,1 GB | CC BY-NC-ND 4.0 | `iu_xray --hf abdulhaseeb1308/IU-Xray` |
| PAX-Ray++ (Zenodo 23627483), só partição test oficial | 800 (400 volumes frontal+lateral, de 1 partição test) | 1,8 GB | CC BY-NC 4.0 | `rx_masks fetch_paxray`, `rx_masks paxray` |

### Pulados / pendentes
- **IU X-Ray direto do Open-i**: não baixado. `https://openi.nlm.nih.gov/robots.txt` = `User-agent: *` / `Disallow: /` (só `/detailedresult` e `/sitemaps/` permitidos); o collector respeita robots (AssertionError em `NLMCXR_reports.tgz`) e um GET direto ao .tgz deu `ConnectionResetError [Errno 54]`. Contornado pelo espelho HF acima (view PA/LATERAL por ordem de arquivo; sem MeSH; só dev).
- **Montgomery e Shenzhen (NLM, imagens)**: mesmos arquivos em `openi.nlm.nih.gov` (robots proíbe). Só as máscaras auxiliares do Zenodo (Brioso 8108809, Stirenko 14059288) são acessíveis, mas sem as imagens não servem. Pendente.
- **VinDr-CXR**: exige credenciamento PhysioNet (DUA assinado). **PENDÊNCIA DO USUÁRIO**: criar credencial, assinar o acordo e baixar; não foi tentado.
- **Chapman-Shaoxing / CPSC2018 (PhysioNet challenge-2020, aberto)**: TODO. Pacote challenge-2020 provavelmente > 5 GB (não verificado), fora da regra de 5 GB; não baixado.

### Splits congelados
`backend/bench/splits.json` + `backend/bench/splits.py`: LUDB 1-160 dev / 161-200 teste; PTB-XL strat_fold 1-8 dev / 9-10 teste (queimado); QTDB teste externo; IU somente dev (vazamento com TorchXRayVision); JSRT/Montgomery/Shenzhen por hash do paciente (70% dev); PAX-Ray++ só split test oficial. Guarda de CI (cobre também `bench/tuning/rx_thresholds.json` da trilha E): `tests/test_no_test_leak.py` (ids de teste proibidos em `backend/bench/tuning/*.json`).
