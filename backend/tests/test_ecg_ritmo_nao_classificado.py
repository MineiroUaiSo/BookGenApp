"""M2-A: sinal `unreliable` do detector de R (E2) chega às regras: FC detectada > 150 bpm sem ritmo classificado
emite `ecg.rhythm_unclassified_fast_rate` (aviso, nunca normal). Limiares de FA/STACH e demais regras intocados."""
from __future__ import annotations

import numpy as np
from synth_ecg import synth_signal
from test_ecg_analysis import codes, run
from test_ecg_rpeaks_t_alta import FS, _amp_ref, _hr, _tspike

from app.ecg.analysis import rpeaks
from app.ecg.analysis import rules
from app.llm import descricao_ecg as D

CODE = "ecg.rhythm_unclassified_fast_rate"


def _ambiguo():
    """T estreita a ~meio ciclo (85 bpm real): o detector conta 157 bpm e marca unreliable."""
    leads, _ = _tspike(85, ratio=0.5, off=0.383)
    pk, _, unreliable = rpeaks.detect_r_peaks_ex(_amp_ref(leads), FS)
    assert unreliable and 60.0 * FS / np.median(np.diff(pk)) > 150   # premissa do teste
    return leads


def test_ritmo_t_08_a_75bpm_nao_gera_achado_novo():
    leads, _ = _tspike(75, ratio=0.8)
    a = run(leads)
    assert abs(_hr(a) - 75) <= 3 and CODE not in codes(a)


def test_ritmo_sinal_ambiguo_acima_de_150_gera_achado_de_aviso():
    a = run(_ambiguo())
    assert _hr(a) > 150 and CODE in codes(a)
    f = next(f for f in a.findings if f.code == CODE)
    assert f.severity == "borderline" and f.origin == "rules"
    assert f.label.startswith("Ritmo não classificado: possível dupla contagem de QRS (onda T)")
    assert "acima de 150 bpm" in f.label and "confirmar o traçado" in f.label
    assert f.references
    assert "ecg.within_normal_limits" not in codes(a)    # nunca "normal" com ritmo não classificado


def test_ritmo_taquicardia_real_160_regular_sem_unreliable_nao_gera():
    leads, _ = synth_signal(hr=160, noise_mv=0.01, seed=1)
    a = run(leads)
    assert abs(_hr(a) - 160) <= 5 and CODE not in codes(a)


def test_ritmo_regra_dispara_so_com_unreliable_e_fc_acima_de_150():
    assert rules.rhythm_unclassified_fast_rate(160.0, True, []) is not None
    assert rules.rhythm_unclassified_fast_rate(160.0, False, []) is None
    assert rules.rhythm_unclassified_fast_rate(150.0, True, []) is None
    assert rules.rhythm_unclassified_fast_rate(None, True, []) is None


def test_ritmo_outra_regra_de_ritmo_acionada_suprime_o_achado():
    class F:   # só o código importa
        def __init__(self, code):
            self.code = code
    assert rules.rhythm_unclassified_fast_rate(170.0, True, [F("ecg.atrial_fibrillation")]) is None
    assert rules.rhythm_unclassified_fast_rate(170.0, True, [F("ecg.atrial_flutter")]) is None
    # taquicardia sinusal é só a regra de FC corrompida pela mesma dupla contagem: não conta como ritmo classificado
    assert rules.rhythm_unclassified_fast_rate(170.0, True, [F("ecg.sinus_tachycardia")]) is not None


def test_ritmo_descricao_completa_cita_a_abstencao():
    a = run(_ambiguo())
    from app.llm import ecg_data_summary
    from app.llm import laudo as L
    prepared = L.prepare_summary(ecg_data_summary(a), sexo="M")
    texto = D.compor_descricao(prepared).texto
    assert "ritmo não classificado" in texto.lower() and "dupla contagem" in texto
