"""R4: structures the pipeline cannot segment are 'não suportado', never scored as Dice 0."""
from app.rx.analyze import supported_structures
from bench.rx_bench import norm_struct


def test_supported_model_has_no_sternum_or_ribs():
    s = supported_structures("model", "frontal")
    assert {"left_lung", "right_lung", "heart", "lungs"} <= s
    assert "sternum" not in s and "ribs" not in s


def test_supported_lateral_has_no_aorta():
    s = supported_structures("model", "lateral")
    assert "aorta" not in s and "sternum" in s and "lungs" in s


def test_norm_struct_image_side_names_flip_to_patient_side():
    # Shenzhen masks are named by image side; patient right = image left in standard display
    assert norm_struct("lung_image_left") == "right_lung"
    assert norm_struct("lung_image_right") == "left_lung"
    assert norm_struct("left_lung") == "left_lung"
