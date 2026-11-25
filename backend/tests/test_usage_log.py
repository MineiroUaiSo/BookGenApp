import json

import pytest

from app import usage_log


@pytest.fixture
def logdir(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDLENS_DATA", str(tmp_path))
    return tmp_path / "logs" / "usage.jsonl"


def _lines(p):
    return [json.loads(x) for x in p.read_text().splitlines()]


def test_log_event_drops_non_whitelisted_and_phi_fields(logdir):
    usage_log.log_event("analyze", "STUDY-UID-1.2.3", kind="ecg", patient_name="Maria", birth_date="1980-01-01",
                        report_text="laudo livre", dicom_uid="1.2.840.1", codes=["ecg.af", "Maria Silva"],
                        latency_ms={"analysis": 12})
    rec = _lines(logdir)[0]
    assert set(rec) <= usage_log.ALLOWED_FIELDS
    assert rec["codes"] == ["ecg.af"] and rec["latency_ms"] == {"analysis": 12}
    blob = logdir.read_text()
    for forbidden in ("Maria", "1980", "laudo livre", "1.2.840", "STUDY-UID"):
        assert forbidden not in blob


def test_study_hash_is_salted_stable_and_not_the_id(logdir):
    a, b = usage_log.study_hash("abc"), usage_log.study_hash("abc")
    assert a == b and a != "abc" and len(a) == 16
    assert usage_log.study_hash("abd") != a


def test_invalid_values_are_rejected(logdir):
    rec = usage_log.sanitize({"kind": "mri", "verdict": "maybe", "code": "Has Space", "ai_requested": "yes",
                              "latency_ms": {"x": "slow"}})
    assert rec == {}


def test_feedback_endpoint_logs_code_and_verdict_only(client, dicom_folder, logdir):
    from test_core import upload
    studies = upload(client, dicom_folder).json()["studies"]
    sid = studies[0]["study_id"]
    r = client.post(f"/api/feedback/{sid}", json={"kind": "ecg", "code": "ecg.av_block_1", "verdict": "disagree"})
    assert r.status_code == 200
    rec = _lines(logdir)[-1]
    assert rec["event"] == "feedback" and rec["code"] == "ecg.av_block_1" and rec["verdict"] == "disagree"
    assert sid not in logdir.read_text()
    bad = client.post(f"/api/feedback/{sid}", json={"kind": "ecg", "code": "x y", "verdict": "agree"})
    assert bad.status_code == 422
