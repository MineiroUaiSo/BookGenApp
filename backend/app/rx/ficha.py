"""Ficha de fatos do RX (`rx_ficha/v1`): o que o app SABE (fatos F com origem e nível) e o que NÃO avaliou (cobertura).

Base do laudo determinístico (spec RX-LAUDO-CONFIAVEL §2): nada entra no laudo sem um fato; região sem fato = não avaliada.
Puro Python, modelos imutáveis, ids F1..Fn estáveis pela ordem de construção."""
from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict

from ..schemas import BodyRegion, Finding, RXAnalysis, RXImageAnalysis, RXView
from . import calibration as CAL
from .findings import PATHO_PT, model_threshold

VERSAO = "rx_ficha/v1"
REGIOES = ("pleura", "pulmoes", "mediastino_hilos", "coracao_vasos", "diafragma", "ossos_partes_moles", "dispositivos")
LIMITE_ICT = 0.50
ZONAS_COM_FATO = (CAL.ZONE_SUGGESTIVE, CAL.ZONE_INDETERMINATE)


class Nivel(str, Enum):
    MEDIDO = "MEDIDO"
    REGRA = "REGRA"
    SUGERIDO_MODELO = "SUGERIDO_MODELO"
    NAO_AVALIADO = "NAO_AVALIADO"
    QUALIDADE = "QUALIDADE"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Fato(_Frozen):
    id: str
    chave: str
    valor: Optional[Union[float, str]] = None
    unidade: Optional[str] = None
    nivel: Nivel
    regiao: str                         # uma de REGIOES ou "tecnica"
    origem: str                         # modelo | heuristica | regra | tag
    imagem: int = 1
    fontes: tuple[str, ...] = ()
    ressalvas: tuple[str, ...] = ()
    zona: Optional[str] = None


class CoberturaRegiao(_Frozen):
    regiao: str
    avaliada: bool                      # há fato MEDIDO/REGRA (o app mediu algo nesta região)
    sinal_modelo: bool                  # só há escore de modelo auxiliar (não conta como avaliada)
    nivel: Nivel
    fatos: tuple[str, ...]
    escopo: str                         # o que foi (ou não) avaliado, em texto curto


class Ficha(_Frozen):
    versao: str = VERSAO
    incidencias: tuple[str, ...]
    fora_de_escopo: bool = False
    motivo_fora_de_escopo: Optional[str] = None
    fatos: tuple[Fato, ...]
    cobertura: tuple[CoberturaRegiao, ...]
    ressalvas: tuple[str, ...] = ()


_ESCOPO_NAO = "não avaliado nesta análise automática"
_ESCOPO_PARCIAL = {
    "pulmoes": "somente assimetria de área pulmonar; opacidades, nódulos e padrão intersticial não avaliados",
    "mediastino_hilos": "largura do mediastino e desvio traqueal; hilos não avaliados",
    "diafragma": "diferença de altura das cúpulas; ar livre subdiafragmático não avaliado",
    "coracao_vasos": "índice cardiotorácico; contorno e vasos não avaliados",
}
_REGIAO_PATOLOGIA = {
    "Effusion": "pleura", "Pleural_Thickening": "pleura", "Pneumothorax": "pleura",
    "Cardiomegaly": "coracao_vasos", "Enlarged Cardiomediastinum": "mediastino_hilos",
    "Fracture": "ossos_partes_moles", "Hernia": "diafragma",
}  # o resto das patologias do modelo cai em "pulmoes"
_QUALIDADE = (("rotação", "rotacao"), ("inspiração", "inspiracao"), ("penetração", "penetracao"))
_ORDEM_NIVEL = (Nivel.REGRA, Nivel.MEDIDO, Nivel.SUGERIDO_MODELO, Nivel.QUALIDADE, Nivel.NAO_AVALIADO)


def _origem_img(img: RXImageAnalysis, *chaves: str) -> str:
    for s in img.structures:
        if s.key in chaves:
            return "modelo" if s.origin in ("model", "cxas") else "heuristica"
    if img.structures:
        return "modelo" if img.structures[0].origin in ("model", "cxas") else "heuristica"
    return "heuristica"


def _estado_qualidade(txt: str) -> str:
    t = (txt or "").lower()
    if t.startswith("adequad"):
        return "adequada"
    if t.startswith("possível") or t.startswith("possivelmente"):
        return "possivelmente_inadequada"
    return "indeterminada"


def _medida(img: RXImageAnalysis, key: str) -> Optional[tuple[float, Optional[str]]]:
    for m in img.measurements:
        if m.key == key and m.value is not None:
            return float(m.value), m.unit
    return None


def _regra(codigos: set[str], *prefixos: str) -> bool:
    return any(c.startswith(p) for c in codigos for p in prefixos)


class _Builder:
    def __init__(self) -> None:
        self.fatos: list[Fato] = []

    def add(self, chave: str, valor, nivel: Nivel, regiao: str, origem: str, imagem: int, unidade=None,
            fontes=(), ressalvas=(), zona=None) -> None:
        self.fatos.append(Fato(id=f"F{len(self.fatos) + 1}", chave=chave, valor=valor, unidade=unidade, nivel=nivel,
                               regiao=regiao, origem=origem, imagem=imagem, fontes=tuple(fontes),
                               ressalvas=tuple(ressalvas), zona=zona))


def _qualidade(b: _Builder, img: RXImageAnalysis, n: int) -> None:
    b.add("incidencia", img.view.value, Nivel.QUALIDADE, "tecnica", "tag", n, fontes=("S1",))
    for chave_q, chave in _QUALIDADE:
        b.add(chave, _estado_qualidade(img.quality.get(chave_q, "")), Nivel.QUALIDADE, "tecnica", "heuristica", n,
              fontes=("S1",), ressalvas=("estimativa automática",))


def _ict(b: _Builder, img: RXImageAnalysis, n: int) -> None:
    m = _medida(img, "cardiothoracic_ratio")
    if m is None:
        return
    if _origem_img(img, "heart") != "modelo":
        b.add("ict", None, Nivel.NAO_AVALIADO, "coracao_vasos", "heuristica", n,
              ressalvas=("segmentação heurística de baixa confiabilidade",))
        return
    ap = img.view == RXView.AP
    nivel = Nivel.REGRA if m[0] > LIMITE_ICT else Nivel.MEDIDO
    b.add("ict", m[0], nivel, "coracao_vasos", "modelo", n, fontes=("S6",),
          ressalvas=("incidência AP magnifica a silhueta cardíaca; não usar para afirmar cardiomegalia",) if ap else ())


_OUTRAS = (  # chave da ficha, medida, região, prefixos de regra, estruturas de origem, nome do tópico
    ("mediastino_largura_mm", "mediastinal_width", "mediastino_hilos", ("rx.mediastinal_widening",), ("mediastinum", "heart")),
    ("mediastino_largura_pct", "mediastinal_width_ratio", "mediastino_hilos", ("rx.mediastinal_widening",), ("mediastinum", "heart")),
    ("traqueia_desvio_pct", "tracheal_deviation_pct", "mediastino_hilos", ("rx.tracheal_deviation",), ("trachea", "heart")),
    ("cupulas_diferenca_pct", "hemidiaphragm_height_difference_pct", "diafragma", ("rx.hemidiaphragm_elevation",), ("right_lung", "left_lung")),
    ("pulmoes_razao_area_E_D", "lung_area_ratio_L_R", "pulmoes", ("rx.lung_volume_asymmetry",), ("right_lung", "left_lung")),
)


def _outras(b: _Builder, img: RXImageAnalysis, n: int, codigos: set[str]) -> None:
    for chave, mkey, regiao, prefixos, estruturas in _OUTRAS:
        m = _medida(img, mkey)
        if m is None:
            continue
        if _origem_img(img, *estruturas) != "modelo":
            b.add(chave, None, Nivel.NAO_AVALIADO, regiao, "heuristica", n,
                  ressalvas=("segmentação heurística de baixa confiabilidade",))
            continue
        regra = _regra(codigos, *prefixos)
        # limiares locais sem fonte primária (spec §7): REGRA "heurística local", sem fonte citável
        b.add(chave, m[0], Nivel.REGRA if regra else Nivel.MEDIDO, regiao, "modelo", n, unidade=m[1],
              ressalvas=("limiar local sem fonte primária (heurística local)",) if regra else ())


def _modelo(b: _Builder, img: RXImageAnalysis, n: int) -> None:
    for k in PATHO_PT:
        raw, prob = img.model_scores.get(k), img.model_probs.get(k)
        zona = img.model_zones.get(k)
        if zona is None:
            if raw is None or raw < model_threshold(k):
                continue
            zona, valor, rs = CAL.ZONE_SUGGESTIVE, round(float(raw), 3), ["escore bruto, sem calibração"]
        else:
            if zona not in ZONAS_COM_FATO:
                continue                     # nao_sugerido nunca vira frase de ausência (D1)
            valor, rs = (round(float(prob), 3) if prob is not None else None), []
        if k in CAL.INSUFFICIENT_EVIDENCE:
            zona = CAL.ZONE_INDETERMINATE
            rs.append("evidência insuficiente: não permite afirmar nem afastar")
        b.add("modelo." + k.lower().replace(" ", "_"), valor, Nivel.SUGERIDO_MODELO,
              _REGIAO_PATOLOGIA.get(k, "pulmoes"), "modelo", n, fontes=("S5",), ressalvas=rs, zona=zona)


def _cobertura(fatos: tuple[Fato, ...]) -> tuple[CoberturaRegiao, ...]:
    out = []
    for r in REGIOES:
        fs = [f for f in fatos if f.regiao == r]
        aval = any(f.nivel in (Nivel.MEDIDO, Nivel.REGRA) for f in fs)
        sinal = not aval and any(f.nivel == Nivel.SUGERIDO_MODELO for f in fs)
        nivel = next((n for n in _ORDEM_NIVEL if any(f.nivel == n for f in fs)), Nivel.NAO_AVALIADO)
        out.append(CoberturaRegiao(regiao=r, avaliada=aval, sinal_modelo=sinal, nivel=nivel,
                                   fatos=tuple(f.id for f in fs),
                                   escopo=_ESCOPO_PARCIAL.get(r, _ESCOPO_NAO) if aval else _ESCOPO_NAO))
    return tuple(out)


def build_ficha(a: RXAnalysis) -> Ficha:
    b = _Builder()
    codigos = {f.code.lower() for f in a.findings}
    incid: list[str] = []
    fora: Optional[str] = None
    ressalvas: list[str] = []
    for n, img in enumerate(a.images, 1):
        incid.append(img.view.value)
        if img.region_uncertain or img.out_of_scope or img.region != BodyRegion.CHEST:
            fora = fora or img.scope_reason or "imagem fora do escopo de RX de tórax adulto ou região incerta"
            continue
        _qualidade(b, img, n)
        if img.view in (RXView.PA, RXView.AP):
            _ict(b, img, n)
            _outras(b, img, n, codigos)
            _modelo(b, img, n)
            if img.view == RXView.AP:
                ressalvas.append("incidência AP: magnifica o coração e o mediastino; medidas com ressalva")
        else:
            ressalvas.append("incidência sem medidas automáticas (perfil/outra): nenhuma região foi medida")
    if b.fatos:
        b.add("dispositivos", None, Nivel.NAO_AVALIADO, "dispositivos", "heuristica", 1,
              ressalvas=("tubos, cateteres e marca-passo não são avaliados",))
    fatos = tuple(b.fatos)
    return Ficha(incidencias=tuple(incid), fora_de_escopo=fora is not None and not fatos, motivo_fora_de_escopo=fora,
                 fatos=fatos, cobertura=_cobertura(fatos), ressalvas=tuple(ressalvas))
