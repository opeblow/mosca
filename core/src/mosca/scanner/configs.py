"""Detector for TLS, SSH and token configuration files.

Configuration is where most real-world key exchange is decided, so this detector is
often the most valuable one: one nginx line can decide the exposure of an entire API.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from ..model import Finding, Kind
from ..taxonomy import Usage, normalize_curve
from .python_ast import JWT_ALGS

CONFIG_SUFFIXES = {".conf", ".cnf", ".cfg", ".ini", ".yaml", ".yml", ".toml", ".json", ".env",
                   ".properties", ".tf", ".hcl"}
CONFIG_NAMES = {"sshd_config", "ssh_config", "nginx.conf", "httpd.conf", "apache2.conf",
                "haproxy.cfg", "caddyfile", "envoy.yaml", "openssl.cnf", ".env",
                "dockerfile", "docker-compose.yml", "docker-compose.yaml"}
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "composer.lock",
              "tsconfig.json", "cbom.json", "bom.json"}


def applies(name: str, suffix: str) -> bool:
    if name in SKIP_NAMES:
        return False
    return name in CONFIG_NAMES or suffix in CONFIG_SUFFIXES or name.startswith(".env")


# Groups and curves that can appear in TLS curve / group lists.
TLS_GROUPS: dict[str, tuple[str, str | None]] = {
    "x25519mlkem768": ("x25519mlkem768", None),
    "secp256r1mlkem768": ("x25519mlkem768", None),
    "mlkem768": ("ml-kem-768", None),
    "x25519kyber768draft00": ("x25519mlkem768", None),
    "x25519": ("x25519", None),
    "x448": ("x25519", None),
    "prime256v1": ("ecdh", "P-256"),
    "secp256r1": ("ecdh", "P-256"),
    "p-256": ("ecdh", "P-256"),
    "secp384r1": ("ecdh", "P-384"),
    "p-384": ("ecdh", "P-384"),
    "secp521r1": ("ecdh", "P-521"),
    "ffdhe2048": ("dh", None),
    "ffdhe3072": ("dh", None),
}

SSH_KEX: dict[str, str] = {
    "mlkem768x25519-sha256": "x25519mlkem768",
    "sntrup761x25519-sha512": "x25519mlkem768",
    "sntrup761x25519-sha512@openssh.com": "x25519mlkem768",
    "curve25519-sha256": "x25519",
    "curve25519-sha256@libssh.org": "x25519",
    "ecdh-sha2-nistp256": "ecdh",
    "ecdh-sha2-nistp384": "ecdh",
    "ecdh-sha2-nistp521": "ecdh",
    "diffie-hellman-group14-sha256": "dh",
    "diffie-hellman-group16-sha512": "dh",
    "diffie-hellman-group-exchange-sha256": "dh",
    "diffie-hellman-group14-sha1": "dh",
    "diffie-hellman-group1-sha1": "dh",
}

SSH_HOSTKEY: dict[str, str] = {
    "ssh-rsa": "rsa-signature",
    "rsa-sha2-256": "rsa-signature",
    "rsa-sha2-512": "rsa-signature",
    "ssh-ed25519": "ed25519",
    "ecdsa-sha2-nistp256": "ecdsa",
    "ecdsa-sha2-nistp384": "ecdsa",
    "ssh-dss": "dsa",
}

CIPHER_TOKENS: tuple[tuple[str, str, Usage | None], ...] = (
    ("3DES", "3des", None),
    ("DES-CBC3", "3des", None),
    ("RC4", "rc4", None),
    ("AES128", "aes-128", None),
    ("AES256", "aes-256", None),
    ("CHACHA20", "chacha20-poly1305", None),
    ("ECDHE", "ecdh", None),
    ("DHE", "dh", None),
    ("ECDSA", "ecdsa", None),
)

RX_TLS_GROUPS = re.compile(
    r"(?i)\b(ssl_ecdh_curve|ssl_conf_command\s+groups|groups|curves|SSLOpenSSLConfCmd\s+(?:Curves|Groups)|"
    r"ecdhCurve|ecdh_curve|curve_preferences|CurvePreferences)\b\s*[:=]?\s*[\"']?([\w:,\-\s\[\]\"']+)"
)
RX_SSL_CIPHERS = re.compile(r"(?i)\b(ssl_ciphers|SSLCipherSuite|ciphers|cipher_suites)\b\s*[:=]?\s*[\"']?([^\n;\"']+)")
RX_SSH = re.compile(r"(?im)^\s*(KexAlgorithms|HostKeyAlgorithms|PubkeyAcceptedAlgorithms|PubkeyAcceptedKeyTypes)\s+(.+)$")
RX_JWT = re.compile(
    r"(?i)\b(?:jwt[_.-]?)?(?:alg|algorithm|signing[_-]?algorithm)\b[\"']?\s*[:=]\s*[\"']?((?:RS|PS|ES|HS)(?:256|384|512)K?|EdDSA)\b"
)
RX_KEY_SIZE = re.compile(r"(?i)\b(rsa[_-]?key[_-]?(?:size|bits)|key[_-]?size|modulus[_-]?length|rsa_bits)\b\s*[:=]\s*[\"']?(\d{3,5})")
RX_OPENSSL_GENRSA = re.compile(r"openssl\s+(?:genrsa|req)\b[^\n]*?(?:rsa:|genrsa\s+(?:-\w+\s+\S+\s+)*)(\d{3,5})")
RX_OPENSSL_EC = re.compile(r"openssl\s+(?:ecparam|genpkey)\b[^\n]*?(?:-name|ec_paramgen_curve:)\s*([\w-]+)")


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _finding(path: str, text: str, offset: int, algorithm: str, *, confidence: float = 0.9,
             note: str = "", **extra) -> Finding:
    line = _line(text, offset)
    lines = text.splitlines()
    snippet = lines[line - 1].strip()[:200] if line <= len(lines) else ""
    return Finding(algorithm=algorithm, path=path, line=line, kind=Kind.CONFIG,
                   detector="config", snippet=snippet, confidence=confidence, note=note, **extra)


def _strip_hash_comments(text: str) -> str:
    """Blank full-line # comments (nginx, ssh, yaml, toml, .env), keeping offsets."""
    return re.sub(r"(?m)^[ \t]*#.*$", lambda m: " " * len(m.group(0)), text)


def detect(path: str, text: str) -> Iterator[Finding]:
    body = _strip_hash_comments(text)

    for m in RX_TLS_GROUPS.finditer(body):
        tokens = re.split(r"[:,\s\[\]\"']+", m.group(2))
        for token in tokens:
            hit = TLS_GROUPS.get(token.strip().lower())
            if hit:
                alg, curve = hit
                yield _finding(path, body, m.start(), alg, note=f"TLS group {token.strip()}",
                               usage=Usage.KEY_EXCHANGE, curve=curve)

    for m in RX_SSL_CIPHERS.finditer(body):
        value = m.group(2).upper()
        for token, alg, usage in CIPHER_TOKENS:
            # Lookarounds keep "DHE" from matching inside "ECDHE".
            if re.search(rf"(?<![A-Z0-9]){re.escape(token)}(?![A-Z])", value):
                yield _finding(path, body, m.start(), alg, note=f"cipher suite token {token}",
                               confidence=0.75, usage=usage)
        if re.search(r"(?<![A-Z])RSA(?![A-Z])", value) and "ECDHE" not in value:
            yield _finding(path, body, m.start(), "rsa", note="RSA key transport in cipher list",
                           confidence=0.7, usage=Usage.KEY_EXCHANGE)

    for m in RX_SSH.finditer(body):
        directive = m.group(1).lower()
        table = SSH_KEX if directive == "kexalgorithms" else SSH_HOSTKEY
        for token in re.split(r"[,\s]+", m.group(2).strip()):
            alg = table.get(token.lstrip("+-^").lower())
            if alg:
                yield _finding(path, body, m.start(), alg, note=f"SSH {m.group(1)} {token}")

    for m in RX_JWT.finditer(body):
        alg, usage = JWT_ALGS.get(m.group(1), (None, None))
        if alg:
            yield _finding(path, body, m.start(), alg, note=f"JWT {m.group(1)}", usage=usage)

    for m in RX_KEY_SIZE.finditer(body):
        bits = int(m.group(2))
        if bits >= 512:
            yield _finding(path, body, m.start(), "rsa", key_bits=bits, confidence=0.6,
                           note=f"configured {m.group(1)}")

    for m in RX_OPENSSL_GENRSA.finditer(body):
        yield _finding(path, body, m.start(), "rsa", key_bits=int(m.group(1)), note="openssl key generation")

    for m in RX_OPENSSL_EC.finditer(body):
        name = m.group(1).lower()
        if name in {"ed25519", "x25519"}:
            yield _finding(path, body, m.start(), name, note="openssl key generation")
        else:
            yield _finding(path, body, m.start(), "ec", curve=normalize_curve(name),
                           note="openssl key generation")
