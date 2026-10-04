# Retomada — Apuração por Região (2026-10-04)

## Estado
App pronto e funcionando com dados reais do TSE (Presidente 2026, 1º turno, eleição 6257).
Site 100% estático: `public/` é o site; o navegador busca o TSE direto (CORS aberto no TSE).
Branch: `claude/vote-count-regional-app-irtq1b`. TODOS os commits estão só locais — `git push` está bloqueado pela regra `deny` em `~/.claude/settings.json`.

## Arquivos
- `public/index.html` — UI (mapa colorido pelo líder: vermelho PT/13, amarelo PL/22, cinza outros; clique na região = zoom + estados ordenados por % apurado).
- `public/apuracao.js` — busca/normaliza TSE (universal: browser `window.Apuracao.buscar({demo})` e Node p/ testes). Fonte: `.../ele2026/6257/dados/{uf}/{uf}-c0001-e006257-u.json` (`br` = Brasil c/ exterior). Config: `window.APURACAO_CFG` {ano,id,cargo}.
- `public/mapa-brasil.js` — paths SVG dos estados.
- `dev.js` — servidor estático local (`PORT=3100 node dev.js`, padrão 3000).
- `test/` — `npm test` (10 testes, sem rede, fixtures reais em `test/fixtures`).

## Decisões
- Arquivo `-r` (dados-simplificados) NÃO existe em 2026; usa-se o `-u`.
- Descoberta da eleição via `ele-c.json`; 2º turno (cdt2=6258) só vale quando tiver seções totalizadas (s.st>0).
- % região = Σ seções totalizadas / Σ seções totais; Brasil = número oficial do `br`.
- Foco mobile e Vercel abandonados (usuário usa no computador). `api/` e `vercel.json` removidos.
- Existe projeto Vercel antigo `apuracao-por-regiao` (deploy desatualizado/quebrado) — ignorado a pedido do usuário.

## Falta / próximos passos
1. Publicar de graça: Netlify Drop (arrastar `public/`) OU `wrangler login` + `npx wrangler pages deploy public --project-name apuracao-por-regiao` (wrangler não instalado).
2. Liberar push: remover `"Bash(git push *)"` de `deny` em `~/.claude/settings.json` (decisão do usuário) e dar `git push -u origin claude/vote-count-regional-app-irtq1b`.
3. Não validado: Safari/Firefox, 2º turno com dados reais, card "ainda não publicou" no browser, legibilidade de ES/RJ na visão Sudeste.
4. Risco: se o TSE fechar CORS o site estático para de carregar (precisaria de proxy/servidor).
