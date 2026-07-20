import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from secure_storage import (
    LOCAL_VAULT_PREFIX,
    SecretStorageError,
    _local_protect,
    _local_unprotect,
    is_protected,
    protect_secret,
    redacted_config,
    redact_text,
    unprotect_secret,
)


class SecureStorageTests(unittest.TestCase):
    def test_unicode_secret_roundtrip(self):
        secret = "中文密钥-测试-123"
        protected = protect_secret(secret)
        self.assertTrue(is_protected(protected))
        self.assertNotIn(secret, protected)
        self.assertEqual(unprotect_secret(protected), secret)
        if os.name == "nt":
            self.assertTrue(protected.startswith("dpapi:"))
        else:
            self.assertTrue(protected.startswith(LOCAL_VAULT_PREFIX))

    def test_reads_legacy_xor_value_for_migration(self):
        secret = "legacy-secret"
        payload = bytes(byte ^ 0x5A for byte in secret.encode("utf-8"))
        legacy = "enc:" + base64.b64encode(payload).decode("ascii")
        self.assertEqual(unprotect_secret(legacy), secret)
        self.assertTrue(
            protect_secret(legacy).startswith(
                "dpapi:" if os.name == "nt" else LOCAL_VAULT_PREFIX
            )
        )

    def test_redaction_removes_nested_secrets(self):
        config = {
            "custom_background_path": r"C:\Users\someone\private.png",
            "providers": {
                "demo": {
                    "api_key": "secret",
                    "api_base": "https://user:password@example.com/v1?token=secret",
                    "model": "model-a",
                }
            },
        }
        safe = redacted_config(config)
        self.assertEqual(safe["providers"]["demo"]["api_key"], "<redacted>")
        self.assertEqual(safe["providers"]["demo"]["model"], "model-a")
        self.assertEqual(safe["custom_background_path"], "<redacted-path>")
        self.assertEqual(safe["providers"]["demo"]["api_base"], "https://example.com/v1")
        simulated_key = "gsk" + "_" + ("x" * 24)
        self.assertNotIn(simulated_key, redact_text(simulated_key))
        self.assertNotIn("someone", redact_text(r"C:\Users\someone\private.png"))

    def test_local_vault_encrypts_and_authenticates(self):
        with tempfile.TemporaryDirectory() as directory:
            key_path = Path(directory) / "vault.key"
            with patch.dict(
                os.environ,
                {"WRITINGTOOLS_VAULT_KEY_PATH": str(key_path)},
                clear=False,
            ):
                encrypted = _local_protect("本地安全存储".encode("utf-8"))
                self.assertNotIn("本地安全存储".encode("utf-8"), encrypted)
                self.assertEqual(_local_unprotect(encrypted).decode("utf-8"), "本地安全存储")
                tampered = bytearray(encrypted)
                tampered[-1] ^= 1
                with self.assertRaises(SecretStorageError):
                    _local_unprotect(bytes(tampered))
                self.assertEqual(len(key_path.read_bytes()), 32)


if __name__ == "__main__":
    unittest.main()
