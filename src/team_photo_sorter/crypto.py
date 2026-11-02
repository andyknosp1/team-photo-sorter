"""Encryption for the static site.

    key   = PBKDF2-HMAC-SHA256(password, salt, ITERATIONS) -> 32 bytes
    file  = iv (12 bytes) || AES-256-GCM(key, iv, plaintext)

The salt is generated once per project and kept in .tps/salt.bin, so the same
password gives the same key on every build. The IV is derived from the file's
path and a hash of its content: rebuilding an unchanged file produces the same
bytes (so static hosts only re-upload what changed), and an IV is only ever
reused with identical plaintext, which reveals nothing beyond "unchanged".
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 600_000   # OWASP 2023 guidance for PBKDF2-HMAC-SHA256


def load_salt(path: Path) -> bytes:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(secrets.token_bytes(16))
    salt = path.read_bytes()
    if len(salt) != 16:
        raise ValueError(f"{path} is not a 16-byte salt")
    return salt


def derive_key(password: str, salt: bytes, iterations: int = ITERATIONS) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=iterations).derive(password.encode())


class Sealer:
    def __init__(self, key: bytes):
        self.key = key
        self.aes = AESGCM(key)

    def iv(self, path: str, plain: bytes) -> bytes:
        return hmac.new(self.key, path.encode() + hashlib.sha256(plain).digest(),
                        "sha256").digest()[:12]

    def seal(self, path: str, plain: bytes) -> bytes:
        iv = self.iv(path, plain)
        return iv + self.aes.encrypt(iv, plain, None)

    def open(self, data: bytes) -> bytes:
        return self.aes.decrypt(data[:12], data[12:], None)

    def token(self, label: str, n: int = 20) -> str:
        """Opaque, stable name derived from the key (hides file and event names)."""
        return hmac.new(self.key, label.encode(), "sha256").hexdigest()[:n]
