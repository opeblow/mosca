"""Catalog of cryptographic algorithms and how a quantum computer affects each one.

Status meanings:
  quantum-broken      Shor's algorithm recovers the key (RSA, ECC, finite-field DH, DSA).
  quantum-weakened    Grover's algorithm roughly halves the security bits. Still usable,
                      but below NIST's preferred level for long-lived secrets.
  classically-broken  Already insecure today, quantum or not (MD5, SHA-1, DES, RC4).
  hybrid              Classical + post-quantum combined (e.g. X25519MLKEM768).
  quantum-safe        Post-quantum standards and large symmetric/hash primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    BROKEN = "quantum-broken"
    WEAKENED = "quantum-weakened"
    CLASSICAL = "classically-broken"
    HYBRID = "hybrid"
    SAFE = "quantum-safe"

    @property
    def needs_migration(self) -> bool:
        return self in (Status.BROKEN, Status.CLASSICAL)


class Usage(str, Enum):
    """What the primitive protects. Drives which Mosca variable applies."""

    KEY_EXCHANGE = "key-exchange"  # confidentiality: harvest-now-decrypt-later applies
    ENCRYPTION = "encryption"      # confidentiality
    SIGNATURE = "signature"        # authenticity: forgery risk starts when the CRQC exists
    HASH = "hash"
    UNKNOWN = "unknown"            # treated as confidentiality (conservative)

    @property
    def confidentiality(self) -> bool:
        return self in (Usage.KEY_EXCHANGE, Usage.ENCRYPTION, Usage.UNKNOWN)


@dataclass(frozen=True)
class Algorithm:
    id: str
    name: str
    family: str
    primitive: str  # CycloneDX 1.6 algorithmProperties.primitive
    status: Status
    usage: Usage
    classical_bits: int | None
    nist_quantum_level: int
    replacement: str
    oid: str | None = None
    functions: tuple[str, ...] = field(default_factory=tuple)


def _a(*args, **kwargs) -> Algorithm:
    return Algorithm(*args, **kwargs)


_ALGORITHMS: tuple[Algorithm, ...] = (
    # --- Shor-breakable public-key cryptography --------------------------------
    _a("rsa", "RSA", "RSA", "pke", Status.BROKEN, Usage.UNKNOWN, 112, 0,
       "ML-KEM-768 for encryption, ML-DSA-65 for signatures",
       "1.2.840.113549.1.1.1", ("keygen", "encrypt", "decrypt", "sign", "verify")),
    _a("rsa-signature", "RSA signature", "RSA", "signature", Status.BROKEN, Usage.SIGNATURE, 112, 0,
       "ML-DSA-65 (FIPS 204), or hybrid composite signatures during transition",
       "1.2.840.113549.1.1.11", ("sign", "verify")),
    _a("ec", "Elliptic-curve key", "ECC", "pke", Status.BROKEN, Usage.UNKNOWN, 128, 0,
       "ML-KEM-768 or ML-DSA-65 depending on use",
       "1.2.840.10045.2.1", ("keygen",)),
    _a("ecdsa", "ECDSA", "ECC", "signature", Status.BROKEN, Usage.SIGNATURE, 128, 0,
       "ML-DSA-65 (FIPS 204)", "1.2.840.10045.4.3.2", ("sign", "verify")),
    _a("ecdh", "ECDH", "ECC", "key-agree", Status.BROKEN, Usage.KEY_EXCHANGE, 128, 0,
       "X25519MLKEM768 hybrid key exchange", "1.3.132.1.12", ("keygen", "keyderive")),
    _a("ed25519", "Ed25519", "EdDSA", "signature", Status.BROKEN, Usage.SIGNATURE, 128, 0,
       "ML-DSA-65 (FIPS 204)", "1.3.101.112", ("sign", "verify")),
    _a("x25519", "X25519", "ECC", "key-agree", Status.BROKEN, Usage.KEY_EXCHANGE, 128, 0,
       "X25519MLKEM768 hybrid key exchange", "1.3.101.110", ("keygen", "keyderive")),
    _a("dh", "Diffie-Hellman", "FFDH", "key-agree", Status.BROKEN, Usage.KEY_EXCHANGE, 112, 0,
       "X25519MLKEM768 hybrid key exchange", "1.2.840.10046.2.1", ("keygen", "keyderive")),
    _a("dsa", "DSA", "DSA", "signature", Status.BROKEN, Usage.SIGNATURE, 112, 0,
       "ML-DSA-65 (FIPS 204)", "1.2.840.10040.4.1", ("sign", "verify")),
    # --- Symmetric and hash ------------------------------------------------------
    _a("aes-128", "AES-128", "AES", "block-cipher", Status.WEAKENED, Usage.ENCRYPTION, 128, 1,
       "AES-256-GCM", "2.16.840.1.101.3.4.1.6", ("encrypt", "decrypt")),
    _a("aes-256", "AES-256", "AES", "block-cipher", Status.SAFE, Usage.ENCRYPTION, 256, 5,
       "none needed", "2.16.840.1.101.3.4.1.46", ("encrypt", "decrypt")),
    _a("aes", "AES (key size unknown)", "AES", "block-cipher", Status.WEAKENED, Usage.ENCRYPTION, 128, 1,
       "Confirm a 256-bit key (AES-256-GCM)", None, ("encrypt", "decrypt")),
    _a("chacha20-poly1305", "ChaCha20-Poly1305", "ChaCha20", "ae", Status.SAFE, Usage.ENCRYPTION, 256, 5,
       "none needed", None, ("encrypt", "decrypt")),
    _a("3des", "Triple DES", "DES", "block-cipher", Status.CLASSICAL, Usage.ENCRYPTION, 112, 0,
       "AES-256-GCM", "1.2.840.113549.3.7", ("encrypt", "decrypt")),
    _a("des", "DES", "DES", "block-cipher", Status.CLASSICAL, Usage.ENCRYPTION, 56, 0,
       "AES-256-GCM", "1.3.14.3.2.7", ("encrypt", "decrypt")),
    _a("rc4", "RC4", "RC4", "stream-cipher", Status.CLASSICAL, Usage.ENCRYPTION, None, 0,
       "AES-256-GCM or ChaCha20-Poly1305", None, ("encrypt", "decrypt")),
    _a("md5", "MD5", "MD5", "hash", Status.CLASSICAL, Usage.HASH, None, 0,
       "SHA-384 or SHA3-384", "1.2.840.113549.2.5", ("digest",)),
    _a("sha1", "SHA-1", "SHA-1", "hash", Status.CLASSICAL, Usage.HASH, None, 0,
       "SHA-384 or SHA3-384", "1.3.14.3.2.26", ("digest",)),
    _a("sha256", "SHA-256", "SHA-2", "hash", Status.SAFE, Usage.HASH, 128, 2,
       "none needed (SHA-384 for long-term signatures)", "2.16.840.1.101.3.4.2.1", ("digest",)),
    _a("sha384", "SHA-384", "SHA-2", "hash", Status.SAFE, Usage.HASH, 192, 4,
       "none needed", "2.16.840.1.101.3.4.2.2", ("digest",)),
    _a("sha512", "SHA-512", "SHA-2", "hash", Status.SAFE, Usage.HASH, 256, 5,
       "none needed", "2.16.840.1.101.3.4.2.3", ("digest",)),
    _a("hmac-sha256", "HMAC-SHA256", "HMAC", "mac", Status.SAFE, Usage.SIGNATURE, 256, 5,
       "none needed", "1.2.840.113549.2.9", ("tag",)),
    # --- Post-quantum and hybrid -------------------------------------------------
    _a("ml-kem-768", "ML-KEM-768", "ML-KEM", "kem", Status.SAFE, Usage.KEY_EXCHANGE, 192, 3,
       "none needed", "2.16.840.1.101.3.4.4.2", ("keygen", "encapsulate", "decapsulate")),
    _a("ml-dsa-65", "ML-DSA-65", "ML-DSA", "signature", Status.SAFE, Usage.SIGNATURE, 192, 3,
       "none needed", "2.16.840.1.101.3.4.3.18", ("keygen", "sign", "verify")),
    _a("slh-dsa", "SLH-DSA", "SLH-DSA", "signature", Status.SAFE, Usage.SIGNATURE, 128, 1,
       "none needed", "2.16.840.1.101.3.4.3.20", ("keygen", "sign", "verify")),
    _a("x25519mlkem768", "X25519MLKEM768", "ML-KEM", "kem", Status.HYBRID, Usage.KEY_EXCHANGE, 192, 3,
       "none needed", None, ("keygen", "encapsulate", "decapsulate")),
)

ALGORITHMS: dict[str, Algorithm] = {a.id: a for a in _ALGORITHMS}


def get(alg_id: str) -> Algorithm:
    try:
        return ALGORITHMS[alg_id]
    except KeyError as exc:  # pragma: no cover - programming error
        raise KeyError(f"unknown algorithm id {alg_id!r}") from exc


def rsa_classical_bits(modulus_bits: int) -> int:
    """NIST SP 800-57 Part 1 comparable-strength table for RSA and finite-field DH."""
    if modulus_bits >= 15360:
        return 256
    if modulus_bits >= 7680:
        return 192
    if modulus_bits >= 3072:
        return 128
    if modulus_bits >= 2048:
        return 112
    if modulus_bits >= 1024:
        return 80
    return 0


CURVE_ALIASES: dict[str, str] = {
    "secp256r1": "P-256", "prime256v1": "P-256", "p256": "P-256", "p-256": "P-256",
    "nistp256": "P-256",
    "secp384r1": "P-384", "p384": "P-384", "p-384": "P-384", "nistp384": "P-384",
    "secp521r1": "P-521", "p521": "P-521", "p-521": "P-521", "nistp521": "P-521",
    "secp256k1": "secp256k1",
    "x25519": "Curve25519", "curve25519": "Curve25519", "ed25519": "Curve25519",
}


def normalize_curve(name: str) -> str:
    return CURVE_ALIASES.get(name.strip().lower().replace("_", ""), name)
