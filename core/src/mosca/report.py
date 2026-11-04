"""Renders assessments for people: chat messages (Markdown) and machine-readable JSON."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .risk import Assessment, AssetRisk


def pct(p: float) -> str:
    if p >= 0.995:
        return "100%"
    if p < 0.005:
        return "<1%" if p > 0 else "0%"
    return f"{p * 100:.0f}%"


def to_json(assessment: Assessment) -> dict[str, Any]:
    return {
        "now_year": assessment.now_year,
        "crqc_median_year": assessment.crqc_median_year,
        "crqc_p05_year": assessment.crqc_p05_year,
        "target_exposure": assessment.target_exposure,
        "readiness": round(assessment.readiness, 4),
        "summary": summary(assessment),
        "pending_questions": [
            {"system": q.system, "owner": q.owner, "kind": q.kind, "text": q.text}
            for q in assessment.pending_questions()
        ],
        "assets": [asdict(a) for a in assessment.assets],
    }


def summary(assessment: Assessment) -> dict[str, int]:
    out = {"assets": len(assessment.assets), "to_migrate": len(assessment.migrate),
           "exposed": len(assessment.exposed), "classically_broken": 0, "quantum_safe": 0}
    for a in assessment.assets:
        if a.status == "classically-broken":
            out["classically_broken"] += 1
        elif a.status in ("quantum-safe", "hybrid"):
            out["quantum_safe"] += 1
    return out


def _row(a: AssetRisk) -> str:
    param = f" {a.parameter}" if a.parameter else ""
    where = a.files[0] + (f" +{len(a.files) - 1}" if len(a.files) > 1 else "")
    if a.status == "classically-broken":
        risk = "broken now"
    else:
        risk = pct(a.exposure)
    deadline = "overdue" if a.years_late > 0 else (f"{a.deadline_year:.0f}" if a.deadline_year else "-")
    return f"| {a.system} | {a.algorithm_name}{param} | {a.usage} | {risk} | {deadline} | `{where}` |"


def chat_summary(assessment: Assessment, limit: int = 8, title: str = "Quantum exposure") -> str:
    """Compact Markdown for posting into a chat room."""
    s = summary(assessment)
    lines = [
        f"**{title}**: {s['to_migrate']} assets need migration, {s['exposed']} are already exposed "
        f"beyond the {pct(assessment.target_exposure)} risk target. Readiness {pct(assessment.readiness)}.",
        "",
    ]
    ranked = [a for a in assessment.assets if a.priority > 0][:limit]
    if ranked:
        lines += ["| System | Algorithm | Protects | P(exposed) | Start by | Where |",
                  "|---|---|---|---|---|---|"]
        lines += [_row(a) for a in ranked]
    else:
        lines.append(f"Nothing to migrate across {len(assessment.assets)} cryptographic assets.")
    hidden = len([a for a in assessment.assets if a.priority > 0]) - len(ranked)
    if hidden > 0:
        lines.append(f"\n{hidden} more in the full report.")
    pending = assessment.pending_questions()
    if pending:
        lines.append("")
        lines.append("**Waiting on owners.** These rows use default lifetimes until answered:")
        for q in pending:
            who = f"@{q.owner}" if q.owner else "owner unknown"
            lines.append(f"- {who}: {q.text}")
    lines.append("")
    lines.append(f"_Model: P(X + Y > Z), CRQC median {assessment.crqc_median_year:.0f}, "
                 f"5% chance by {assessment.crqc_p05_year:.0f}._")
    return "\n".join(lines)


def asset_detail(a: AssetRisk) -> str:
    param = f" {a.parameter}" if a.parameter else ""
    lines = [f"**{a.algorithm_name}{param}** in `{a.system}` ({a.status}, protects {a.usage})", a.verdict]
    if a.status == "quantum-broken":
        lines.append(f"X = {a.x_years:g} years ({a.x_source}), Y = {a.y_years:g} years migration, "
                     f"P(exposed) = {pct(a.exposure)}.")
    lines.append(f"Replace with: {a.replacement}.")
    lines.append("Occurrences:")
    for o in a.occurrences[:10]:
        lines.append(f"- `{o.path}:{o.line}` {o.snippet[:90]}")
    if len(a.occurrences) > 10:
        lines.append(f"- and {len(a.occurrences) - 10} more")
    return "\n".join(lines)
