import os
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MEDLENS_DATA", tempfile.mkdtemp(prefix="medlens-test-"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from fixtures_dicom import make_dx_dicom, make_ecg_dicom  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path / "data")
    return store


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def dicom_folder(tmp_path):
    """A nested folder: PA + lateral (same study), MONOCHROME1 (other study), ECG (no extension)."""
    from pydicom.uid import generate_uid

    root = tmp_path / "exam"
    study = generate_uid()
    make_dx_dicom(root / "CHEST" / "pa.dcm", "PA", study_uid=study)
    make_dx_dicom(root / "CHEST" / "sub" / "IM0002", "LL", study_uid=study)  # no extension
    make_dx_dicom(root / "mono1.dcm", "PA", monochrome1=True)
    make_ecg_dicom(root / "ECG" / "ecg_file", fs=500, seconds=10)
    (root / "readme.txt").write_text("not dicom")
    return root


def install_fake(monkeypatch, name: str, **attrs):
    """Register a fake module (and parent packages) so lazy imports resolve to stubs."""
    parts = name.split(".")
    for i in range(1, len(parts)):
        pkg = ".".join(parts[:i])
        if pkg not in sys.modules or not hasattr(sys.modules[pkg], "__path__"):
            m = types.ModuleType(pkg)
            m.__path__ = []
            monkeypatch.setitem(sys.modules, pkg, m)
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod
