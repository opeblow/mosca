"""Python detector built on the standard-library AST.

Imports are resolved, so `from cryptography.hazmat.primitives.asymmetric import rsa as r`
followed by `r.generate_private_key(...)` is still recognised as RSA key generation.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..model import Finding, Kind
from ..taxonomy import Usage, normalize_curve

ASYM = "cryptography.hazmat.primitives.asymmetric"
HASHES = "cryptography.hazmat.primitives.hashes"
CIPHERS = "cryptography.hazmat.primitives.ciphers"


@dataclass(frozen=True)
class Rule:
    algorithm: str
    extract: Callable[[ast.Call], dict] | None = None
    usage: Usage | None = None


def _kw(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _arg(call: ast.Call, index: int, name: str | None = None) -> ast.expr | None:
    if name is not None and (v := _kw(call, name)) is not None:
        return v
    return call.args[index] if len(call.args) > index else None


def _int(node: ast.expr | None) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    return None


def _str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _key_size(index: int, name: str) -> Callable[[ast.Call], dict]:
    def extract(call: ast.Call) -> dict:
        bits = _int(_arg(call, index, name))
        return {"key_bits": bits} if bits else {}
    return extract


def _ec_curve(call: ast.Call) -> dict:
    node = _arg(call, 0, "curve")
    if isinstance(node, ast.Call):
        node = node.func
    name = None
    if isinstance(node, ast.Attribute):
        name = node.attr
    elif isinstance(node, ast.Name):
        name = node.id
    return {"curve": normalize_curve(name)} if name else {}


RULES: dict[str, Rule] = {
    # cryptography (pyca)
    f"{ASYM}.rsa.generate_private_key": Rule("rsa", _key_size(1, "key_size")),
    f"{ASYM}.rsa.RSAPrivateNumbers": Rule("rsa"),
    f"{ASYM}.padding.OAEP": Rule("rsa", usage=Usage.ENCRYPTION),
    f"{ASYM}.padding.PSS": Rule("rsa-signature"),
    f"{ASYM}.padding.PKCS1v15": Rule("rsa"),
    f"{ASYM}.ec.generate_private_key": Rule("ec", _ec_curve),
    f"{ASYM}.ec.ECDSA": Rule("ecdsa"),
    f"{ASYM}.ec.ECDH": Rule("ecdh"),
    f"{ASYM}.ed25519.Ed25519PrivateKey.generate": Rule("ed25519"),
    f"{ASYM}.ed448.Ed448PrivateKey.generate": Rule("ed25519"),
    f"{ASYM}.x25519.X25519PrivateKey.generate": Rule("x25519"),
    f"{ASYM}.dh.generate_parameters": Rule("dh", _key_size(1, "key_size")),
    f"{ASYM}.dsa.generate_private_key": Rule("dsa", _key_size(0, "key_size")),
    f"{HASHES}.MD5": Rule("md5"),
    f"{HASHES}.SHA1": Rule("sha1"),
    f"{HASHES}.SHA256": Rule("sha256"),
    f"{HASHES}.SHA384": Rule("sha384"),
    f"{HASHES}.SHA512": Rule("sha512"),
    f"{CIPHERS}.algorithms.TripleDES": Rule("3des"),
    f"{CIPHERS}.algorithms.ARC4": Rule("rc4"),
    f"{CIPHERS}.algorithms.ChaCha20": Rule("chacha20-poly1305"),
    f"{CIPHERS}.aead.ChaCha20Poly1305": Rule("chacha20-poly1305"),
    # hashlib
    "hashlib.md5": Rule("md5"),
    "hashlib.sha1": Rule("sha1"),
    "hashlib.sha256": Rule("sha256"),
    "hashlib.sha384": Rule("sha384"),
    "hashlib.sha512": Rule("sha512"),
    # PyCryptodome / PyCrypto
    "Crypto.PublicKey.RSA.generate": Rule("rsa", _key_size(0, "bits")),
    "Crypto.PublicKey.ECC.generate": Rule("ec", lambda c: {"curve": normalize_curve(_str(_kw(c, "curve")) or "")} if _str(_kw(c, "curve")) else {}),
    "Crypto.PublicKey.DSA.generate": Rule("dsa", _key_size(0, "bits")),
    "Crypto.Cipher.PKCS1_OAEP.new": Rule("rsa", usage=Usage.ENCRYPTION),
    "Crypto.Signature.pkcs1_15.new": Rule("rsa-signature"),
    "Crypto.Signature.DSS.new": Rule("ecdsa"),
    "Crypto.Cipher.DES.new": Rule("des"),
    "Crypto.Cipher.DES3.new": Rule("3des"),
    "Crypto.Cipher.ARC4.new": Rule("rc4"),
    "Crypto.Hash.MD5.new": Rule("md5"),
    "Crypto.Hash.SHA1.new": Rule("sha1"),
    "Cryptodome.PublicKey.RSA.generate": Rule("rsa", _key_size(0, "bits")),
    # python-rsa, ecdsa, paramiko
    "rsa.newkeys": Rule("rsa", _key_size(0, "nbits")),
    "ecdsa.SigningKey.generate": Rule("ecdsa"),
    "paramiko.RSAKey.generate": Rule("rsa", _key_size(0, "bits")),
    "paramiko.ECDSAKey.generate": Rule("ecdsa"),
    "paramiko.DSSKey.generate": Rule("dsa", _key_size(0, "bits")),
}

HASHLIB_NEW = {"md5": "md5", "sha1": "sha1", "sha256": "sha256", "sha384": "sha384", "sha512": "sha512"}

# JWT algorithm names, shared with the config and lexical detectors.
JWT_ALGS: dict[str, tuple[str, Usage | None]] = {
    **{f"RS{n}": ("rsa-signature", None) for n in (256, 384, 512)},
    **{f"PS{n}": ("rsa-signature", None) for n in (256, 384, 512)},
    **{f"ES{n}": ("ecdsa", None) for n in (256, 384, 512)},
    "ES256K": ("ecdsa", None),
    "EdDSA": ("ed25519", None),
    **{f"HS{n}": ("hmac-sha256", None) for n in (256, 384, 512)},
}

JWT_CALLS = {"jwt.encode", "jwt.decode", "jose.jwt.encode", "jose.jwt.decode"}


def _dotted(node: ast.expr) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    if isinstance(node, ast.Call):  # e.g. ed25519.Ed25519PrivateKey.generate()
        inner = _dotted(node.func)
        if inner:
            return ".".join([inner, *reversed(parts)])
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self, path: str, lines: list[str]) -> None:
        self.path = path
        self.lines = lines
        self.aliases: dict[str, str] = {}
        self.findings: list[Finding] = []

    # ---- import tracking -------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            self.aliases[local] = alias.name if alias.asname else alias.name.split(".")[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None or node.level:
            return
        for alias in node.names:
            self.aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def resolve(self, dotted: str) -> str:
        head, _, rest = dotted.partition(".")
        target = self.aliases.get(head)
        if target is None:
            return dotted
        return f"{target}.{rest}" if rest else target

    # ---- calls -----------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        dotted = _dotted(node.func)
        if dotted:
            self._match(self.resolve(dotted), node)
        self.generic_visit(node)

    def _emit(self, node: ast.AST, algorithm: str, *, usage: Usage | None = None,
              confidence: float = 0.95, note: str = "", **extra) -> None:
        line = getattr(node, "lineno", 1)
        snippet = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.findings.append(Finding(
            algorithm=algorithm, path=self.path, line=line, kind=Kind.CODE,
            detector="python-ast", snippet=snippet[:200], confidence=confidence,
            usage=usage, note=note, **extra,
        ))

    def _match(self, name: str, call: ast.Call) -> None:
        rule = RULES.get(name)
        if rule is not None:
            extra = rule.extract(call) if rule.extract else {}
            self._emit(call, rule.algorithm, usage=rule.usage, **extra)
            return

        if name == "hashlib.new":
            algo = (_str(_arg(call, 0, "name")) or "").lower().replace("-", "")
            if algo in HASHLIB_NEW:
                self._emit(call, HASHLIB_NEW[algo])
            return

        if name in JWT_CALLS:
            node = _kw(call, "algorithm")
            values: list[str] = []
            if (s := _str(node)) is not None:
                values.append(s)
            algs = _kw(call, "algorithms")
            if isinstance(algs, (ast.List, ast.Tuple)):
                values.extend(v for e in algs.elts if (v := _str(e)) is not None)
            for value in values:
                if value in JWT_ALGS:
                    alg, usage = JWT_ALGS[value]
                    self._emit(call, alg, usage=usage, note=f"JWT {value}")
            return

        # AES with a literal key length: algorithms.AES(os.urandom(16))
        if name == f"{CIPHERS}.algorithms.AES":
            self._emit(call, _aes_from_key(call), confidence=0.8)


def _aes_from_key(call: ast.Call) -> str:
    key = _arg(call, 0, "key")
    if isinstance(key, ast.Call) and _dotted(key.func) in {"os.urandom", "secrets.token_bytes"}:
        n = _int(_arg(key, 0))
        if n == 16:
            return "aes-128"
        if n == 32:
            return "aes-256"
    return "aes"


def detect(path: str, text: str) -> Iterator[Finding]:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError:
        return iter(())
    visitor = _Visitor(path, text.splitlines())
    # Imports are collected first so later aliases resolve regardless of order.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            visitor.visit_Import(node)
        elif isinstance(node, ast.ImportFrom):
            visitor.visit_ImportFrom(node)
    visitor.visit(tree)
    return iter(visitor.findings)
