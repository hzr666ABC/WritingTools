import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from aiprovider import OpenAICompatibleProvider
from WritingToolApp import WritingToolApp


class ProviderRuntimeTests(unittest.TestCase):
    def test_partial_provider_config_cannot_abort_application_startup(self):
        provider = SimpleNamespace(
            before_load=Mock(),
            load_config=Mock(side_effect=ValueError("missing API key")),
            client=object(),
            api_key="",
        )
        app = SimpleNamespace(
            _safe_error_text=lambda error, provider=None: str(error)
        )

        loaded = WritingToolApp._load_provider_config_safely(
            app,
            provider,
            {},
            context="writing",
        )

        self.assertFalse(loaded)
        self.assertIsNone(provider.client)

    def test_prompt_profile_saves_without_touching_main_provider_config(self):
        app = SimpleNamespace(
            config={
                "providers": {
                    "OpenAI Compatible (For Experts)": {"api_key": "main-key"}
                },
                "prompt_providers": {},
            },
            save_config=lambda config: None,
        )
        provider = OpenAICompatibleProvider(app).set_config_namespace("prompt_providers")
        for setting in provider.settings:
            value = {
                "api_key": "prompt-key",
                "api_base": "https://api.openai.com/v1",
                "api_organisation": "",
                "api_project": "",
                "api_model": "gpt-4o-mini",
            }[setting.name]
            setting.get_value = lambda selected=value: selected

        provider.save_config()

        self.assertEqual(
            app.config["providers"]["OpenAI Compatible (For Experts)"]["api_key"],
            "main-key",
        )
        saved = app.config["prompt_providers"]["OpenAI Compatible (For Experts)"]
        self.assertNotEqual(saved["api_key"], "prompt-key")
        self.assertEqual(saved["api_model"], "gpt-4o-mini")

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

    def test_streaming_joins_chunks_and_reports_progress(self):
        provider = self._provider()
        provider.client.chat.completions.create.return_value = iter(
            [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="完"))]
                ),
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="成"))]
                ),
            ]
        )
        progress = Mock()

        response = provider.get_response(
            "system",
            "prompt",
            request_options={"stream": True, "max_tokens": 200},
            progress_callback=progress,
        )

        self.assertEqual(response, "完成")
        self.assertEqual([call.args[0] for call in progress.call_args_list], [1, 2])
        call = provider.client.chat.completions.create.call_args.kwargs
        self.assertTrue(call["stream"])
        self.assertEqual(call["max_tokens"], 200)

    def test_deepseek_fast_strategy_disables_thinking_and_requests_json(self):
        provider = SimpleNamespace(
            api_base="https://api.deepseek.com",
            api_model="deepseek-v4-flash",
        )
        window = SimpleNamespace(generation_strategy="fast")

        options = WritingToolApp._prompt_request_options(window, "compiler", provider)

        self.assertEqual(options["extra_body"]["thinking"]["type"], "disabled")
        self.assertEqual(options["response_format"], {"type": "json_object"})
        self.assertTrue(options["stream"])

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
