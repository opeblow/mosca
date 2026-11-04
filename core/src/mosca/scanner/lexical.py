"""Pattern detector for JavaScript, TypeScript, Go, Java, Kotlin, C# and Rust.

Comments are blanked out first, keeping line numbers intact, so commented-out code
and documentation never produce findings. String literals are kept because most
crypto APIs in these languages take the algorithm name as a string.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..model import Finding, Kind
from ..taxonomy import Usage, normalize_curve

C_LIKE = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".go", ".java",
          ".kt", ".kts", ".cs", ".rs", ".scala", ".swift"}
LANGUAGES = C_LIKE


def strip_comments(src: str) -> str:
    """Blank `//` and `/* */` comments, leaving strings and newlines untouched."""
    out: list[str] = []
    i, n = 0, len(src)
    quote: str | None = None
    while i < n:
        c = src[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            # Single-line string kinds cannot span a newline; this also recovers
            # from Rust lifetimes ('a) and other stray quote characters.
            if c == quote or (c == "\n" and quote != "`"):
                quote = None
            i += 1
            continue
        if c in "\"'`":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            end = src.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.extend("\n" if ch == "\n" else " " for ch in src[i:end])
            i = end
            continue
        out.append(c)
        i += 1
    return "".join(out)


Extract = Callable[[re.Match[str]], dict]


@dataclass(frozen=True)
class Pattern:
    regex: re.Pattern[str]
    algorithm: str | Callable[[re.Match[str]], str | None]
    extract: Extract | None = None
    usage: Usage | None = None
    confidence: float = 0.9
    exts: frozenset[str] = frozenset(C_LIKE)


def P(rx: str, algorithm, extract: Extract | None = None, *, usage: Usage | None = None,
      confidence: float = 0.9, exts: set[str] | None = None) -> Pattern:
    return Pattern(re.compile(rx), algorithm, extract, usage, confidence,
                   frozenset(exts) if exts else frozenset(C_LIKE))


JS = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts"}
GO = {".go"}
JVM = {".java", ".kt", ".kts", ".scala"}


def _bits(group: int) -> Extract:
    return lambda m: {"key_bits": int(m.group(group))} if m.group(group) else {}


def _curve(group: int) -> Extract:
    return lambda m: {"curve": normalize_curve(m.group(group))}


_NODE_KEYTYPES = {"rsa": "rsa", "rsa-pss": "rsa-signature", "ec": "ec", "ed25519": "ed25519",
                  "ed448": "ed25519", "x25519": "x25519", "x448": "x25519", "dh": "dh", "dsa": "dsa"}

_NODE_HASHES = {"md5": "md5", "sha1": "sha1", "sha-1": "sha1", "sha256": "sha256",
                "sha-256": "sha256", "sha384": "sha384", "sha512": "sha512"}


def _node_cipher(m: re.Match[str]) -> str | None:
    name = m.group(1).lower()
    if name.startswith("aes-128") or name.startswith("aes128"):
        return "aes-128"
    if name.startswith("aes-256") or name.startswith("aes256"):
        return "aes-256"
    if name.startswith("aes"):
        return "aes"
    if name.startswith("des-ede3") or name == "des3":
        return "3des"
    if name.startswith("des"):
        return "des"
    if name.startswith("rc4"):
        return "rc4"
    if name.startswith("chacha20"):
        return "chacha20-poly1305"
    return None


def _jwt(m: re.Match[str]) -> str | None:
    from .python_ast import JWT_ALGS
    hit = JWT_ALGS.get(m.group(1))
    return hit[0] if hit else None


_JAVA_SIG = {"rsa": "rsa-signature", "ecdsa": "ecdsa", "dsa": "dsa", "ed25519": "ed25519", "eddsa": "ed25519"}


def _java_signature(m: re.Match[str]) -> str | None:
    tail = m.group(1).lower()
    for key, alg in _JAVA_SIG.items():
        if tail.endswith(key):
            return alg
    return None


_JAVA_KPG = {"rsa": "rsa", "ec": "ec", "dsa": "dsa", "dh": "dh", "diffiehellman": "dh",
             "ed25519": "ed25519", "x25519": "x25519", "ml-kem": "ml-kem-768", "ml-dsa": "ml-dsa-65"}
_JAVA_DIGEST = {"md5": "md5", "sha-1": "sha1", "sha1": "sha1", "sha-256": "sha256",
                "sha-384": "sha384", "sha-512": "sha512"}


def _java_cipher(m: re.Match[str]) -> str | None:
    name = m.group(1).split("/")[0].lower()
    return {"desede": "3des", "tripledes": "3des", "des": "des", "rc4": "rc4", "arcfour": "rc4",
            "rsa": "rsa", "aes": "aes", "aes_128": "aes-128", "aes_256": "aes-256",
            "chacha20-poly1305": "chacha20-poly1305"}.get(name)


PATTERNS: tuple[Pattern, ...] = (
    # ---- Node.js crypto / WebCrypto / jsonwebtoken ------------------------------
    P(r"generateKeyPair(?:Sync)?\(\s*['\"]([\w-]+)['\"]",
      lambda m: _NODE_KEYTYPES.get(m.group(1).lower()), exts=JS),
    P(r"modulusLength\s*:\s*(\d{3,5})", "rsa", _bits(1), confidence=0.8, exts=JS),
    P(r"namedCurve\s*:\s*['\"]([\w-]+)['\"]", "ec", _curve(1), exts=JS),
    P(r"createHash\(\s*['\"]([\w-]+)['\"]", lambda m: _NODE_HASHES.get(m.group(1).lower()), exts=JS),
    P(r"createHmac\(\s*['\"](sha256|sha384|sha512)['\"]", "hmac-sha256", exts=JS),
    P(r"create(?:De)?[Cc]ipheriv\(\s*['\"]([\w-]+)['\"]", _node_cipher, exts=JS),
    P(r"createECDH\(\s*['\"]([\w-]+)['\"]", "ecdh", _curve(1), exts=JS),
    P(r"createDiffieHellman(?:Group)?\(", "dh", exts=JS),
    P(r"publicEncrypt\(|privateDecrypt\(", "rsa", usage=Usage.ENCRYPTION, exts=JS),
    P(r"name\s*:\s*['\"](RSA-OAEP)['\"]", "rsa", usage=Usage.ENCRYPTION, exts=JS),
    P(r"name\s*:\s*['\"](RSA-PSS|RSASSA-PKCS1-v1_5)['\"]", "rsa-signature", exts=JS),
    P(r"name\s*:\s*['\"](ECDSA)['\"]", "ecdsa", exts=JS),
    P(r"name\s*:\s*['\"](ECDH)['\"]", "ecdh", exts=JS),
    P(r"name\s*:\s*['\"](Ed25519)['\"]", "ed25519", exts=JS),
    P(r"name\s*:\s*['\"](X25519)['\"]", "x25519", exts=JS),
    P(r"algorithms?\s*:\s*\[?\s*['\"]((?:RS|PS|ES|HS)(?:256|384|512)K?|EdDSA)['\"]", _jwt, exts=JS),
    P(r"pki\.rsa\.generateKeyPair\(\s*(?:\{\s*bits\s*:\s*)?(\d{3,5})?", "rsa", _bits(1), exts=JS),
    P(r"new\s+NodeRSA\(", "rsa", confidence=0.8, exts=JS),
    P(r"new\s+(?:EC|ec)\(\s*['\"](\w+)['\"]", "ec", _curve(1), confidence=0.8, exts=JS),
    P(r"\bml_kem768\b|MlKem768", "ml-kem-768", exts=JS),
    # ---- Go standard library ----------------------------------------------------
    P(r"rsa\.GenerateKey\([^,()]+,\s*(\d{3,5})\)", "rsa", _bits(1), exts=GO),
    P(r"rsa\.(?:EncryptOAEP|DecryptOAEP|EncryptPKCS1v15|DecryptPKCS1v15)\(", "rsa",
      usage=Usage.ENCRYPTION, exts=GO),
    P(r"rsa\.(?:SignPKCS1v15|SignPSS|VerifyPKCS1v15|VerifyPSS)\(", "rsa-signature", exts=GO),
    P(r"ecdsa\.GenerateKey\(\s*elliptic\.(P\d{3})\(\)", "ecdsa", _curve(1), exts=GO),
    P(r"ecdsa\.(?:Sign|SignASN1|Verify|VerifyASN1)\(", "ecdsa", exts=GO),
    P(r"ecdh\.(P256|P384|P521)\(\)", "ecdh", _curve(1), exts=GO),
    P(r"ecdh\.X25519\(\)", "x25519", exts=GO),
    P(r"ed25519\.(?:GenerateKey|Sign|Verify)\(", "ed25519", exts=GO),
    P(r"tls\.Curve(P256|P384|P521)\b", "ecdh", _curve(1), exts=GO),
    P(r"tls\.X25519\b(?!MLKEM)", "x25519", exts=GO),
    P(r"tls\.X25519MLKEM768\b", "x25519mlkem768", exts=GO),
    P(r"mlkem\.GenerateKey768\(|mlkem\.NewEncapsulationKey768\(", "ml-kem-768", exts=GO),
    P(r"\bmd5\.(?:New|Sum)\(", "md5", exts=GO),
    P(r"\bsha1\.(?:New|Sum)\(", "sha1", exts=GO),
    P(r"\bsha256\.(?:New|Sum256)\(", "sha256", exts=GO),
    P(r"des\.NewTripleDESCipher\(", "3des", exts=GO),
    P(r"des\.NewCipher\(", "des", exts=GO),
    P(r"rc4\.NewCipher\(", "rc4", exts=GO),
    P(r"dsa\.GenerateParameters\(", "dsa", exts=GO),
    # ---- Java / Kotlin JCA ------------------------------------------------------
    P(r"KeyPairGenerator\.getInstance\(\s*\"([\w-]+)\"",
      lambda m: _JAVA_KPG.get(m.group(1).lower()), exts=JVM),
    P(r"\.initialize\(\s*(\d{4,5})\s*[,)]", "rsa", _bits(1), confidence=0.6, exts=JVM),
    P(r"Signature\.getInstance\(\s*\"([\w-]+)\"", _java_signature, exts=JVM),
    P(r"MessageDigest\.getInstance\(\s*\"([\w-]+)\"",
      lambda m: _JAVA_DIGEST.get(m.group(1).lower()), exts=JVM),
    P(r"Cipher\.getInstance\(\s*\"([\w/-]+)\"", _java_cipher, exts=JVM),
    P(r"KeyAgreement\.getInstance\(\s*\"(ECDH|DH|X25519|XDH)\"",
      lambda m: {"ecdh": "ecdh", "dh": "dh", "x25519": "x25519", "xdh": "x25519"}[m.group(1).lower()],
      exts=JVM),
    P(r"new\s+ECGenParameterSpec\(\s*\"([\w-]+)\"", "ec", _curve(1), exts=JVM),
)


def detect(path: str, text: str) -> Iterator[Finding]:
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    clean = strip_comments(text)
    raw_lines = text.splitlines()
    line_starts = [0]
    for i, ch in enumerate(clean):
        if ch == "\n":
            line_starts.append(i + 1)

    def line_of(offset: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    for pattern in PATTERNS:
        if ext not in pattern.exts:
            continue
        for m in pattern.regex.finditer(clean):
            algorithm = pattern.algorithm(m) if callable(pattern.algorithm) else pattern.algorithm
            if not algorithm:
                continue
            line = line_of(m.start())
            extra = pattern.extract(m) if pattern.extract else {}
            yield Finding(
                algorithm=algorithm, path=path, line=line, kind=Kind.CODE, detector="lexical",
                snippet=raw_lines[line - 1].strip()[:200] if line <= len(raw_lines) else "",
                confidence=pattern.confidence, usage=pattern.usage, **extra,
            )
