"""
Symmetric encryption for secrets that have to live in the database — right
now that's OAuth access/refresh tokens on IntegrationCredential. Nothing
outside this module should import `cryptography` directly for that purpose,
so there's exactly one place that knows the key and the algorithm.

Uses Fernet (AES-128-CBC + HMAC-SHA256, from the `cryptography` package,
already a dependency via python-jose[cryptography]) — authenticated
encryption, so a tampered ciphertext fails to decrypt rather than silently
returning garbage.
"""
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.exceptions import JarvisError

# Fixed, obviously-fake key so local dev works with zero setup — the
# startup check below refuses to use it in production.
_DEV_ONLY_FALLBACK_KEY = "gK5s5aM1v1z9od0uW6oT8u3nT2yqf2h4wA6d5c1f0eE="


class EncryptionError(JarvisError):
    status_code = 500
    code = "encryption_error"


@lru_cache
def _fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    if not key:
        if settings.ENVIRONMENT == "production":
            raise EncryptionError(
                "CREDENTIAL_ENCRYPTION_KEY must be set in production — refusing to store "
                "OAuth tokens with a fallback dev key. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        key = _DEV_ONLY_FALLBACK_KEY
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise EncryptionError(f"CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key: {exc}") from exc


def encrypt(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str | None) -> str | None:
    if ciphertext is None:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        # Wrong/rotated key, or the value predates encryption (plaintext
        # already stored) — surface clearly rather than crash the caller
        # with a raw cryptography exception.
        raise EncryptionError("Stored credential could not be decrypted (wrong key, or corrupted).") from exc
