"""Windows-bound secret protection with backwards-compatible migration."""

from __future__ import annotations

import base64
import copy
import ctypes
import os
import re
import stat
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DPAPI_PREFIX = "dpapi:"
LOCAL_VAULT_PREFIX = "vault-v1:"
LEGACY_PREFIX = "enc:"
_LEGACY_XOR_KEY = 0x5A
_LOCAL_VAULT_AAD = b"WritingTools:local-vault:v1"


class SecretStorageError(RuntimeError):
    """Raised when protected data cannot be encrypted or decrypted."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob_from_bytes(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _dpapi(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise SecretStorageError("DPAPI is only available on Windows")

    input_blob, input_buffer = _blob_from_bytes(data)
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    function_name = "CryptProtectData" if protect else "CryptUnprotectData"
    function = getattr(crypt32, function_name)
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    description = "Writing Tools local vault" if protect else None
    result = function(
        ctypes.byref(input_blob),
        description,
        None,
        None,
        None,
        0x01,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(output_blob),
    )
    del input_buffer
    if not result:
        raise SecretStorageError(str(ctypes.WinError()))
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def _local_vault_key_path() -> Path:
    override = os.environ.get("WRITINGTOOLS_VAULT_KEY_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return base / "writing-tools" / "vault.key"


def _load_local_vault_key() -> bytes:
    """Load or create an owner-only Linux/macOS master key."""
    path = _local_vault_key_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            path.parent.chmod(0o700)
        except OSError:
            pass
        if path.is_symlink():
            raise SecretStorageError("Local vault key must not be a symbolic link")

    create_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        create_flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        create_flags |= os.O_BINARY
    try:
        descriptor = os.open(path, create_flags, 0o600)
    except FileExistsError:
        descriptor = None
    if descriptor is not None:
        try:
            key = AESGCM.generate_key(bit_length=256)
            os.write(descriptor, key)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise SecretStorageError("Local vault key path is not a regular file")
        if os.name != "nt" and hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise SecretStorageError("Local vault key is owned by another user")
        if os.name != "nt" and info.st_mode & 0o077:
            path.chmod(0o600)
        key = path.read_bytes()
    except OSError as error:
        raise SecretStorageError(f"Unable to access local vault key: {error}") from error
    if len(key) != 32:
        raise SecretStorageError("Local vault key has an invalid length")
    return key


def _local_protect(data: bytes) -> bytes:
    nonce = os.urandom(12)
    encrypted = AESGCM(_load_local_vault_key()).encrypt(nonce, data, _LOCAL_VAULT_AAD)
    return nonce + encrypted


def _local_unprotect(data: bytes) -> bytes:
    if len(data) < 29:
        raise SecretStorageError("Local vault payload is truncated")
    try:
        return AESGCM(_load_local_vault_key()).decrypt(
            data[:12], data[12:], _LOCAL_VAULT_AAD
        )
    except Exception as error:
        raise SecretStorageError("Local vault payload failed authentication") from error


def _legacy_protect(value: str) -> str:
    payload = bytes(byte ^ _LEGACY_XOR_KEY for byte in value.encode("utf-8"))
    return LEGACY_PREFIX + base64.b64encode(payload).decode("ascii")


def _legacy_unprotect(value: str) -> str:
    payload = base64.b64decode(value[len(LEGACY_PREFIX):])
    return bytes(byte ^ _LEGACY_XOR_KEY for byte in payload).decode("utf-8")


def protect_secret(value: str | None) -> str:
    """Protect plaintext for the current OS user; preserve empty values."""
    value = str(value or "")
    if not value:
        return ""
    if value.startswith(DPAPI_PREFIX):
        return value
    if value.startswith(LOCAL_VAULT_PREFIX):
        return value
    if value.startswith(LEGACY_PREFIX):
        value = _legacy_unprotect(value)
    if os.name == "nt":
        encrypted = _dpapi(value.encode("utf-8"), protect=True)
        return DPAPI_PREFIX + base64.b64encode(encrypted).decode("ascii")
    encrypted = _local_protect(value.encode("utf-8"))
    return LOCAL_VAULT_PREFIX + base64.b64encode(encrypted).decode("ascii")


def unprotect_secret(value: str | None) -> str:
    """Return plaintext from DPAPI, legacy XOR, or already-plain input."""
    value = str(value or "")
    if not value:
        return ""
    if value.startswith(DPAPI_PREFIX):
        encrypted = base64.b64decode(value[len(DPAPI_PREFIX):])
        return _dpapi(encrypted, protect=False).decode("utf-8")
    if value.startswith(LOCAL_VAULT_PREFIX):
        encrypted = base64.b64decode(value[len(LOCAL_VAULT_PREFIX):], validate=True)
        return _local_unprotect(encrypted).decode("utf-8")
    if value.startswith(LEGACY_PREFIX):
        return _legacy_unprotect(value)
    return value


def is_protected(value: str | None) -> bool:
    value = str(value or "")
    return value.startswith((DPAPI_PREFIX, LOCAL_VAULT_PREFIX, LEGACY_PREFIX))


def redact_text(text: str, secrets: list[str] | None = None) -> str:
    """Remove common API-key shapes and any explicitly supplied secrets."""
    redacted = str(text or "")
    for secret in secrets or []:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    redacted = re.sub(
        r"\b(?:gsk|sk|AIza|hf)_[A-Za-z0-9._-]{12,}\b|\bAIza[A-Za-z0-9_-]{20,}\b",
        "<redacted>",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\b[A-Z]:\\Users\\[^\\\s]+|/(?:home|Users)/[^/\s]+",
        "<user-home>",
        redacted,
    )
    return redacted


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "<redacted-url>"
    if not parsed.scheme or not parsed.netloc:
        return redact_text(value)
    try:
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
    except ValueError:
        return "<redacted-url>"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def redacted_config(config: dict) -> dict:
    """Deep-copy a config and replace every secret-like field."""
    output = copy.deepcopy(config or {})

    def clean(value):
        if isinstance(value, dict):
            for key in list(value):
                lowered = key.lower()
                if any(part in lowered for part in ("key", "token", "secret", "password")):
                    value[key] = "<redacted>" if value[key] else ""
                elif "path" in lowered or "directory" in lowered:
                    value[key] = "<redacted-path>" if value[key] else ""
                elif lowered in ("api_base", "base_url", "url") and isinstance(value[key], str):
                    value[key] = _redact_url(value[key])
                else:
                    value[key] = clean(value[key])
            return value
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, str):
            return redact_text(value)
        return value

    clean(output)
    return output
