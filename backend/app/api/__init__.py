from fastapi import APIRouter

from . import analysis, health, ingest, studies

router = APIRouter(prefix="/api")
for _m in (health, ingest, studies, analysis):
    router.include_router(_m.router)
