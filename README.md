# Apuração por Região

Mostra a apuração da eleição para **Presidente** separada por região (Norte, Nordeste, Centro-Oeste, Sudeste, Sul), com dados oficiais do TSE.

- Mapa do Brasil com as regiões coloridas e o % apurado de cada uma.
- Clique numa região: o mapa mostra o % de cada estado e a lista ordena do mais apurado ao menos apurado.
- Votos por candidato somados por região e para o Brasil.
- Atualiza sozinho a cada 30 s.

## Como rodar

    node dev.js        # precisa de Node 18+; sem dependências
    # abra http://localhost:3000

Teste da interface com dados fictícios: `http://localhost:3000/?demo=1`

## Configuração (opcional)

| Variável | Padrão | Para quê |
|---|---|---|
| `ELEICAO_ANO` | `2026` | ano da eleição no TSE |
| `ELEICAO_ID` | auto | código da eleição no TSE (ex.: `6257` = 1º turno 2026, `6258` = 2º turno). Defina se a descoberta automática falhar |
| `CARGO` | `0001` | `0001` = Presidente |
| `PORT` | `3000` | porta |

## Fonte dos dados

`https://resultados.tse.jus.br/oficial/ele{ANO}/{ID}/dados/{uf}/{uf}-c0001-e{ID}-u.json`
(`br` = Brasil, incluindo exterior).

- % apurado da região = Σ seções totalizadas / Σ seções totais das UFs da região.
- % apurado do Brasil = número oficial do TSE (arquivo `br`).
- O código da eleição é descoberto pela configuração oficial do TSE. A troca automática para o 2º turno (`6258`) só acontece quando ele já tem seções totalizadas; antes disso vale o 1º turno (`6257`).

## Testes

    npm test

Rodam sem rede, com arquivos reais do TSE em `test/fixtures/`.
