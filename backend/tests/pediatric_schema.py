"""Espelho Python do esquema estrito (Zod .strict()) do contrato ResultadoExame de
docs/PEDIATRIA-INTEGRACAO-PLANO.md §2, em snake_case. Campo desconhecido ou de tipo errado reprova."""
import re

VETADO = re.compile(r"\b(normal|anormal|aumentad|reduzid|prolongad|curto|hipertrofi|sobrecarga|cardiomegalia|"
                    r"bloqueio|desvio do eixo|isquemi|infarto|pneumonia|derrame|consolida)", re.I)

TOP_OBRIGATORIOS = {"tipo", "modo", "idade_meses", "medidas", "qualidade", "descricao_tecnica", "avisos",
                    "versao_motor"}
TOP_OPCIONAIS = {"incidencia", "regiao"}
MEDIDA_OBRIG = {"codigo", "rotulo", "valor", "unidade", "confiavel"}
MEDIDA_OPC = {"nota"}


def _chaves(d: dict, obrig: set, opc: set, onde: str) -> None:
    ks = set(d)
    assert obrig <= ks, f"{onde}: faltam {obrig - ks}"
    assert ks <= obrig | opc, f"{onde}: campos fora do esquema {ks - obrig - opc}"


def validar_contrato(d: dict) -> None:
    _chaves(d, TOP_OBRIGATORIOS, TOP_OPCIONAIS, "raiz")
    assert d["tipo"] in ("ecg", "rx")
    assert d["modo"] == "pediatrico"
    assert d["idade_meses"] is None or (isinstance(d["idade_meses"], int) and 0 <= d["idade_meses"] <= 215)
    for k in ("incidencia", "regiao"):
        assert k not in d or isinstance(d[k], str)
    assert isinstance(d["medidas"], list)
    for m in d["medidas"]:
        _chaves(m, MEDIDA_OBRIG, MEDIDA_OPC, "medida")
        assert isinstance(m["codigo"], str) and isinstance(m["rotulo"], str) and isinstance(m["unidade"], str)
        assert isinstance(m["valor"], (int, float)) and not isinstance(m["valor"], bool)
        assert isinstance(m["confiavel"], bool)
        assert "nota" not in m or isinstance(m["nota"], str)
    assert isinstance(d["qualidade"], list)
    for q in d["qualidade"]:
        _chaves(q, {"codigo", "texto", "nivel"}, set(), "qualidade")
        assert q["nivel"] in ("info", "alerta")
        assert isinstance(q["codigo"], str) and isinstance(q["texto"], str)
    assert isinstance(d["descricao_tecnica"], str) and d["descricao_tecnica"]
    assert isinstance(d["avisos"], list) and d["avisos"] and all(isinstance(a, str) for a in d["avisos"])
    assert isinstance(d["versao_motor"], str) and d["versao_motor"]


def textos_filtrados(d: dict) -> list[str]:
    """Textos sujeitos ao filtro de vocabulário no Pediatria: descricao_tecnica, avisos, qualidade[].texto."""
    return [d["descricao_tecnica"], *d["avisos"], *(q["texto"] for q in d["qualidade"])]
