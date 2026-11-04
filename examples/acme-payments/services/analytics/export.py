"""Nightly analytics export, encrypted at rest."""

import os

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305


def seal(blob: bytes) -> bytes:
    key = ChaCha20Poly1305.generate_key()
    nonce = os.urandom(12)
    return nonce + ChaCha20Poly1305(key).encrypt(nonce, blob, None)
