"""Envelope encryption for connector secrets (AT-IDENTITY_POLICY-004, design D10).

Each secret gets its own random 256-bit DEK (AES-GCM). The DEK is wrapped by a KEK from a KeyProvider:
`LocalKeyProvider` (base64 key from ARCHTWIN_KEK, dev) or an OpenBao/Vault Transit provider (prod, same interface).
Primitives come from `cryptography`; only the envelope wiring is ours.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from archtwin.config import settings


class KeyProvider(Protocol):
    kek_id: str

    def wrap(self, dek: bytes) -> tuple[bytes, bytes]: ...
    def unwrap(self, wrapped: bytes, nonce: bytes) -> bytes: ...


class LocalKeyProvider:
    def __init__(self, kek_b64: str, kek_id: str) -> None:
        key = base64.b64decode(kek_b64) if kek_b64 else b""
        if len(key) != 32:
            raise RuntimeError("ARCHTWIN_KEK must be a base64-encoded 32-byte key")
        self._aead, self.kek_id = AESGCM(key), kek_id

    def wrap(self, dek: bytes) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        return self._aead.encrypt(nonce, dek, self.kek_id.encode()), nonce

    def unwrap(self, wrapped: bytes, nonce: bytes) -> bytes:
        return self._aead.decrypt(nonce, wrapped, self.kek_id.encode())


@dataclass(frozen=True)
class Envelope:
    kek_id: str
    wrapped_dek: bytes
    dek_nonce: bytes
    nonce: bytes
    ciphertext: bytes


_provider: KeyProvider | None = None


def provider() -> KeyProvider:
    global _provider
    if _provider is None:
        _provider = LocalKeyProvider(settings().kek, settings().kek_id)
    return _provider


def seal(payload: dict, aad: str, kp: KeyProvider | None = None) -> Envelope:
    kp = kp or provider()
    dek = AESGCM.generate_key(bit_length=256)
    wrapped, dek_nonce = kp.wrap(dek)
    nonce = os.urandom(12)
    ct = AESGCM(dek).encrypt(nonce, json.dumps(payload).encode(), aad.encode())
    return Envelope(kp.kek_id, wrapped, dek_nonce, nonce, ct)


def open_envelope(env: Envelope, aad: str, kp: KeyProvider | None = None) -> dict:
    kp = kp or provider()
    if env.kek_id != kp.kek_id:
        raise RuntimeError(f"secret sealed with KEK {env.kek_id}, provider has {kp.kek_id}")
    dek = kp.unwrap(env.wrapped_dek, env.dek_nonce)
    return json.loads(AESGCM(dek).decrypt(env.nonce, env.ciphertext, aad.encode()))
