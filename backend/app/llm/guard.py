"""Barreira LGPD única antes de QUALQUER chamada ao provedor de LLM (chamada em client.run_resilient).

Só texto estruturado/medidas/regras podem sair: bloqueia imagem ou base64 embutidos em TEXTO, CPF, datas (numéricas,
ISO e por extenso), e-mail, telefone BR, CNS/RG e identificadores de exame. Blocos de imagem ESTRUTURADOS
({"type": "image"}) não são texto: a política de enviá-los (plot do sinal, RX) é decisão do chamador, que pode
proibi-los com allow_images=False (laudo v2). Valores clínicos (mm, ms, bpm, razões) não casam com nenhum padrão.
Puro Python, sem rede.
"""
from __future__ import annotations

import re
from typing import Any, Iterable


class PayloadBloqueado(Exception):
    """O payload ao provedor contém imagem em texto, identificação pessoal ou não é texto."""


_MESES = (r"janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro")
_DIA = r"(?:0?[1-9]|[12]\d|3[01])"
_MES = r"(?:0?[1-9]|1[0-2])"
_ANO = r"(?:19|20)\d{2}"

_PADROES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64", re.I), "imagem embutida (data URI)"),
    (re.compile(r"(?:iVBORw0KGgo|/9j/[A-Za-z0-9+/]{4})[A-Za-z0-9+/=]{20,}"), "imagem embutida (base64 PNG/JPEG)"),
    (re.compile(r"[A-Za-z0-9+/=]{200,}"), "bloco binário/base64"),
    (re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)"), "CPF"),
    (re.compile(rf"(?<![\d/.-]){_DIA}[/.-]{_MES}[/.-]{_ANO}(?![\d/.-])"), "data"),
    (re.compile(rf"(?<![\d/.-]){_ANO}[/.-]{_MES}[/.-]{_DIA}(?![\d/.-])"), "data (ISO)"),
    (re.compile(rf"\b{_DIA}\s+de\s+(?:{_MESES})(?:\s+de\s+{_ANO})?\b", re.I), "data por extenso"),
    (re.compile(rf"\b(?:{_MESES})\s+de\s+{_ANO}\b", re.I), "data por extenso (mês/ano)"),
    (re.compile(r"\bORDER\s*ECG\w*|\bECG\d{6,}\b", re.I), "identificador de exame"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "e-mail"),
    (re.compile(r"\(\d{2}\)\s*9?\d{4}[-.\s]?\d{4}(?!\d)"), "telefone"),
    (re.compile(r"(?<!\d)\+55[\s-]?\(?\d{2}\)?[\s-]?9?\d{4}[-.\s]?\d{4}(?!\d)"), "telefone"),
    (re.compile(r"(?<![\d.])\d{2}[\s.-]9\d{4}[-.\s]\d{4}(?!\d)"), "telefone"),
    (re.compile(r"\b(?:CPF|RG|CNS|MRN|prontu[aá]rio)\b[^\n\d]{0,8}\d{4,}", re.I), "documento/identificador rotulado"),
    (re.compile(r"(?<![\d.])\d{1,2}\.\d{3}\.\d{3}-[\dXx](?!\d)"), "RG"),
]
_CPF_PLANO = re.compile(r"(?<![\d.-])\d{11}(?![\d.-])")
_CNS_CAND = re.compile(r"(?<![\d.-])(?:\d[ ]?){14}\d(?![\d.-])")


def cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(digitos[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(digitos[n]):
            return False
    return True


def cns_valido(digitos: str) -> bool:
    return len(digitos) == 15 and digitos[0] in "12789" \
        and sum(int(d) * (15 - i) for i, d in enumerate(digitos)) % 11 == 0


def scan_text(texto: str) -> str | None:
    """Nome do primeiro padrão proibido encontrado no texto (ou None)."""
    for rx, nome in _PADROES:
        if rx.search(texto):
            return nome
    if any(cpf_valido(m.group()) for m in _CPF_PLANO.finditer(texto)):
        return "CPF"
    if any(cns_valido(m.group().replace(" ", "")) for m in _CNS_CAND.finditer(texto)):
        return "CNS"
    return None


def _textos(o: Any, allow_images: bool) -> Iterable[str]:
    """Strings do payload; blocos de imagem estruturados são pulados (ou proibidos, se allow_images=False)."""
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        if o.get("type") == "image" or o.get("type") == "image_url":
            if not allow_images:
                raise PayloadBloqueado("imagem no payload (o laudo é só texto)")
            return
        for v in o.values():
            yield from _textos(v, allow_images)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _textos(v, allow_images)
    elif o is not None and not isinstance(o, (int, float, bool)):
        raise PayloadBloqueado("payload não é texto")


def assert_payload(system: Any, messages: Any, *, allow_images: bool = True) -> None:
    """Levanta PayloadBloqueado se o que iria ao provedor tiver identificação/imagem em texto."""
    for t in (*_textos(system, allow_images), *_textos(messages, allow_images)):
        nome = scan_text(t)
        if nome:
            raise PayloadBloqueado(nome)


def assert_text_only(system: str, user: str) -> None:
    """Barreira do laudo: dois textos puros (sem imagem, sem identificação)."""
    if not isinstance(system, str) or not isinstance(user, str):
        raise PayloadBloqueado("payload não é texto")
    for t in (system, user):
        nome = scan_text(t)
        if nome:
            raise PayloadBloqueado(nome)
