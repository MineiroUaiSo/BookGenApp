"""Anonimizacao do TEXTO enviado ao provedor de IA (RX): sem study_id, UIDs, datas nem idade exata.

Defesa em profundidade: o texto e montado a partir de medidas/regras (sem tags DICOM), mas strings livres
(avisos, evidencias) podem repetir ids/datas/idade. Aqui elas viram marcadores; a barreira LGPD (guard) continua
sendo a ultima palavra. Puro Python, sem rede.
"""
from __future__ import annotations

import re
from typing import Iterable

_UID = re.compile(r"(?<![\d.])\d+(?:\.\d+){4,}(?![\d.])")
_ANOS = re.compile(r"(?<![\d.,-])(\d{1,3})\s*anos?\b", re.I)
_IDADE = re.compile(r"\b(idade\s*[:=]?\s*)(\d{1,3})\b", re.I)
_DATAS = (
    re.compile(r"(?<![\d/.-])(?:0?[1-9]|[12]\d|3[01])[/.-](?:0?[1-9]|1[0-2])[/.-](?:19|20)\d{2}(?![\d/.-])"),
    re.compile(r"(?<![\d/.-])(?:19|20)\d{2}[/.-](?:0?[1-9]|1[0-2])[/.-](?:0?[1-9]|[12]\d|3[01])(?![\d/.-])"),
    re.compile(r"(?<!\d)(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?!\d)"),
)


def age_band(n: int) -> str:
    """Faixa decenal ('60-69 anos'); 90+ agrupado."""
    if n >= 90:
        return "90+ anos"
    lo = (n // 10) * 10
    return f"{lo}-{lo + 9} anos"


def anonymize_text(text: str, ids: Iterable[str] = ()) -> str:
    """Troca ids conhecidos (study_id, instance ids), UIDs, datas e idade exata por marcadores."""
    for ident in sorted({x for x in ids if x and len(x) >= 3}, key=len, reverse=True):
        text = re.sub(rf"(?<![\w.-]){re.escape(ident)}(?![\w.-])", "[id]", text)
    text = _UID.sub("[uid]", text)
    for rx in _DATAS:
        text = rx.sub("[data]", text)
    text = _IDADE.sub(lambda m: m.group(1) + age_band(int(m.group(2))), text)
    return _ANOS.sub(lambda m: age_band(int(m.group(1))), text)
