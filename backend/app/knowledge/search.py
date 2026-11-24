"""Busca lexical (SQLite FTS5, BM25) sobre os cartões ECG e seleção por achados/índices/padrões.

Sem embeddings nem modelo: índice em memória reconstruído a partir dos YAML (não versionado).
"""
from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from typing import Iterable

from .cards import Cartao, gatilho_casa, load_cards

LIMITE_PADRAO = 20
_PESO_GATILHO, _PESO_MEDIDA, _PESO_PADRAO, _PESO_NC = 10.0, 2.0, 5.0, 1.0
_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _texto_indexavel(c: Cartao) -> tuple[str, str, str]:
    nome = f"{c.nome_pt} {c.id.replace('.', ' ').replace('_', ' ')}"
    corpo = " ".join([c.criterio, *c.armadilhas, " ".join(f"{k} {v}" for k, v in c.limiares.items())])
    extra = " ".join([*c.medidas, c.fonte.ref, c.fonte.local])
    return nome, corpo, extra


@lru_cache(maxsize=4)
def _indice(chave: tuple[str, ...]) -> sqlite3.Connection:
    cards = {c.id: c for c in load_cards()}
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.execute("CREATE VIRTUAL TABLE cartoes USING fts5(id UNINDEXED, nome, corpo, extra, "
                "tokenize='unicode61 remove_diacritics 2')")
    for cid in sorted(cards):
        con.execute("INSERT INTO cartoes(id, nome, corpo, extra) VALUES (?,?,?,?)", (cid, *_texto_indexavel(cards[cid])))
    return con


def _con() -> sqlite3.Connection:
    return _indice(tuple(sorted(c.id + str(c.versao) for c in load_cards())))


def _match_query(texto: str) -> str:
    termos = [t for t in _TOKEN_RE.findall(texto.lower()) if len(t) > 1]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(termos))


def search_cards(consulta: str, limite: int = LIMITE_PADRAO) -> list[Cartao]:
    """Busca livre BM25 (nome pesa mais que corpo). Ordem: relevância, desempate por id."""
    q = _match_query(consulta)
    if not q:
        return []
    rows = _con().execute(
        "SELECT id FROM cartoes WHERE cartoes MATCH ? ORDER BY bm25(cartoes, 0.0, 8.0, 2.0, 1.0), id LIMIT ?",
        (q, limite)).fetchall()
    por_id = {c.id: c for c in load_cards()}
    return [por_id[r[0]] for r in rows]


def select_cards(
    findings_codes: Iterable[str] | None = None,
    indices_keys: Iterable[str] | None = None,
    padroes: Iterable[str] | None = None,
    limite: int = LIMITE_PADRAO,
) -> list[Cartao]:
    """União determinística: cartões ligados aos achados (gatilhos), às medidas/índices
    (calculados ou não), a padrões (busca textual) e seus 'nao_confundir'. Até `limite`."""
    cards = load_cards()
    por_id = {c.id: c for c in cards}
    codes = sorted(set(findings_codes or []))
    keys = set(indices_keys or [])
    score: dict[str, float] = {}

    def add(cid: str, v: float) -> None:
        score[cid] = score.get(cid, 0.0) + v

    for c in cards:
        for code in codes:
            if any(gatilho_casa(g, code) for g in c.gatilhos):
                add(c.id, _PESO_GATILHO)
        if keys & set(c.medidas):
            add(c.id, _PESO_MEDIDA * len(keys & set(c.medidas)))
    for p in sorted(set(padroes or [])):
        for pos, c in enumerate(search_cards(p, limite)):
            add(c.id, _PESO_PADRAO / (1 + pos))
    for cid in [i for i, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))]:
        for n in por_id[cid].nao_confundir:
            if n in por_id and n not in score:
                score[n] = _PESO_NC  # só entra se sobrar espaço, atrás dos demais
    ordem = sorted(score, key=lambda i: (-score[i], i))
    return [por_id[i] for i in ordem[:limite]]


def format_cards(cards: list[Cartao]) -> str:
    """Texto compacto e determinístico para o prompt."""
    out = []
    for c in cards:
        lim = "; ".join(f"{k} {v}" for k, v in c.limiares.items())
        out.append(
            f"[{c.id}] {c.nome_pt}: {' '.join(c.criterio.split())}"
            + (f" | Limiares: {lim}" if lim else "")
            + (f" | Armadilhas: {' '.join(c.armadilhas)}" if c.armadilhas else "")
            + (f" | Não confundir com: {', '.join(c.nao_confundir)}" if c.nao_confundir else "")
            + f" | Fonte: {c.fonte.ref} ({c.fonte.local})"
            + (" | VERIFICAR" if c.verificar else "")
        )
    return "\n".join(out)
