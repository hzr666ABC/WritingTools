import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from aiprovider import OpenAICompatibleProvider


class ProviderRuntimeTests(unittest.TestCase):
    def _provider(self):
        provider = OpenAICompatibleProvider(SimpleNamespace())
        provider.api_key = "test-secret-value"
        provider.api_base = "https://api.example.com/v1"
        provider.api_model = "model-a"
        provider.client = Mock()
        return provider

    def test_success_always_returns_text_to_request_coordinator(self):
        provider = self._provider()
        provider.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="  完成  "))]
        )

        response = provider.get_response("system", "prompt")

        self.assertEqual(response, "完成")

    def test_failure_is_redacted_and_raised_for_request_scoped_handling(self):
        provider = self._provider()
        provider.client.chat.completions.create.side_effect = RuntimeError(
            "request failed with test-secret-value"
        )

        with self.assertRaises(RuntimeError) as captured:
            provider.get_response("system", "prompt", return_response=True)

        self.assertNotIn("test-secret-value", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
