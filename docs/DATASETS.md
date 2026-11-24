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
