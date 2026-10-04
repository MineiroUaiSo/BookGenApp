# Apuração por Região

Mostra a apuração da eleição para **Presidente** separada por região (Norte, Nordeste, Centro-Oeste, Sudeste, Sul), com dados oficiais do TSE.

- Mapa do Brasil com as regiões coloridas e o % apurado de cada uma.
- Clique numa região: o mapa mostra o % de cada estado e a lista ordena do mais apurado ao menos apurado.
- Votos por candidato somados por região e para o Brasil.
- Atualiza sozinho a cada 30 s.

## Como rodar

Site 100% estático: a pasta `public/` sozinha é o site. O navegador busca os dados direto no TSE (sem backend).

    node dev.js        # Node 18+, sem dependências
    # abra http://localhost:3000

Ou use qualquer servidor estático apontando para `public/` (ex.: `python3 -m http.server -d public`).
Teste da interface com dados fictícios: `/?demo=1`.

## Testes

    npm test

Rodam sem rede, com arquivos reais do TSE em `test/fixtures/`.

## Publicar de graça

- **Cloudflare Pages**: conecte o repositório, deixe o build command vazio e use `public` como output directory. Ou pela CLI: `npx wrangler pages deploy public --project-name apuracao-por-regiao`.
- **Netlify**: arraste a pasta `public/` em https://app.netlify.com/drop.

Atenção: o site depende de o TSE manter o CORS aberto em `resultados.tse.jus.br`.

## Configuração (opcional)

Defina antes de carregar `apuracao.js` no `index.html`:

    <script>window.APURACAO_CFG = { ano: '2026', id: '6257' };</script>

| Campo | Padrão | Para quê |
|---|---|---|
| `ano` | `2026` | ano da eleição no TSE |
| `id` | auto | código da eleição no TSE (ex.: `6257` = 1º turno 2026, `6258` = 2º turno). Defina se a descoberta automática falhar |
| `cargo` | `0001` | `0001` = Presidente |

## Fonte dos dados

`https://resultados.tse.jus.br/oficial/ele{ANO}/{ID}/dados/{uf}/{uf}-c0001-e{ID}-u.json`
(`br` = Brasil, incluindo exterior).

- % apurado da região = Σ seções totalizadas / Σ seções totais das UFs da região.
- % apurado do Brasil = número oficial do TSE (arquivo `br`).
- O código da eleição é descoberto pela configuração oficial do TSE. A troca automática para o 2º turno (`6258`) só acontece quando ele já tem seções totalizadas; antes disso vale o 1º turno (`6257`).
