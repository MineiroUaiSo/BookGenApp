import json
import re

import pytest

from app import llm
from app.llm import laudo as L
from app.schemas import AIReport
import laudo_fixtures as F


def _gen(summary, resp, **kw):
    prepared = L.prepare_summary(summary, **kw)
    return prepared, L.generate_laudo(prepared, lambda s, u: resp)


def test_laudo_schema_is_strict_and_matches_model():
    sch = L.output_schema()
    assert sch["additionalProperties"] is False and set(sch["required"]) == set(sch["properties"])
    assert "validacao" not in sch["properties"] and "impressao" in sch["properties"]


def test_laudo_prompt_versioned_and_has_hard_rules():
    p = L.system_prompt()
    assert L.PROMPT_VERSION in p and "aviso_topo" in p and "NÃO diagnostique" in p


@pytest.mark.parametrize("name", ["normal", "iam", "fa"])
def test_laudo_fewshot_examples_validate_clean(name):
    summary, resp = F.FEWSHOT[name]
    _, lau = _gen(summary, resp)
    assert lau.validacao["numeros_divergentes"] == 0, lau.avisos_validacao
    assert lau.validacao["numeros_fora_das_medidas"] == 0, lau.avisos_validacao
    assert lau.validacao["criticos_sem_lastro"] == 0
    md = L.render_markdown(lau)
    assert "## IMPRESSÃO DIAGNÓSTICA" in md and "## Intervalos" in md and "Rascunho" in md


def test_laudo_caso1_wrong_digitization_opens_with_discordance_and_denies_preexcitation():
    prepared, lau = _gen(F.CASO1_ERRADA, F.CASO1_ERRADA_RESP, sexo="M")
    assert {a["medida"] for a in L.digitization_alerts(prepared)} >= {"PR", "QRS"}
    assert lau.aviso_topo and "112" in " ".join(lau.aviso_topo)
    md = L.render_markdown(lau)
    assert md.index("DISCORDÂNCIA") < md.index("## Qualidade técnica")
    text = " ".join([lau.complexo_qrs, lau.st_t, *lau.impressao])
    assert not re.search(r"(?<!não avali)(síndrome de pré|WPW|isquemia miocárdica)", text, re.I)


def test_laudo_caso1_wrong_with_misbehaving_llm_is_scrubbed_and_topped():
    _, lau = _gen(F.CASO1_ERRADA, F.CASO1_ERRADA_BAD_RESP, sexo="M")
    assert lau.aviso_topo, "validador deve abrir com a discordância mesmo se a LLM não abriu"
    assert lau.validacao["afirmacoes_removidas"] >= 3
    joined = " ".join([lau.complexo_qrs, lau.st_t, *lau.impressao])
    assert not re.search(r"pré-excita|WPW|isquemi|infra de ST", joined, re.I)
    assert "Hipertrofia ventricular esquerda por voltagem." in lau.impressao   # achado confiável preservado


def test_laudo_caso1_correct_gives_lve_and_cmh_pattern():
    prepared, lau = _gen(F.CASO1_OK, F.CASO1_OK_RESP, sexo="M")
    assert L.digitization_alerts(prepared) == []
    idx = prepared["indices_calculados"]
    assert idx["cornell_mm"] == 58.0 and idx["sokolow_lyon_mm"] == 60.0 and idx["peguero_preenchido"] is False
    assert idx["romhilt_estes_pontos"] == 6
    assert lau.aviso_topo == []
    imp = " ".join(lau.impressao).lower()
    assert "sobrecarga de câmaras esquerdas" in imp and "miocardiopatia hipertrófica" in imp
    assert "repolarização secundária" in imp and "não como isquemia" in imp
    assert "sem desvio de eixo" in lau.eixos and "Peguero" in lau.complexo_qrs and "focal" in lau.complexo_qrs
    assert lau.validacao["numeros_divergentes"] == 0, lau.avisos_validacao
    assert lau.validacao["numeros_fora_das_medidas"] == 0, lau.avisos_validacao


def test_laudo_number_not_in_measures_is_flagged():
    resp = json.loads(F.NORMAL_RESP)
    resp["intervalos"] = "PR 160 ms, QRS 140 ms, QT 380 ms."
    _, lau = _gen(F.NORMAL, json.dumps(resp))
    assert lau.validacao["numeros_divergentes"] >= 1
    assert "[⚠" in lau.intervalos and any("QRS" in a for a in lau.avisos_validacao)


def test_laudo_unverified_numbers_ignores_leads_grid_and_references():
    s = L.prepare_summary(F.NORMAL)
    assert L.unverified_numbers("Em V5 e D2, 25 mm/s e 10 mm/mV; Cornell limite 28 mm; FC 72 bpm.", s) == []
    assert L.unverified_numbers("FC de 131 bpm.", s) == ["131 bpm"]


def test_laudo_critical_claim_without_rule_is_marked():
    resp = json.loads(F.NORMAL_RESP)
    resp["impressao"] = ["Taquicardia ventricular sustentada."]
    _, lau = _gen(F.NORMAL, json.dumps(resp))
    assert lau.validacao["criticos_sem_lastro"] == 1 and "não corroborado" in lau.impressao[0]


def test_laudo_short_version_is_single_paragraph():
    _, lau = _gen(F.CASO1_OK, F.CASO1_OK_RESP, sexo="M")
    short = L.render_short(lau)
    assert "\n" not in short and "Impressão:" in short and short.endswith("Rascunho para revisão médica.")


def test_laudo_compute_indices_needs_sex_for_limits():
    idx = L.compute_indices(F.CASO1_OK)
    assert "cornell_mm" in idx and "cornell_limite_mm" not in idx and "peguero_preenchido" not in idx


def test_laudo_endpoint_fields_added_to_ai_report(monkeypatch):
    monkeypatch.setenv("MEDLENS_LAUDO", "1")
    extra = llm.ecg_laudo_fields(F.CASO1_OK, sexo="M", call=lambda s, u: F.CASO1_OK_RESP)
    rep = AIReport(**extra)
    assert rep.laudo["impressao"] and rep.laudo_markdown.startswith("# Laudo de ECG") and rep.laudo_curto
    assert AIReport().laudo is None and AIReport().laudo_markdown == ""   # contrato antigo intacto


def test_laudo_fields_never_raise_on_bad_llm_output():
    assert llm.ecg_laudo_fields(F.NORMAL, call=lambda s, u: "não é json") == {}
