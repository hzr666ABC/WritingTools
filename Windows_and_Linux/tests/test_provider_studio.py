import unittest
from types import SimpleNamespace
from unittest.mock import patch

from provider_studio import (
    OPENAI_COMPATIBLE,
    normalize_base_url,
    probe_provider,
    validate_base_url,
)


class ProviderStudioTests(unittest.TestCase):
    def test_normalizes_common_openai_compatible_urls(self):
        self.assertEqual(
            normalize_base_url(OPENAI_COMPATIBLE, " https://api.groq.com "),
            "https://api.groq.com/openai/v1",
        )
        self.assertEqual(
            normalize_base_url(OPENAI_COMPATIBLE, "https://api.openai.com/"),
            "https://api.openai.com/v1",
        )
        self.assertEqual(
            normalize_base_url(OPENAI_COMPATIBLE, "https://openrouter.ai/api/v1"),
            "https://openrouter.ai/api/v1",
        )

    def test_rejects_insecure_remote_or_credential_bearing_urls(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_base_url(OPENAI_COMPATIBLE, "http://api.example.com/v1")
        with self.assertRaisesRegex(ValueError, "用户名或密码"):
            validate_base_url(OPENAI_COMPATIBLE, "https://user:pass@example.com/v1")
        with self.assertRaisesRegex(ValueError, "端口"):
            validate_base_url(OPENAI_COMPATIBLE, "https://example.com:99999/v1")
        self.assertEqual(
            validate_base_url(OPENAI_COMPATIBLE, "http://127.0.0.1:8000/v1"),
            "http://127.0.0.1:8000/v1",
        )

    @patch("provider_studio.OpenAI")
    def test_probe_lists_models_and_checks_configured_model(self, openai_class):
        openai_class.return_value.models.list.return_value = SimpleNamespace(
            data=[SimpleNamespace(id="model-b"), SimpleNamespace(id="model-a")]
        )
        result = probe_provider(
            OPENAI_COMPATIBLE,
            {
                "api_key": "test-only-key",
                "api_base": "https://api.groq.com",
                "api_model": "model-a",
            },
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.models, ["model-a", "model-b"])
        self.assertTrue(result.configured_model_found)
        self.assertEqual(
            result.normalized_values["api_base"],
            "https://api.groq.com/openai/v1",
        )


if __name__ == "__main__":
    unittest.main()
