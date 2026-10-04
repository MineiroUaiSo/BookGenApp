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
| `ELEICAO_ID` | auto | código da eleição no TSE (ex.: `544` = 1º turno 2022). Defina se a descoberta automática falhar |
| `CARGO` | `0001` | `0001` = Presidente |
| `PORT` | `3000` | porta |

Fonte: `https://resultados.tse.jus.br/oficial/ele{ANO}/{ID}/dados-simplificados/{uf}/{uf}-c0001-e{ID}-r.json`.
O % por região é ponderado pelas seções totalizadas de cada estado.
