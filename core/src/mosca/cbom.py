"""CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) writer and reader."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .model import Finding, Kind, ScanResult
from .taxonomy import Usage, get


def _bom_ref(asset_key: str) -> str:
    return f"crypto/algorithm/{asset_key}"


def to_cbom(scan: ScanResult, name: str | None = None) -> dict[str, Any]:
    groups: dict[str, list[Finding]] = defaultdict(list)
    for f in scan.findings:
        groups[f.asset_key].append(f)

    components: list[dict[str, Any]] = []
    for asset_key, findings in sorted(groups.items()):
        lead = findings[0]
        alg = get(lead.algorithm)
        algo_props: dict[str, Any] = {
            "primitive": alg.primitive,
            "executionEnvironment": "software-plain-ram",
            "implementationPlatform": "unknown",
            "certificationLevel": ["none"],
            "cryptoFunctions": list(alg.functions) or ["unknown"],
            "nistQuantumSecurityLevel": alg.nist_quantum_level,
        }
        bits = lead.classical_bits
        if bits is not None:
            algo_props["classicalSecurityLevel"] = bits
        if lead.key_bits:
            algo_props["parameterSetIdentifier"] = str(lead.key_bits)
        if lead.curve:
            algo_props["curve"] = lead.curve

        component: dict[str, Any] = {
            "type": "cryptographic-asset",
            "bom-ref": _bom_ref(asset_key),
            "name": alg.name + (f"-{lead.parameter}" if lead.parameter else ""),
            "cryptoProperties": {"assetType": "algorithm", "algorithmProperties": algo_props},
            "evidence": {
                "occurrences": [
                    {"location": f.path, "line": f.line,
                     **({"additionalContext": f.note} if f.note else {})}
                    for f in findings
                ]
            },
            "properties": [
                {"name": "mosca:status", "value": lead.status.value},
                {"name": "mosca:usage", "value": lead.effective_usage.value},
                {"name": "mosca:replacement", "value": alg.replacement},
                {"name": "mosca:kinds", "value": ",".join(sorted({f.kind.value for f in findings}))},
                {"name": "mosca:detectors", "value": ",".join(sorted({f.detector for f in findings}))},
                {"name": "mosca:confidence", "value": f"{max(f.confidence for f in findings):.2f}"},
            ],
        }
        if alg.oid:
            component["cryptoProperties"]["oid"] = alg.oid
        components.append(component)

    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "tools": {"components": [{"type": "application", "name": "mosca", "version": __version__}]},
            "component": {"type": "application", "name": name or Path(scan.root).name,
                          "bom-ref": "root"},
            "properties": [
                {"name": "mosca:files_scanned", "value": str(scan.files_scanned)},
            ],
        },
        "components": components,
        "dependencies": [{"ref": "root", "dependsOn": [c["bom-ref"] for c in components]}],
    }


def from_cbom(doc: dict[str, Any], root: str = ".") -> ScanResult:
    """Rebuild findings from a CBOM written by `to_cbom` (used for diffs and re-assessment)."""
    if doc.get("bomFormat") != "CycloneDX":
        raise ValueError("not a CycloneDX document")
    result = ScanResult(root=root)
    for comp in doc.get("components", []):
        if comp.get("type") != "cryptographic-asset":
            continue
        ref = comp.get("bom-ref", "")
        asset_key = ref.removeprefix("crypto/algorithm/")
        props = {p["name"]: p["value"] for p in comp.get("properties", [])}
        algo_props = comp.get("cryptoProperties", {}).get("algorithmProperties", {})
        alg_id = _alg_id_from_key(asset_key)
        param = algo_props.get("parameterSetIdentifier")
        curve = algo_props.get("curve")
        kinds = props.get("mosca:kinds", "code").split(",")
        usage = props.get("mosca:usage")
        for occ in comp.get("evidence", {}).get("occurrences", []):
            result.findings.append(Finding(
                algorithm=alg_id, path=occ["location"], line=int(occ.get("line", 1)),
                kind=Kind(kinds[0]), detector="cbom", note=occ.get("additionalContext", ""),
                confidence=float(props.get("mosca:confidence", 0.9)),
                key_bits=int(param) if param and param.isdigit() else None,
                curve=curve, usage=Usage(usage) if usage else None,
            ))
    return result


def _alg_id_from_key(asset_key: str) -> str:
    # Asset keys are "<algorithm>" or "<algorithm>-<parameter>". Algorithm ids contain
    # hyphens too, so match the longest known id that prefixes the key.
    from .taxonomy import ALGORITHMS
    candidates = [a for a in ALGORITHMS if asset_key == a or asset_key.startswith(a + "-")]
    if not candidates:
        raise ValueError(f"unknown asset {asset_key!r}")
    return max(candidates, key=len)
