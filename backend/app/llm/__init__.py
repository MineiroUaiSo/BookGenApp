"""Relatórios de IA (Claude) para ECG e RX: descrição minuciosa + análise crítica estruturada."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from ..dicom.burned_text import scrub_enabled
from ..knowledge import (format_items, format_references, known_reference_ids, load_criteria,
                         select_relevant)
from ..rx import claim_check
from ..schemas import AIReport, ECGAnalysis, RXAnalysis
from . import client as _client
from . import laudo as laudo_mod
from .anon import anonymize_text
from .client import ai_available, model_name  # noqa: F401  (API pública)
from .guard import PayloadBloqueado, assert_text_only
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


def blocked_external(analysis: RXAnalysis) -> AIReport:
    """Política PHI: imagem com texto queimado (tag YES, ou detectado e não mascarado) não vai ao provedor
    externo; as regras/medidas locais seguem valendo."""
    why = "; ".join(f"{im.instance_id}: {im.burned_text}" for im in analysis.images[:6] if im.external_ai_blocked)
    return AIReport(available=False, model=None, external_ai_blocked=True,
                    limitations=["imagem com texto queimado não enviada à IA externa (regras e medidas locais "
                                 "permanecem válidas).", why])


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


def rx_data_summary(a: RXAnalysis, *, anonymize: bool = False) -> dict:
    """Resumo determinístico do RX. anonymize=True (texto que vai ao provedor): instance_id vira 'img<n>' e as
    strings livres perdem study_id, UIDs, datas e idade exata (idade só por faixa)."""
    imgs = []
    for n, im in enumerate(a.images, 1):
        imgs.append(_round({
            "instance_id": f"img{n}" if anonymize else im.instance_id,
            "incidencia": im.view.value,
            "regiao": im.region.value,
            "tamanho_px": [im.width, im.height],
            "pixel_spacing_mm": im.pixel_spacing_mm,
            "qualidade": im.quality,
            "medidas": [m.model_dump(include={"key", "label", "value", "unit", "normal_range"}, exclude_none=True)
                        for m in im.measurements],
            "probabilidades_modelo_auxiliar": im.model_probs or im.model_scores,
            "zonas_modelo_auxiliar": im.model_zones or None,
            "estruturas_segmentadas": [{"chave": s.key, "rotulo": s.label, "bbox": s.bbox,
                                         "area_mm2": s.area_mm2, "confianca": s.confidence}
                                        for s in im.structures],
        }))
    out = {"imagens": imgs,
           "achados_por_regras": [f.model_dump(include={"code", "label", "severity", "evidence"}) for f in a.findings],
           "avisos": a.warnings}
    if not anonymize:
        return out
    ids = [a.study_id, *(im.instance_id for im in a.images)]
    return json.loads(anonymize_text(json.dumps(out, ensure_ascii=False), ids))


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
        desc, _, prov1 = c.run_resilient(
            client, system,
            [{"role": "user", "content": content + [{"type": "text", "text": _prompt(f"{domain}_describe")}]}],
            c.MAX_TOKENS_DESCRIBE, allow_images=bool(images))
        # Etapa 2: análise crítica com saída estruturada.
        refs = sorted(known_reference_ids())
        msgs = [{"role": "user", "content": content + [
            {"type": "text", "text": f"DESCRIÇÃO DA ETAPA 1\n{desc}"},
            {"type": "text", "text": _prompt("analyze")},
        ]}]
        text, final, prov2 = c.run_resilient(client, system, msgs, c.MAX_TOKENS_ANALYZE, schema=output_schema(refs),
                                             allow_images=bool(images))
        data = c.parse_json(text)
        rep = to_report(data, getattr(final, "model", None) or model, description_fallback=desc)
        rep = rep.model_copy(update={"provider": prov2 if prov1 == prov2 else f"{prov1}+{prov2}"})
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
    except c.PayloadBloqueado as e:
        log.warning("llm payload blocked (LGPD): %s", e)
        return AIReport(available=False, model=model,
                        limitations=[f"Envio à IA bloqueado pela barreira LGPD ({e}); nada foi enviado."])
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


def laudo_enabled() -> bool:
    return os.environ.get("MEDLENS_LAUDO", "1") != "0"


def _laudo_call(system: str, user: str) -> str:
    c = _client
    text, _, _ = c.run_resilient(c.make_client(), [{"type": "text", "text": system}],
                                 [{"role": "user", "content": user}], c.MAX_TOKENS_LAUDO,
                                 schema=laudo_mod.output_schema())
    return text


def ecg_laudo_fields(summary: dict, *, printed_header: Optional[dict] = None, sexo: Optional[str] = None,
                     call: Optional[laudo_mod.LLMCall] = None) -> dict:
    """Campos novos do AIReport (laudo, laudo_markdown, laudo_curto); {} se falhar (nunca derruba o relatório)."""
    try:
        susp = next((w for w in summary.get("avisos") or [] if re.search(r"suspeit|diverg", str(w), re.I)), None)
        prepared = laudo_mod.prepare_summary(summary, printed_header=printed_header, sexo=sexo,
                                             digitalizacao_suspeita=susp)
        lau = laudo_mod.generate_laudo(prepared, call or _laudo_call)
        return {"laudo": lau.model_dump(), "laudo_markdown": laudo_mod.render_markdown(lau),
                "laudo_curto": laudo_mod.render_short(lau)}
    except Exception:
        log.exception("laudo failure")
        return {}


def ecg_report_v2(analysis: ECGAnalysis, *, printed_header: Optional[dict] = None,
                  sexo: Optional[str] = None, call: Optional[laudo_mod.LLMCall] = None) -> AIReport:
    """Laudo v2 (MEDLENS_LAUDO_V2=1): ficha ecg_features/v1 -> UMA chamada só de texto (sem imagem, sem cabeçalho)
    -> afirmações citadas validadas em código; qualquer falha vira abstenção explícita, nunca texto inventado."""
    from ..ecg.features import features_from_analysis   # import tardio: evita ciclo llm <-> ecg
    ficha = features_from_analysis(analysis, printed_header=printed_header, sexo=sexo)
    schema = laudo_mod.output_schema_v2(ficha)
    provider: dict[str, Optional[str]] = {"name": None}

    def _call(system: str, user: str) -> str:
        c = _client
        text, _, prov = c.run_resilient(c.make_client(), [{"type": "text", "text": system}],
                                        [{"role": "user", "content": user}], c.MAX_TOKENS_LAUDO, schema=schema,
                                        allow_images=False)
        provider["name"] = prov
        return text

    lau = laudo_mod.generate_laudo_v2(ficha, call or _call)
    curto = laudo_mod.render_short_v2(lau)
    return AIReport(available=True, model=model_name(), provider=provider["name"], validation=lau.validacao,
                    description=curto, disagreements_with_measurements=list(lau.aviso_topo),
                    limitations=list(lau.abstencao.motivos) if lau.abstencao else [],
                    laudo=lau.model_dump(), laudo_markdown=laudo_mod.render_markdown_v2(lau, ficha),
                    laudo_curto=curto)


def ecg_report(analysis: ECGAnalysis, image_png: Optional[bytes] = None, *, printed_header: Optional[dict] = None,
               sexo: Optional[str] = None) -> AIReport:
    if not ai_available():
        return unavailable()
    if laudo_enabled() and laudo_mod.v2_enabled():
        del image_png   # LGPD: v2 é só texto
        try:
            return ecg_report_v2(analysis, printed_header=printed_header, sexo=sexo)
        except Exception:
            log.exception("laudo v2 failure")
            return AIReport(available=False, model=model_name(),
                            limitations=["Sem laudo automático confiável: falha interna no laudo v2."])
    # LGPD: a foto/captura original do ECG (cabeçalho com nome, data de nascimento etc.) NUNCA vai ao
    # provedor externo. image_png é aceito só por compatibilidade de assinatura e é ignorado; ao LLM vai
    # apenas o plot renderizado do sinal digitalizado (sem cabeçalho) e o texto das medidas/achados.
    del image_png
    images: list[tuple[str, bytes]] = []
    plot = render_ecg_plot(analysis)
    if plot:
        images.append(("Plot dos 12 derivações a partir do sinal processado, em grade 25 mm/s e 10 mm/mV:", plot))
    ctx = _user_context("ecg", ecg_data_summary(analysis), analysis.findings,
                        [k for k, v in analysis.global_measurements.model_dump().items() if v is not None])
    summary = ecg_data_summary(analysis)
    rep = _two_stage("ecg", images, ctx, summary, analysis.findings)
    if not images and rep.available:
        rep.limitations.append("Sem imagem do traçado; análise baseada somente nas medidas.")
    if rep.available and laudo_enabled():
        extra = ecg_laudo_fields(summary, printed_header=printed_header, sexo=sexo)
        if extra:
            rep = rep.model_copy(update=extra)
    return rep


def rx_image_ai_mode() -> str:
    """MEDLENS_RX_IMAGE_AI: 'optin' (padrão: a imagem só vai à IA com consentimento da requisição) | 'off' (nunca)."""
    v = os.environ.get("MEDLENS_RX_IMAGE_AI", "optin").strip().lower()
    return "off" if v in ("off", "0", "false", "no") else "optin"


def blocked_scrub_off() -> AIReport:
    """Com a máscara de texto queimado desligada não há garantia de imagem limpa: nada de imagem ao provedor externo."""
    return AIReport(available=False, model=None, external_ai_blocked=True,
                    limitations=["Imagem NÃO enviada à IA externa: a detecção de texto queimado está desligada "
                                 "(MEDLENS_BURNED_TEXT=off), então não há garantia de que a imagem esteja livre de "
                                 "identificação (regras e medidas locais permanecem válidas)."])


_SEM_IMAGEM_CTX = ("\n\nNenhuma imagem anexada: a imagem da radiografia NÃO foi enviada. Baseie-se SOMENTE nas medidas e "
                   "regras acima; não descreva nem presuma achados visuais.")


def rx_report(analysis: RXAnalysis, send_images: bool = False) -> AIReport:
    """Texto de IA do RX. A IMAGEM só sai com consentimento explícito (send_images) e sem texto queimado; sem isso a
    análise usa apenas medidas/regras (sem imagem no payload) e a limitação fica explícita no laudo."""
    if not ai_available():
        return unavailable()
    motivo_sem_imagem = None
    if rx_image_ai_mode() == "off":
        motivo_sem_imagem = "envio de imagem desativado no servidor (MEDLENS_RX_IMAGE_AI=off)"
    elif not send_images:
        motivo_sem_imagem = "sem consentimento do usuário para enviar a imagem à IA na nuvem"
    if motivo_sem_imagem is None:
        if any(im.external_ai_blocked for im in analysis.images[:6]):
            return blocked_external(analysis)
        if not scrub_enabled():
            return blocked_scrub_off()
    images: list[tuple[str, bytes]] = []
    for n, im in enumerate(analysis.images[:6], 1):
        if motivo_sem_imagem is not None:
            break
        tag = f"{im.view.value} / {im.region.value} (img{n})"
        images.append((f"Radiografia {tag}:", rx_image_png(im)))
        ov = rx_overlay_png(im)
        if ov:
            images.append((f"Sobreposição da segmentação automática com legenda de cores, {tag}:", ov))
    keys = [m.key for im in analysis.images for m in im.measurements]
    ctx = _user_context("rx", rx_data_summary(analysis, anonymize=True), analysis.findings, keys)
    if motivo_sem_imagem is not None:
        ctx += _SEM_IMAGEM_CTX
    # Barreira LGPD do texto em TODO caminho (com ou sem imagem): o texto do RX nunca sai sem passar por ela.
    try:
        assert_text_only("\n".join(b["text"] for b in _system_blocks("rx")), ctx)
    except PayloadBloqueado as e:
        log.warning("rx text payload blocked (LGPD): %s", e)
        return AIReport(available=False, model=model_name(),
                        limitations=[f"Envio à IA bloqueado pela barreira LGPD ({e}); nada foi enviado."])
    rep = _two_stage("rx", images, ctx, rx_data_summary(analysis), analysis.findings)
    try:   # barreira qualitativa do RX: sem lastro nos fatos, a frase sai (spec RX-LAUDO-CONFIAVEL §3.1)
        rep = claim_check.sanitize_report(rep, rx_data_summary(analysis), image_sent=motivo_sem_imagem is None)
    except Exception:  # a barreira nunca derruba o laudo
        log.exception("rx claim_check failure")
    if motivo_sem_imagem is not None:
        rep.limitations.append(f"Imagem NÃO enviada à IA ({motivo_sem_imagem}); análise apenas pelas medidas e regras locais.")
    return rep
