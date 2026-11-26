"""Entrypoint ASGI do projeto Vercel 'medlens-api' (ECG/RX pediátrico, sem estado, sem IA).

A Vercel procura a variável `app` em api/index.py. Aqui as travas de IA são FORÇADAS (atribuição, não setdefault):
mesmo que alguém crie OPENROUTER_API_KEY/ANTHROPIC_API_KEY ou ligue um flag no painel, nenhum caminho chama LLM.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for _flag in ("MEDLENS_DESCRICAO_IA", "MEDLENS_RX_DESCRICAO_IA", "MEDLENS_RX_IMAGE_AI", "MEDLENS_RX_LAUDO_IA",
              "MEDLENS_LAUDO", "MEDLENS_RX_MODELS"):
    os.environ[_flag] = "0"
os.environ.setdefault("MEDLENS_DATA", "/tmp/medlens")  # nunca usado pelo oneshot; /tmp é o único gravável na Vercel
os.environ.setdefault("MEDLENS_RETENCAO_HORAS", "0.1")

from app.main import create_app  # noqa: E402

app = create_app(oneshot_only=True)
