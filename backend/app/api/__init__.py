from fastapi import APIRouter

from . import analysis, health, ingest, oneshot, studies

router = APIRouter(prefix="/api")
for _m in (health, ingest, studies, analysis, oneshot):
    router.include_router(_m.router)
