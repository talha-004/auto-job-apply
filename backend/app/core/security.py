"""
Enterprise Security, Credential Encryption, and Sensitive Data Sanitization.
Provides authenticated symmetric encryption (AES-128-CBC + HMAC-SHA256 via Fernet),
key derivation from environment or local persistent keystore, and PII/secret scrubbing.
"""

import os
import re
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

# Prefix used to distinguish encrypted secrets in configuration or files
ENCRYPTED_PREFIX = "enc:"
DEFAULT_SALT = b"autoapply-enterprise-sec-salt-2026"


class SecurityManager:
    """Manages symmetric credential encryption, decryption, and text sanitization."""

    def __init__(self, custom_key: Optional[str] = None):
        self._key: bytes = self._resolve_or_create_key(custom_key or settings.ENCRYPTION_KEY)
        self._fernet: Fernet = Fernet(self._key)

    def _resolve_or_create_key(self, provided_key: Optional[str] = None) -> bytes:
        """Derive or load a 32-byte urlsafe base64 key."""
        if provided_key:
            clean_key = provided_key.strip()
            # If already valid 44-char urlsafe base64
            try:
                decoded = base64.urlsafe_b64decode(clean_key.encode("utf-8"))
                if len(decoded) == 32:
                    return clean_key.encode("utf-8")
            except Exception:
                pass

            # Otherwise derive via PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=DEFAULT_SALT,
                iterations=100_000,
            )
            derived = kdf.derive(clean_key.encode("utf-8"))
            return base64.urlsafe_b64encode(derived)

        # Fallback to persistent keyfile in DATA_DIR
        key_file = settings.DATA_PATH / ".secret.key"
        if key_file.exists():
            try:
                stored = key_file.read_bytes().strip()
                if len(stored) == 44:
                    return stored
            except Exception:
                pass

        # Generate new random key and persist
        new_key = Fernet.generate_key()
        try:
            key_file.write_bytes(new_key)
            # Restrict permissions on POSIX systems if applicable
            if hasattr(os, "chmod"):
                try:
                    os.chmod(key_file, 0o600)
                except Exception:
                    pass
        except Exception:
            pass

        return new_key

    def encrypt_value(self, plaintext: str) -> str:
        """Encrypt plaintext string into an 'enc:' prefixed ciphertext."""
        if not plaintext:
            return ""
        if plaintext.startswith(ENCRYPTED_PREFIX):
            return plaintext  # Already encrypted
        token = self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        return f"{ENCRYPTED_PREFIX}{token}"

    def decrypt_value(self, ciphertext: str) -> str:
        """Decrypt ciphertext string. Returns original text if not encrypted."""
        if not ciphertext:
            return ""
        raw = ciphertext[len(ENCRYPTED_PREFIX):] if ciphertext.startswith(ENCRYPTED_PREFIX) else ciphertext
        try:
            return self._fernet.decrypt(raw.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # If not an encrypted token or corrupted, return as-is
            return ciphertext

    def is_encrypted(self, value: str) -> bool:
        """Check if a string represents an encrypted value."""
        if not isinstance(value, str):
            return False
        if value.startswith(ENCRYPTED_PREFIX):
            return True
        try:
            self._fernet.decrypt(value.encode("utf-8"))
            return True
        except Exception:
            return False

    def encrypt_dict(
        self,
        data: Dict[str, Any],
        sensitive_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Encrypt values for specific sensitive keys in a dictionary."""
        target_keys = set(sensitive_keys or [
            "password", "api_key", "secret", "token", "smtp_password",
            "imap_password", "linkedin_password", "naukri_password", "indeed_password"
        ])
        result = {}
        for k, v in data.items():
            if isinstance(v, str) and (k.lower() in target_keys or any(sk in k.lower() for sk in ["password", "secret", "api_key"])):
                result[k] = self.encrypt_value(v)
            elif isinstance(v, dict):
                result[k] = self.encrypt_dict(v, sensitive_keys)
            else:
                result[k] = v
        return result

    def decrypt_dict(
        self,
        data: Dict[str, Any],
        sensitive_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Decrypt values for specific sensitive keys in a dictionary."""
        result = {}
        for k, v in data.items():
            if isinstance(v, str) and self.is_encrypted(v):
                result[k] = self.decrypt_value(v)
            elif isinstance(v, dict):
                result[k] = self.decrypt_dict(v, sensitive_keys)
            else:
                result[k] = v
        return result

    @staticmethod
    def mask_email(email_str: str) -> str:
        """Mask email address (e.g. j***e@domain.com)."""
        if not email_str or "@" not in email_str:
            return email_str
        user, domain = email_str.split("@", 1)
        if len(user) <= 2:
            masked_user = user[0] + "*"
        else:
            masked_user = user[0] + ("*" * (len(user) - 2)) + user[-1]
        return f"{masked_user}@{domain}"

    @staticmethod
    def mask_phone(phone_str: str) -> str:
        """Mask phone number preserving leading country code and last 3 digits."""
        if not phone_str:
            return phone_str
        clean = re.sub(r"[^\d+]", "", phone_str)
        if len(clean) <= 4:
            return "****"
        return clean[:3] + ("*" * (len(clean) - 6)) + clean[-3:]

    @staticmethod
    def mask_secret(secret_str: str, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
        """Mask API key or secret token."""
        if not secret_str:
            return ""
        if len(secret_str) <= (visible_prefix + visible_suffix):
            return "********"
        return f"{secret_str[:visible_prefix]}...{secret_str[-visible_suffix:]}"

    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Redact sensitive tokens, passwords, cookies, Bearer credentials,
        and common LLM API keys from text or log messages.
        """
        if not isinstance(text, str) or not text:
            return text

        sanitized = text

        # 1. Bearer / Basic Auth headers
        sanitized = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", r"\1[REDACTED_TOKEN]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"(Basic\s+)[A-Za-z0-9+/=]{15,}", r"\1[REDACTED_CREDENTIALS]", sanitized, flags=re.IGNORECASE)

        # 2. URLs with embedded basic auth (e.g., http://user:pass@host)
        sanitized = re.sub(r"(https?://[^:]+:)([^@]+)(@)", r"\1*****\3", sanitized)

        # 3. Known API Key formats (OpenAI, Groq, GitHub, Anthropic)
        sanitized = re.sub(r"sk-[a-zA-Z0-9_\-]{20,}", "[REDACTED_OPENAI_KEY]", sanitized)
        sanitized = re.sub(r"gsk_[a-zA-Z0-9_\-]{20,}", "[REDACTED_GROQ_KEY]", sanitized)
        sanitized = re.sub(r"ghp_[a-zA-Z0-9]{30,}", "[REDACTED_GITHUB_TOKEN]", sanitized)

        # 4. JSON / key-value sensitive parameters (password, api_key, secret, token, li_at)
        sanitized = re.sub(
            r'("(?:password|secret|api_key|token|auth_token|li_at)":\s*")[^"]+(")',
            r'\1[REDACTED]\2',
            sanitized,
            flags=re.IGNORECASE
        )
        sanitized = re.sub(
            r"((?:password|secret|api_key|token|li_at)=)[^&\s]+",
            r"\1[REDACTED]",
            sanitized,
            flags=re.IGNORECASE
        )

        return sanitized


security_manager = SecurityManager()
