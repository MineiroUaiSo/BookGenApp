"""Round trip: synthetic 12-lead -> paper image (clean / phone-photo effects) -> digitize_image."""
import cv2
import numpy as np
import pytest
from scipy.signal import find_peaks

from app.ecg.digitize import digitize_image
from synth_ecg import LEAD_ORDER, render_paper, synth_signal

FS = 500


def _truth_segment(leads, sig, name):
    y = np.asarray(sig.leads[name])
    off = int(round(sig.calibration[f"offset_s.{name}"] * FS))
    return y, np.asarray(leads[name][off:off + len(y)])


def lead_corr(leads, sig, name, max_lag_ms=0):
    """Pearson correlation; optional +-lag tolerance (time origin of a photo is only known to ~ms)."""
    y, t = _truth_segment(leads, sig, name)
    n = min(len(y), len(t))
    y, t = y[:n], t[:n]
    k = int(max_lag_ms * FS / 1000)
    best = -1.0
    for d in range(-k, k + 1):
        a, b = np.roll(y, d)[k + 1:n - k - 1], t[k + 1:n - k - 1]
        best = max(best, float(np.corrcoef(a, b)[0, 1]))
    return best


def r_peak_errors_ms(leads_fid, sig, name="II"):
    y = np.asarray(sig.leads[name])
    pk, _ = find_peaks(y, height=0.5 * y.max(), distance=int(0.3 * FS))
    pk = pk / FS
    true = leads_fid["r_peaks_s"]
    # drop true peaks too close to the ends / not covered
    err = [abs(pk[np.argmin(abs(pk - t))] - t) * 1000 for t in true if t < len(y) / FS - 0.2]
    return np.array(err), len(pk)


@pytest.fixture(scope="module")
def case():
    leads, fid = synth_signal(hr=72, fs=FS, seconds=10, seed=5)
    return leads, fid


@pytest.fixture(scope="module")
def clean(case):
    leads, fid = case
    img, info = render_paper(leads, FS, px_per_mm=12, return_info=True)
    return img, info, digitize_image(img)


@pytest.fixture(scope="module")
def photo(case):
    leads, fid = case
    img, info = render_paper(leads, FS, px_per_mm=12, photo_effects=True, return_info=True, seed=3)
    return img, info, digitize_image(img)


def test_clean_calibration(clean):
    img, info, sig = clean
    assert abs(sig.calibration["px_per_mm"] - 12) / 12 < 0.03
    assert sig.calibration["gain_mm_mv"] == 10 and sig.calibration["paper_speed_mm_s"] == 25
    assert sig.fs == 500 and set(sig.leads) == set(LEAD_ORDER)
    assert abs(len(sig.leads["II"]) / FS - 10) < 0.05           # rhythm strip 10 s
    assert abs(len(sig.leads["V3"]) / FS - 2.5) < 0.05          # panels 2.5 s


def test_clean_correlation_and_amplitude(case, clean):
    leads, _ = case
    _, _, sig = clean
    for k in LEAD_ORDER:
        assert lead_corr(leads, sig, k) > 0.9, k
        assert sig.quality[k] > 0.95, k
    # amplitude in mV (gain 10 mm/mV): R of lead II ~1.2 mV
    assert abs(np.max(sig.leads["II"]) - np.max(leads["II"])) < 0.08
    assert abs(np.min(sig.leads["V2"]) - np.min(leads["V2"][:1250])) < 0.12


def test_clean_r_peak_timing(case, clean):
    _, fid = case
    err, n = r_peak_errors_ms(fid, clean[2])
    assert n == len(fid["r_peaks_s"]) and err.max() < 20


def test_photo_calibration(photo):
    img, info, sig = photo
    assert abs(sig.calibration["px_per_mm"] - info["px_per_mm"]) / info["px_per_mm"] < 0.03
    assert sig.calibration["gain_mm_mv"] == 10 and sig.calibration["paper_speed_mm_s"] == 25


def test_photo_correlation(case, photo):
    leads, _ = case
    sig = photo[2]
    for k in LEAD_ORDER:
        assert lead_corr(leads, sig, k, max_lag_ms=20) > 0.75, k
        assert sig.quality[k] > 0.85, k


def test_photo_r_peak_timing(case, photo):
    _, fid = case
    err, n = r_peak_errors_ms(fid, photo[2])
    assert n == len(fid["r_peaks_s"]) and err.max() < 20


@pytest.mark.parametrize("layout,n_expected", [("6x2", 5.0), ("12x1", 10.0)])
def test_other_layouts(case, layout, n_expected):
    leads, _ = case
    img = render_paper(leads, FS, layout=layout)
    sig = digitize_image(img)          # layout auto-detected from the row count
    assert set(sig.leads) == set(LEAD_ORDER)
    assert abs(len(sig.leads["V1"]) / FS - n_expected) < 0.05
    for k in LEAD_ORDER:
        # aVL peaks at ~0.4 mV (5 px): pixel quantisation limits its correlation a bit
        assert lead_corr(leads, sig, k) > 0.85, (layout, k)


def test_gain_5_and_20_pulse_calibration(case):
    leads, _ = case
    sig5 = digitize_image(render_paper(leads, FS, gain_mm_mv=5.0))
    assert sig5.calibration["gain_mm_mv"] == 5
    assert abs(np.max(sig5.leads["II"]) - np.max(leads["II"])) < 0.1  # amplitude still in true mV
    small = {k: v * 0.4 for k, v in leads.items()}
    sig20 = digitize_image(render_paper(small, FS, gain_mm_mv=20.0, layout="12x1"))
    assert sig20.calibration["gain_mm_mv"] == 20
    assert abs(np.max(sig20.leads["II"]) - np.max(small["II"])) < 0.08


def test_speed_50(case):
    leads5, _ = synth_signal(hr=72, fs=FS, seconds=5, seed=5)
    sig = digitize_image(render_paper(leads5, FS, speed_mm_s=50.0))
    assert sig.calibration["paper_speed_mm_s"] == 50
    assert abs(len(sig.leads["II"]) / FS - 5) < 0.05
    assert lead_corr(leads5, sig, "II") > 0.9


def test_rotated_scan_and_grayscale(case):
    leads, _ = case
    img = render_paper(leads, FS)
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), 2.0, 1.0)
    rot = cv2.warpAffine(img, M, (w, h), borderValue=(255, 244, 240))
    sig = digitize_image(rot)
    assert abs(sig.calibration["skew_deg"] + 2.0) < 0.3
    assert min(lead_corr(leads, sig, k, max_lag_ms=10) for k in LEAD_ORDER) > 0.9
    sig_g = digitize_image(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
    assert min(lead_corr(leads, sig_g, k) for k in LEAD_ORDER) > 0.9


def test_abnormal_intervals_survive_digitization():
    leads, fid = synth_signal(hr=60, fs=FS, seconds=10, pr_ms=240, qrs_ms=140, seed=1)
    sig = digitize_image(render_paper(leads, FS))
    assert min(lead_corr(leads, sig, k) for k in LEAD_ORDER) > 0.9


def test_returns_valid_schema(clean):
    from app.schemas import ECGSignal, SourceKind
    sig = clean[2]
    assert isinstance(sig, ECGSignal) and sig.source == SourceKind.IMAGE
    ECGSignal.model_validate(sig.model_dump())
