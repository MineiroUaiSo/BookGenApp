"""Barreira qualitativa do texto livre de IA do ECG (v1 e laudo v1): falha FECHADA.

O validador numérico (validate.py) só confere números e marca; frases sem lastro passavam. Aqui a frase que
(a) nega isquemia/IAM/supra/BAV/bloqueio/etc., (b) afirma normalidade do exame ou (c) afirma diagnóstico ausente de
`achados_por_regras` é REMOVIDA (não marcada). Com `ecg.st_not_assessable` presente, negar ST/isquemia e afirmar
normalidade são sempre removidos. Reaproveita os tópicos de claim_semantics (somente importa). Puro Python, sem rede.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from .claim_semantics import (CODIGO_NORMAL, SEVERIDADES_ANORMAIS, TOPICOS, Topico, _QUALIFICADOR, _negado, _rx,
                              normal_global)

_ST_NA = "st_not_assessable"

# tópicos de ECG que o claim_semantics (v2, baseado em Ficha) não cobre
_EXTRA: tuple[Topico, ...] = (
    Topico("alteração de ST/T", _rx(r"altera[cç][oõ]es? (?:agudas? )?(?:d[oe]s? )?(?:segmento )?ST(?:-?T)?\b|"
                                    r"altera[cç][oõ]es isqu[eê]micas"),
           _rx(r"^ecg\.(st_|t_inversion_|secondary_repol|pathologic_q_)")),
    Topico("síndrome de Brugada", _rx(r"brugada"), _rx(r"^ecg\.brugada")),
    Topico("distúrbio eletrolítico", _rx(r"hiper-?calemia|hipo-?calemia|hiper-?calcemia|hipo-?calcemia|"
                                         r"hiper-?magnesemia|dist[uú]rbio eletrol[ií]tico"),
           _rx(r"^ecg\.(hyper|hypo)(kal|calc|magn)|^ecg\.electrolyte")),
    Topico("embolia pulmonar", _rx(r"embolia pulmonar|tromboembolismo|\bTEP\b|S1-?Q3-?T3"),
           _rx(r"^ecg\.(pulmonary_embol|s1q3t3)")),
    Topico("pericardite/derrame pericárdico", _rx(r"pericardite|derrame peric[aá]rdico"), _rx(r"^ecg\.pericard")),
    Topico("taquiarritmia ventricular/supraventricular", _rx(r"taquicardia (?:ventricular|supraventricular)|"
                                                              r"\bTSV\b|\bTV\b|fibrila[cç][aã]o ventricular"),
           _rx(r"^ecg\.(ventricular|vtach|vfib|svt|supraventricular)")),
    Topico("síndrome coronariana", _rx(r"s[ií]ndrome coronari\w+|\bSCA\b|\bWellen\b|De Winter|oclus[aã]o coron\w+"),
           _rx(r"^ecg\.(st_elevation_|wellen|acs)")),
    Topico("extrassístole", _rx(r"extrass[ií]stole\w*|\bESV\b|\bESSV\b|\bPVC\b"),
           _rx(r"^ecg\.(pvc|pac|ectopic|extrasyst)")),
)
_TODOS: tuple[Topico, ...] = TOPICOS + _EXTRA
_FAMILIA_ST = {"isquemia", "supradesnivelamento de ST / infarto", "infradesnivelamento de ST", "alteração de ST/T",
               "síndrome coronariana", "onda Q patológica / área inativa"}

# negação só é barrada para o que um médico leria como exclusão diagnóstica; "sem desvio de eixo" etc. não entram
_NEG_BARRADA = {"bloqueio de ramo esquerdo", "bloqueio de ramo direito", "distúrbio de condução intraventricular",
                "hemibloqueio anterior esquerdo", "hemibloqueio posterior esquerdo", "pré-excitação",
                "bloqueio atrioventricular", "fibrilação atrial", "flutter atrial", "ritmo de marca-passo",
                "onda Q patológica / área inativa", *_FAMILIA_ST} | {t.nome for t in _EXTRA}

_NORMAL_EXTRA = _rx(r"sem anormalidades|sem achados (?:patol[oó]gic\w+|relevantes|significativos)|"
                    r"nada digno de nota|n[aã]o h[aá] altera[cç][oõ]es|dentro dos padr[oõ]es")
_MEDIDA_NA_FRASE = _rx(r"\bPR\b|\bQRS\b|\bQTc?\b|\bST\b|frequ[eê]ncia|\bFC\b|\beixo\b|\bonda\b|intervalo|segmento|"
                       r"\bbpm\b|\bms\b|\bmm\b|voltagem|[ií]ndice")
_SPLIT = re.compile(r"((?<=[.!?])\s+|\n+)")


def _regras(summary: dict) -> list[tuple[str, str]]:
    """(código em minúsculas, severidade) de cada achado por regra."""
    return [(str(f.get("code", "")).lower(), str(f.get("severity", "")))
            for f in (summary or {}).get("achados_por_regras") or [] if isinstance(f, dict)]


def _suporte_alem_das_regras(t: Topico, summary: dict) -> bool:
    """Lastro determinístico que não é código de regra: ritmo medido e critérios de voltagem calculados."""
    if t.nome == "ritmo sinusal":
        rit = str(((summary or {}).get("medidas_globais") or {}).get("rhythm") or "").lower()
        return "sinusal" in rit and not re.search(r"n[aã]o|ausen", rit)
    if t.nome == "hipertrofia ventricular esquerda":
        idx = (summary or {}).get("indices_calculados") or {}
        def acima(v: str, lim: str) -> bool:
            a, b = idx.get(v), idx.get(lim)
            return isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > b
        return (acima("sokolow_lyon_mm", "sokolow_lyon_limite_mm") or acima("cornell_mm", "cornell_limite_mm")
                or idx.get("peguero_preenchido") is True)
    return False


def _topicos(texto: str) -> list[tuple[Topico, bool]]:
    """(tópico, negado?) por tópico citado; medida só conta quando afirmada; uma ocorrência afirmada => afirmado."""
    out: list[tuple[Topico, bool]] = []
    for t in _TODOS:
        ocorr = [_negado(texto, m.start()) for m in t.texto.finditer(texto)]
        if not ocorr:
            continue
        if all(ocorr):
            if not t.medida:
                out.append((t, True))
        else:
            out.append((t, False))
    return out


def _normal(texto: str) -> bool:
    return normal_global(texto) or bool(_NORMAL_EXTRA.search(texto) and not _MEDIDA_NA_FRASE.search(texto))


def sentence_problem(sentence: str, summary: dict) -> Optional[str]:
    """Motivo de a frase não poder ser emitida (None = pode). Falha fechada: sem lastro => problema."""
    regras = _regras(summary)
    codigos = [c for c, _ in regras]
    st_na = any(_ST_NA in c for c in codigos)
    if _normal(sentence):
        anormal = any(s in SEVERIDADES_ANORMAIS for _, s in regras)
        if st_na or anormal or CODIGO_NORMAL not in codigos or not _QUALIFICADOR.search(sentence):
            return "afirmação de normalidade sem lastro nas regras automáticas"
    for t, negado in _topicos(sentence):
        casa = [c for c in codigos if t.codigos and t.codigos.search(c)]
        if negado:
            if t.nome not in _NEG_BARRADA:
                continue
            if st_na and t.nome in _FAMILIA_ST:
                return f"negação de {t.nome} com ST não interpretável"
            if casa:
                return f"negação de {t.nome} contradiz regra ativa"
            if not _QUALIFICADOR.search(sentence):
                return f"negação de {t.nome} sem qualificador: ausência de regra não exclui o achado"
        elif not t.medida and not casa and not _suporte_alem_das_regras(t, summary):
            return f"afirmação sobre {t.nome} sem regra correspondente"
    return None


Substituto = Callable[[str], Optional[str]]


def filter_text(text: str, summary: dict, replace: Optional[Substituto] = None) -> tuple[str, int]:
    """Remove as frases sem lastro; devolve (texto, nº de frases removidas). Sem remoção, o texto sai intacto.
    `replace(frase)` pode devolver um aviso curto (sem o conteúdo removido) para ficar no lugar da frase."""
    if not text or not text.strip():
        return text, 0
    parts = _SPLIT.split(text)
    kept: list[str] = []
    removed = 0
    for i in range(0, len(parts), 2):
        sent = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        if sent.strip() and sentence_problem(sent, summary):
            removed += 1
            note = replace(sent) if replace else None
            if note:
                kept.append(note + sep)
            continue
        kept.append(sent + sep)
    return ("".join(kept).strip(), removed) if removed else (text, 0)


def filter_items(items: list[str], summary: dict, replace: Optional[Substituto] = None) -> tuple[list[str], int]:
    """Aplica filter_text a cada item de uma lista; itens que ficam vazios saem."""
    out: list[str] = []
    removed = 0
    for it in items:
        new, n = filter_text(it, summary, replace)
        removed += n
        if new.strip():
            out.append(new)
    return out, removed


def finding_problem(code: str, label: str, summary: dict) -> Optional[str]:
    """Motivo de o achado `ia.*` (código/rótulo) não ter lastro nas regras (None = ok)."""
    return sentence_problem(label, summary) or sentence_problem(re.sub(r"[._]+", " ", code or ""), summary)


def removed_note(n: int) -> str:
    return f"{n} frase sem lastro removida" if n == 1 else f"{n} frases sem lastro removidas"


FALHA_NOTE = "barreira de verificação falhou: narrativa descartada"
