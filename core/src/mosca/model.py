"""Core data types shared by the scanner, the CBOM writer and the risk engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from . import taxonomy
from .taxonomy import Algorithm, Status, Usage


class Kind(str, Enum):
    CODE = "code"
    CONFIG = "config"
    CERTIFICATE = "certificate"
    KEY = "key"
    DEPENDENCY = "dependency"


@dataclass(frozen=True)
class Finding:
    """One place in the codebase where a cryptographic algorithm is used."""

    algorithm: str
    path: str  # POSIX-style, relative to the scan root
    line: int
    kind: Kind
    detector: str
    snippet: str = ""
    confidence: float = 0.9
    key_bits: int | None = None
    curve: str | None = None
    usage: Usage | None = None  # overrides the algorithm's default usage
    note: str = ""

    @property
    def alg(self) -> Algorithm:
        return taxonomy.get(self.algorithm)

    @property
    def effective_usage(self) -> Usage:
        return self.usage or self.alg.usage

    @property
    def parameter(self) -> str | None:
        if self.key_bits:
            return str(self.key_bits)
        return self.curve

    @property
    def asset_key(self) -> str:
        """Identity of the cryptographic asset this finding belongs to."""
        p = self.parameter
        return f"{self.algorithm}-{p}".lower() if p else self.algorithm

    @property
    def classical_bits(self) -> int | None:
        if self.alg.family in ("RSA", "FFDH") and self.key_bits:
            return taxonomy.rsa_classical_bits(self.key_bits)
        return self.alg.classical_bits

    @property
    def status(self) -> Status:
        status = self.alg.status
        # Short RSA/DH keys are already breakable without a quantum computer.
        bits = self.classical_bits
        if status is Status.BROKEN and bits is not None and bits < 112:
            return Status.CLASSICAL
        return status

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["usage"] = self.effective_usage.value
        d["status"] = self.status.value
        return d


@dataclass
class ScanResult:
    root: str
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def by_status(self) -> dict[Status, list[Finding]]:
        out: dict[Status, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.status, []).append(f)
        return out
