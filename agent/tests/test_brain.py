from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mosca_ledger.app import create_app
from mosca_ledger.store import Store

from mosca_agent.brain import Document, Mosca, Post, parse, strip_mentions
from mosca_agent.ledger import LedgerStore, MemoryStore
from mosca_agent.workspace import Workspace


@pytest.mark.parametrize("text,name,arg", [
    ("@mosca scan", "scan", ""),
    ("@mosca: top 3", "top", "3"),
    ("@mosca explain ledger x25519", "explain", "ledger x25519"),
    ("@mosca rescan pq/ledger-hybrid-tls", "rescan", "pq/ledger-hybrid-tls"),
    ("@mosca", "help", ""),
    ("@mosca make coffee", "unknown", "make coffee"),
])
def test_parse_commands(text, name, arg):
    cmd = parse(text)
    assert (cmd.name, cmd.arg) == (name, arg)


@pytest.mark.parametrize("text,system,kind,years", [
    ("@mosca 10 years", None, None, 10.0),
    ("10 yrs", None, None, 10.0),
    ("@mosca payments 12 years", "payments", None, 12.0),
    ("@mosca payments signatures 7 years", "payments", "signature_lifetime_years", 7.0),
    ("@mosca ledger data: 15 years", "ledger", "shelf_life_years", 15.0),
    ("@mosca 1.5 years.", None, None, 1.5),
])
def test_parse_answers(text, system, kind, years):
    cmd = parse(text)
    assert cmd.name == "answer"
    assert (cmd.system, cmd.kind, cmd.years) == (system, kind, years)


def test_strip_mentions():
    assert strip_mentions("@mosca @migrator, scan") == "scan"


def bodies(actions):
    return "\n".join(a.body for a in actions if isinstance(a, Post))


def test_scan_posts_report_document_and_question(repo: Path):
    store = MemoryStore()
    m = Mosca(Workspace(repo), store, "acme")
    actions = m.handle("@mosca scan", "kofi")
    docs = [a for a in actions if isinstance(a, Document)]
    assert len(docs) == 1 and docs[0].name == "CBOM acme main"
    assert '"specVersion": "1.6"' in docs[0].content
    text = bodies(actions)
    assert "Quantum exposure" in text and "Question for" in text
    assert store.assessments and store.assessments[0]["ref"].startswith("main@")


def test_answer_is_recorded_in_ledger_and_changes_ranking(repo: Path, tmp_path: Path):
    client = TestClient(create_app(Store(str(tmp_path / "l.db")), token="t"),
                        headers={"Authorization": "Bearer t"})
    m = Mosca(Workspace(repo), LedgerStore("acme", client), "acme")
    m.handle("scan", "sec-lead")
    out = bodies(m.handle("@mosca payments signatures 10 years", "ana"))
    assert "Recorded in the ledger" in out and "answered by ana" in out
    assert "overdue" in out  # ten-year signatures are past the deadline
    answers = client.get("/v1/repos/acme/answers").json()
    assert answers["payments"]["signature_lifetime_years"] == 10
    assert answers["payments"]["answered_by"] == "ana"
    history = client.get("/v1/repos/acme").json()["history"]
    assert len(history) == 2


def test_bare_answer_resolves_the_open_question(repo: Path):
    store = MemoryStore()
    m = Mosca(Workspace(repo), store, "acme")
    m.handle("scan", "x")
    asked = m.asking
    assert asked is not None
    m.handle("5 years", "dev")
    assert store.answers()[asked.system][asked.kind] == 5


def test_passing_mention_gets_no_reply(repo: Path):
    m = Mosca(Workspace(repo), MemoryStore(), "acme")
    assert m.handle("Thanks for approving. Next: @mosca rescan the branch.", "migrator") == []
    assert "didn't understand" in bodies(m.handle("@mosca make coffee", "x"))


def test_unknown_system_is_rejected(repo: Path):
    m = Mosca(Workspace(repo), MemoryStore(), "acme")
    assert "don't know a system" in bodies(m.handle("nowhere 3 years", "x"))


def test_top_and_explain(repo: Path):
    m = Mosca(Workspace(repo), MemoryStore(), "acme")
    assert "Fix first" in bodies(m.handle("top 3", "x"))
    out = bodies(m.handle("explain ledger x25519", "x"))
    assert "X25519" in out and "server.go" in out and "Replace with" in out


def test_rescan_reports_reduction(repo: Path):
    store = MemoryStore()
    m = Mosca(Workspace(repo), store, "acme")
    actions = m.handle("@mosca rescan pq/ledger-hybrid-tls", "x")
    text = bodies(actions)
    assert "exposure down" in text and "Resolved" in text
    assert store.assessments[-1]["ref"].startswith("pq/ledger-hybrid-tls@")


@pytest.mark.parametrize("ref", ["--upload-pack=x", "../etc", "no-such-branch"])
def test_rescan_bad_branch(repo: Path, ref: str):
    m = Mosca(Workspace(repo), MemoryStore(), "acme")
    out = bodies(m.handle(f"rescan {ref}", "x"))
    assert "valid branch" in out or "can't find" in out
