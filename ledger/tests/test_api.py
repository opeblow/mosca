import os

os.environ["MOSCA_LEDGER_AUTOSTART"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from mosca_ledger.app import create_app  # noqa: E402
from mosca_ledger.store import Store  # noqa: E402

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def assessment(readiness=0.2, to_migrate=10):
    return {
        "ref": "main",
        "now_year": 2026.84,
        "crqc_median_year": 2036,
        "crqc_p05_year": 2031.9,
        "target_exposure": 0.05,
        "readiness": readiness,
        "summary": {"assets": 20, "to_migrate": to_migrate, "exposed": 8,
                    "classically_broken": 3, "quantum_safe": 2},
        "pending_questions": [],
        "assets": [{"id": "payments/rsa-2048", "exposure": 0.65}],
    }


@pytest.fixture
def client():
    return TestClient(create_app(Store(":memory:"), token=TOKEN))


def test_health(client):
    assert client.get("/healthz").json()["status"] == "ok"


def test_writes_need_token(client):
    assert client.post("/v1/repos/acme/assessments", json=assessment()).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.post("/v1/repos/acme/assessments", json=assessment(), headers=bad).status_code == 401


def test_writes_disabled_without_configured_token():
    c = TestClient(create_app(Store(":memory:"), token=""))
    r = c.post("/v1/repos/acme/assessments", json=assessment(), headers=AUTH)
    assert r.status_code == 503


def test_history_and_latest(client):
    client.post("/v1/repos/acme/assessments", json=assessment(0.2, 10), headers=AUTH)
    client.post("/v1/repos/acme/assessments", json=assessment(0.6, 4), headers=AUTH)
    data = client.get("/v1/repos/acme").json()
    assert data["assessment"]["readiness"] == 0.6
    assert [h["to_migrate"] for h in data["history"]] == [10, 4]
    assert client.get("/v1/repos").json()[0]["repo"] == "acme"


def test_answers_fold_latest_wins(client):
    for years in (7, 10):
        r = client.post("/v1/repos/acme/answers", headers=AUTH, json={
            "system": "payments", "kind": "shelf_life_years", "years": years, "answered_by": "ana"})
        assert r.status_code == 201
    answers = client.get("/v1/repos/acme/answers").json()
    assert answers["payments"]["shelf_life_years"] == 10
    assert answers["payments"]["answered_by"] == "ana"


def test_validation(client):
    r = client.post("/v1/repos/acme/answers", headers=AUTH, json={
        "system": "payments", "kind": "shelf_life_years", "years": 500, "answered_by": "ana"})
    assert r.status_code == 422
    assert client.get("/v1/repos/..%2Fetc").status_code in (404, 422)
    assert client.get("/v1/repos/unknown").status_code == 404
