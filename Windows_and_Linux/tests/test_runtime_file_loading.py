import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from WritingToolApp import WritingToolApp


class RuntimeFileLoadingTests(unittest.TestCase):
    def test_v11_migration_adds_empty_prompt_profile_without_copying_main_key(self):
        main_key = "dpapi:main-only"
        config = {
            "providers": {
                "OpenAI Compatible (For Experts)": {"api_key": main_key}
            },
            "is_config_file_updated_for_v8": True,
            "is_config_file_updated_for_v9": True,
            "is_config_file_updated_for_v10": True,
        }
        app = SimpleNamespace(config=config, save_config=lambda value: None)
        WritingToolApp._migrate_config(app)
        self.assertEqual(config["prompt_providers"], {})
        self.assertEqual(
            config["providers"]["OpenAI Compatible (For Experts)"]["api_key"],
            main_key,
        )
        self.assertFalse(config["prompt_workbench"]["memory_enabled"])
        self.assertEqual(config["prompt_workbench"]["shortcut"], "ctrl+shift+p")
        self.assertTrue(config["is_config_file_updated_for_v11"])
        self.assertTrue(config["is_config_file_updated_for_v12"])
        self.assertTrue(config["is_config_file_updated_for_v13"])
        self.assertTrue(config["is_config_file_updated_for_v14"])

    def test_v12_migration_moves_conflicting_prompt_default(self):
        config = {
            "prompt_workbench": {"shortcut": "ctrl+shift+space"},
            "is_config_file_updated_for_v8": True,
            "is_config_file_updated_for_v9": True,
            "is_config_file_updated_for_v10": True,
            "is_config_file_updated_for_v11": True,
        }
        app = SimpleNamespace(config=config, save_config=lambda value: None)

        WritingToolApp._migrate_config(app)

        self.assertEqual(config["prompt_workbench"]["shortcut"], "ctrl+shift+p")
        self.assertTrue(config["is_config_file_updated_for_v12"])

    def test_v11_migration_repairs_invalid_prompt_container_types(self):
        config = {
            "prompt_workbench": ["invalid"],
            "prompt_providers": "invalid",
            "is_config_file_updated_for_v8": True,
            "is_config_file_updated_for_v9": True,
            "is_config_file_updated_for_v10": True,
        }
        app = SimpleNamespace(config=config, save_config=lambda value: None)

        WritingToolApp._migrate_config(app)

        self.assertIsInstance(config["prompt_workbench"], dict)
        self.assertEqual(config["prompt_providers"], {})

    def test_v13_and_v14_keep_fast_model_and_restore_original_shortcut(self):
        config = {
            "shortcut": "ctrl+space",
            "providers": {
                "OpenAI Compatible (For Experts)": {
                    "api_base": "https://api.groq.com/openai/v1",
                    "api_model": "openai/gpt-oss-120b",
                }
            },
            "prompt_workbench": {},
        }
        for version in range(8, 13):
            config[f"is_config_file_updated_for_v{version}"] = True
        app = SimpleNamespace(config=config, save_config=lambda value: None)

        WritingToolApp._migrate_config(app)

        self.assertEqual(config["shortcut"], "ctrl+space")
        self.assertEqual(
            config["providers"]["OpenAI Compatible (For Experts)"]["api_model"],
            "openai/gpt-oss-20b",
        )
        self.assertEqual(config["prompt_workbench"]["default_scene"], "smart")
        self.assertTrue(config["prompt_workbench"]["fallback_enabled"])
        self.assertTrue(config["is_config_file_updated_for_v13"])
        self.assertTrue(config["is_config_file_updated_for_v14"])

    def test_v14_restores_deployed_alt_shortcut_to_ctrl_space(self):
        config = {
            "shortcut": "ctrl+alt+space",
            **{f"is_config_file_updated_for_v{n}": True for n in range(8, 14)},
        }
        app = SimpleNamespace(config=config, save_config=lambda value: None)

        WritingToolApp._migrate_config(app)

        self.assertEqual(config["shortcut"], "ctrl+space")
        self.assertTrue(config["is_config_file_updated_for_v14"])

    def _runtime(self, directory):
        return str(Path(directory) / "Writing Tools CN.exe")

    def test_malformed_config_falls_back_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "config.json").write_text("{broken", encoding="utf-8")
            app = SimpleNamespace(config=None, config_path=None)

            with patch("WritingToolApp.sys.argv", [self._runtime(directory)]):
                WritingToolApp.load_config(app)

            self.assertIsNone(app.config)

    def test_non_object_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "config.json").write_text("[]", encoding="utf-8")
            app = SimpleNamespace(config=None, config_path=None)

            with patch("WritingToolApp.sys.argv", [self._runtime(directory)]):
                WritingToolApp.load_config(app)

            self.assertIsNone(app.config)

    def test_malformed_options_falls_back_and_reports_error(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "options.json").write_text("{broken", encoding="utf-8")
            error_signal = Mock()
            app = SimpleNamespace(
                options=None,
                options_path=None,
                show_message_signal=SimpleNamespace(emit=error_signal),
            )

            with patch("WritingToolApp.sys.argv", [self._runtime(directory)]):
                WritingToolApp.load_options(app)

            self.assertEqual(app.options, {})
            error_signal.assert_called_once()

    def test_valid_options_are_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "options.json").write_text(
                json.dumps(
                    {
                        "Rewrite": {
                            "instruction": "改写",
                            "open_in_window": False,
                        },
                        "Broken": "invalid",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            app = SimpleNamespace(
                options=None,
                options_path=None,
                show_message_signal=SimpleNamespace(emit=Mock()),
            )

            with patch("WritingToolApp.sys.argv", [self._runtime(directory)]):
                WritingToolApp.load_options(app)

            self.assertEqual(list(app.options), ["Rewrite"])
            self.assertEqual(app.options["Rewrite"]["label"], "改写")


if __name__ == "__main__":
    unittest.main()
