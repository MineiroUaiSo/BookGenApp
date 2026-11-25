"""Ficha de medidas ecg_features/v1: identificadores estáveis [F..] (fatos) e [C..] (cartões de critério)."""
import json

import laudo_fixtures as F
from app.ecg import features as FT


def _ficha(summary=F.CASO1_OK, **kw):
    return FT.features_from_summary(summary, **kw)


def _walk(o, path=""):
    """Gera (caminho, valor) de todo escalar da ficha serializada."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, o


def test_ficha_ids_sao_contiguos_e_estaveis_entre_execucoes():
    a, b = _ficha(), _ficha()
    assert a.to_json() == b.to_json()
    assert [f.id for f in a.fatos] == [f"F{i}" for i in range(1, len(a.fatos) + 1)]
    assert [c.id for c in a.cartoes] == [f"C{i}" for i in range(1, len(a.cartoes) + 1)]
    assert a.schema_ == "ecg_features/v1" and 1 <= len(a.cartoes) <= 20


def test_ficha_serializada_nao_tem_nulos():
    nulos = [p for p, v in _walk(json.loads(_ficha().to_json())) if v is None]
    assert nulos == []


def test_ficha_fato_global_traz_valor_e_unidade():
    f = _ficha()
    fc = f.fato_por_chave("globais.heart_rate_bpm")
    assert fc.valor == 68 and fc.unidade == "bpm" and "68" in fc.texto
    pr = f.fato_por_chave("globais.pr_ms")
    assert pr.valor == 148 and pr.unidade == "ms"


def test_ficha_derivacao_em_mm_a_partir_de_mv():
    v5 = _ficha().fato_por_chave("derivacao.V5")
    assert "R 55 mm" in v5.texto and "S 3 mm" in v5.texto
    assert "r_amplitude_mv" in v5.chaves


def test_ficha_indices_hve_vem_prontos_e_com_limiar():
    f = _ficha(sexo="M")
    sok = f.fato_por_chave("indice.sokolow_lyon")
    assert "60" in sok.texto and "35" in sok.texto and sok.unidade == "mm"
    assert "indices.sokolow_mm" in sok.chaves
    assert f.fato_por_chave("indice.romhilt_estes") is not None


def test_ficha_cartoes_selecionados_incluem_criterio_do_achado():
    f = _ficha()
    ids = {c.card_id for c in f.cartoes}
    assert "lvh.sokolow_lyon" in ids
    assert all(c.criterio and c.nome for c in f.cartoes)


def test_ficha_narrativa_tem_um_identificador_por_linha_e_abre_com_estado():
    n = _ficha().narrative().splitlines()
    assert n[0].startswith("[F1]") and "digitalização" in n[0].lower()
    assert all(l.startswith("[F") for l in n)


def test_ficha_qualidade_ok_sem_divergencia():
    f = _ficha()
    assert f.qualidade.nivel == "ok" and f.aviso_topo == [] and f.suprimidos == []


def test_ficha_caso1_errado_vira_suspeita_e_nao_expoe_medida_divergente():
    f = _ficha(F.CASO1_ERRADA)
    assert f.qualidade.nivel == "suspeita"
    assert f.aviso_topo and "112" in " ".join(f.aviso_topo)
    nar = f.narrative()
    assert "270" not in nar.replace("[F", "") and "wpw" not in nar.lower() and "pré-excita" not in nar.lower()
    assert f.fato_por_chave("globais.qrs_ms").nao_avaliavel is True
    assert f.fato_por_chave("globais.pr_ms").nao_avaliavel is True
    assert {s.categoria for s in f.suprimidos} >= {"PR", "QRS", "ST"}
    assert not [x for x in f.fatos if x.codigo.startswith(("ecg.wpw", "ecg.st_depression"))]


def test_ficha_derivacao_com_qualidade_baixa_fica_nao_avaliavel():
    s = {**F.CASO1_OK, "qualidade_por_derivacao": {"V5": 0.2, "V6": 0.9}}
    f = _ficha(s)
    v5 = f.fato_por_chave("derivacao.V5")
    assert v5.nao_avaliavel is True and "não avaliável" in v5.texto and "55" not in v5.texto
    assert f.fato_por_chave("derivacao.V6").nao_avaliavel is False


def test_ficha_sem_medidas_e_invalida():
    f = FT.features_from_summary({"medidas_globais": {}, "medidas_por_derivacao": [], "achados_por_regras": []})
    assert f.qualidade.nivel == "invalida" and f.qualidade.motivos


def test_ficha_nao_carrega_identificacao_do_paciente():
    s = {**F.CASO1_OK, "paciente": "Maria Souza", "study_id": "ORDER ECG22125996",
         "cabecalho_impresso": {**F.PRINTED, "nome": "Maria Souza", "id": "ORDER ECG22125996"},
         "contexto": {"sexo": "M", "nome": "Joao Pereira", "nascimento": "01/02/1960"},
         "avisos": ["Paciente Maria Souza CPF 123.456.789-09 nasc 01/02/1960"]}
    f = _ficha(s)
    blob = f.to_json() + f.narrative()
    for proibido in ("Maria", "Souza", "ORDER", "ECG22125996", "Joao", "123.456.789", "01/02/1960"):
        assert proibido not in blob


def test_ficha_a_partir_de_analise_real_sintetica():
    from app.ecg.analysis import analyze_signal
    from app.schemas import ECGSignal, SourceKind
    from synth_ecg import synth_signal
    leads, _ = synth_signal(hr=72, seed=1)
    sig = ECGSignal(fs=500, leads={k: [float(x) for x in v] for k, v in leads.items()}, duration_s=10.0,
                    source=SourceKind.CSV)
    a = analyze_signal(sig, "t")
    f = FT.features_from_analysis(a, sexo="M")
    assert f.fato_por_chave("globais.heart_rate_bpm") is not None
    assert f.qualidade.nivel == "ok" and f.cartoes
    assert [x.id for x in f.fatos] == [f"F{i}" for i in range(1, len(f.fatos) + 1)]
