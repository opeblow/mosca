"""Detector for certificates, private keys and SSH public keys checked into a repo.

Certificates are parsed with `cryptography` when it is installed, which yields the
exact key type, key size, curve and expiry. Without it the PEM header is used.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import timezone

from ..model import Finding, Kind
from ..taxonomy import Usage, normalize_curve

SUFFIXES = {".pem", ".crt", ".cer", ".key", ".pub", ".csr"}
NAMES = {"id_rsa", "id_ecdsa", "id_ed25519", "id_dsa", "authorized_keys", "known_hosts"}

RX_BLOCK = re.compile(r"-----BEGIN ([A-Z0-9 ]+)-----\s+([A-Za-z0-9+/=\s:,-]+?)-----END \1-----", re.S)
RX_SSH_PUB = re.compile(r"(?m)^(?:\S+\s+)?(ssh-rsa|ssh-ed25519|ssh-dss|ecdsa-sha2-nistp(?:256|384|521))\s+[A-Za-z0-9+/=]{20,}")

HEADER_ALG = {
    "RSA PRIVATE KEY": "rsa",
    "RSA PUBLIC KEY": "rsa",
    "EC PRIVATE KEY": "ec",
    "DSA PRIVATE KEY": "dsa",
    "DH PARAMETERS": "dh",
}
SSH_PUB = {"ssh-rsa": "rsa-signature", "ssh-ed25519": "ed25519", "ssh-dss": "dsa"}


def applies(name: str, suffix: str) -> bool:
    return suffix in SUFFIXES or name in NAMES


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _from_public_key(key) -> tuple[str, dict]:
    from cryptography.hazmat.primitives.asymmetric import dh, dsa, ec, ed448, ed25519, rsa, x448, x25519

    if isinstance(key, rsa.RSAPublicKey):
        return "rsa", {"key_bits": key.key_size}
    if isinstance(key, ec.EllipticCurvePublicKey):
        return "ec", {"curve": normalize_curve(key.curve.name)}
    if isinstance(key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
        return "ed25519", {}
    if isinstance(key, (x25519.X25519PublicKey, x448.X448PublicKey)):
        return "x25519", {}
    if isinstance(key, dsa.DSAPublicKey):
        return "dsa", {"key_bits": key.key_size}
    if isinstance(key, dh.DHPublicKey):
        return "dh", {"key_bits": key.key_size}
    return "", {}


def _certificate(pem_block: bytes) -> tuple[str, dict, str] | None:
    try:
        from cryptography import x509
    except ImportError:
        return None
    try:
        cert = x509.load_pem_x509_certificate(pem_block)
    except ValueError:
        return None
    alg, extra = _from_public_key(cert.public_key())
    if not alg:
        return None
    if alg in ("rsa", "ec", "dsa"):
        alg = {"rsa": "rsa-signature", "ec": "ecdsa", "dsa": "dsa"}[alg]
    try:
        expires = cert.not_valid_after_utc
    except AttributeError:  # cryptography < 42
        expires = cert.not_valid_after.replace(tzinfo=timezone.utc)
    subject = cert.subject.rfc4514_string() or "(no subject)"
    return alg, extra, f"certificate {subject}, expires {expires.date().isoformat()}"


def _private_key(pem_block: bytes) -> tuple[str, dict] | None:
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return None
    try:
        key = serialization.load_pem_private_key(pem_block, password=None)
    except (ValueError, TypeError):
        return None
    alg, extra = _from_public_key(key.public_key())
    return (alg, extra) if alg else None


def detect(path: str, text: str) -> Iterator[Finding]:
    for m in RX_BLOCK.finditer(text):
        label = m.group(1)
        line = _line(text, m.start())
        block = m.group(0).encode()
        if label == "CERTIFICATE":
            parsed = _certificate(block)
            if parsed:
                alg, extra, note = parsed
                yield Finding(algorithm=alg, path=path, line=line, kind=Kind.CERTIFICATE,
                              detector="pem", snippet=f"-----BEGIN {label}-----", confidence=1.0,
                              usage=Usage.SIGNATURE, note=note, **extra)
            continue
        if label.endswith("PRIVATE KEY"):
            parsed_key = _private_key(block)
            if parsed_key:
                alg, extra = parsed_key
                yield Finding(algorithm=alg, path=path, line=line, kind=Kind.KEY, detector="pem",
                              snippet=f"-----BEGIN {label}-----", confidence=1.0,
                              note="private key committed to the repository", **extra)
                continue
        alg = HEADER_ALG.get(label)
        if alg:
            yield Finding(algorithm=alg, path=path, line=line, kind=Kind.KEY, detector="pem",
                          snippet=f"-----BEGIN {label}-----", confidence=0.9,
                          note="key material committed to the repository")

    for m in RX_SSH_PUB.finditer(text):
        kind = m.group(1)
        if kind.startswith("ecdsa"):
            alg, extra = "ecdsa", {"curve": normalize_curve(kind.rsplit("-", 1)[-1])}
        else:
            alg, extra = SSH_PUB[kind], {}
        yield Finding(algorithm=alg, path=path, line=_line(text, m.start()), kind=Kind.KEY,
                      detector="pem", snippet=kind, confidence=1.0, note="SSH public key", **extra)
