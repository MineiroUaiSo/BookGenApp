---
name: rx-systematic-reading
description: Método de leitura sistemática de radiografia do MedLens (tórax PA/AP e perfil, abdome, ossos) — identificar e legendar cada estrutura, medir, descrever e só então fazer análise crítica com diferenciais citados. Use ao escrever ou revisar prompts, regras (knowledge/rx_signs.yaml), código em backend/app/rx e recon3d, ou laudos de RX gerados pelo app.
---

# Leitura sistemática de RX (MedLens)

Apoio/ensino; sempre com aviso de revisão médica. Terminologia: Glossário Fleischner 2024; IDs RadLex quando possível.

## Regra de ouro: segmentar/medir → descrever → interpretar
1. Estruturas e medidas vêm de `RXImageAnalysis` (máscaras, ICT, desvio traqueal, seios, cúpulas). Origem `model` > `heuristic`; diga qual.
2. Descrição estrutura a estrutura, sem diagnóstico.
3. Interpretação só com `knowledge/rx_signs.yaml` + ids de `knowledge/references.yaml`. Discordância visual × medida → `disagreements_with_measurements`.

## Tórax PA/AP — ordem
1. Identificação da incidência (PA/AP/leito), qualidade: rotação (extremidades mediais das clavículas × processos espinhosos), inspiração (6 arcos anteriores / 9–10 posteriores acima da cúpula D), penetração (vértebras atrás do coração).
2. Partes moles e ossos: clavículas, escápulas, arcos costais (contar, fraturas, lesões), coluna, úmeros, mamas.
3. Vias aéreas: traqueia (centrada?), carina, brônquios principais.
4. Mediastino: largura, contornos (botão aórtico, janela aortopulmonar, linhas paratraqueal/paraesofágica).
5. Coração: ICT (<0,5 no PA; AP magnifica), contornos (AD, VE, apêndice atrial E, tronco pulmonar).
6. Hilos: posição (E mais alto), tamanho, densidade.
7. Pulmões por zonas (superior/média/inferior, comparando lados): opacidades, padrão (consolidação, intersticial, nódulo), broncograma aéreo, sinal da silhueta, hiperinsuflação, Kerley.
8. Pleura: seios costofrênicos, menisco, linha pleural (pneumotórax), espessamentos.
9. Diafragma: altura e contorno das cúpulas, ar livre subdiafragmático.
10. Abdome superior visível, dispositivos (tubos, cateteres, marcapasso — posição).
11. "Áreas de revisão": ápices, retrocardíaco, atrás das cúpulas, hilos, ossos.

## Perfil
Espaço claro retroesternal e retrocardíaco, sinal da coluna (vértebras devem escurecer de cima para baixo), cúpulas (D vs E pelo coração/bolha gástrica), cissuras, seios posteriores, traqueia e ângulo da carina.

## Abdome
Padrão gasoso (delgado central, válvulas coniventes; cólon periférico, haustrações), regra 3-6-9 cm, níveis, ar livre (Rigler, sob cúpulas), calcificações, sombras de psoas/órgãos, ossos (coluna, pelve).

## 3D (PA + Perfil)
Reconstrução aproximada (casco visual + prior anatômico) — nunca chamar de tomografia; estruturas vistas em uma só incidência são estimativas.

## Laudo
pt-BR; cada achado com evidência, referência e confiança; diferenciais com a favor/contra; limitações (incidência única, rotação, ausência de exame prévio). Considere variantes normais (Keats) antes de patologia.

## Referências-núcleo (ver docs/research/rx_bibliografia.md)
Fleischner 2024; Felson 5ª; Diagnostic Imaging: Chest 3ª; Webb & Higgins 4ª; Keats 9ª; RadLex.
