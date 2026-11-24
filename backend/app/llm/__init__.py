"""Relatórios de IA (Claude) para ECG e RX: descrição minuciosa + análise crítica estruturada."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from ..knowledge import (format_items, format_references, known_reference_ids, load_criteria,
                         select_relevant)
from ..schemas import AIReport, ECGAnalysis, RXAnalysis
from . import client as _client
from .client import ai_available, model_name  # noqa: F401  (API pública)
from .render import render_ecg_plot, rx_image_png, rx_overlay_png
from .schema import output_schema, to_report
from .validate import validate_report

log = logging.getLogger("medlens.llm")
PROMPTS = Path(__file__).parent / "prompts"

__all__ = ["ai_available", "ecg_report", "rx_report", "model_name"]


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def unavailable(reason: str | None = None) -> AIReport:
    lim = ["IA indisponível: defina ANTHROPIC_API_KEY (ou ANTHROPIC_AUTH_TOKEN) e instale o pacote 'anthropic', ou defina OPENROUTER_API_KEY (fallback)."]
    if reason:
        lim.append(reason)
    return AIReport(available=False, model=None, limitations=lim)


def _system_blocks(domain: str) -> list[dict]:
    """Blocos estáticos (cacheáveis): método + conhecimento completo + referências."""
    knowledge = format_items(load_criteria(domain))  # type: ignore[arg-type]
    refs = format_references()
    return [
        {"type": "text", "text": _prompt(f"{domain}_system")},
        {"type": "text",
         "text": f"CONHECIMENTO (critérios reescritos; use como base)\n{knowledge}\n\nREFERÊNCIAS (ids permitidos)\n{refs}",
         "cache_control": {"type": "ephemeral"}},
    ]


def _round(o: Any, nd: int = 2) -> Any:
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items() if v is not None}
    if isinstance(o, list):
        return [_round(v, nd) for v in o]
    return o


def ecg_data_summary(a: ECGAnalysis) -> dict:
    return _round({
        "fonte": a.signal.source.value,
        "fs_hz": a.signal.fs,
        "duracao_s": a.signal.duration_s,
        "calibracao": a.signal.calibration,
        "qualidade_por_derivacao": a.signal.quality,
        "medidas_globais": a.global_measurements.model_dump(exclude_none=True),
        "medidas_por_derivacao": [m.model_dump(exclude_none=True) for m in a.lead_measurements],
        "n_picos_R": len(a.r_peaks_ms),
        "achados_por_regras": [f.model_dump(include={"code", "label", "severity", "evidence"}) for f in a.findings],
        "avisos": a.warnings,
    })


def rx_data_summary(a: RXAnalysis) -> dict:
    imgs = []
    for im in a.images:
        imgs.append(_round({
            "instance_id": im.instance_id,
            "incidencia": im.view.value,
            "regiao": im.region.value,
            "tamanho_px": [im.width, im.height],
            "pixel_spacing_mm": im.pixel_spacing_mm,
            "qualidade": im.quality,
            "medidas": [m.model_dump(include={"key", "label", "value", "unit", "normal_range"}, exclude_none=True)
                        for m in im.measurements],
            "probabilidades_modelo_auxiliar": im.model_scores,
            "estruturas_segmentadas": [{"chave": s.key, "rotulo": s.label, "bbox": s.bbox,
                                         "area_mm2": s.area_mm2, "confianca": s.confidence}
                                        for s in im.structures],
        }))
    return {"imagens": imgs,
            "achados_por_regras": [f.model_dump(include={"code", "label", "severity", "evidence"}) for f in a.findings],
            "avisos": a.warnings}


def _user_context(domain: str, data: dict, findings, measurement_keys) -> str:
    rel = select_relevant(domain, findings, measurement_keys)  # type: ignore[arg-type]
    ids = ", ".join(i["id"] for i in rel)
    return (f"DADOS DETERMINÍSTICOS (JSON)\n{json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"
            f"Critérios do bloco de CONHECIMENTO mais pertinentes a estes dados: {ids}.")


def _two_stage(domain: str, images: list[tuple[str, bytes]], context: str,
               summary: Optional[dict] = None, rule_findings: Optional[list] = None) -> AIReport:
    c = _client
    client = c.make_client()
    system = _system_blocks(domain)
    content: list[dict] = []
    for caption, png in images:
        content.append({"type": "text", "text": caption})
        content.append(c.image_block(png))
    content.append({"type": "text", "text": context})
    model = c.model_name()
    try:
        # Etapa 1: descrição minuciosa (visão), sem saída estruturada.
        desc, _ = c.run(client, system,
                        [{"role": "user", "content": content + [{"type": "text", "text": _prompt(f"{domain}_describe")}]}],
                        c.MAX_TOKENS_DESCRIBE)
        # Etapa 2: análise crítica com saída estruturada.
        refs = sorted(known_reference_ids())
        msgs = [{"role": "user", "content": content + [
            {"type": "text", "text": f"DESCRIÇÃO DA ETAPA 1\n{desc}"},
            {"type": "text", "text": _prompt("analyze")},
        ]}]
        text, final = c.run(client, system, msgs, c.MAX_TOKENS_ANALYZE, schema=output_schema(refs))
        data = c.parse_json(text)
        rep = to_report(data, getattr(final, "model", None) or model, description_fallback=desc)
        if summary is not None:
            try:
                rep = validate_report(rep, summary, rule_findings)
            except Exception:  # validador nunca derruba o laudo
                log.exception("validate_report failure")
        return rep
    except c.LLMRefusal as e:
        return AIReport(available=True, model=model,
                        limitations=[f"O modelo recusou a requisição ({e}). Revisão humana necessária."])
    except c.LLMTruncated:
        return AIReport(available=True, model=model,
                        limitations=["Resposta do modelo truncada (limite de tokens); tente novamente."])
    except json.JSONDecodeError:
        return AIReport(available=True, model=model,
                        limitations=["A resposta estruturada do modelo não pôde ser interpretada."])
    except _client.LLMProviderError as e:
        log.warning("llm provider failure: %s", e)
        return AIReport(available=False, model=model, limitations=[str(e)])
    except Exception as e:  # erros tipados da API (anthropic.*) e demais
        try:
            import anthropic
        except ImportError:
            log.exception("llm failure")
            return AIReport(available=False, model=model, limitations=[f"Erro inesperado na IA: {type(e).__name__}"])

        if isinstance(e, anthropic.RateLimitError):
            msg = "Limite de requisições da API atingido; tente novamente em instantes."
        elif isinstance(e, anthropic.AuthenticationError):
            msg = "Credenciais da API inválidas."
        elif isinstance(e, anthropic.APIConnectionError):
            msg = "Falha de conexão com a API."
        elif isinstance(e, anthropic.APIStatusError):
            msg = f"Erro da API ({e.status_code})."
        else:
            msg = f"Erro inesperado na IA: {type(e).__name__}"
        log.exception("llm failure")
        return AIReport(available=False, model=model, limitations=[msg])


def ecg_report(analysis: ECGAnalysis, image_png: Optional[bytes] = None) -> AIReport:
    if not ai_available():
        return unavailable()
    images: list[tuple[str, bytes]] = []
    if image_png:
        images.append(("Imagem original do ECG (foto/impressão/captura):", image_png))
    plot = render_ecg_plot(analysis)
    if plot:
        images.append(("Plot dos 12 derivações a partir do sinal processado, em grade 25 mm/s e 10 mm/mV:", plot))
    ctx = _user_context("ecg", ecg_data_summary(analysis), analysis.findings,
                        [k for k, v in analysis.global_measurements.model_dump().items() if v is not None])
    summary = ecg_data_summary(analysis)
    rep = _two_stage("ecg", images, ctx, summary, analysis.findings)
    if not images and rep.available:
        rep.limitations.append("Sem imagem do traçado; análise baseada somente nas medidas.")
    return rep


def rx_report(analysis: RXAnalysis) -> AIReport:
    if not ai_available():
        return unavailable()
    images: list[tuple[str, bytes]] = []
    for im in analysis.images[:6]:
        tag = f"{im.view.value} / {im.region.value} (id {im.instance_id})"
        images.append((f"Radiografia {tag}:", rx_image_png(im)))
        ov = rx_overlay_png(im)
        if ov:
            images.append((f"Sobreposição da segmentação automática com legenda de cores, {tag}:", ov))
    keys = [m.key for im in analysis.images for m in im.measurements]
    ctx = _user_context("rx", rx_data_summary(analysis), analysis.findings, keys)
    return _two_stage("rx", images, ctx, rx_data_summary(analysis), analysis.findings)
