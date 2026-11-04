"""Compares two assessments, for example before and after a migration branch."""

from __future__ import annotations

from dataclasses import dataclass, field

from .report import pct
from .risk import Assessment


@dataclass
class Delta:
    removed: list[str] = field(default_factory=list)   # assets that no longer appear
    added: list[str] = field(default_factory=list)     # assets that are new
    changed: list[tuple[str, float, float]] = field(default_factory=list)
    exposure_before: float = 0.0
    exposure_after: float = 0.0
    remaining: int = 0

    @property
    def reduction(self) -> float:
        if self.exposure_before == 0:
            return 0.0
        return 1 - self.exposure_after / self.exposure_before


def _total(a: Assessment) -> float:
    """Expected number of exposed assets, weighted by occurrences."""
    return sum(x.exposure * len(x.occurrences) for x in a.assets
               if x.status in ("quantum-broken", "classically-broken"))


def compare(before: Assessment, after: Assessment) -> Delta:
    b = {a.id: a for a in before.assets}
    a = {x.id: x for x in after.assets}
    delta = Delta(exposure_before=_total(before), exposure_after=_total(after))
    delta.removed = sorted(k for k in b if k not in a and b[k].priority > 0)
    delta.added = sorted(k for k in a if k not in b and a[k].priority > 0)
    for k in sorted(b.keys() & a.keys()):
        if abs(b[k].exposure - a[k].exposure) >= 0.005:
            delta.changed.append((k, b[k].exposure, a[k].exposure))
    delta.remaining = len(after.migrate)
    return delta


def chat(delta: Delta) -> str:
    lines = [f"**Rescan**: exposure down {pct(delta.reduction)}. {delta.remaining} assets still need migration."]
    if delta.removed:
        lines.append("Resolved: " + ", ".join(f"`{r}`" for r in delta.removed))
    if delta.added:
        lines.append("New: " + ", ".join(f"`{r}`" for r in delta.added))
    for k, was, now in delta.changed:
        lines.append(f"- `{k}`: {pct(was)} -> {pct(now)}")
    return "\n".join(lines)
