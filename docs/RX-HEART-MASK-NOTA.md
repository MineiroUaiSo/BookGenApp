# Nota: máscara do coração do modelo curta na borda esquerda (RX CC0 PA)

Lote H1 (investigação, sem alterar modelo nem limiar). Imagem: `rx_cc0_pa.png` (CC0, 2412 x 1956 px).

## Observação
O coração do PSPNet (ChestX-Det, `seg_model.py`) termina em x ≈ 1687 px; a borda visual estimada está em ≈ 1770–1800 px
(~85–115 px, ~4% da largura da imagem, a mais). ICT medido 0,373 (heart 763 px / campos pulmonares 2045 px) contra ≈ 0,42 estimado.

## Margem sistemática no código?
- Limiar fixo `prob > 0.5` em `masks_from_probs` (`seg_model.py`), mais `_largest` (maior componente) e `resize(order=0)` de 512x512 para a
  resolução de trabalho. Entrada redimensionada para 512x512 sem preservar proporção (1 px do modelo = 4,7 px da imagem).
- `measure_frontal` usa a bbox da máscara: largura do coração = x2 - x1 + 1; largura torácica = bbox da união dos pulmões. Sem margem adicional.

## Teste de sensibilidade ao limiar (probabilidade do coração, mesma imagem; larguras em px da imagem original)
| limiar | x1 | x2 | largura coração | largura pulmões | ICT |
|---|---|---|---|---|---|
| 0,50 (atual) | 928 | 1687 | 763 | 2045 | 0,373 |
| 0,40 | 928 | 1691 | 768 | 2049 | 0,375 |
| 0,30 | 923 | 1696 | 777 | 2059 | 0,378 |
| 0,20 | 914 | 1701 | 791 | 2068 | 0,383 |
| 0,10 | 900 | 1757 | 862 | 2082 | 0,414 |
| 0,05 | 857 | 1884 | 1032 | 2101 | 0,491 |

Sem `_largest` no limiar 0,50: x2 continua 1687 (não há fragmento descartado). Perfil de probabilidade na linha média do coração:
0,51 em x=1639; 0,30 em 1649; 0,10 em 1663; < 0,03 depois de 1677; ≈ 0,00 de 1734 em diante.

## Conclusão
- O limiar de 0,5 NÃO é a causa principal: baixar para 0,3 move a borda só ~9 px (ICT 0,373 -> 0,378). A probabilidade cai
  quase a zero antes da borda real (≈ 0,00 em x ≥ 1734); o modelo é confiante e errado nessa borda, não "quase passando".
- Só um limiar de 0,10 chega perto da borda estimada (x2 1757, ICT 0,414), mas já aumenta a máscara dos dois lados (x1 928 -> 900) e a
  0,05 explode (ICT 0,491, falso aumento). Não é um ajuste seguro com uma única imagem.
- Causas prováveis (hipóteses, não verificadas): deformação por 512x512 sem proporção; ponta do ventrículo esquerdo
  sobreposta à cúpula/estômago; viés do conjunto de treino. Um possível reparo é pós-processamento, não limiar.

## Proposta (não aplicada)
1. Manter limiar 0,5 e a incerteza declarada do ICT (±0,05, "pode estar subestimado"), que já cobre esta diferença (0,373 vs ≈ 0,42).
2. Avaliar em um conjunto pequeno com ICT manual (≥ 20 PA) o viés da borda esquerda; se sistemático, calibrar por regressão em vez
   de mexer no limiar global.
3. Testar entrada com proporção preservada (letterbox 512x512) e comparar bordas.
4. Opcional: limiar adaptativo só para o coração (histerese 0,5 -> 0,1 conectada à máscara) e checar contra o ICT manual.
