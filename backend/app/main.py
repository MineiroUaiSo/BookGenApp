import hmac
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.api import router
from app.store import store

log = logging.getLogger(__name__)

# "testclient" é o host que o TestClient do Starlette usa; um cliente real nunca chega com esse valor.
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
OPEN_PATHS = {"/api/health"}


def _bearer_ok(header: str, token: str) -> bool:
    scheme, _, given = header.partition(" ")
    return scheme.lower() == "bearer" and hmac.compare_digest(given.strip().encode(), token.encode())


async def phi_guard(request: Request, call_next):
    """Toda rota /api (menos /health) protege dado de paciente.

    MEDLENS_API_TOKEN definido: exige 'Authorization: Bearer <token>' (401).
    Sem token: só aceita cliente de loopback (403), o que mantém o uso local como antes.
    """
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api") or path in OPEN_PATHS:
        return await call_next(request)
    token = os.environ.get("MEDLENS_API_TOKEN", "")
    if not token and path.startswith("/api/oneshot"):  # serviço hospedado: sem token a rota falha fechada (503)
        return JSONResponse({"detail": {"codigo": "nao_configurado", "mensagem": "Serviço sem token configurado."}},
                            status_code=503)
    if token:
        if not _bearer_ok(request.headers.get("authorization", ""), token):
            return JSONResponse({"detail": "Não autenticado: informe o token da API."}, status_code=401,
                                headers={"WWW-Authenticate": "Bearer"})
    elif (request.client.host if request.client else "") not in LOOPBACK_HOSTS:
        return JSONResponse({"detail": "Acesso negado: sem MEDLENS_API_TOKEN configurado, "
                                       "a API só aceita conexões locais."}, status_code=403)
    return await call_next(request)


def create_app(oneshot_only: bool = False) -> FastAPI:
    """oneshot_only=True: instância hospedada (Vercel), sem estado: só /api/health e /api/oneshot/*."""
    app = FastAPI(title="MedLens", version="0.1.0",
                  description="ECG and chest X-ray reader. Decision support / teaching only.")
    app.middleware("http")(phi_guard)  # antes do CORS: o CORS fica por fora e responde o preflight
    app.add_middleware(
        CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"]
    )
    if oneshot_only:
        from fastapi import APIRouter

        from app.api import oneshot

        hosted = APIRouter(prefix="/api")
        hosted.add_api_route("/health", lambda: {"status": "ok", "modo": "oneshot-pediatrico"}, methods=["GET"])
        hosted.include_router(oneshot.router)
        app.include_router(hosted)
        return app  # sem frontend, sem retenção em disco: nada para varrer
    app.include_router(router)
    if config.FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
    try:
        store.purge_expired()
    except Exception:  # a retenção nunca impede o servidor de subir
        log.exception("falha ao aplicar a retenção na inicialização")
    return app


app = create_app()
