"""Esquema de saída estruturada do LLM e conversão para AIReport."""
from __future__ import annotations

from typing import Any

from ..knowledge import is_known_reference, reference
from ..schemas import AIReport, Differential, Finding

SEVERITIES = ["normal", "borderline", "abnormal", "critical"]


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props),
            "additionalProperties": False}


_STR = {"type": "string"}
_STRS = {"type": "array", "items": {"type": "string"}}
_NUM = {"type": "number"}


def output_schema(reference_ids: list[str] | None = None) -> dict:
    """JSON Schema (estrito) para output_config.format. Sem minimum/maximum (não suportados)."""
    ref_items: dict = {"type": "string"}
    if reference_ids:
        ref_items = {"type": "string", "enum": sorted(reference_ids)}
    refs = {"type": "array", "items": ref_items}
    finding = _obj({
        "code": _STR, "label": _STR, "severity": {"type": "string", "enum": SEVERITIES},
        "evidence": _STRS, "references": refs, "confidence": _NUM,
    })
    diff = _obj({
        "diagnosis": _STR, "rationale": _STR, "supporting": _STRS, "against": _STRS,
        "references": refs, "confidence": _NUM,
    })
    return _obj({
        "description": _STR,
        "findings": {"type": "array", "items": finding},
        "differentials": {"type": "array", "items": diff},
        "disagreements_with_measurements": _STRS,
        "limitations": _STRS,
    })


def _clamp(x: Any) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.5


def _refs(ids: Any, dropped: list[str]):
    out, seen = [], set()
    for i in ids or []:
        if not isinstance(i, str):
            continue
        if not is_known_reference(i):
            dropped.append(i)
            continue
        if i not in seen:
            seen.add(i)
            out.append(reference(i))
    return out


def to_report(data: dict, model: str | None, description_fallback: str = "") -> AIReport:
    """Converte o JSON do modelo em AIReport validando referências contra references.yaml."""
    dropped: list[str] = []
    findings = []
    for f in data.get("findings") or []:
        sev = f.get("severity")
        findings.append(Finding(
            code=str(f.get("code") or "llm.finding"),
            label=str(f.get("label") or f.get("code") or ""),
            severity=sev if sev in SEVERITIES else "abnormal",
            evidence=[str(e) for e in f.get("evidence") or []],
            references=_refs(f.get("references"), dropped),
            confidence=_clamp(f.get("confidence")),
            origin="llm",
        ))
    diffs = []
    for d in data.get("differentials") or []:
        diffs.append(Differential(
            diagnosis=str(d.get("diagnosis") or ""),
            rationale=str(d.get("rationale") or ""),
            supporting=[str(s) for s in d.get("supporting") or []],
            against=[str(s) for s in d.get("against") or []],
            references=_refs(d.get("references"), dropped),
            confidence=_clamp(d.get("confidence")),
        ))
    limitations = [str(x) for x in data.get("limitations") or []]
    return AIReport(
        available=True,
        model=model,
        description=str(data.get("description") or description_fallback),
        findings=findings,
        differentials=diffs,
        disagreements_with_measurements=[str(x) for x in data.get("disagreements_with_measurements") or []],
        limitations=limitations,
    )
