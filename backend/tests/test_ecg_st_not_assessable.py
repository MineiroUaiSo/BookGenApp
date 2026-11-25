"""ST não avaliável (BRE, marca-passo ventricular, QRS >= 120 ms), texto não tranquilizador e STE em BRD.

Sem Sgarbossa (decisão clínica do médico): só avisa que isquemia/STE não é avaliável de forma confiável."""
from __future__ import annotations

import pytest

import laudo_fixtures as F
from app.ecg import features as FT
from tests.test_ecg_analysis import _brd_prec, _lbbb_prec, codes, run, sinus
from tests.test_ecg_pacing import paced_ventricular
from synth_ecg import synth_signal

ST_NOT_ASSESSABLE_CODE = "ecg.st_not_assessable"


def _achado(a, code):
    return next((f for f in a.findings if f.code == code), None)


def _normal():
    L, _ = sinus(70, noise=0.005)
    return run(L)


def _lbbb():
    L, _ = sinus(70, qrs_scale=1.35, prec=_lbbb_prec(), axis_deg=10, noise=0.005)
    return run(L)


# ---------------------------------------------------------------- texto tranquilizador
def test_normal_pelas_regras_nao_diz_sem_alteracoes_e_avisa_que_nao_exclui():
    f = _achado(_normal(), "ecg.within_normal_limits")
    assert f is not None
    low = f.label.lower()
    assert "sem alterações" not in low and "sem alteracoes" not in low
    assert "nenhuma regra automática disparou" in low and "não exclui" in low
    assert "iam" in low and "bav" in low


def test_ficha_v2_do_normal_carrega_o_texto_cauteloso():
    a = _normal()
    ficha = FT.features_from_analysis(a)
    fato = next(x for x in ficha.fatos if x.codigo == "ecg.within_normal_limits")
    assert "não exclui" in fato.texto and "sem alterações" not in fato.texto.lower()


# ---------------------------------------------------------------- ST não avaliável
def test_bre_emite_aviso_st_nao_avaliavel_sem_sgarbossa_implementado():
    a = _lbbb()
    f = _achado(a, ST_NOT_ASSESSABLE_CODE)
    assert f is not None and f.severity != "critical"
    txt = " ".join([f.label, *f.evidence]).lower()
    assert "não avaliável" in txt and "sgarbossa" in txt and "smith" in txt and "bre" in txt.replace("bloqueio de ramo esquerdo", "bre")
    assert not any(c.startswith("ecg.sgarbossa") for c in codes(a))


def test_marcapasso_ventricular_emite_aviso_st_nao_avaliavel():
    leads, _ = paced_ventricular()
    a = run(leads)
    f = _achado(a, ST_NOT_ASSESSABLE_CODE)
    assert "ecg.paced_rhythm" in codes(a) and f is not None
    assert "marca-passo" in " ".join(f.evidence).lower()


def test_qrs_largo_sem_bloqueio_definido_emite_aviso_st_nao_avaliavel():
    leads, _ = synth_signal(hr=70, qrs_ms=150, noise_mv=0.01, wander_mv=0.1, seed=3)
    a = run(leads)
    assert a.global_measurements.qrs_ms >= 120
    f = _achado(a, ST_NOT_ASSESSABLE_CODE)
    assert f is not None and "120" in " ".join(f.evidence)


def test_qrs_estreito_nao_emite_aviso_st_nao_avaliavel():
    assert _achado(_normal(), ST_NOT_ASSESSABLE_CODE) is None


def test_aviso_st_nao_avaliavel_aparece_no_topo_da_ficha_v2():
    ficha = FT.features_from_analysis(_lbbb())
    assert any("não avaliável" in x and "Sgarbossa" in x for x in ficha.aviso_topo)
    assert any(f.codigo == ST_NOT_ASSESSABLE_CODE for f in ficha.fatos)


def test_ficha_sem_o_aviso_nao_ganha_aviso_de_st_no_topo():
    ficha = FT.features_from_summary(F.CASO1_OK, sexo="M")
    assert not any("Sgarbossa" in x for x in ficha.aviso_topo)


# ---------------------------------------------------------------- BRD: STE de V1-V3 não é mais suprimido
def test_brd_mantem_supradesnivelamento_de_v1_a_v3_como_achado():
    L, _ = sinus(75, qrs_scale=1.5, prec=_brd_prec(), axis_deg=30, noise=0.005,
                 st={"V1": 0.3, "V2": 0.35, "V3": 0.3})
    a = run(L)
    c = codes(a)
    assert "ecg.rbbb" in c
    ste = [f for f in a.findings if f.code.startswith("ecg.st_elevation_")]
    assert ste, c
    assert any("bloqueio de ramo" in " ".join(f.evidence) for f in ste)     # com a ressalva de cautela
    # ST segue avaliável no BRD (Sgarbossa vale p/ BRE e marca-passo): sem aviso de "não avaliável"
    assert _achado(a, ST_NOT_ASSESSABLE_CODE) is None
    assert any("não esperado no BRD" in " ".join(f.evidence) and "Brugada" in " ".join(f.evidence) for f in ste)


def test_bre_continua_sem_supradesnivelamento_plano_de_v1_a_v3():
    L, _ = sinus(70, qrs_scale=1.35, prec=_lbbb_prec(), axis_deg=10, noise=0.005,
                 st={"V1": 0.25, "V2": 0.3, "V3": 0.25})
    assert not any(x.startswith("ecg.st_elevation") for x in codes(run(L)))


def test_brd_isolado_tambem_nao_emite_st_nao_avaliavel():
    L, _ = sinus(75, qrs_scale=1.5, prec=_brd_prec(), axis_deg=30, noise=0.005)
    a = run(L)
    assert _achado(a, ST_NOT_ASSESSABLE_CODE) is None


def test_aviso_st_nao_avaliavel_nao_cita_brd_nem_qrs_generico():
    from app.ecg.features import AVISO_ST_NAO_AVALIAVEL
    assert "QRS >= 120" not in AVISO_ST_NAO_AVALIAVEL
    assert "BRD" not in AVISO_ST_NAO_AVALIAVEL and "direito" not in AVISO_ST_NAO_AVALIAVEL
