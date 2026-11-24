# Estrutura do laudo de ECG (resumo próprio para o MedLens)

Resumo estruturado, em palavras próprias, para desenhar o laudo gerado pela LLM (trilha r2-laudo, 2026-11).
Nota de método: as buscas web (2026-11-24) confirmaram a existência e a referência bibliográfica das fontes; o texto
integral da Diretriz SBC 2022 e da declaração AHA/ACCF/HRS NÃO foi aberto nesta sessão (o fetch foi bloqueado pelo
ambiente). Itens abaixo vêm de (a) trechos retornados pelas buscas e (b) conhecimento geral de eletrocardiografia;
os pontos marcados com "[conferir]" devem ser verificados no texto integral por um médico antes de uso clínico.
Esta ferramenta é apoio a laudo, não dispositivo certificado.

## Fontes
- Samesima N, et al. Diretriz da SBC sobre a Análise e Emissão de Laudos Eletrocardiográficos - 2022.
  Arq Bras Cardiol 2022;119(4):638-680. DOI 10.36660/abc.20220623. (PMC9563889)
- Kligfield P, et al. AHA/ACCF/HRS Recommendations for the Standardization and Interpretation of the
  Electrocardiogram, Part I. Circulation 2007;115:1306-24 (também Heart Rhythm 2007;4:394-412; JACC 2007;49:1109-27).
  Ideia central usada: intervalos globais (início mais precoce ao fim mais tardio entre as derivações, a partir de
  complexos sobrepostos/mediana) são o padrão preferido e são mais longos que medidas de uma derivação isolada;
  algoritmos diferentes dão valores diferentes, então o laudo deve declarar de onde vem a medida.
- Goldberger AL, et al. Goldberger's Clinical Electrocardiography (abordagem sistemática por etapas).
- Peguero JG, et al. J Am Coll Cardiol 2017;69(13):1694-1703 (critério de Peguero-Lo Presti para HVE:
  maior S em qualquer derivação + S de V4; corte >= 28 mm (2,8 mV) homens / >= 23 mm (2,3 mV) mulheres;
  confirmado em busca web 2026-11-24 (resumo ACC e JACC). Correção: versão anterior deste doc trazia V3 e cortes invertidos).
- Romhilt DW, Estes EH. Am Heart J 1968;75:752-8 (escore de pontos para HVE: voltagem 3, strain ST-T 3 [1 com digital],
  aumento de AE 3, desvio de eixo para a esquerda 2, QRS >= 90 ms 1, deflexão intrinsecoide >50 ms 1;
  >= 5 pontos HVE, 4 provável [conferir]).
- Makavos G, et al. Heart Fail Rev 2019;24(4):439-459 (ECG na miocardiopatia hipertrófica).

## Ordem de leitura/redação adotada (convergente entre as fontes)
1. Qualidade técnica e calibração (25 mm/s, 10 mm/mV, ruído, linha de base, troca de eletrodos).
2. Ritmo e frequência (origem do ritmo, relação P-QRS, regularidade, FC).
3. Intervalos: PR, QRS, QT e QTc, sempre dizendo a fórmula do QTc.
4. Eixos no plano frontal: P, QRS, T.
5. Onda P (duração, morfologia, sobrecarga atrial).
6. Complexo QRS: morfologia, voltagem/critérios de hipertrofia, ondas Q patológicas, progressão da onda R.
7. Segmento ST e onda T, por parede/território (inferior, lateral, anterior, septal, posterior, VD).
8. Comparação com ECG anterior, quando existir.
9. Impressão diagnóstica: síntese clínica, ordenada por relevância; achados limítrofes marcados como tais;
   correlação clínica e recomendação objetiva.

## Boas práticas de redação (para o prompt)
- Impressão curta, em frases afirmativas só quando as medidas sustentam; usar "sugestivo de", "compatível com",
  "correlacionar com..." para achados que dependem de contexto.
- Padrões ST-T com sobrecarga de ventrículo (strain) descrevem repolarização secundária; não equivaler a isquemia
  sem lastro (dinâmica, sintomas, comparação).
- Critérios de voltagem isolados são limítrofes quanto à especificidade; citar o índice e o valor medido.
- Medida impressa no cabeçalho do aparelho e medida do algoritmo que divergem muito = suspeita de erro de
  digitalização/delineação: relatar a discordância no TOPO e não diagnosticar os achados dependentes dela.
- Sempre declarar limitações (foto, digitalização, ausência de dados clínicos, ausência de ECG prévio).

## Caso-ouro caso1 (gabarito de cardiologista, confirmado por eco) - uso como teste
Laudo correto: sobrecarga de câmaras esquerdas; padrão sugestivo de miocardiopatia hipertrófica.
Evidências do gabarito: R > 20 mm em D1/aVL e > 30 mm em V3-V6; strain de VE; Romhilt-Estes 6 pontos; Cornell 58 mm;
Sokolow-Lyon 60 mm; Peguero-Lo Presti NÃO preenchido (sugere hipertrofia focal); sem desvio de eixo; P ~120 ms.
O app errou por digitalização (PR 88, QRS 270, pré-excitação, ST -4,9 mm em aVF); impresso: PR 148, QRS 112, QTc 482.
