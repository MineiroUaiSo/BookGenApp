"""Barreira LGPD: corpus estático (conhecimento + prompts) NUNCA bloqueia; corpus sintético de dado pessoal SEMPRE bloqueia.
Sem rede, sem PHI real (todos os dados abaixo são fabricados)."""
from pathlib import Path

import pytest

from app import llm
from app.llm import guard as G
from app.llm import laudo as L

KNOWLEDGE = Path(__file__).resolve().parents[2] / "knowledge"
PROMPTS = Path(llm.__file__).parent / "prompts"


def _estaticos():
    for p in sorted(KNOWLEDGE.rglob("*.yaml")):
        yield f"knowledge/{p.relative_to(KNOWLEDGE)}", p.read_text(encoding="utf-8")
    for p in sorted(PROMPTS.glob("*.md")):
        yield f"prompts/{p.name}", p.read_text(encoding="utf-8")
    yield "system_prompt_v2", L.system_prompt_v2()
    for dom in ("ecg", "rx"):
        for i, b in enumerate(llm._system_blocks(dom)):
            yield f"_two_stage/system/{dom}/{i}", b["text"]
        yield f"_two_stage/{dom}_describe", llm._prompt(f"{dom}_describe")
    yield "_two_stage/analyze", llm._prompt("analyze")


ESTATICOS = list(_estaticos())


def test_corpus_estatico_nao_vazio_e_cobre_yaml_de_conhecimento():
    ids = [n for n, _ in ESTATICOS]
    assert any(n.startswith("knowledge/ecg/cards/") for n in ids)
    assert "knowledge/references.yaml" in ids and "system_prompt_v2" in ids
    assert "_two_stage/system/ecg/1" in ids and "_two_stage/system/rx/1" in ids


@pytest.mark.parametrize("nome,texto", ESTATICOS, ids=[n for n, _ in ESTATICOS])
def test_texto_estatico_nao_e_bloqueado(nome, texto):
    assert G.scan_text(texto) is None, (nome, G.scan_text(texto))


def test_payload_dois_estagios_montado_com_conhecimento_completo_passa_na_barreira():
    for dom in ("ecg", "rx"):
        G.assert_payload(llm._system_blocks(dom), [{"role": "user", "content": [
            {"type": "text", "text": llm._prompt(f"{dom}_describe")}, {"type": "text", "text": llm._prompt("analyze")}]}])


# ---------------------------------------------------------------- corpus sintético de dado pessoal (fabricado)
PESSOAIS = [
    "CPF 529.982.247-25", "cpf: 52998224725", "CPF do paciente 111.444.777-35", "doc 11144477735",
    "Nascimento 01/02/1960", "nasc. 1-2-1960", "exame em 12-03-2024", "coleta 12.03.2024", "realizado 2024-03-12",
    "Data: 05/11/2025 14:30", "em 5 de novembro de 2025", "nov/2025 internação",
    "contato maria.silva@example.com", "joao_pereira+exame@hospital.org.br",
    "tel (27) 99876-5432", "celular 27 998765432", "+55 27 99876-5432", "fone 3333-4444", "WhatsApp 11987654321",
    "CNS 898 0001 0000 0004", "CNS: 700000000000005", "RG 12.345.678-9", "RG: MG-12.345.678", "prontuário 123456",
    "MRN 998877", "ORDER ECG 20251105-0042",
    "data:image/png;base64,iVBORw0KGgo", "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMC", "A" * 300,
]


@pytest.mark.parametrize("texto", PESSOAIS)
def test_corpus_sintetico_de_dado_pessoal_e_bloqueado(texto):
    assert G.scan_text(texto) is not None, texto
    with pytest.raises(G.PayloadBloqueado):
        G.assert_text_only("sistema neutro", f"Descrição técnica. {texto}")
    with pytest.raises(G.PayloadBloqueado):
        G.assert_payload([{"type": "text", "text": "sistema"}], [{"role": "user", "content": [{"type": "text", "text": texto}]}])


def test_corpus_nao_pessoal_clinico_passa():
    for t in ("QRS 112 ms, PR 148 ms, FC 75 bpm", "Sokolow-Lyon 35 mm (limiar 35)", "ST +2,5 mm em V2",
              "Cornell 2440 mm.ms", "idade 65 anos", "AHA/ACC/HRS 2009; SBC 2022", "R/S em V1 > 1", "eixo -30 graus"):
        assert G.scan_text(t) is None, t
