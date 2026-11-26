"""Descrição completa do RX redigida por IA (L1): reescreve o parágrafo determinístico a partir dos FATOS do laudo.

Só texto estruturado (JSON de fatos/frases), sem imagem. A saída passa, afirmação a afirmação, pelo mesmo validador das
afirmações da IA (`laudo.problemas_oracao` = `laudo_validate._problemas` + claim_check + léxico) e pela barreira de PHI.
Falha fechada: recusa, erro, truncamento, retenção baixa, região/medida perdida ou qualquer exceção -> parágrafo
determinístico (`descricao_origem="deterministico"`). A frase CRITICO é sempre a última, em texto fixo."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Callable, Optional

from . import laudo as LA
from . import lexico as LX
from .ficha import Ficha, Nivel, build_ficha
from ..schemas import RXAnalysis

log = logging.getLogger(__name__)

LIMITE_RETENCAO = 0.7       # fração mínima de afirmações da IA que sobrevivem ao validador
MAX_TOKENS = 4000
MAX_CARACTERES = 5000
_PNEUMO = re.compile(r"pneumot[oó]rax|pneumoperit", re.IGNORECASE)
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["afirmacoes"], "properties": {"afirmacoes": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["texto", "fatos"],
                               "properties": {"texto": {"type": "string"},
                                              "fatos": {"type": "array", "items": {"type": "string"}}}}}}}
SISTEMA = (
    "Você redige a DESCRIÇÃO COMPLETA de uma radiografia de tórax em português do Brasil, como parágrafo único coeso de "
    "laudo, usando EXCLUSIVAMENTE os fatos e frases fornecidos em JSON (ficha de fatos, frases do laudo e rascunho "
    "determinístico). Regras inegociáveis: (1) nada fora dos fatos: nenhum achado, medida ou número novo; (2) mantenha toda "
    "região como está: o que o rascunho diz 'não avaliado' continua não avaliado, agrupado em uma oração só; (3) nunca "
    "escreva normal, livre, sem alterações, afasta, descarta, ausência de ou confirma; (4) o índice cardiotorácico (ICT) "
    "sempre com a incerteza de ±0,05 e, se de modelo e até 0,50, 'não exclui aumento da silhueta cardíaca'; ICT sem medida "
    "confiável não aparece como número; (5) ordem do checklist do documento de modelos: técnica e qualidade, pleura e pulmões, "
    "mediastino/hilos/traqueia, coração/vasos (ICT, abrindo com 'na região do coração e vasos'), diafragma/seios costofrênicos, "
    "ossos/partes moles, dispositivos, limitações, impressão; (6) conectivos naturais ('na região de', 'no mediastino', "
    "'enquanto', 'sem avaliação de', 'em trecho separado', 'o que limita a avaliação de', 'e por isso'), sem listas, sem "
    "quebras de linha; cada oração com uma região e um nível só, e a abstenção dita uma vez por item, agrupando as regiões "
    "não avaliadas; (7) não escreva a frase sobre pneumotórax/pneumoperitônio/tubos: ela é acrescentada depois; (8) nunca "
    "'não é possível' nem 'não foi possível' (o verificador lê 'possível' como grau de certeza): para o que falta diga 'não "
    "avaliado' ou 'não há como afirmar', e 'indeterminado' nunca numa oração de não avaliado; (9) não calcule, não converta "
    "nem arredonde números; sem descritor visual (lobo, lado, contorno, broncograma, 'a imagem mostra'), sem conduta nem "
    "tratamento, sem nenhum termo vetado pelo léxico de RX. Responda só com JSON: {\"afirmacoes\": [{\"texto\": <uma ou duas orações>, \"fatos\": [<ids F# "
    "dos fatos que a sustentam>]}]}, na ordem do parágrafo; cite o id de todo fato usado (a oração de limitações e a de "
    "técnica citam os fatos de incidência/qualidade ou nenhum). Frases com medida: sem 'possível/possivelmente/sugere/"
    "compatível' (use 'pode estar subestimado' para o ICT); 'possivelmente inadequada' só para a qualidade técnica; 'sugere' só "
    "com fato de nível REGRA. Sinais do modelo auxiliar (nível SUGERIDO_MODELO): no máximo uma oração dizendo que constam em "
    "caixa separada, fora da impressão, e que não confirmam nem afastam achados, sem nomear patologias. O verificador só "
    "aceita estes termos assim: 'não confirma nem afasta' (exatamente, no singular, com sujeito singular: 'o sinal do modelo "
    "auxiliar ... não confirma nem afasta achados'); 'posição da traqueia em relação à linha média' (nunca 'desvio traqueal' "
    "nem 'desvio da traqueia', salvo fato de nível REGRA); 'não exclui aumento da silhueta cardíaca'; 'limiar local' só em fato "
    "REGRA. Mantenha os valores com a mesma formatação do rascunho.")

Chamar = Callable[[str, str], str]


def ia_habilitada() -> bool:
    return os.environ.get("MEDLENS_RX_DESCRICAO_IA", "1").strip().lower() not in {"0", "false", "off", "nao", "não"}


def _chamar_padrao(sistema: str, usuario: str) -> str:
    from ..llm import client as c

    texto, _, _ = c.run_resilient(c.make_client(), [{"type": "text", "text": sistema}],
                                  [{"role": "user", "content": usuario}], MAX_TOKENS, schema=SCHEMA)
    return texto


def _contexto(laudo: LA.LaudoRX, f: Ficha, base: str) -> str:
    fatos = [{"id": x.id, "chave": x.chave, "valor": x.valor, "unidade": x.unidade, "nivel": x.nivel.value,
              "regiao": x.regiao, "zona": x.zona, "ressalvas": list(x.ressalvas)} for x in f.fatos]
    frases = [{"secao": s.id, "texto": fr.texto, "fatos": list(fr.fatos)} for s in laudo.secoes
              if s.id != "revisao_medica" for fr in s.frases]
    return json.dumps({"incidencias": list(f.incidencias), "fatos": fatos, "frases_do_laudo": frases,
                       "rascunho_deterministico": base}, ensure_ascii=False)


def _afirmacoes(bruto: str) -> list[dict]:
    dados = json.loads(bruto)
    afs = dados["afirmacoes"]
    if not isinstance(afs, list):
        raise ValueError("afirmacoes não é lista")
    return [a for a in afs if isinstance(a, dict)]


def _normalizar(t: str) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip()


def _numeros_obrigatorios(f: Ficha) -> list[str]:
    """Medidas que a descrição não pode perder (mesma formatação do parágrafo determinístico)."""
    out = []
    for x in f.fatos:
        if x.nivel not in (Nivel.MEDIDO, Nivel.REGRA) or not isinstance(x.valor, (int, float)):
            continue
        if x.chave == "ict":
            out.append(LA._n(float(x.valor)))
        elif x.chave in LA._MEDIDA_ORACAO:
            out.append(LA._MEDIDA_ORACAO[x.chave][2](float(x.valor)))
    return out


def _conteudo_completo(texto: str, f: Ficha) -> bool:
    baixo = texto.lower()
    if any(p not in baixo for p in LA.PALAVRAS_REGIAO.values()):
        return False
    if any(n not in texto for n in _numeros_obrigatorios(f)):
        return False
    ict = [x for x in f.fatos if x.chave == "ict" and x.nivel in (Nivel.MEDIDO, Nivel.REGRA)]
    return not ict or "±0,05" in texto


def _validar(afs: list[dict], f: Ficha) -> tuple[list[str], int, int]:
    """(orações aceitas, total avaliado, removidas). Orações de pneumotórax/tubos da IA são descartadas sem contar:
    a frase CRITICO fixa as substitui."""
    aceitas, total, removidas = [], 0, 0
    ids = {x.id for x in f.fatos}
    for a in afs:
        texto = _normalizar(a.get("texto"))
        if not texto or _PNEUMO.search(texto):
            continue
        total += 1
        citados = [str(i) for i in a.get("fatos") or []]
        motivos = (["fato inexistente"] if any(i not in ids for i in citados) else []) or LA.problemas_oracao(texto, citados, f)
        if motivos:
            log.info("afirmação da IA removida: %s | %s", motivos[0][:80], texto[:120])
            removidas += 1
        else:
            aceitas.append(texto)
    return aceitas, total, removidas


def _compor(aceitas: list[str], f: Ficha) -> Optional[str]:
    from ..llm.guard import scan_text

    texto = _normalizar(" ".join(aceitas + [LA.CRITICO]))
    if len(texto) > MAX_CARACTERES or LX.termos_proibidos(texto) or scan_text(texto):
        return None
    if not _conteudo_completo(texto, f):
        log.info("descrição da IA perdeu região/medida obrigatória")
        return None
    return texto


def aplicar(laudo: LA.LaudoRX, a: RXAnalysis, chamar: Optional[Chamar] = None) -> LA.LaudoRX:
    """Laudo com `descricao_completa` redigida pela IA e verificada, ou o próprio laudo (determinístico) se algo falhar.
    `chamar(sistema, usuario) -> json`; sem ele usa o cliente LLM do app (precisa de provedor e MEDLENS_RX_DESCRICAO_IA!=0)."""
    base = laudo.descricao_completa
    if not base or not ia_habilitada():
        return laudo
    if chamar is None:
        from ..llm import client as c

        if not c.ai_available():
            return laudo
        chamar = _chamar_padrao
    try:
        f = build_ficha(a)
        aceitas, total, removidas = _validar(_afirmacoes(chamar(SISTEMA, _contexto(laudo, f, base))), f)
        validacao = {"frases": total, "removidas": removidas}
        retencao = (total - removidas) / total if total else 0.0
        texto = _compor(aceitas, f) if retencao >= LIMITE_RETENCAO else None
        if texto is None:
            log.warning("descricao_completa da IA descartada (retenção %.2f); vale a determinística", retencao)
            return laudo.model_copy(update={"descricao_validacao": validacao})
        return laudo.model_copy(update={"descricao_completa": texto, "descricao_origem": "ia",
                                        "descricao_validacao": validacao})
    except Exception as e:  # recusa, erro de rede, JSON inválido, PHI bloqueado...: falha fechada
        log.warning("descricao_completa por IA indisponível (%s); vale a determinística", type(e).__name__)
        return laudo
