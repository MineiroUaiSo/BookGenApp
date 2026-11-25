"""Barreira de afirmações qualitativas do texto de IA do RX (spec RX-LAUDO-CONFIAVEL §3.1).

`llm/validate.py` só confere números e 5 tópicos "críticos", e só sinaliza. Aqui o caminho RX é estrito: cada frase da IA
que afirma OU nega um tópico radiológico (derrame, pneumotórax, consolidação, nódulo, fratura, dispositivos, "seios
livres", "exame normal"...) precisa de lastro nos fatos determinísticos; sem lastro a frase é REMOVIDA de
`description`/`findings`/`differentials` e registrada em `disagreements_with_measurements`.

Lastro (só o que o app realmente sabe):
- afirmação: regra disparada, ou escore de modelo na zona calibrada `sugestivo` (sem calibração: escore bruto >= limiar);
  `INSUFFICIENT_EVIDENCE` (pneumotórax) nunca sustenta; o escore bruto isolado não vale quando há zona;
- negação / "normal": só com MEDIDA na faixa e nenhuma regra disparada (ICT, traqueia, mediastino, cúpulas);
  derrame, pneumotórax, seios, opacidades, dispositivos etc. nunca podem ser negados (o app não os avalia);
- tamanho de lesão (mm/cm) nunca tem lastro; lateralidade/lobo/broncograma só passam se a imagem foi enviada.
Frases que dizem "não avaliado/indeterminado" são legítimas e passam. Puro Python, sem rede.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..schemas import AIReport, Differential, Finding
from . import calibration as CAL
from .findings import model_threshold

CHAVE_REMOVIDAS = "claims_rx_removidas"


def _re(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE)


# ---------------------------------------------------------------- tópicos
@dataclass(frozen=True)
class Topico:
    nome: str
    achado: re.Pattern                         # termo patológico: citá-lo sem negação é AFIRMAR
    anat: Optional[re.Pattern] = None          # termo anatômico: só conta junto de negação/"normal"/"livre"
    patologias: tuple[str, ...] = ()           # chaves de escore de modelo que podem sustentar a afirmação
    codigos: tuple[str, ...] = ()              # prefixos de regra que sustentam a afirmação
    medidas: tuple[str, ...] = ()              # medidas que permitem negar (na faixa e sem regra)
    lesao: bool = False                        # tamanho em mm/cm nunca tem lastro


TOPICOS: tuple[Topico, ...] = (
    Topico("pneumotórax", _re(r"pneumot[oó]rax|pneumothorax")),
    Topico("derrame pleural", _re(r"derrame\w*(?:\s+pleural)?|efus[aã]o pleural|effusion"), _re(r"\bpleur\w+"),
           ("Effusion",), ("rx.model.effusion",)),
    Topico("seio costofrênico", _re(r"(?:velamento|embotamento|apagamento) d[oe]s? seios?|costophrenic"),
           _re(r"\bseios?\b(?:\s+costofr[eê]nic\w+)?|costofr[eê]nic\w+"), (), ("rx.costophrenic_blunting",)),
    Topico("consolidação/pneumonia", _re(r"consolida\w+|pneumonia|broncograma(?:\s+a[eé]reo)?|consolidation"), None,
           ("Consolidation", "Pneumonia"), ("rx.model.consolidation", "rx.model.pneumonia"), lesao=True),
    Topico("atelectasia", _re(r"atelecta\w+|colapso (?:pulmonar|lobar)|atelectasis"), None, ("Atelectasis",),
           ("rx.model.atelectasis",)),
    Topico("opacidade", _re(r"opacidades?|opacification|infiltra\w+|velamento (?:pulmonar|parenquimatoso)"),
           _re(r"pulm[oõ]es|campos? pulmonares?|par[eê]nquima|hemit[oó]rax"),
           ("Lung Opacity", "Infiltration", "Consolidation", "Atelectasis", "Edema", "Pneumonia"),
           ("rx.model.lung_opacity", "rx.model.infiltration", "rx.model.consolidation", "rx.model.atelectasis",
            "rx.model.edema", "rx.model.pneumonia")),
    Topico("nódulo/massa", _re(r"n[oó]dulos?|massas?\b|micron[oó]dulos?|les[aã]o (?:pulmonar|expansiva)|nodule"),
           None, ("Nodule", "Mass", "Lung Lesion"), ("rx.model.nodule", "rx.model.mass", "rx.model.lung_lesion"),
           lesao=True),
    Topico("edema/congestão", _re(r"edema|congest[aã]o (?:pulmonar|vascular)|linhas? de kerley|cefaliza[cç][aã]o"),
           None, ("Edema",), ("rx.model.edema",)),
    Topico("enfisema/hiperinsuflação", _re(r"enfisema|hiperinsufla\w+|hiperl?ucen\w+|emphysema"), None,
           ("Emphysema",), ("rx.model.emphysema",)),
    Topico("fibrose/intersticial", _re(r"fibrose|padr[aã]o intersticial|reticula\w+|fibrosis"), None, ("Fibrosis",),
           ("rx.model.fibrosis",)),
    Topico("espessamento pleural", _re(r"espessamento pleural|placas? pleura\w+"), None, ("Pleural_Thickening",),
           ("rx.model.pleural_thickening",)),
    Topico("fratura/ossos", _re(r"fratura\w*|fracture|les[aã]o [oó]ssea|osteo\w+|l[ií]tica|blástica"),
           _re(r"\bossos?\b|[oó]sse[oa]s?|arcos? costais?|costelas?|clav[ií]culas?|esc[aá]pulas?|coluna"),
           ("Fracture",), ("rx.model.fracture",)),
    Topico("hérnia", _re(r"h[eé]rnia"), None, ("Hernia",), ("rx.model.hernia",)),
    Topico("dispositivos", _re(r"\b(?:tubo|cateter|sonda|dreno|eletrodo|marca-?passo|picc|port-a-cath|cvc)s?\b|"
                               r"dispositivos?"), None),
    Topico("ar livre", _re(r"pneumoperit\w+|ar livre|free air|gás (?:livre|subdiafragm\w+)"), None),
    Topico("hilos/trama", _re(r"hilos?|hilar\w*|trama (?:vascular|pulmonar)|vasculariza[cç][aã]o"), None),
    Topico("partes moles", _re(r"enfisema subcut[aâ]neo|partes? moles"), None),
    Topico("cardiomegalia", _re(r"cardiomegalia|c[aá]rdio?megalia|aumento (?:da )?(?:silhueta|[aá]rea) card[ií]ac\w+|"
                                r"cora[cç][aã]o aumentado|cardiomegaly"),
           _re(r"silhueta (?:cardio?\w*|card[ií]ac\w+)|cora[cç][aã]o|[aá]rea card[ií]aca|\bICT\b|"
               r"[ií]ndice cardiotor[aá]cico|cardiotor[aá]cic\w+"),
           (), ("rx.cardiomegaly",), ("cardiothoracic_ratio",)),
    Topico("mediastino", _re(r"alargamento (?:do )?mediastin\w+|mediastino alargado|cardiomediastinal alargad\w+"),
           _re(r"mediastin\w+"), ("Enlarged Cardiomediastinum",), ("rx.mediastinal_widening",),
           ("mediastinal_width", "mediastinal_width_ratio")),
    Topico("traqueia", _re(r"desvio (?:da )?traqueal?|traqueia desviada|desvio d[ao] traqueia"), _re(r"traqu\w+"),
           (), ("rx.tracheal_deviation",), ("tracheal_deviation", "tracheal_deviation_pct")),
    Topico("diafragma", _re(r"eleva[cç][aã]o d[ae] (?:hemi)?c[uú]pula|c[uú]pula elevada|paralisia frênica"),
           _re(r"c[uú]pulas?|diafragma\w*|hemidiafragma\w*"), (), ("rx.hemidiaphragm_elevation",),
           ("hemidiaphragm_height_difference", "hemidiaphragm_height_difference_pct")),
)

# ---------------------------------------------------------------- vocabulário
_NEG = _re(r"\b(?:sem|aus[eê]ncia(?: de)?|n[aã]o h[aá]|n[aã]o se (?:observa|vê|ve|evidencia|identifica|visualiza)|"
           r"n[aã]o (?:evidencia|identifica|visualiza|apresenta|demonstra|há)|descart\w+|afasta\w*|exclu\w+|"
           r"nega|negativo|livre de|isento de|sem sinais de)\b")
_LIVRE = _re(r"\b(?:livres?|limpos?|limpas?|claros?|claras?|preservad[oa]s?|[ií]ntegr[oa]s?|transparentes?|"
             r"normais?|normal|normalidade|dentro d[oa]s? (?:limites?|faixa|normalidade)|sem altera\w+|"
             r"habituais?|simétric\w+|regulares?)\b")
_REF_NORMAL = _re(r"(?:limites?|valor(?:es)?|faixa|refer[eê]ncia|crit[eé]rio|esperad\w+)\s+(?:de\s+)?"
                  r"(?:normal\w*|normalidade)|normal\s*[≤<(]")
_NORMAL_GLOBAL = _re(r"\bnormal(?:is|idade)?\b|sem altera[cç][oõ]es|sem achados|sem anormalidades?|"
                     r"sem sinais de doen[cç]a|pulm[oõ]es limpos|campos? pulmonares? (?:limpos|livres|claros|"
                     r"transparentes)|exame (?:sem|dentro)|n[aã]o h[aá] altera[cç][oõ]es|aus[eê]ncia de altera\w+|"
                     r"dentro d[oa]s? (?:limites? normais|normalidade)")
_ABST = _re(r"n[aã]o (?:[eé]|foi|foram) (?:poss[ií]vel|avaliad\w+|analisad\w+)|n[aã]o (?:avali\w+|analis\w+|permite|"
            r"h[aá] como|se pode|confirma nem afasta|se aplica)|n[aã]o (?:poss[ií]vel )?(?:avali\w+|afirmar)|"
            r"indeterminad\w+|inconclusiv\w+|sem avalia[cç][aã]o|n[aã]o pode ser (?:avaliad\w+|afirmad\w+|exclu\w+)|"
            r"limita(?:r|ndo|m)? (?:a )?avalia[cç][aã]o|revisar a imagem")
_SIZE = _re(r"\b\d+(?:[.,]\d+)?\s*(?:mm|cm)\b")
_VISUAL = _re(r"\blobos?\b|\bl[oó]bulo\b|\bsegmento\b|\bl[ií]ngula\b|broncograma|\bapic\w+|\bbasal\b|\bbasais\b|"
              r"perihilar|\bcontorno\w*|a imagem (?:mostra|revela|demonstra)|arcos? costais?|\bdireit[oa]s?\b|"
              r"\besquerd[oa]s?\b|bilateral\w*|\b(?:superior|inferior|m[eé]dio)\b")
_SPLIT_CLAUSE = re.compile(r"[,;:()\[\]]|\s[—–-]\s|\bmas\b|\bporém\b|\bentretanto\b", re.IGNORECASE)
_SPLIT_SENT = re.compile(r"((?<=[.!?])\s+|\n+)")
_CODE_NOISE = re.compile(r"[._]+")


# ---------------------------------------------------------------- lastro
@dataclass(frozen=True)
class Fatos:
    medidas: dict[str, float]
    codigos: tuple[str, ...]
    zonas: dict[str, str]
    probs: dict[str, float]

    @classmethod
    def de(cls, summary: dict) -> "Fatos":
        medidas: dict[str, float] = {}
        zonas: dict[str, str] = {}
        probs: dict[str, float] = {}
        for im in summary.get("imagens") or []:
            for m in im.get("medidas") or []:
                v = m.get("value")
                if isinstance(v, (int, float)) and m.get("key") and m["key"] not in medidas:
                    medidas[str(m["key"])] = float(v)
            for k, z in (im.get("zonas_modelo_auxiliar") or {}).items():
                zonas.setdefault(k, z)
            for k, p in (im.get("probabilidades_modelo_auxiliar") or {}).items():
                if isinstance(p, (int, float)):
                    probs[k] = max(float(p), probs.get(k, 0.0))
        codigos = tuple(str(f.get("code", "")).lower() for f in summary.get("achados_por_regras") or [])
        return cls(medidas, codigos, zonas, probs)

    def regra(self, prefixos: tuple[str, ...]) -> bool:
        return any(c.startswith(p) for c in self.codigos for p in prefixos)

    def escore_sustenta(self, patologia: str) -> bool:
        if patologia in CAL.INSUFFICIENT_EVIDENCE:
            return False
        if patologia in self.zonas:               # zona calibrada manda; escore bruto isolado não vale
            return self.zonas[patologia] == CAL.ZONE_SUGGESTIVE
        slug = "rx.model." + patologia.lower().replace(" ", "_")
        if slug in self.codigos:
            return True
        return self.probs.get(patologia, 0.0) >= model_threshold(patologia) and patologia in self.probs


def _afirmacao_ok(t: Topico, f: Fatos) -> bool:
    if t.nome == "cardiomegalia" and f.medidas.get("cardiothoracic_ratio", 0.0) > 0.50:
        return True
    return f.regra(t.codigos) or any(f.escore_sustenta(p) for p in t.patologias)


def _negacao_ok(t: Topico, f: Fatos) -> bool:
    """Negar/dar como normal só com medida do tópico presente, na faixa, e nenhuma regra disparada."""
    if not t.medidas or not any(k in f.medidas for k in t.medidas):
        return False
    if f.regra(t.codigos):
        return False
    if t.nome == "cardiomegalia":
        return f.medidas.get("cardiothoracic_ratio", 1.0) <= 0.50
    return True


# ---------------------------------------------------------------- verificação de texto
def _mencoes(t: Topico, clausula: str):
    for m in t.achado.finditer(clausula):
        yield m, False
    if t.anat is not None:
        for m in t.anat.finditer(clausula):
            yield m, True


def _negada(clausula: str, m: re.Match) -> bool:
    antes = clausula[max(0, m.start() - 45):m.start()]
    depois = _REF_NORMAL.sub(" ", clausula[m.end():m.end() + 40])
    return bool(_NEG.search(antes) or _LIVRE.search(depois) or _LIVRE.search(_REF_NORMAL.sub(" ", antes[-18:])))


def _clausula_problema(clausula: str, fatos: Fatos, imagem: bool, so_afirmacao: bool) -> Optional[str]:
    a = _ABST.search(clausula)
    if a and not _NEG.search(clausula[:a.start()]):
        return None                                   # "não avaliado / indeterminado": legítimo
    avaliou = False
    for t in TOPICOS:
        for m, so_anat in _mencoes(t, clausula):
            neg = False if so_afirmacao else _negada(clausula, m)
            if so_anat and not neg:
                continue                              # termo anatômico solto não afirma nada
            avaliou = True
            if neg:
                if not _negacao_ok(t, fatos):
                    return f"negação/normalidade de '{t.nome}' sem medida que a sustente"
                continue
            if not _afirmacao_ok(t, fatos):
                return f"'{t.nome}' sem fato de apoio (regra ou escore calibrado sugestivo)"
            if t.lesao and _SIZE.search(clausula):
                return f"tamanho de '{t.nome}' sem medida"
            if not imagem and _VISUAL.search(clausula) and not t.medidas:
                return f"descritor visual/lateralidade de '{t.nome}' sem imagem enviada"
    if not avaliou and not so_afirmacao and _NORMAL_GLOBAL.search(_REF_NORMAL.sub(" ", clausula)):
        return "afirmação de normalidade global sem avaliação"
    return None


def problema_da_frase(frase: str, fatos: Fatos, imagem: bool = False, so_afirmacao: bool = False) -> Optional[str]:
    """Motivo da rejeição, ou None se a frase tem lastro (ou não afirma nem nega tópico RX)."""
    for clausula in _SPLIT_CLAUSE.split(frase):
        if not clausula or not clausula.strip():
            continue
        p = _clausula_problema(clausula, fatos, imagem, so_afirmacao)
        if p:
            return p
    return None


def _frases(texto: str) -> list[tuple[str, str]]:
    partes = _SPLIT_SENT.split(texto)
    return [(partes[i], partes[i + 1] if i + 1 < len(partes) else "") for i in range(0, len(partes), 2)]


def _filtrar_texto(texto: str, fatos: Fatos, imagem: bool, rotulo: str, removidas: list[str]) -> str:
    if not texto or not texto.strip():
        return texto
    mantidas: list[tuple[str, str]] = []
    for frase, sep in _frases(texto):
        p = problema_da_frase(frase, fatos, imagem) if frase.strip() else None
        if p:
            removidas.append(f"{rotulo}Frase da IA removida (sem lastro nas medidas): «{frase.strip()}» — {p}.")
        else:
            mantidas.append((frase, sep))
    return "".join(f + (s if i < len(mantidas) - 1 else "") for i, (f, s) in enumerate(mantidas)).strip()


def _codigo_texto(code: str) -> str:
    return _CODE_NOISE.sub(" ", code or "")


def _filtrar_finding(f: Finding, fatos: Fatos, imagem: bool, removidas: list[str]) -> Optional[Finding]:
    motivo = problema_da_frase(f.label, fatos, imagem) or problema_da_frase(_codigo_texto(f.code), fatos, imagem,
                                                                            so_afirmacao=True)
    if motivo:
        removidas.append(f"Achado da IA removido (sem lastro nas medidas): «{f.label}» — {motivo}.")
        return None
    ev: list[str] = []
    for e in f.evidence:
        m = problema_da_frase(e, fatos, imagem)
        if m:
            removidas.append(f"Evidência da IA removida (sem lastro nas medidas): «{e}» — {m}.")
        else:
            ev.append(e)
    return f.model_copy(update={"evidence": ev})


def _filtrar_diferencial(d: Differential, fatos: Fatos, imagem: bool, removidas: list[str]) -> Optional[Differential]:
    motivo = problema_da_frase(d.diagnosis, fatos, imagem, so_afirmacao=True) \
        or problema_da_frase(d.rationale, fatos, imagem)
    if motivo:
        removidas.append(f"Diagnóstico diferencial da IA removido (sem lastro nas medidas): «{d.diagnosis}» — "
                         f"{motivo}.")
        return None
    sup = [s for s in d.supporting if not problema_da_frase(s, fatos, imagem)]
    ctr = [s for s in d.against if not problema_da_frase(s, fatos, imagem)]
    for s in d.supporting + d.against:
        m = problema_da_frase(s, fatos, imagem)
        if m:
            removidas.append(f"Argumento da IA removido (sem lastro nas medidas): «{s}» — {m}.")
    return d.model_copy(update={"supporting": sup, "against": ctr})


def sanitize_report(rep: AIReport, summary: dict, *, image_sent: bool = False,
                    fatos: Optional[Fatos] = None) -> AIReport:
    """Cópia do AIReport sem as afirmações/negações RX sem lastro; as removidas vão para
    `disagreements_with_measurements` (nunca levanta por conteúdo do texto)."""
    if not rep.available:
        return rep
    fatos = fatos or Fatos.de(summary)
    removidas: list[str] = []
    desc = _filtrar_texto(rep.description, fatos, image_sent, "", removidas)
    findings = [g for g in (_filtrar_finding(f, fatos, image_sent, removidas) for f in rep.findings) if g]
    diffs = [g for g in (_filtrar_diferencial(d, fatos, image_sent, removidas) for d in rep.differentials) if g]
    if not removidas:
        return rep
    disc = list(rep.disagreements_with_measurements)
    disc.extend(x for x in removidas if x not in disc)
    validation = dict(rep.validation)
    validation[CHAVE_REMOVIDAS] = validation.get(CHAVE_REMOVIDAS, 0) + len(removidas)
    return rep.model_copy(update={"description": desc, "findings": findings, "differentials": diffs,
                                  "disagreements_with_measurements": disc, "validation": validation})
