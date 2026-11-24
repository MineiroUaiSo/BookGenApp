# Trilha I - fallback OpenRouter para a IA do laudo

Commits: cf024d4 (.gitignore .env.*), 1d9e666 (provedor OpenRouter + testes).

- Backend: `backend/app/llm/client.py` (OpenRouterClient via httpx; `provider()`: anthropic tem prioridade, openrouter se so OPENROUTER_API_KEY).
- Modelo: env `MEDLENS_OR_MODEL`; default `anthropic/claude-sonnet-5.5` (input text/image/file, conferido em GET /api/v1/models em 2026-11-24).
- Erros: 402 (creditos/limite), 429, 401/403, conexao, truncamento e content_filter com mensagens em pt-BR; chave nunca logada.
- Testes: `tests/test_llm_openrouter.py` (httpx mockado). Suite: so as 2 falhas pre-existentes de test_collector_litfl.
- Integracao local porta 8101 sem chaves: `/api/health` ai_available=false; analyze?ai=true devolve "IA indisponivel (ANTHROPIC_API_KEY ou OPENROUTER_API_KEY ausente)". Servidor encerrado.
- Chave real: OPENROUTER_API_KEY estava no ambiente; chamada minima texto-only (max_tokens 16) com anthropic/claude-sonnet-5.5 retornou "OK". Fluxo completo com imagem ECG/RX real nao exercitado (pendente do usuario).
