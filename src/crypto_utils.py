from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC_HEADER = b"OKAPIENC1"


def _b64decode_maybe(data: str) -> bytes:
    try:
        return base64.b64decode(data)
    except Exception:
        return bytes.fromhex(data)


@dataclass
class EnvelopeKey:
    key_id: str
    salt: bytes


def derive_data_key(master_key: bytes, salt: bytes) -> bytes:
    label = b"okapi-conversation"
    digest = hashlib.sha256(master_key + salt + label).digest()
    return digest


def encrypt_json_bytes(
    plaintext: bytes, master_key_str: str | None
) -> tuple[bytes, EnvelopeKey | None]:
    if not master_key_str:
        return plaintext, None

    master_key = _b64decode_maybe(master_key_str)
    if len(master_key) < 32:
        master_key = hashlib.sha256(master_key).digest()

    salt = os.urandom(16)
    data_key = derive_data_key(master_key, salt)

    aesgcm = AESGCM(data_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # envelope: MAGIC || salt (16) || nonce (12) || ciphertext
    result = MAGIC_HEADER + salt + nonce + ciphertext
    key_id = hashlib.sha256(master_key).hexdigest()[:16]
    return result, EnvelopeKey(key_id=key_id, salt=salt)


def decrypt_json_bytes(ciphertext: bytes, master_key_str: str | None) -> bytes:
    # If payload doesn't start with our header, return as-is for backward compatibility
    if not ciphertext.startswith(MAGIC_HEADER):
        return ciphertext

    if not master_key_str:
        raise ValueError("DATA_ENCRYPTION_KEY not set but encrypted payload detected")

    if len(ciphertext) < len(MAGIC_HEADER) + 28:
        raise ValueError("ciphertext too short")

    salt = ciphertext[len(MAGIC_HEADER) : len(MAGIC_HEADER) + 16]
    nonce = ciphertext[len(MAGIC_HEADER) + 16 : len(MAGIC_HEADER) + 28]
    payload = ciphertext[len(MAGIC_HEADER) + 28 :]

    master_key = _b64decode_maybe(master_key_str)
    if len(master_key) < 32:
        master_key = hashlib.sha256(master_key).digest()

    data_key = derive_data_key(master_key, salt)
    aesgcm = AESGCM(data_key)
    return aesgcm.decrypt(nonce, payload, None)
