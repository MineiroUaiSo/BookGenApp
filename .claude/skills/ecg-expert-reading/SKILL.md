---
name: ecg-expert-reading
description: Método de leitura expert de ECG de 12 derivações do MedLens — ordem sistemática, medir antes de interpretar, onda a onda por derivação, condução cardíaca, critérios com citação. Use ao escrever ou revisar prompts, regras (knowledge/ecg_criteria.yaml), código em backend/app/ecg ou laudos de ECG gerados pelo app.
---

# Leitura expert de ECG (MedLens)

Ferramenta de apoio/ensino. Nada aqui é laudo definitivo; toda saída leva o aviso de revisão médica.

## Regra de ouro: medir → descrever → interpretar
1. **Medir** (determinístico, `backend/app/ecg/analysis`): use os números de `ECGAnalysis`
   (batimento mediano por derivação; QRS/QT globais = onset mais precoce → offset mais tardio entre derivações).
2. **Descrever** sem diagnosticar: onda a onda, derivação a derivação.
3. **Interpretar** só com critérios de `knowledge/ecg_criteria.yaml`, citando ids de `knowledge/references.yaml`.
   Se a impressão visual discordar da medida, registre em `disagreements_with_measurements` — nunca "corrija" a medida no texto.

## Ordem de leitura (não pular etapas)
1. Técnica: calibração (10 mm/mV, 25 mm/s), qualidade por derivação, troca de eletrodos (aVR positivo, D1 negativo global), artefato.
2. Ritmo: regularidade RR, P antes de cada QRS, P positiva em D1/D2/aVF e negativa em aVR (sinusal), relação P:QRS.
3. FC (1500/nº de quadradinhos ou RR médio).
4. Onda P: duração (<120 ms), amplitude (<2,5 mm em D2), morfologia (bífida, apiculada), índice de Morris em V1.
5. PR: 120–200 ms; curto + delta → pré-excitação; longo → BAV 1º; PR variável → Wenckebach / dissociação.
6. QRS: duração (<120 ms), morfologia por derivação (qR, rS, rSR', QS), Q patológica (≥40 ms ou ≥25% do R, territórios contíguos), deflexão intrinsecoide, transição precordial, voltagem (baixa / critérios de sobrecarga).
7. Eixos P, QRS, T (plano frontal, hexaxial) e ângulo QRS-T.
8. Ponto J e segmento ST em J, J+60, J+80 por derivação, agrupados por território (inferior, lateral, anterior, septal, posterior por espelho em V1–V3).
9. Onda T: polaridade esperada por derivação, simetria, amplitude (apiculada / achatada / invertida).
10. QT e QTc (Bazett, Fridericia, Framingham, Hodges — relate os quatro; Bazett superestima com FC alta).
11. Onda U.
12. Síntese de condução (abaixo) e comparação entre derivações.

## Condução cardíaca (mapear tempo → estrutura)
SA (antes da P, invisível) → átrios (onda P) → nó AV (segmento PR, maior parte do atraso) → His/ramos (final do PR, HV ~35–55 ms) → ramos D/E e Purkinje (início do QRS) → despolarização ventricular (QRS) → repolarização (ST-T).
Bloqueios mudam a linha do tempo: BRD atrasa ativação do VD (R' tardio em V1), BRE atrasa VE (R alargado entalhado em D1/V6), BAV prolonga o nó AV, pré-excitação encurta o PR por via acessória.
Polaridade de uma onda numa derivação = projeção do vetor médio (eixo) sobre o eixo da derivação.

## Escrita do laudo
- pt-BR, terminologia da Diretriz SBC de laudos (2022, com errata) e AHA/ACCF/HRS 2007–2009.
- Cada achado: rótulo, evidência numérica, referência, confiança. Diferenciais com "a favor" e "contra".
- Limitações explícitas (foto digitalizada, derivações de baixa qualidade, ausência de ECG prévio/clínica).

## Referências-núcleo (ver docs/research/ecg_bibliografia.md)
SBC laudos 2022; AHA/ACCF/HRS Partes I–VI; Marriott 13ª; Bayés de Luna; Goldberger 10ª; Definição Universal de IM.
