"""Where owner answers and assessments are recorded.

The Mosca ledger is the system of record. Without one, answers live in memory for
the life of the process, which is enough for a quick trial but leaves no audit trail.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class AnswerStore(Protocol):
    def answers(self) -> dict[str, dict[str, Any]]: ...
    def record_answer(self, system: str, kind: str, years: float, answered_by: str) -> None: ...
    def record_assessment(self, report: dict[str, Any], ref: str) -> int | None: ...


class MemoryStore:
    def __init__(self) -> None:
        self._answers: dict[str, dict[str, Any]] = {}
        self.assessments: list[dict[str, Any]] = []

    def answers(self) -> dict[str, dict[str, Any]]:
        return {k: dict(v) for k, v in self._answers.items()}

    def record_answer(self, system: str, kind: str, years: float, answered_by: str) -> None:
        self._answers.setdefault(system, {}).update({kind: years, "answered_by": answered_by})

    def record_assessment(self, report: dict[str, Any], ref: str) -> int | None:
        self.assessments.append({**report, "ref": ref})
        return None


class LedgerStore:
    """Client for the Mosca ledger API (`ledger/`)."""

    def __init__(self, repo: str, client: httpx.Client) -> None:
        self.repo = repo
        self.client = client

    @classmethod
    def connect(cls, url: str, repo: str, token: str | None) -> LedgerStore:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return cls(repo, httpx.Client(base_url=url.rstrip("/"), headers=headers, timeout=20))

    def answers(self) -> dict[str, dict[str, Any]]:
        r = self.client.get(f"/v1/repos/{self.repo}/answers")
        r.raise_for_status()
        return r.json()

    def record_answer(self, system: str, kind: str, years: float, answered_by: str) -> None:
        r = self.client.post(f"/v1/repos/{self.repo}/answers", json={
            "system": system, "kind": kind, "years": years, "answered_by": answered_by[:100]})
        r.raise_for_status()

    def record_assessment(self, report: dict[str, Any], ref: str) -> int | None:
        r = self.client.post(f"/v1/repos/{self.repo}/assessments", json={**report, "ref": ref})
        r.raise_for_status()
        return r.json().get("seq")
