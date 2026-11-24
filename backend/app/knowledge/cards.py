"""Cartões de critério ECG (um critério por cartão): esquema pydantic + carregador.

Os cartões ficam em knowledge/ecg/cards/*.yaml (lista `cartoes:` por arquivo/família).
Texto é paráfrase própria; `revisado_por_medico: false` até revisão humana.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import knowledge_dir, known_reference_ids

_ID_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
_GATILHO_RE = re.compile(r"^ecg\.[a-z0-9_.]+\*?$")

Limiar = Union[str, int, float]


class Fonte(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str                       # id em knowledge/references.yaml
    local: str                     # periódico/ano/página ou seção
    tipo: Literal["paráfrase"] = "paráfrase"


class Cartao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    versao: int = Field(ge=1)
    nome_pt: str = Field(min_length=3)
    criterio: str = Field(min_length=20)       # paráfrase própria, curta
    limiares: dict[str, Limiar] = Field(default_factory=dict)
    medidas: list[str] = Field(default_factory=list)      # chaves da ficha, ex. indices.peguero_mm
    gatilhos: list[str] = Field(default_factory=list)     # códigos ecg.*; sufixo * = prefixo
    armadilhas: list[str] = Field(default_factory=list)
    nao_confundir: list[str] = Field(default_factory=list)  # ids de outros cartões
    fonte: Fonte
    revisado_por_medico: bool = False
    verificar: str | None = None               # preenchido quando limiar/fonte não foi confirmado
    leitura: str | None = None                 # link opcional de leitura (nunca fonte de texto)

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError(f"id inválido: {v!r}")
        return v

    @field_validator("gatilhos")
    @classmethod
    def _gatilhos_ok(cls, v: list[str]) -> list[str]:
        for g in v:
            if not _GATILHO_RE.match(g):
                raise ValueError(f"gatilho inválido: {g!r}")
        return v

    @property
    def familia(self) -> str:
        return self.id.split(".")[0]


def cards_dir() -> Path:
    return knowledge_dir() / "ecg" / "cards"


def gatilho_casa(gatilho: str, code: str) -> bool:
    """Gatilho casa com código emitido. 'x*' = prefixo; código terminado em '_' é prefixo de família."""
    if gatilho.endswith("*"):
        return code.startswith(gatilho[:-1]) or gatilho[:-1].startswith(code)
    return gatilho == code or (code.endswith("_") and gatilho.startswith(code))


def parse_cards(data: dict, origem: str = "?") -> list[Cartao]:
    itens = (data or {}).get("cartoes")
    if not isinstance(itens, list):
        raise ValueError(f"{origem}: chave 'cartoes' ausente")
    return [Cartao(**i) for i in itens]


def validate_cards(cards: list[Cartao], refs: set[str] | None = None) -> list[str]:
    """Erros de consistência entre cartões (ids duplicados, nao_confundir órfão, ref desconhecida)."""
    erros: list[str] = []
    ids = [c.id for c in cards]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        erros.append(f"id duplicado: {i}")
    idset = set(ids)
    refs = known_reference_ids() if refs is None else refs
    for c in cards:
        erros += [f"{c.id}: nao_confundir desconhecido {n}" for n in c.nao_confundir if n not in idset]
        if c.fonte.ref not in refs:
            erros.append(f"{c.id}: fonte.ref desconhecida {c.fonte.ref}")
    return erros


@lru_cache(maxsize=None)
def _load(base: str) -> tuple[Cartao, ...]:
    out: list[Cartao] = []
    for p in sorted(Path(base).glob("*.yaml")):
        with open(p, encoding="utf-8") as f:
            out += parse_cards(yaml.safe_load(f), p.name)
    erros = validate_cards(out)
    if erros:
        raise ValueError("cartões inválidos: " + "; ".join(erros))
    return tuple(sorted(out, key=lambda c: c.id))


def load_cards() -> list[Cartao]:
    d = cards_dir()
    return list(_load(str(d))) if d.exists() else []
