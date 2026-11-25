"""Léxico de incerteza e termos proibidos do laudo de RX (spec RX-LAUDO-CONFIAVEL §2.2). Tabela única: usada pelo laudo
determinístico e pelo validador da IA (`laudo_validate`). Grau de certeza nunca pode ser mais forte que o nível do fato."""
from __future__ import annotations

import re

from .ficha import Nivel

GRAUS: dict[str, re.Pattern] = {
    "sugere": re.compile(r"\bsuger\w*|\bsugestiv\w+", re.IGNORECASE),
    "compativel_com": re.compile(r"compat[ií]vel(?:eis)? com|compat[ií]veis com", re.IGNORECASE),
    "possivel": re.compile(r"\bposs[ií]ve(?:l|is)\b|\bpossivelmente\b", re.IGNORECASE),
    "indeterminado": re.compile(r"\bindeterminad\w+", re.IGNORECASE),
    "nao_avaliado": re.compile(r"n[aã]o avaliad\w+|n[aã]o (?:permite|há como) afirmar", re.IGNORECASE),
}

# grau máximo que cada nível de fato admite
GRAUS_PERMITIDOS: dict[Nivel, frozenset[str]] = {
    Nivel.MEDIDO: frozenset({"compativel_com", "indeterminado", "nao_avaliado"}),   # compatível: só com a própria medida
    Nivel.REGRA: frozenset({"sugere", "indeterminado", "nao_avaliado"}),
    Nivel.SUGERIDO_MODELO: frozenset({"possivel", "indeterminado", "nao_avaliado"}),
    Nivel.QUALIDADE: frozenset({"possivel", "indeterminado", "nao_avaliado"}),
    Nivel.NAO_AVALIADO: frozenset({"nao_avaliado"}),
}

PROIBIDOS = re.compile(
    r"\bnormal(?:is|idade)?\b|sem altera[cç][oõ]es|dentro d[aeo]s? normalidade|\bafasta\w*|\bdescarta\w*|"
    r"aus[eê]ncia de|\blivres?\b|diagn[oó]stico de|\bconfirma\w*", re.IGNORECASE)
# frases-molde legítimas que contêm palavra proibida só para NEGAR o poder do modelo
_ISENTAS = re.compile(r"n[aã]o confirma nem afasta|nem afastar|n[aã]o confirma", re.IGNORECASE)
_FAIXA_REF = re.compile(r"dentro d[aeo]s? faixa de refer[eê]ncia", re.IGNORECASE)
_MEDIDA = re.compile(r"\bmedid[ao]s?\b|faixa de refer[eê]ncia", re.IGNORECASE)


def termos_proibidos(texto: str) -> list[str]:
    limpo = _FAIXA_REF.sub(" ", _ISENTAS.sub(" ", texto or ""))
    return sorted({m.group(0).lower() for m in PROIBIDOS.finditer(limpo)})


def graus_usados(texto: str) -> set[str]:
    return {g for g, rx in GRAUS.items() if rx.search(texto or "")}


def problemas(texto: str, nivel: Nivel) -> list[str]:
    """Motivos pelos quais `texto` não pode rotular um fato de `nivel` (lista vazia = ok)."""
    out = [f"termo proibido: {t}" for t in termos_proibidos(texto)]
    permitidos = GRAUS_PERMITIDOS[nivel]
    for g in sorted(graus_usados(texto)):
        if g not in permitidos:
            out.append(f"grau '{g}' mais forte que o nível {nivel.value}")
        elif g == "compativel_com" and not _MEDIDA.search(texto):
            out.append("'compatível com' só vale para a própria medida")
    if _FAIXA_REF.search(texto) and nivel != Nivel.MEDIDO:
        out.append("'dentro da faixa de referência' exige fato MEDIDO")
    return out
