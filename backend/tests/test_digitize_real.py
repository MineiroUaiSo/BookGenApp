"""Robustness cases seen on real web images: strips, cropped pages, pulse on the right, dark grid lines, no grid."""
import numpy as np
import pytest
from scipy.signal import find_peaks

from app.ecg.digitize import digitize_image, trace
from synth_ecg import LEAD_ORDER, render_paper, synth_signal

FS = 500


@pytest.fixture(scope="module")
def page():
    leads, fid = synth_signal(hr=75, fs=FS, seconds=10, seed=7)
    img, info = render_paper(leads, FS, px_per_mm=8, return_info=True)
    return leads, fid, img, info


def _rows(info, img, k0, k1):
    """crop the image to rows k0..k1-1 (half a pitch margin around each baseline)"""
    ys = info["row_baseline_px"]
    pitch = ys[1] - ys[0]
    return np.ascontiguousarray(img[int(ys[k0] - pitch / 2):int(ys[k1 - 1] + pitch / 2)])


def _hr_from(sig, lead):
    y = np.asarray(sig.leads[lead])
    pk, _ = find_peaks(y, height=0.5 * y.max(), distance=int(0.3 * FS))
    return 60.0 / np.median(np.diff(pk) / FS)


def test_rhythm_strip_only(page):
    leads, fid, img, info = page
    strip = _rows(info, img, 3, 4)
    sig, dbg = digitize_image(strip, return_debug=True)
    assert dbg["layout"] == "strips" and list(sig.leads) == ["II"]
    assert abs(sig.duration_s - 10) < 0.6
    assert abs(_hr_from(sig, "II") - 75) < 4


def test_two_strips_and_scale_without_pulse(page):
    leads, fid = page[:2]
    img, info = render_paper(leads, FS, px_per_mm=8, layout="12x1", return_info=True)
    x0 = int(info["x0_px"]) + 4
    crop = np.ascontiguousarray(_rows(info, img, 0, 2)[:, x0:])      # two long strips, no calibration pulse
    sig, dbg = digitize_image(crop, return_debug=True)
    assert dbg["layout"] == "strips" and len(sig.leads) == 2
    assert abs(sig.calibration["px_per_mm"] - 8) / 8 < 0.05
    assert abs(_hr_from(sig, "II") - 75) < 4


def test_3x4_without_rhythm_strip_has_offsets(page):
    leads, fid, img, info = page
    sig = digitize_image(_rows(info, img, 0, 3))
    assert set(sig.leads) == set(LEAD_ORDER)
    assert sig.calibration["offset_s.V1"] == pytest.approx(5.0, abs=0.3)
    # analysis must treat the 2.5 s leads as a staggered page, not as simultaneous recordings
    from app.ecg.analysis import analyze_signal
    an = analyze_signal(sig, "t")
    hr = an.global_measurements.heart_rate_bpm
    assert hr is not None and abs(hr - 75) < 8


def test_pulse_on_the_right_end(page):
    leads, fid, img, info = page
    f = np.ascontiguousarray(img[:, ::-1])                            # mirror: pulse now at the right end
    # mirrored traces are time-reversed, but scale/gain must come out right and a long trace must still be found
    sig, dbg = digitize_image(f, return_debug=True)
    assert sig.calibration["gain_mm_mv"] == 10
    assert abs(sig.calibration["px_per_mm"] - 8) / 8 < 0.05


def test_dark_vertical_grid_lines_do_not_become_trace(page):
    leads, fid, img, info = page
    g = img.copy()
    ppm = info["px_per_mm"]
    for i in range(0, g.shape[1], int(round(5 * ppm))):
        g[:, i:i + 2] = (60, 60, 60)
    sig = digitize_image(g)
    y = np.asarray(sig.leads["II"])
    assert np.max(np.abs(y)) < 2.0                                    # no full-height spikes
    assert abs(_hr_from(sig, "II") - 75) < 4


def test_grid_missing_falls_back_to_low_confidence(page):
    leads, fid, img, info = page
    white = img.copy()
    white[(white[..., 0] > 200) & (white[..., 1] > 100)] = 255       # wipe the pink grid, keep black ink
    sig = digitize_image(white)
    assert sig.calibration["grid_confidence"] <= 0.5
    assert len(sig.leads) >= 1


def test_triplet_classifier_limb_vs_chest(page):
    leads, fid, img, info = page
    limb = trace.classify_triplet([leads["I"], leads["II"], leads["III"]])
    assert limb[0] < 0.2
    avr = trace.classify_triplet([leads["aVR"], leads["aVL"], leads["aVF"]])
    assert avr[1] < 0.2
