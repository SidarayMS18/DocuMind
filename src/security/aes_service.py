"""
AES-256-GCM Encryption Service
- AES-256 key (32 bytes)
- GCM mode (authenticated encryption — detects tampering)
- Random 96-bit IV per operation
- PBKDF2 key derivation from password
"""

import os
import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# Fixed salt for key derivation (in production, store this securely)
_SALT = b"DocGenAI_AES_Salt_2025"
_ITERATIONS = 100_000


def _derive_key(password: str) -> bytes:
    """Derive a 256-bit AES key from a password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    return kdf.derive(password.encode())


@dataclass
class EncryptionResult:
    success: bool
    ciphertext_b64: str        # base64(iv + ciphertext + tag)
    iv_b64: str                # base64 of IV (for display)
    key_b64: str               # base64 of key (for display)
    algorithm: str = "AES-256-GCM"
    key_size_bits: int = 256
    iv_size_bits: int = 96
    original_size: int = 0
    encrypted_size: int = 0
    error: Optional[str] = None


@dataclass
class DecryptionResult:
    success: bool
    plaintext: str
    error: Optional[str] = None


class AESService:
    """AES-256-GCM encryption/decryption service."""

    def __init__(self, password: Optional[str] = None):
        pwd = password or os.getenv("AES_SECRET_KEY", "DocGenAI-SecureKey-2025")
        self.key = _derive_key(pwd)
        self.key_b64 = base64.b64encode(self.key).decode()
        logger.info("AES-256-GCM service initialized")

    def encrypt_text(self, plaintext: str) -> EncryptionResult:
        """Encrypt a text string using AES-256-GCM."""
        try:
            data = plaintext.encode("utf-8")
            iv = os.urandom(12)          # 96-bit random IV
            aesgcm = AESGCM(self.key)
            ciphertext = aesgcm.encrypt(iv, data, None)  # includes GCM tag

            # Pack: iv (12 bytes) + ciphertext+tag
            packed = iv + ciphertext
            packed_b64 = base64.b64encode(packed).decode()

            return EncryptionResult(
                success=True,
                ciphertext_b64=packed_b64,
                iv_b64=base64.b64encode(iv).decode(),
                key_b64=self.key_b64,
                original_size=len(data),
                encrypted_size=len(packed)
            )
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return EncryptionResult(
                success=False, ciphertext_b64="", iv_b64="",
                key_b64=self.key_b64, error=str(e)
            )

    def decrypt_text(self, ciphertext_b64: str) -> DecryptionResult:
        """Decrypt a base64-encoded AES-256-GCM ciphertext."""
        try:
            packed = base64.b64decode(ciphertext_b64)
            iv = packed[:12]
            ciphertext = packed[12:]
            aesgcm = AESGCM(self.key)
            plaintext = aesgcm.decrypt(iv, ciphertext, None)
            return DecryptionResult(success=True, plaintext=plaintext.decode("utf-8"))
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return DecryptionResult(success=False, plaintext="", error=str(e))

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes — used for file encryption."""
        iv = os.urandom(12)
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(iv, data, None)
        return iv + ciphertext

    def decrypt_bytes(self, data: bytes) -> bytes:
        """Decrypt raw bytes."""
        iv = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(iv, ciphertext, None)

    def get_key_info(self) -> dict:
        return {
            "algorithm": "AES-256-GCM",
            "key_size": "256 bits",
            "mode": "GCM (Galois/Counter Mode)",
            "iv_size": "96 bits (random per operation)",
            "tag_size": "128 bits",
            "key_derivation": "PBKDF2-SHA256",
            "iterations": _ITERATIONS,
            "authenticated": True,
            "key_preview": self.key_b64[:16] + "..."
        }


# Singleton
_aes_instance: Optional[AESService] = None

def get_aes_service() -> AESService:
    global _aes_instance
    if _aes_instance is None:
        _aes_instance = AESService()
    return _aes_instance
