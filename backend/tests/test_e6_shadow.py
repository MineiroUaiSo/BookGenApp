"""Unit tests for the E6 shadow-mode metric helpers (bench only)."""
import numpy as np

from bench import e6_shadow as e6


def test_auc_perfect_and_inverted():
    y = np.array([0, 0, 1, 1])
    assert e6.auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert e6.auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == 0.0


def test_auc_ties_count_half():
    y = np.array([0, 1])
    assert e6.auc(y, np.array([0.5, 0.5])) == 0.5


def test_auc_nan_without_both_classes():
    assert np.isnan(e6.auc(np.array([1, 1]), np.array([0.2, 0.3])))


def test_sens_at_spec_uses_negative_quantile():
    y = np.array([0] * 10 + [1] * 4)
    s = np.array([i / 10 for i in range(10)] + [0.95, 0.5, 0.2, 1.0])
    # 90th percentile of negatives = 0.81 -> only scores > 0.81 count: 0.95 and 1.0
    assert e6.sens_at_spec(y, s, 0.9) == 0.5


def test_counts_and_prf():
    y = np.array([1, 1, 0, 0, 0], dtype=bool)
    p = np.array([1, 0, 1, 0, 0], dtype=bool)
    assert e6.counts(y, p) == (1, 1, 1, 2)
    se, sp, ppv = e6.prf(1, 1, 1, 2)
    assert (se, round(sp, 3), ppv) == (0.5, 0.667, 0.5)


def test_kappa_agreement_and_chance():
    a = np.array([1, 0, 1, 0], dtype=bool)
    assert e6.kappa(a, a) == 1.0
    assert abs(e6.kappa(a, ~a) + 1.0) < 1e-9


def test_label_maps_cover_model_classes():
    assert set(e6.MAP) == set(e6.CLASSES) == set(e6.PAPER_THR)
