import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from WritingToolApp import WritingToolApp


class RuntimeFileLoadingTests(unittest.TestCase):
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
