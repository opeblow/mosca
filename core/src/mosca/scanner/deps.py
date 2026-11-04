"""Detector for dependency manifests that pull in classical public-key libraries.

A dependency is weaker evidence than a call site, so these findings carry lower
confidence. They matter because they reveal crypto hidden in transitive code paths.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from ..model import Finding, Kind

MANIFESTS = {"package.json", "requirements.txt", "pyproject.toml", "go.mod", "pom.xml",
             "build.gradle", "build.gradle.kts", "cargo.toml", "pipfile", "setup.cfg"}

# library name -> (algorithm, note). Lower-cased names.
LIBRARIES: dict[str, tuple[str, str]] = {
    # JavaScript
    "node-rsa": ("rsa", "RSA library"),
    "node-forge": ("rsa", "node-forge PKI toolkit (RSA)"),
    "jsrsasign": ("rsa-signature", "jsrsasign (RSA/ECDSA signatures)"),
    "elliptic": ("ec", "elliptic curve library"),
    "tweetnacl": ("x25519", "NaCl (X25519/Ed25519)"),
    "jsonwebtoken": ("rsa-signature", "JWT library; check the configured algorithm"),
    "jose": ("rsa-signature", "JOSE library; check the configured algorithm"),
    "@noble/curves": ("ec", "noble curves (ECC)"),
    "@noble/post-quantum": ("ml-kem-768", "noble post-quantum (ML-KEM/ML-DSA)"),
    # Python
    "rsa": ("rsa", "python-rsa"),
    "ecdsa": ("ecdsa", "python-ecdsa"),
    "pycryptodome": ("rsa", "PyCryptodome"),
    "pycrypto": ("rsa", "PyCrypto (unmaintained)"),
    "paramiko": ("rsa-signature", "paramiko SSH"),
    "pyjwt": ("rsa-signature", "PyJWT; check the configured algorithm"),
    "python-jose": ("rsa-signature", "python-jose; check the configured algorithm"),
    "liboqs-python": ("ml-kem-768", "Open Quantum Safe bindings"),
    # Go
    "golang.org/x/crypto": ("ecdh", "x/crypto (curve25519, ssh)"),
    "github.com/golang-jwt/jwt": ("rsa-signature", "golang-jwt"),
    "github.com/golang-jwt/jwt/v5": ("rsa-signature", "golang-jwt"),
    "github.com/cloudflare/circl": ("ml-kem-768", "CIRCL (post-quantum)"),
    "github.com/open-quantum-safe/liboqs-go": ("ml-kem-768", "Open Quantum Safe bindings"),
    # JVM
    "org.bouncycastle": ("rsa", "Bouncy Castle provider"),
    "io.jsonwebtoken": ("rsa-signature", "jjwt"),
}

RX_REQ = re.compile(r"(?m)^\s*([A-Za-z0-9_.\-]+)\s*(?:[<>=!~;\[]|$)")
RX_TOML_DEP = re.compile(r"""(?m)^\s*["']?([A-Za-z0-9_.\-]+)["']?\s*(?:=|[<>=!~])""")
RX_GO = re.compile(r"(?m)^\s*(?:require\s+)?([a-z0-9.\-]+\.[a-z]{2,}/[^\s]+)\s+v")
RX_MAVEN = re.compile(r"<groupId>\s*([\w.\-]+)\s*</groupId>")
RX_GRADLE = re.compile(r"""['"]([\w.\-]+):[\w.\-]+:""")


def applies(name: str) -> bool:
    return name in MANIFESTS


def _line_of(text: str, needle: str) -> int:
    idx = text.find(needle)
    return text.count("\n", 0, idx) + 1 if idx >= 0 else 1


def _names(filename: str, text: str) -> list[str]:
    if filename == "package.json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        out: list[str] = []
        for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            out.extend((data.get(section) or {}).keys())
        return out
    if filename in ("requirements.txt", "pipfile", "setup.cfg"):
        return [m.group(1) for m in RX_REQ.finditer(text)]
    if filename in ("pyproject.toml", "cargo.toml"):
        quoted = re.findall(r"""["']([A-Za-z0-9_.\-]+)\s*(?:[<>=!~\[;]|["'])""", text)
        return quoted + [m.group(1) for m in RX_TOML_DEP.finditer(text)]
    if filename == "go.mod":
        return [m.group(1) for m in RX_GO.finditer(text)]
    if filename == "pom.xml":
        return RX_MAVEN.findall(text)
    if filename.startswith("build.gradle"):
        return RX_GRADLE.findall(text)
    return []


def _lookup(key: str) -> tuple[str, str] | None:
    if key in LIBRARIES:
        return LIBRARIES[key]
    # Go module paths and Maven group ids also match by prefix.
    for lib, hit in LIBRARIES.items():
        if ("/" in lib or lib.startswith(("org.", "io."))) and key.startswith(lib):
            return hit
    return None


def detect(path: str, text: str) -> Iterator[Finding]:
    filename = path.rsplit("/", 1)[-1].lower()
    seen: set[str] = set()
    for name in _names(filename, text):
        key = name.lower()
        hit = _lookup(key)
        if hit is None or key in seen:
            continue
        seen.add(key)
        alg, note = hit
        yield Finding(algorithm=alg, path=path, line=_line_of(text, name), kind=Kind.DEPENDENCY,
                      detector="dependency", snippet=name, confidence=0.5, note=note)
