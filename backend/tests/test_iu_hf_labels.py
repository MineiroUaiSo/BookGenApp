"""iu_xray --hf mirror: negation-aware text labels (no network)."""
from medlens_data.collectors.iu_xray import text_labels


def test_text_labels_skips_negated_findings():
    assert text_labels("There is no pneumothorax. No pleural effusion.") == []


def test_text_labels_detects_positive_findings():
    got = text_labels("Mild cardiomegaly. Small left pleural effusion. No pneumothorax.")
    assert "rx.cardiomegaly" in got and "rx.pleural_effusion" in got and "rx.pneumothorax" not in got


def test_text_labels_normal_report():
    assert text_labels("The heart is normal in size. No acute cardiopulmonary abnormality.") == ["rx.normal"]
