"""Laudo determinístico de RX de tórax (`rx_laudo/v1`, spec RX-LAUDO-CONFIAVEL §2). Sem IA: cada frase nasce de um fato da
ficha (`rx_ficha/v1`) ou de uma região sem fato ("não avaliado nesta análise automática"). Nunca diz normal/livre/afasta."""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel, ConfigDict

from . import fontes as FT
from . import lexico as LX
from .ficha import REGIOES, Ficha, Nivel, build_ficha
from .findings import PATHO_PT
from ..schemas import RXAnalysis

VERSAO = "rx_laudo/v1"
TITULOS = {"identificacao_tecnica": "Identificação e técnica", "qualidade": "Qualidade técnica e limitações",
           "achados": "Achados por região", "sinais_modelo": "Sinais do modelo auxiliar",
           "impressao": "Impressão", "recomendacoes": "Recomendações", "revisao_medica": "Revisão médica"}
NOMES = {"pleura": "Pleura", "pulmoes": "Pulmões", "mediastino_hilos": "Mediastino e hilos",
         "coracao_vasos": "Coração e vasos", "diafragma": "Diafragma", "ossos_partes_moles": "Ossos e partes moles",
         "dispositivos": "Dispositivos"}
# o que continua não avaliado quando a região foi medida só em parte
_RESTO = {"coracao_vasos": "contorno cardíaco e vasos não avaliados", "pulmoes": "opacidades, nódulos e padrão "
          "intersticial não avaliados", "mediastino_hilos": "hilos não avaliados",
          "diafragma": "ar livre subdiafragmático não avaliado"}
CRITICO = ("Pneumotórax, pneumoperitônio e posição de tubos/cateteres NÃO são avaliados por esta análise: "
           "revisar a imagem.")
_LIMIAR_LOCAL = "acima do limiar local (heurística local, sem fonte primária; correlacionar)"
_ROTULO = {"mediastino_largura_mm": "Largura do mediastino", "mediastino_largura_pct": "Largura do mediastino",
           "traqueia_desvio_pct": "Desvio traqueal", "cupulas_diferenca_pct": "Diferença de altura das cúpulas",
           "pulmoes_razao_area_E_D": "Razão de área pulmonar E/D", "ict": "Silhueta cardíaca"}
_ORDEM_IMPRESSAO = ("ict", "mediastino_largura_pct", "mediastino_largura_mm", "traqueia_desvio_pct",
                    "cupulas_diferenca_pct", "pulmoes_razao_area_E_D")
_PATOLOGIA_DE = {"modelo." + k.lower().replace(" ", "_"): v for k, v in PATHO_PT.items()}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Frase(_Frozen):
    secao: str
    texto: str
    fatos: tuple[str, ...] = ()
    fontes: tuple[str, ...] = ()
    nivel: Nivel


class Secao(_Frozen):
    id: str
    titulo: str
    frases: tuple[Frase, ...]


class LaudoRX(_Frozen):
    versao: str = VERSAO
    status: str = "rascunho"
    secoes: tuple[Secao, ...]
    descricao_completa: str = ""        # aditivo (L1): parágrafo único; vazio = abstenção do validador
    descricao_origem: str = "deterministico"      # 'ia' (redigido por IA e verificado) | 'deterministico'
    descricao_validacao: dict[str, int] = {}      # {'frases': avaliadas, 'removidas': sem lastro} da etapa de IA


def _n(v: float, nd: int = 2) -> str:
    return f"{v:.{nd}f}".replace(".", ",")


def _sinal(v: float) -> str:
    return f"{v:+.1f}".replace(".", ",")


def _fr(secao: str, texto: str, nivel: Nivel, fatos=(), fontes=()) -> Frase:
    assert not LX.problemas(texto, nivel), (texto, LX.problemas(texto, nivel))   # tabela única de léxico
    FT.citar(fontes)
    return Frase(secao=secao, texto=texto, nivel=nivel, fatos=tuple(fatos), fontes=tuple(fontes))


def _ident(a: RXAnalysis, f: Ficha) -> list[Frase]:
    ids = [x.id for x in f.fatos if x.chave == "incidencia"]
    inc = ", ".join(sorted(set(f.incidencias))) or "não informada"
    return [_fr("identificacao_tecnica", f"Incidência(s): {inc}.", Nivel.QUALIDADE, ids, ("S1",) if ids else ()),
            _fr("identificacao_tecnica", f"Número de imagens: {len(a.images)}.", Nivel.QUALIDADE)]


_QUAL = {
    "rotacao": ("Rotação", "mediastino, traqueia e silhueta cardíaca"),
    "inspiracao": ("Inspiração", "volumes pulmonares e cúpulas"),
    "penetracao": ("Penetração", "parênquima e estruturas retrocardíacas"),
}


def _qualidade(f: Ficha) -> list[Frase]:
    out: list[Frase] = []
    for x in f.fatos:
        if x.chave not in _QUAL:
            continue
        nome, alvo = _QUAL[x.chave]
        if x.valor == "adequada":
            t = f"{nome}: estimativa automática adequada."
        elif x.valor == "possivelmente_inadequada":
            t = f"{nome} possivelmente inadequada (estimativa automática): limita a avaliação de {alvo}."
        else:
            t = f"{nome} indeterminada (estimativa automática): limita a avaliação de {alvo}."
        out.append(_fr("qualidade", t, Nivel.QUALIDADE, [x.id], x.fontes))
    if not out:
        out.append(_fr("qualidade", "Qualidade técnica: não avaliada (sem imagem de tórax analisável).",
                       Nivel.NAO_AVALIADO))
    return out


def _frase_fato(x) -> tuple[str, Nivel]:
    """Texto e nível da frase de uma medida da ficha."""
    rotulo = _ROTULO.get(x.chave, x.chave)
    if x.nivel == Nivel.NAO_AVALIADO:
        if x.chave == "ict":
            return "Silhueta cardíaca não medida com confiança (segmentação de baixa confiabilidade).", Nivel.NAO_AVALIADO
        return f"{rotulo} não medido com confiança (segmentação de baixa confiabilidade).", Nivel.NAO_AVALIADO
    v, regra = float(x.valor), x.nivel == Nivel.REGRA
    if x.chave == "ict":
        if any("magnifica" in r for r in x.ressalvas):
            return (f"ICT {_n(v)} em AP: a incidência magnifica o coração; não usar para afirmar cardiomegalia.",
                    Nivel.REGRA)
        if regra:
            return (f"Índice cardiotorácico medido {_n(v)}, acima de 0,50: sugere aumento da silhueta cardíaca "
                    "(critério de acurácia limitada; correlacionar). Medida com incerteza de ±0,05; pode estar "
                    "subestimada.", Nivel.REGRA)
        return (f"Índice cardiotorácico medido {_n(v)}, com incerteza (±0,05; pode estar subestimado): "
                "não exclui aumento da silhueta cardíaca.", Nivel.MEDIDO)
    base = {
        "mediastino_largura_pct": f"Largura do mediastino medida {_n(v, 0)}% da largura torácica",
        "mediastino_largura_mm": f"Largura do mediastino medida {_n(v, 0)} mm",
        "traqueia_desvio_pct": f"Desvio traqueal medido {_sinal(v)}% da largura torácica",
        "cupulas_diferenca_pct": f"Diferença de altura das cúpulas medida {_sinal(v)}% da altura pulmonar",
        "pulmoes_razao_area_E_D": f"Razão de área pulmonar E/D medida {_n(v)}",
    }[x.chave]
    if regra:
        return f"{base}, {_LIMIAR_LOCAL}.", Nivel.REGRA
    return f"{base}.", Nivel.MEDIDO


def _achados(f: Ficha) -> list[Frase]:
    out: list[Frase] = []
    for c in f.cobertura:
        nome = NOMES[c.regiao]
        if c.avaliada:
            out.append(_fr("achados", f"{nome}: {_RESTO.get(c.regiao, 'parte da região não avaliada')} nesta análise "
                           "automática.", Nivel.NAO_AVALIADO, c.fatos))
        else:
            out.append(_fr("achados", f"{nome}: não avaliado nesta análise automática.", Nivel.NAO_AVALIADO, c.fatos))
        vistos = {fr.texto for fr in out}
        for x in (y for y in f.fatos if y.regiao == c.regiao and y.chave in _ROTULO):
            t, n = _frase_fato(x)
            if t not in vistos:                      # mm e % do mediastino geram a mesma frase não medida
                vistos.add(t)
                out.append(_fr("achados", t, n, [x.id], x.fontes))
    return out


def _sinais(f: Ficha) -> list[Frase]:
    out = [_fr("sinais_modelo", "Caixa separada: escore de modelo auxiliar, fora da Impressão; não confirma nem afasta "
               "achados.", Nivel.SUGERIDO_MODELO, (), ("S5",))]
    for x in f.fatos:
        if x.nivel != Nivel.SUGERIDO_MODELO:
            continue
        nome = _PATOLOGIA_DE.get(x.chave, x.chave)
        if x.zona == "sugestivo":
            p = (f"probabilidade calibrada ≈ {_n(float(x.valor))}" if x.valor is not None
                 else "escore bruto, sem calibração")
            t = f"Modelo auxiliar: possível {nome} ({p}); escore de modelo; não confirma nem afasta."
        else:
            t = f"Modelo auxiliar: indeterminado para {nome}; não permite afirmar nem afastar."
        out.append(_fr("sinais_modelo", t, Nivel.SUGERIDO_MODELO, [x.id], x.fontes))
    return out


def _impressao(f: Ficha) -> list[Frase]:
    regras = sorted((x for x in f.fatos if x.nivel == Nivel.REGRA and x.chave in _ORDEM_IMPRESSAO),
                    key=lambda x: _ORDEM_IMPRESSAO.index(x.chave))
    out = []
    for x in regras:
        t, n = _frase_fato(x)
        out.append(_fr("impressao", t, n, [x.id], x.fontes))
    if not out:
        out.append(_fr("impressao", "Nenhum critério automático atingido nas medidas feitas; regiões não avaliadas "
                       "listadas em Achados.", Nivel.NAO_AVALIADO))
    out.append(_fr("impressao", CRITICO, Nivel.NAO_AVALIADO))
    return out


def _recomendacoes(f: Ficha) -> list[Frase]:
    out = [_fr("recomendacoes", "Correlacionar com a clínica.", Nivel.QUALIDADE, (), ("S2",))]
    if any("AP" == i for i in f.incidencias):
        out.append(_fr("recomendacoes", "Se a dúvida persistir, considerar incidência em perfil ou PA.",
                       Nivel.QUALIDADE, (), ("S1",)))
    if any(x.valor == "possivelmente_inadequada" for x in f.fatos):
        out.append(_fr("recomendacoes", "As limitações técnicas listadas podem justificar nova radiografia, a "
                       "critério do médico.", Nivel.QUALIDADE, (), ("S1",)))
    return out


def _revisao() -> list[Frase]:
    return [
        _fr("revisao_medica", "Rascunho gerado por análise automática; exige revisão médica e assinatura antes de "
            "qualquer uso. Status: rascunho.", Nivel.QUALIDADE, (), ("S2",)),
        _fr("revisao_medica", "Nota de IA: este texto usa análise computacional; a decisão final é do médico, sem "
            "aprovação automática de laudos.", Nivel.QUALIDADE, (), ("S8",)),
        _fr("revisao_medica", "Campos do médico: concordância por seção, comentário aberto para regiões não avaliadas e "
            "registro de comunicação não rotineira (somente local).", Nivel.QUALIDADE, (), ("S2",)),
    ]


# ---------------------------------------------------------------- descrição completa (parágrafo único, L1)
_VISTA = {"PA": "PA", "AP": "AP", "LATERAL": "perfil"}
_NUM_EXTENSO = {"1": "uma imagem", "2": "duas imagens", "3": "três imagens", "4": "quatro imagens"}
_NOME_QUAL = {"rotacao": "rotação", "inspiracao": "inspiração", "penetracao": "penetração"}
# chave -> (sujeito, particípio, valor)
_MEDIDA_ORACAO = {
    "mediastino_largura_pct": ("a largura do mediastino", "medida", lambda v: f"{_n(v, 0)}% da largura torácica"),
    "mediastino_largura_mm": ("a largura do mediastino", "medida", lambda v: f"{_n(v, 0)} mm"),
    "traqueia_desvio_pct": ("a posição da traqueia em relação à linha média", "medida", lambda v: f"{_sinal(v)}% da largura torácica"),
    "cupulas_diferenca_pct": ("a diferença de altura das cúpulas", "medida", lambda v: f"{_sinal(v)}% da altura pulmonar"),
    "pulmoes_razao_area_E_D": ("a razão de área pulmonar E/D", "medida", lambda v: _n(v)),
}
_PREFIXO_ICT = "Na região do coração e vasos"
_PREFIXO_REGIAO = {"pulmoes": "Nos pulmões", "mediastino_hilos": "No mediastino", "diafragma": "No diafragma"}
_LIMIAR_CURTO = "acima do limiar local"
_LIMIAR_NOTA = " (limiar local: heurística local, sem fonte primária; correlacionar)"
# o que fica não avaliado: região inteira / região medida só em parte (ordem do laudo: pulmões e pleura primeiro)
_ORDEM_DESCRICAO = ("pleura", "pulmoes", "mediastino_hilos", "coracao_vasos", "diafragma", "ossos_partes_moles",
                    "dispositivos")
_NAO_AVALIADO_TOTAL = {
    "pleura": "a pleura", "pulmoes": "os pulmões (parênquima, opacidades, nódulos e padrão intersticial)",
    "mediastino_hilos": "o mediastino, os hilos e a traqueia", "coracao_vasos": "a silhueta cardíaca, o contorno cardíaco "
    "e os vasos", "diafragma": "o diafragma e os seios costofrênicos",
    "ossos_partes_moles": "o arcabouço ósseo e as partes moles",
    "dispositivos": "os dispositivos (tubos, cateteres e marca-passo)"}
_NAO_AVALIADO_PARCIAL = {
    "pulmoes": ["opacidades, nódulos e padrão intersticial dos pulmões"], "mediastino_hilos": ["os hilos"],
    "coracao_vasos": ["o contorno cardíaco e os vasos"],
    "diafragma": ["os seios costofrênicos", "o ar livre subdiafragmático"]}


def _lista(xs: list[str]) -> str:
    return xs[0] if len(xs) <= 1 else ", ".join(xs[:-1]) + " e " + xs[-1]


def _minusc(t: str) -> str:
    return t[:1].lower() + t[1:]


def _oracao_tecnica(f: Ficha, ident: tuple[Frase, ...]) -> tuple[str, tuple[str, ...]]:
    ids = tuple(x.id for x in f.fatos if x.chave == "incidencia")
    if f.fora_de_escopo:
        aviso = next((fr.texto for fr in ident if fr.texto.startswith("Imagem fora do escopo")), "")
        return aviso, ()
    vistas = sorted({_VISTA.get(i, "não informada") for i in f.incidencias})
    ordem = [v for v in ("PA", "AP", "perfil") if v in vistas] + [v for v in vistas if v not in ("PA", "AP", "perfil")]
    plural = "incidências" if len(ordem) > 1 else "incidência"
    n = next((m.group(1) for fr in ident if (m := re.search(r"Número de imagens: (\d+)", fr.texto))), "")
    imagens = f", {_NUM_EXTENSO[n]}" if n in _NUM_EXTENSO else ""      # por extenso: não cria número solto no texto
    t = f"Radiografia de tórax em {plural} {_lista(ordem) if ordem else 'não informada'}{imagens}, descrita a partir de análise automática."
    extra = []
    if any(r.startswith("incidência AP") for r in f.ressalvas):
        extra.append("em incidência AP, que magnifica o coração e o mediastino, as medidas têm ressalva")
    if any(r.startswith("incidência sem medidas") for r in f.ressalvas):
        extra.append("a incidência em perfil fica sem medidas automáticas, e nenhuma região foi medida nela")
    if extra:
        t = t[:-1] + "; " + "; ".join(extra) + "."
    return t, ids


def _oracao_qualidade(f: Ficha) -> tuple[str, tuple[str, ...]]:
    itens, ids = [], []
    for x in f.fatos:
        if x.chave not in _QUAL:
            continue
        nome, alvo = _NOME_QUAL[x.chave], _QUAL[x.chave][1]
        ids.append(x.id)
        if x.valor == "adequada":
            itens.append(f"a {nome} é adequada")
        elif x.valor == "possivelmente_inadequada":
            itens.append(f"a {nome} é possivelmente inadequada, o que limita a avaliação de {alvo}")
        else:
            itens.append(f"a {nome} é indeterminada, o que limita a avaliação de {alvo}")
    itens = list(dict.fromkeys(itens))      # PA + perfil com o mesmo resultado: cada item sai uma vez
    if not itens:
        return "A qualidade técnica não foi avaliada (sem imagem de tórax analisável).", ()
    return "Quanto à qualidade técnica (estimativa automática), " + "; ".join(itens) + ".", tuple(ids)


def _oracao_ict(x) -> tuple[str, tuple[str, ...]]:
    if x.nivel == Nivel.NAO_AVALIADO:
        return (f"{_PREFIXO_ICT}, a silhueta cardíaca não foi medida com confiança (segmentação de baixa confiabilidade).",
                (x.id,))
    v = float(x.valor)
    if any("magnifica" in r for r in x.ressalvas):
        return (f"{_PREFIXO_ICT}, em incidência AP, que magnifica a silhueta cardíaca, o índice cardiotorácico de {_n(v)} "
                "não deve ser usado para afirmar cardiomegalia.", (x.id,))
    if x.nivel == Nivel.REGRA:
        return (f"{_PREFIXO_ICT}, o índice cardiotorácico foi medido em {_n(v)}, acima de 0,50, o que sugere aumento da silhueta cardíaca "
                "(critério de acurácia limitada; correlacionar), com incerteza de ±0,05 e podendo estar subestimado.",
                (x.id,))
    return (f"{_PREFIXO_ICT}, o índice cardiotorácico foi medido em {_n(v)}, com incerteza (±0,05; pode estar subestimado), "
            "o que não exclui aumento da silhueta cardíaca.", (x.id,))


def _oracao_regiao(regiao: str, fatos: list) -> tuple[str, tuple[str, ...]] | None:
    por_sujeito: dict[str, dict] = {}      # mm e % da mesma largura saem numa oração só
    for x in fatos:
        sujeito, part, valor = _MEDIDA_ORACAO[x.chave]
        d = por_sujeito.setdefault(sujeito, {"part": part, "valores": [], "regra": False, "sem": False, "ids": []})
        d["ids"].append(x.id)
        if x.nivel == Nivel.NAO_AVALIADO:
            d["sem"] = True
        else:
            d["valores"].append(valor(float(x.valor)))
            d["regra"] = d["regra"] or x.nivel == Nivel.REGRA
    clausulas, ids = [], []
    for sujeito, d in por_sujeito.items():
        ids += d["ids"]
        if d["valores"]:
            clausulas.append(f"{sujeito} foi {d['part']} em {' e em '.join(d['valores'])}"
                             + (f", {_LIMIAR_CURTO}" if d["regra"] else ""))
        else:
            clausulas.append(f"{sujeito} não foi {d['part']} com confiança (segmentação de baixa confiabilidade)")
    if not clausulas:
        return None
    nota = _LIMIAR_NOTA if any(d["regra"] for d in por_sujeito.values()) else ""
    return f"{_PREFIXO_REGIAO[regiao]}, {_lista(clausulas)}{nota}.", tuple(ids)


def _oracao_limitacoes(f: Ficha, achados: list) -> tuple[str, tuple[str, ...]]:
    medidas = {x.chave for x in achados if x.nivel in (Nivel.MEDIDO, Nivel.REGRA)}
    itens: list[str] = []
    for c in sorted(f.cobertura, key=lambda c: _ORDEM_DESCRICAO.index(c.regiao)):
        if not c.avaliada:
            itens.append(_NAO_AVALIADO_TOTAL[c.regiao])
            continue
        resto = list(_NAO_AVALIADO_PARCIAL.get(c.regiao, []))
        if c.regiao == "mediastino_hilos":
            if "traqueia_desvio_pct" not in medidas:
                resto.append("a traqueia")
            if not medidas & {"mediastino_largura_pct", "mediastino_largura_mm"}:
                resto.append("a largura do mediastino")
        itens.extend(resto)
    return "Não foram avaliados nesta análise automática: " + _lista(itens) + ".", ()


def _oracao_impressao(f: Ficha, impressao: Secao) -> tuple[str, tuple[str, ...]]:
    por_id = {x.id: x for x in f.fatos}
    regras = [por_id[i] for fr in impressao.frases for i in fr.fatos if i in por_id]
    clausulas, ids, vistos = [], [], set()
    for x in regras:
        if x.chave == "ict":
            ap = any("magnifica" in r for r in x.ressalvas)
            c = (f"o índice cardiotorácico de {_n(float(x.valor))} em AP não deve ser usado para afirmar cardiomegalia, pois a "
                 "incidência magnifica o coração" if ap else f"o índice cardiotorácico de {_n(float(x.valor))}, acima de 0,50, "
                 "sugere aumento da silhueta cardíaca (critério de acurácia limitada)")
        else:
            sujeito, part, valor = _MEDIDA_ORACAO[x.chave]
            if x.chave == "traqueia_desvio_pct":
                sujeito = "o desvio traqueal"      # com regra disparada o claim_check aceita o termo
                part = "medido"
            c = f"{sujeito}, {part} em {valor(float(x.valor))}, está {_LIMIAR_CURTO}"
        if c not in vistos:
            vistos.add(c)
            clausulas.append(c)
        ids.append(x.id)
    if not clausulas:
        return ("Em síntese, nenhum critério automático foi atingido nas medidas feitas, o que descreve o alcance da análise "
                "e não o estado do exame: as regiões não avaliadas dependem da leitura do médico; correlacionar com a clínica.", ())
    return "Em síntese, " + "; ".join(clausulas) + "; correlacionar com a clínica.", tuple(ids)


def oracoes_descricao(laudo: LaudoRX, f: Ficha) -> list[tuple[str, tuple[str, ...]]]:
    """Orações da descrição completa, na ordem do laudo. Cada uma nasce de Frases/fatos já presentes nas seções;
    nada de fato novo, nada de normal/livre/afasta; o que não foi avaliado vai agrupado numa oração só."""
    sec = {s.id: s for s in laudo.secoes}
    por_id = {x.id: x for x in f.fatos}
    vistos: set[str] = set()
    achados = []
    for fr in sec["achados"].frases:
        for i in fr.fatos:
            x = por_id.get(i)
            if x is not None and x.chave in _ROTULO and i not in vistos:
                vistos.add(i)
                achados.append(x)
    por_regiao = {r: [x for x in achados if x.regiao == r] for r in _ORDEM_DESCRICAO}
    out = [_oracao_tecnica(f, sec["identificacao_tecnica"].frases), _oracao_qualidade(f)]
    for r in ("pulmoes", "mediastino_hilos"):
        o = _oracao_regiao(r, por_regiao[r])
        if o:
            out.append(o)
    out.extend(_oracao_ict(x) for x in por_regiao["coracao_vasos"] if x.chave == "ict")
    o = _oracao_regiao("diafragma", por_regiao["diafragma"])
    if o:
        out.append(o)
    out.append(_oracao_limitacoes(f, achados))
    modelo = tuple(x.id for x in f.fatos if x.nivel == Nivel.SUGERIDO_MODELO)
    if modelo:
        out.append(("O sinal do modelo auxiliar consta em caixa separada, fora da impressão, e não confirma nem afasta "
                    "achados.", modelo))
    out.append(_oracao_impressao(f, sec["impressao"]))
    out.append((CRITICO, ()))
    return [(t, ids) for t, ids in out if t]


PALAVRAS_REGIAO = {"pleura": "pleura", "pulmoes": "pulmões", "mediastino": "mediastino", "hilos": "hilos",
                   "traqueia": "traqueia", "coracao": "silhueta cardíaca", "vasos": "vasos", "diafragma": "diafragma",
                   "seios": "seios costofrênicos", "ossos": "ósseo", "partes_moles": "partes moles",
                   "dispositivos": "dispositivos"}
# frases-molde do ICT (já aprovadas no léxico do laudo): o claim_check as leria como negação/afirmação de cardiomegalia
_M_EXCLUI = re.compile(r"n[aã]o exclui aumento da silhueta card[ií]aca", re.IGNORECASE)
_M_SUGERE = re.compile(r"sugere aumento da silhueta card[ií]aca", re.IGNORECASE)
_M_AP = re.compile(r"n[aã]o deve ser usado para afirmar cardiomegalia", re.IGNORECASE)


def problemas_oracao(texto: str, ids, f: Ficha) -> list[str]:
    """Mesmo validador das afirmações da IA (`laudo_validate._problemas`: fatos citados, fontes, números, léxico, claim_check).
    Os moldes do ICT só são aceitos se o fato do ICT que os sustenta está citado (sugere: só com nível REGRA)."""
    from . import laudo_validate as LV

    por_id = {x.id: x for x in f.fatos}
    ict = [por_id[i] for i in ids if i in por_id and por_id[i].chave == "ict" and por_id[i].valor is not None]
    neutro = texto
    if ict:
        neutro = _M_EXCLUI.sub("ressalva do ICT", neutro)
        neutro = _M_AP.sub("ressalva do ICT", neutro)
        if any(x.nivel == Nivel.REGRA for x in ict):
            neutro = _M_SUGERE.sub("ressalva do ICT", neutro)
    return LV._problemas({"texto": neutro, "fatos": list(ids), "fontes": []}, f, False)


def _descricao_validada(laudo: LaudoRX, f: Ficha) -> str:
    """Parágrafo único; passa pelo validador de afirmações e pela barreira de PHI. Qualquer problema = abstenção ('')."""
    try:
        from ..llm.guard import scan_text

        oracoes = oracoes_descricao(laudo, f)
        texto = " ".join(t for t, _ in oracoes)
        ruim = [t for t, ids in oracoes if problemas_oracao(t, ids, f)]
        if ruim or "\n" in texto or LX.termos_proibidos(texto) or scan_text(texto):
            logging.getLogger(__name__).warning("descricao_completa descartada: %s", ruim[:1])
            return ""
        return texto
    except Exception:
        logging.getLogger(__name__).exception("descricao_completa failure")
        return ""


def build_laudo(a: RXAnalysis) -> LaudoRX:
    f = build_ficha(a)
    aviso = []
    if f.fora_de_escopo:
        aviso = [_fr("identificacao_tecnica", "Imagem fora do escopo desta análise (radiografia de tórax adulto): "
                     f"{f.motivo_fora_de_escopo}.", Nivel.NAO_AVALIADO)]
    blocos = {"identificacao_tecnica": _ident(a, f) + aviso, "qualidade": _qualidade(f), "achados": _achados(f),
              "sinais_modelo": _sinais(f), "impressao": _impressao(f), "recomendacoes": _recomendacoes(f),
              "revisao_medica": _revisao()}
    laudo = LaudoRX(secoes=tuple(Secao(id=i, titulo=TITULOS[i], frases=tuple(fr)) for i, fr in blocos.items()))
    return laudo.model_copy(update={"descricao_completa": _descricao_validada(laudo, f)})


def render_markdown(l: LaudoRX) -> str:
    linhas = ["# Laudo de radiografia de tórax (rascunho para revisão médica)", ""]
    for s in l.secoes:
        linhas.append(f"## {s.titulo}")
        for fr in s.frases:
            fonte = f" ({', '.join(fr.fontes)})" if fr.fontes else ""
            pref = "> " if s.id == "sinais_modelo" else "- "
            linhas.append(f"{pref}{fr.texto}{fonte} _[{fr.nivel.value}]_")
        linhas.append("")
    if l.descricao_completa:
        linhas += ["## Descrição completa", l.descricao_completa, ""]
    return "\n".join(linhas).rstrip() + "\n"
