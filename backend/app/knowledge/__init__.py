"""Carrega a base de conhecimento (knowledge/*.yaml) e resolve referências."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

from ..schemas import Reference

Domain = Literal["ecg", "rx"]

_FILES = {"ecg": "ecg_criteria.yaml", "rx": "rx_signs.yaml"}
# Itens sempre incluídos no prompt (abordagem sistemática / valores normais).
_ALWAYS = {"ecg": ["ecg.normal_intervals"], "rx": ["rx.systematic_approach", "rx.technical_quality"]}


def knowledge_dir() -> Path:
    env = os.environ.get("MEDLENS_KNOWLEDGE")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "knowledge"


@lru_cache(maxsize=None)
def _load_yaml(name: str, base: str) -> Any:
    with open(Path(base) / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _y(name: str) -> Any:
    return _load_yaml(name, str(knowledge_dir()))


def load_criteria(domain: Domain) -> list[dict]:
    if domain not in _FILES:
        raise ValueError(f"domínio desconhecido: {domain}")
    data = _y(_FILES[domain])
    return [dict(i) for i in data.get("items", [])]


def references_map() -> dict[str, dict]:
    return dict(_y("references.yaml"))


def known_reference_ids() -> set[str]:
    return set(references_map())


def reference(id: str, note: str | None = None) -> Reference:
    """Reference completa para um id; id desconhecido -> Reference(id, source=id)."""
    r = references_map().get(id)
    if not r:
        return Reference(id=id, source=id, note=note)
    parts = [r.get("title", id)]
    if r.get("edition"):
        parts.append(str(r["edition"]))
    if r.get("year"):
        parts.append(str(r["year"]))
    src = ", ".join(parts)
    if r.get("authors"):
        src = f"{r['authors']}. {src}"
    if r.get("journal"):
        src += f". {r['journal']}"
    return Reference(id=id, source=src, note=note or r.get("note"))


def is_known_reference(id: str) -> bool:
    return id in references_map()


def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().replace(".", " ").replace("_", " ").split() if len(t) > 2}


def select_relevant(
    domain: Domain,
    findings: Iterable[Any] | None = None,
    measurements: Iterable[str] | None = None,
    max_items: int = 14,
) -> list[dict]:
    """Escolhe critérios relevantes: itens fixos + os que casam com códigos de achados
    (id exato ou prefixo/tokens) e com as medidas presentes."""
    items = load_criteria(domain)
    by_id = {i["id"]: i for i in items}
    codes: list[str] = []
    for f in findings or []:
        code = f if isinstance(f, str) else getattr(f, "code", None) or (f.get("code") if isinstance(f, dict) else None)
        if code:
            codes.append(code)
    mkeys = set(measurements or [])
    scores: dict[str, float] = {}
    for it in items:
        s = 0.0
        iid = it["id"]
        for c in codes:
            if c == iid:
                s += 10
            else:
                common = _tokens(c) & _tokens(iid + " " + it.get("label_pt", ""))
                common -= {"ecg", "rx"}
                s += 2 * len(common)
        s += 0.5 * len(mkeys & set(it.get("measurements_used", [])))
        if s:
            scores[iid] = s
    chosen = [i for i in _ALWAYS[domain] if i in by_id]
    for iid, _ in sorted(scores.items(), key=lambda kv: -kv[1]):
        if iid not in chosen:
            chosen.append(iid)
        if len(chosen) >= max_items:
            break
    return [by_id[i] for i in chosen]


def format_items(items: list[dict]) -> str:
    """Texto compacto e determinístico para o prompt."""
    out = []
    for it in items:
        out.append(
            f"[{it['id']}] {it['label_pt']}: {' '.join(str(it['criteria']).split())}"
            f" | Diferenciais: {', '.join(it.get('differentials', []))}"
            f" | Armadilhas: {' '.join(it.get('pitfalls', []))}"
            f" | Refs: {', '.join(it.get('references', []))}"
        )
    return "\n".join(out)


def format_references(ids: Iterable[str] | None = None) -> str:
    m = references_map()
    ids = sorted(ids) if ids is not None else sorted(m)
    return "\n".join(f"{i}: {reference(i).source}" for i in ids if i in m)
