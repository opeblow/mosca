"""What Mosca does with a message addressed to it. No network code here.

Every handler returns actions (a chat post, a room document) for the runtime to carry
out, so the behaviour can be tested without a Switch server.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mosca import cbom, diff, policy, report, risk
from mosca.model import ScanResult
from mosca.report import pct
from mosca.scanner import scan

from .ledger import AnswerStore
from .workspace import Workspace, WorkspaceError

HELP = """**Mosca** finds the cryptography in this repository and ranks it by quantum exposure.

| Say | What happens |
|---|---|
| `@mosca scan` | Scan the main branch, post the ranked report, attach the CBOM to this room |
| `@mosca top 5` | The five assets to fix first |
| `@mosca explain ledger x25519` | Where an asset is used, its X, Y and P(exposed), and what replaces it |
| `@mosca 10 years` | Answer the question I last asked an owner |
| `@mosca payments signatures 10 years` | Answer for a named system |
| `@mosca rescan <branch>` | Scan a migration branch and report how much exposure it removes |"""


@dataclass(frozen=True)
class Post:
    body: str


@dataclass(frozen=True)
class Document:
    name: str
    description: str
    instructions: str
    content: str


Action = Post | Document


# ---- parsing ------------------------------------------------------------------

MENTION_RX = re.compile(r"^\s*(?:@[\w.-]+[:,]?\s*)+")
ANSWER_RX = re.compile(
    r"^(?:(?P<system>[A-Za-z0-9._()/-]+)\s+)?(?:(?P<what>data|secrets?|signatures?|sigs?)\s*)?[:=-]?\s*"
    r"(?P<years>\d{1,3}(?:\.\d+)?)\s*(?:years?|yrs?|y)\b\.?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Command:
    name: str           # help | scan | top | explain | rescan | answer | unknown
    arg: str = ""
    years: float | None = None
    system: str | None = None
    kind: str | None = None  # shelf_life_years | signature_lifetime_years


def strip_mentions(text: str) -> str:
    return MENTION_RX.sub("", text).strip()


def parse(text: str) -> Command:
    text = strip_mentions(text)
    if not text:
        return Command("help")
    head, _, rest = text.partition(" ")
    word = head.lower().strip("!/")
    rest = rest.strip()
    if word in ("help", "hi", "hello", "?"):
        return Command("help")
    if word in ("scan", "top", "explain", "rescan"):
        return Command(word, rest)
    m = ANSWER_RX.match(text)
    if m:
        what = (m.group("what") or "").lower()
        kind = None
        if what.startswith("sig"):
            kind = "signature_lifetime_years"
        elif what:
            kind = "shelf_life_years"
        return Command("answer", years=float(m.group("years")), system=m.group("system"), kind=kind)
    return Command("unknown", text)


# ---- behaviour --------------------------------------------------------------------

def _years(y: float) -> str:
    return f"{y:g} year" + ("" if y == 1 else "s")


def _start_by(a: risk.AssetRisk) -> str:
    if a.status == "classically-broken":
        return "now"
    if a.years_late > 0:
        return "overdue"
    return f"{a.deadline_year:.0f}" if a.deadline_year else "-"


def _label(a: risk.AssetRisk) -> str:
    return f"{a.system} {a.algorithm_name}" + (f" {a.parameter}" if a.parameter else "")


class Mosca:
    def __init__(self, workspace: Workspace, store: AnswerStore, repo_name: str) -> None:
        self.workspace = workspace
        self.store = store
        self.repo_name = repo_name
        self.assessment: risk.Assessment | None = None
        self._scan: ScanResult | None = None
        self._policy: policy.Policy | None = None
        self._commit = ""
        self.asking: risk.Question | None = None

    # -- entry point --
    def handle(self, text: str, sender: str) -> list[Action]:
        cmd = parse(text)
        try:
            if cmd.name == "help":
                return [Post(HELP)]
            if cmd.name == "scan":
                return self.scan()
            if cmd.name == "top":
                return self.top(cmd.arg)
            if cmd.name == "explain":
                return self.explain(cmd.arg)
            if cmd.name == "rescan":
                return self.rescan(cmd.arg)
            if cmd.name == "answer":
                return self.answer(cmd, sender)
        except WorkspaceError as exc:
            return [Post(str(exc))]
        if not text.lstrip().startswith("@"):
            # Mentioned in passing (often by another agent), not spoken to: stay quiet.
            return []
        return [Post(f"I didn't understand `{cmd.arg[:80]}`. Say `@mosca help` for what I can do.")]

    # -- assessment --
    def _assess(self, root: Path) -> tuple[ScanResult, policy.Policy, risk.Assessment]:
        result = scan(root)
        pol = policy.load(root)
        pol.answers = self.store.answers()
        return result, pol, risk.assess(result, pol)

    def _refresh(self) -> risk.Assessment:
        """Re-run the model on the last scan with the latest answers. No rescan needed."""
        assert self._scan is not None and self._policy is not None
        self._policy.answers = self.store.answers()
        self.assessment = risk.assess(self._scan, self._policy)
        return self.assessment

    def _ensure(self) -> risk.Assessment:
        if self.assessment is None:
            self.scan()
        assert self.assessment is not None
        return self.assessment

    def _ref(self) -> str:
        return f"{self.workspace.base_ref}@{self._commit}"

    def scan(self) -> list[Action]:
        base = self.workspace.base_ref
        with self.workspace.checkout(base) as (root, commit):
            self._scan, self._policy, self.assessment = self._assess(root)
            doc = cbom.to_cbom(self._scan, self.repo_name)
        self._commit = commit
        self.store.record_assessment(report.to_json(self.assessment), self._ref())
        s = report.summary(self.assessment)
        actions: list[Action] = [
            Document(
                name=f"CBOM {self.repo_name} {base}",
                description=(f"CycloneDX 1.6 cryptographic bill of materials for {self.repo_name} at "
                             f"{base} ({commit}): {len(doc['components'])} assets, "
                             f"{len(self._scan.findings)} occurrences."),
                instructions=("Read this to see which algorithms the repository uses and where. Each "
                              "component lists its occurrences as file and line. Mosca updates it on every scan."),
                content=json.dumps(doc, indent=2),
            ),
            Post(f"Scanned `{base}` at `{commit}`: {s['assets']} cryptographic assets in "
                 f"{self._scan.files_scanned} files. The CBOM is attached to this room as a document, "
                 f"and the assessment is in the ledger.\n\n"
                 + report.chat_summary(self.assessment, limit=8).split("\n**Waiting on owners.**")[0]),
        ]
        actions += self._next_question()
        return actions

    def _next_question(self) -> list[Action]:
        assert self.assessment is not None
        pending = self.assessment.pending_questions()
        self.asking = pending[0] if pending else None
        if not self.asking:
            return []
        q = self.asking
        who = f"{q.owner}, owner of `{q.system}`" if q.owner else f"the owner of `{q.system}`"
        affected = [a for a in self.assessment.assets if a.system == q.system and a.needs_owner_input]
        rows = ", ".join(_label(a) for a in affected[:4])
        more = f" ({len(pending) - 1} more after this)" if len(pending) > 1 else ""
        return [Post(f"**Question for {who}**{more}: {q.text}\n"
                     f"Until you answer I assume the default, which affects: {rows}.\n"
                     f"Reply `@mosca 10 years` (or whatever is true).")]

    def top(self, arg: str) -> list[Action]:
        n = int(arg) if arg.strip().isdigit() else 5
        a = self._ensure()
        return [Post(report.chat_summary(a, limit=max(1, min(n, 25)), title="Fix first")
                     .split("\n**Waiting on owners.**")[0])]

    def find(self, query: str) -> list[risk.AssetRisk]:
        a = self._ensure()
        q = query.lower().strip()
        exact = [x for x in a.assets if x.id.lower() == q]
        if exact:
            return exact
        tokens = q.replace("/", " ").replace(":", " ").split()
        hits = [x for x in a.assets
                if all(t in f"{x.id} {x.system} {x.algorithm} {x.algorithm_name} {x.parameter or ''} {x.usage}".lower()
                       for t in tokens)]
        return sorted(hits, key=lambda x: -x.priority)

    def explain(self, query: str) -> list[Action]:
        if not query.strip():
            return [Post("Which asset? For example `@mosca explain ledger x25519`.")]
        hits = self.find(query)
        if not hits:
            return [Post(f"No asset matches `{query[:80]}`. Try `@mosca top 10` for names.")]
        body = report.asset_detail(hits[0])
        if len(hits) > 1:
            body += "\n\nAlso matching: " + ", ".join(f"`{_label(h)}`" for h in hits[1:6])
        return [Post(body)]

    def answer(self, cmd: Command, sender: str) -> list[Action]:
        a = self._ensure()
        assert self._policy is not None
        known = {x.system for x in a.assets} | {s.name for s in self._policy.systems}
        system, kind = cmd.system, cmd.kind
        if system and system not in known:
            return [Post(f"I don't know a system called `{system}`. Systems: "
                         + ", ".join(f"`{s}`" for s in sorted(known)) + ".")]
        if not system:
            if not self.asking:
                return [Post("Which system is that for? For example `@mosca payments 10 years`.")]
            system, kind = self.asking.system, kind or self.asking.kind
        if not kind:
            asked = [q for q in a.pending_questions() if q.system == system]
            kind = asked[0].kind if asked else "shelf_life_years"
        assert cmd.years is not None

        before = {x.id: x for x in a.assets if x.system == system}
        self.store.record_answer(system, kind, cmd.years, sender)
        after = self._refresh()
        self.store.record_assessment(report.to_json(after), self._ref())

        what = ("data must stay secret" if kind == "shelf_life_years" else "signatures must stay trusted")
        lines = [f"Recorded in the ledger: `{system}` {what} for {_years(cmd.years)} (answered by {sender})."]
        changed = [(before[x.id], x) for x in after.assets if x.id in before
                   and (abs(before[x.id].exposure - x.exposure) >= 0.005 or _start_by(before[x.id]) != _start_by(x))]
        if changed:
            lines += ["", "| Asset | P(exposed) | Start by |", "|---|---|---|"]
            lines += [f"| {_label(new)} | {pct(old.exposure)} -> **{pct(new.exposure)}** | "
                      f"{_start_by(old)} -> {_start_by(new)} |" for old, new in changed]
        else:
            lines.append("No ranking changed.")
        if self.asking and self.asking.system == system and self.asking.kind == kind:
            self.asking = None
        actions: list[Action] = [Post("\n".join(lines))]
        follow = self._next_question()
        if follow:
            actions += follow
        else:
            actions.append(Post("Every owner question is answered. "
                                + report.chat_summary(after, limit=5, title="Fix first")))
        return actions

    def rescan(self, ref: str) -> list[Action]:
        ref = ref.strip()
        if not ref:
            return [Post("Which branch? For example `@mosca rescan pq/ledger-hybrid-tls`.")]
        base = self.workspace.base_ref
        with self.workspace.checkout(base) as (root, base_commit):
            _, _, before = self._assess(root)
        with self.workspace.checkout(ref) as (root, commit):
            result, _, after = self._assess(root)
            doc = cbom.to_cbom(result, self.repo_name)
        delta = diff.compare(before, after)
        self.store.record_assessment(report.to_json(after), f"{ref}@{commit}")
        lines = [f"Rescanned `{ref}` at `{commit}` against `{base}` at `{base_commit}`.", "", diff.chat(delta)]
        late = [x for x in after.migrate if x.years_late > 0 or x.status == "classically-broken"]
        lines.append(f"\nReadiness {pct(before.readiness)} -> {pct(after.readiness)}. "
                     f"{len(late)} assets still need to start migrating now.")
        return [
            Document(
                name=f"CBOM {self.repo_name} {ref}",
                description=f"CycloneDX 1.6 CBOM for branch {ref} ({commit}).",
                instructions="Compare with the main-branch CBOM to see which algorithms the branch removed.",
                content=json.dumps(doc, indent=2),
            ),
            Post("\n".join(lines)),
        ]


def summarize_for_log(actions: list[Action]) -> list[dict[str, Any]]:
    return [{"type": type(x).__name__, "chars": len(getattr(x, "body", "") or getattr(x, "content", ""))}
            for x in actions]
