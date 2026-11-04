"""Card tokenisation: card numbers are encrypted to the vault's public key."""

import hashlib

import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def new_vault_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def seal_card(public_key, pan: str) -> bytes:
    return public_key.encrypt(
        pan.encode(),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )


def settlement_token(private_key, batch_id: str) -> str:
    return jwt.encode({"batch": batch_id}, private_key, algorithm="RS256")


def idempotency_key(payload: bytes) -> str:
    # Legacy: kept for compatibility with the 2019 settlement API.
    return hashlib.md5(payload).hexdigest()
