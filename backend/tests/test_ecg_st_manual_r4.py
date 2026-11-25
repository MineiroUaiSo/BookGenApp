"""R4 T4: com BRE ou marca-passo ventricular o ST e declarado nao interpretavel pelas regras (aplicar Sgarbossa/Smith
manualmente) e o caso nunca sai como 'sem alteracoes'/normal. Sgarbossa NAO e implementado."""
from __future__ import annotations

import pytest

from app.ecg import features as FT
from tests.test_ecg_analysis import _lbbb_prec, codes, run, sinus
from tests.test_ecg_pacing import paced_ventricular

NOTE = "ST não interpretável pelas regras; aplicar Sgarbossa/Smith manualmente"
ST_CODE = "ecg.st_not_assessable"


def _lbbb():
    L, _ = sinus(70, qrs_scale=1.35, prec=_lbbb_prec(), axis_deg=10, noise=0.005)
    return run(L)


def _paced():
    leads, _ = paced_ventricular()
    return run(leads)


@pytest.fixture(params=["bre", "marcapasso"])
def caso(request):
    return _lbbb() if request.param == "bre" else _paced()


def test_st_nao_interpretavel_texto_literal_no_achado(caso):
    f = next((f for f in caso.findings if f.code == ST_CODE), None)
    assert f is not None
    assert NOTE in f.label


def test_bre_ou_marcapasso_nunca_sai_como_sem_alteracoes(caso):
    c = codes(caso)
    assert "ecg.within_normal_limits" not in c
    assert any(f.severity in ("abnormal", "critical") for f in caso.findings)
    assert not any(code.startswith("ecg.sgarbossa") for code in c)


def test_st_nao_interpretavel_no_topo_da_ficha(caso):
    ficha = FT.features_from_analysis(caso)
    assert any(NOTE in x for x in ficha.aviso_topo), ficha.aviso_topo
