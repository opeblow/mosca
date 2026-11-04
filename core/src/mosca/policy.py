"""Team policy: which code belongs to which system, who owns it, and the threat prior.

Loaded from `mosca.toml` at the root of the scanned repository, plus an optional
answers file holding what owners told Mosca in chat (data shelf life per system).
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CrqcPrior:
    """Prior on the arrival year of a cryptographically relevant quantum computer (CRQC).

    Modelled as earliest_year + LogNormal, with the given median year. These are
    deliberately configurable: every organisation should set them from its own threat
    model (for example the Global Risk Institute's annual Quantum Threat Timeline).
    """

    median_year: float = 2036.0
    earliest_year: float = 2029.0
    spread: float = 0.6  # sigma of the underlying normal

    def __post_init__(self) -> None:
        if self.median_year <= self.earliest_year:
            raise ValueError("crqc.median_year must be after crqc.earliest_year")
        if self.spread <= 0:
            raise ValueError("crqc.spread must be positive")


@dataclass(frozen=True)
class System:
    name: str
    paths: tuple[str, ...] = ()
    owner: str | None = None
    data_class: str | None = None
    shelf_life_years: float | None = None
    signature_lifetime_years: float | None = None
    migration_years: float | None = None
    criticality: float = 1.0
    description: str = ""


@dataclass
class Policy:
    crqc: CrqcPrior = field(default_factory=CrqcPrior)
    default_shelf_life_years: float = 7.0
    default_signature_lifetime_years: float = 2.0
    data_classes: dict[str, float] = field(default_factory=lambda: {
        "public": 0.0, "operational": 2.0, "internal": 5.0, "pii": 10.0,
        "financial": 10.0, "legal": 15.0, "secrets": 20.0, "health": 25.0, "national-security": 50.0,
    })
    systems: list[System] = field(default_factory=list)
    answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    target_exposure: float = 0.05

    # ---- system resolution ---------------------------------------------------
    def system_for(self, path: str) -> System:
        for system in self.systems:
            if any(glob_regex(p).fullmatch(path) for p in system.paths):
                return system
        head = path.split("/", 1)[0] if "/" in path else "(root)"
        return System(name=head)

    def system(self, name: str) -> System:
        for system in self.systems:
            if system.name == name:
                return system
        return System(name=name)

    # ---- Mosca X ---------------------------------------------------------------
    def shelf_life(self, system: System) -> tuple[float, str]:
        """Years the data must stay secret, and where that number came from."""
        answer = self.answers.get(system.name, {})
        if "shelf_life_years" in answer:
            who = answer.get("answered_by", "owner")
            return float(answer["shelf_life_years"]), f"answered by {who}"
        if system.shelf_life_years is not None:
            return system.shelf_life_years, "set in mosca.toml"
        if system.data_class and system.data_class in self.data_classes:
            return self.data_classes[system.data_class], f"data class '{system.data_class}'"
        return self.default_shelf_life_years, "default (owner has not answered)"

    def signature_lifetime(self, system: System) -> tuple[float, str]:
        answer = self.answers.get(system.name, {})
        if "signature_lifetime_years" in answer:
            return float(answer["signature_lifetime_years"]), f"answered by {answer.get('answered_by', 'owner')}"
        if system.signature_lifetime_years is not None:
            return system.signature_lifetime_years, "set in mosca.toml"
        return self.default_signature_lifetime_years, "default (owner has not answered)"


@lru_cache(maxsize=512)
def glob_regex(pattern: str) -> re.Pattern[str]:
    """Translate a path glob with `**` support into a regex over POSIX paths."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def _system(raw: dict[str, Any]) -> System:
    paths = raw.get("paths", [])
    if isinstance(paths, str):
        paths = [paths]
    return System(
        name=str(raw["name"]),
        paths=tuple(paths),
        owner=raw.get("owner"),
        data_class=raw.get("data_class"),
        shelf_life_years=_opt_float(raw.get("shelf_life_years")),
        signature_lifetime_years=_opt_float(raw.get("signature_lifetime_years")),
        migration_years=_opt_float(raw.get("migration_years")),
        criticality=float(raw.get("criticality", 1.0)),
        description=str(raw.get("description", "")),
    )


def _opt_float(v: Any) -> float | None:
    return None if v is None else float(v)


def from_dict(data: dict[str, Any], answers: dict[str, dict[str, Any]] | None = None) -> Policy:
    policy = Policy()
    crqc = data.get("crqc", {})
    if crqc:
        policy.crqc = CrqcPrior(
            median_year=float(crqc.get("median_year", policy.crqc.median_year)),
            earliest_year=float(crqc.get("earliest_year", policy.crqc.earliest_year)),
            spread=float(crqc.get("spread", policy.crqc.spread)),
        )
    defaults = data.get("defaults", {})
    policy.default_shelf_life_years = float(defaults.get("shelf_life_years", policy.default_shelf_life_years))
    policy.default_signature_lifetime_years = float(
        defaults.get("signature_lifetime_years", policy.default_signature_lifetime_years))
    policy.target_exposure = float(defaults.get("target_exposure", policy.target_exposure))
    policy.data_classes.update({k: float(v) for k, v in data.get("data_classes", {}).items()})
    policy.systems = [_system(s) for s in data.get("systems", [])]
    policy.answers = dict(answers or {})
    return policy


def load(root: str | Path, config: str | Path | None = None, answers: str | Path | None = None) -> Policy:
    root = Path(root)
    config_path = Path(config) if config else root / "mosca.toml"
    data: dict[str, Any] = {}
    if config_path.is_file():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    answer_data: dict[str, dict[str, Any]] = {}
    if answers and Path(answers).is_file():
        answer_data = json.loads(Path(answers).read_text(encoding="utf-8"))
    return from_dict(data, answer_data)
