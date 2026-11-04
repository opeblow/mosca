"""Quantum exposure model based on Mosca's inequality.

    Data protected today is exposed if   X + Y > Z
      X  how long it must stay secret (or how long signatures must stay trusted)
      Y  how long the migration to post-quantum cryptography will take
      Z  how long until a cryptographically relevant quantum computer exists

Z and Y are uncertain, so instead of a yes/no answer each asset gets
P(X + Y > Z), estimated by seeded Monte Carlo sampling. Results are reproducible:
the same inputs always produce the same numbers.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from .model import Finding, Kind, ScanResult
from .policy import Policy, System
from .taxonomy import Status, Usage, get

SAMPLES = 20_000

# Base migration effort in years for one asset, by where it lives.
BASE_EFFORT = {
    Kind.CONFIG: 0.15,
    Kind.DEPENDENCY: 0.4,
    Kind.CODE: 0.3,
    Kind.KEY: 0.3,
    Kind.CERTIFICATE: 0.6,
}
ROLLOUT_OVERHEAD = 0.25  # testing, staged rollout, coordination with other teams
SIGNATURE_FACTOR = 1.5   # every verifier has to upgrade too


def year_fraction(d: date) -> float:
    start = date(d.year, 1, 1)
    days = (date(d.year + 1, 1, 1) - start).days
    return d.year + (d - start).days / days


@dataclass(frozen=True)
class Occurrence:
    path: str
    line: int
    kind: str
    snippet: str
    confidence: float


@dataclass
class AssetRisk:
    id: str
    system: str
    owner: str | None
    algorithm: str
    algorithm_name: str
    parameter: str | None
    usage: str
    status: str
    replacement: str
    occurrences: list[Occurrence] = field(default_factory=list)
    x_years: float = 0.0
    x_source: str = ""
    y_years: float = 0.0
    exposure: float = 0.0
    deadline_year: float | None = None
    years_late: float = 0.0
    priority: float = 0.0
    needs_owner_input: bool = False
    verdict: str = ""

    @property
    def files(self) -> list[str]:
        return sorted({o.path for o in self.occurrences})


@dataclass
class Assessment:
    now_year: float
    crqc_median_year: float
    crqc_p05_year: float
    target_exposure: float
    assets: list[AssetRisk]

    @property
    def migrate(self) -> list[AssetRisk]:
        return [a for a in self.assets if a.status in (Status.BROKEN.value, Status.CLASSICAL.value)]

    @property
    def exposed(self) -> list[AssetRisk]:
        return [a for a in self.assets if a.exposure > self.target_exposure]

    @property
    def readiness(self) -> float:
        """Share of findings that are already quantum-safe or hybrid, weighted by occurrences."""
        total = sum(len(a.occurrences) for a in self.assets)
        if not total:
            return 1.0
        safe = sum(len(a.occurrences) for a in self.assets
                   if a.status in (Status.SAFE.value, Status.HYBRID.value, Status.WEAKENED.value))
        return safe / total

    def pending_questions(self) -> list[Question]:
        """What Mosca still needs owners to tell it, one question per system and kind."""
        seen: dict[tuple[str, str], Question] = {}
        for a in self.assets:
            if not a.needs_owner_input:
                continue
            kind = "shelf_life_years" if Usage(a.usage).confidentiality else "signature_lifetime_years"
            seen.setdefault((a.system, kind), Question(a.system, a.owner, kind))
        return sorted(seen.values(), key=lambda q: (q.system, q.kind))


@dataclass(frozen=True)
class Question:
    system: str
    owner: str | None
    kind: str  # "shelf_life_years" | "signature_lifetime_years"

    @property
    def text(self) -> str:
        if self.kind == "shelf_life_years":
            return f"How many years must `{self.system}` data stay secret?"
        return f"How many years must signatures from `{self.system}` stay trusted?"


def _seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _quantile_lognormal(mu: float, sigma: float, q: float) -> float:
    """Bisection on the closed-form log-normal CDF."""
    lo, hi = 1e-9, 1e4
    for _ in range(200):
        mid = (lo + hi) / 2
        cdf = 0.5 * (1 + math.erf((math.log(mid) - mu) / (sigma * math.sqrt(2))))
        if cdf < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def migration_years(findings: list[Finding], usage: Usage, override: float | None = None) -> float:
    if override is not None:
        return override
    base = max(BASE_EFFORT[f.kind] for f in findings)
    occurrences = len(findings)
    files = len({f.path for f in findings})
    years = base + 0.12 * math.log2(1 + occurrences) + 0.1 * math.log2(1 + files) + ROLLOUT_OVERHEAD
    if usage is Usage.SIGNATURE:
        years *= SIGNATURE_FACTOR
    return round(years, 2)


def exposure_probability(x: float, y: float, z_offset: float, mu: float, sigma: float,
                         seed: int, samples: int = SAMPLES) -> float:
    """P(X + Y > Z) with Y ~ Triangular(0.7y, y, 2.0y) and Z ~ offset + LogNormal(mu, sigma)."""
    rng = random.Random(seed)
    hits = 0
    for _ in range(samples):
        y_s = rng.triangular(0.7 * y, 2.0 * y, y)
        z_s = z_offset + rng.lognormvariate(mu, sigma)
        if x + y_s > z_s:
            hits += 1
    return hits / samples


def assess(scan: ScanResult, policy: Policy, today: date | None = None,
           samples: int = SAMPLES) -> Assessment:
    now = year_fraction(today or date.today())
    prior = policy.crqc
    z_offset = max(prior.earliest_year - now, 0.0)
    mu = math.log(max(prior.median_year - now - z_offset, 0.25))
    sigma = prior.spread
    z_p05 = z_offset + _quantile_lognormal(mu, sigma, policy.target_exposure)

    # One asset per (system, algorithm). Key sizes and usages seen at different call
    # sites (key generation vs. encryption) describe the same asset.
    groups: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    systems: dict[str, System] = {}
    for f in scan.findings:
        system = policy.system_for(f.path)
        systems[system.name] = system
        groups[(system.name, f.algorithm)].append(f)

    _merge_generic_keys(groups)

    assets: list[AssetRisk] = []
    for (system_name, alg_id), findings in groups.items():
        system = systems[system_name]
        alg = get(alg_id)
        status = min((f.status for f in findings), key=_STATUS_ORDER.index)
        usage = next((f.effective_usage for f in findings if f.effective_usage is not Usage.UNKNOWN),
                     Usage.UNKNOWN)
        params = Counter(f.parameter for f in findings if f.parameter)
        parameter = params.most_common(1)[0][0] if params else None
        # The id must not depend on the parameter: a rescan that loses the curve name
        # (or changes a key size) is the same asset, not a resolved one plus a new one.
        asset = AssetRisk(
            id=f"{system_name}/{alg_id}",
            system=system_name,
            owner=system.owner,
            algorithm=alg.id,
            algorithm_name=alg.name,
            parameter=parameter,
            usage=usage.value,
            status=status.value,
            replacement=alg.replacement,
            occurrences=[Occurrence(f.path, f.line, f.kind.value, f.snippet, f.confidence) for f in findings],
        )
        confidence = max(f.confidence for f in findings)

        if status is Status.CLASSICAL:
            asset.exposure = 1.0
            asset.verdict = "Broken today, independent of quantum computing. Replace now."
            asset.priority = round(100 * system.criticality * confidence, 1)
        elif status is Status.BROKEN:
            if usage.confidentiality:
                x, src = policy.shelf_life(system)
            else:
                x, src = policy.signature_lifetime(system)
            y = migration_years(findings, usage, system.migration_years)
            p = exposure_probability(x, y, z_offset, mu, sigma, _seed(asset.id, x, y, mu, sigma), samples)
            asset.x_years, asset.x_source, asset.y_years = x, src, y
            asset.exposure = round(p, 4)
            asset.needs_owner_input = src.startswith("default")
            asset.deadline_year = round(now + z_p05 - x - y, 1)
            asset.years_late = round(max(0.0, now - asset.deadline_year), 1)
            asset.priority = round(100 * p * system.criticality * confidence, 1)
            if usage.confidentiality:
                asset.verdict = ("Harvest-now-decrypt-later: traffic recorded today stays readable "
                                 f"for {x:g} more years.")
            else:
                asset.verdict = "Signatures become forgeable once a quantum computer exists."
        elif status is Status.WEAKENED:
            asset.verdict = "Grover's algorithm halves the security level. Prefer 256-bit keys for long-lived data."
            asset.priority = round(2 * confidence, 1)
        else:
            asset.verdict = "Quantum-safe."
        assets.append(asset)

    assets.sort(key=lambda a: (-a.priority, a.system, a.algorithm))
    return Assessment(
        now_year=round(now, 2),
        crqc_median_year=prior.median_year,
        crqc_p05_year=round(now + z_p05, 1),
        target_exposure=policy.target_exposure,
        assets=assets,
    )


# A bare key generation ("ec", "rsa") says nothing about what the key protects. When the
# same system uses that key family in exactly one specific way, they are the same asset.
_GENERIC_KEYS = {"ec": ("ecdsa", "ecdh"), "rsa": ("rsa-signature",)}


def _merge_generic_keys(groups: dict[tuple[str, str], list[Finding]]) -> None:
    for system_name in {s for s, _ in groups}:
        for generic, specifics in _GENERIC_KEYS.items():
            key = (system_name, generic)
            if key not in groups:
                continue
            if any(f.effective_usage is not Usage.UNKNOWN for f in groups[key]):
                continue  # the generic finding already carries its own usage
            present = [s for s in specifics if (system_name, s) in groups]
            if len(present) == 1:
                groups[(system_name, present[0])].extend(groups.pop(key))


_STATUS_ORDER = [Status.CLASSICAL, Status.BROKEN, Status.WEAKENED, Status.HYBRID, Status.SAFE]
