"""Registro de fontes do laudo de RX (knowledge/rx_report_sources.yaml). O laudo só cita fontes `verificado: true`."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

import yaml
from pydantic import BaseModel, ConfigDict

from ..knowledge import knowledge_dir

SECOES = ("identificacao_tecnica", "qualidade", "achados", "sinais_modelo", "impressao", "recomendacoes",
          "revisao_medica")
ARQUIVO = "rx_report_sources.yaml"


class FonteNaoVerificada(ValueError):
    """Tentativa de citar fonte inexistente ou com verificado: false."""


class Fonte(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    titulo: str
    entidade: str
    ano: Optional[int] = None
    url: Optional[str] = None
    direitos: str
    secoes: tuple[str, ...] = ()
    verificado: bool
    lido: Optional[str] = None
    nota: Optional[str] = None


@lru_cache(maxsize=None)
def _carregar(base: str) -> tuple[Fonte, ...]:
    data = yaml.safe_load((Path(base) / ARQUIVO).read_text(encoding="utf-8")) or {}
    fontes = tuple(Fonte(**f) for f in data.get("fontes", []))
    ids = [f.id for f in fontes]
    if len(ids) != len(set(ids)):
        raise ValueError("ids de fonte duplicados em " + ARQUIVO)
    return fontes


def todas() -> tuple[Fonte, ...]:
    return _carregar(str(knowledge_dir()))


def verificadas() -> dict[str, Fonte]:
    return {f.id: f for f in todas() if f.verificado}


def citar(ids: Iterable[str]) -> tuple[Fonte, ...]:
    """Fontes para citar no laudo; levanta FonteNaoVerificada se algum id não for verificado."""
    ok = verificadas()
    ruins = [i for i in ids if i not in ok]
    if ruins:
        raise FonteNaoVerificada("fonte(s) não verificada(s) ou inexistente(s): " + ", ".join(sorted(set(ruins))))
    return tuple(ok[i] for i in ids)
