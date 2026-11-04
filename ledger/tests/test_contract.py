"""The ledger must accept exactly what `mosca assess --json` produces."""

import os
from datetime import date
from pathlib import Path

os.environ["MOSCA_LEDGER_AUTOSTART"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from mosca_ledger.app import create_app  # noqa: E402
from mosca_ledger.store import Store  # noqa: E402

mosca = pytest.importorskip("mosca")
from mosca import policy, report, risk  # noqa: E402
from mosca.scanner import scan  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "acme-payments"
AUTH = {"Authorization": "Bearer t"}


def run(answers=None):
    pol = policy.load(SAMPLE)
    pol.answers = answers or {}
    return report.to_json(risk.assess(scan(SAMPLE), pol, today=date(2026, 11, 4), samples=2000))


def test_round_trip_through_ledger():
    client = TestClient(create_app(Store(":memory:"), token="t"))
    first = run()
    assert client.post("/v1/repos/acme-payments/assessments", json={**first, "ref": "main"},
                       headers=AUTH).status_code == 201

    q = first["pending_questions"][0]
    r = client.post("/v1/repos/acme-payments/answers", headers=AUTH,
                    json={"system": q["system"], "kind": q["kind"], "years": 15, "answered_by": "ana"})
    assert r.status_code == 201

    answers = client.get("/v1/repos/acme-payments/answers").json()
    second = run(answers)
    assert len(second["pending_questions"]) == len(first["pending_questions"]) - 1
    client.post("/v1/repos/acme-payments/assessments", json=second, headers=AUTH)

    repo = client.get("/v1/repos/acme-payments").json()
    assert len(repo["history"]) == 2
    assert repo["assessment"]["summary"] == second["summary"]
