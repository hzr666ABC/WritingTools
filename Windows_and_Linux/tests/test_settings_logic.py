import unittest

from settings_logic import (
    find_hotkey_conflict,
    find_named_hotkey_conflict,
    provider_index_by_name,
)


class SettingsLogicTests(unittest.TestCase):
    def test_provider_selection_uses_saved_identity(self):
        names = ["Gemini", "OpenAI", "Ollama"]
        self.assertEqual(provider_index_by_name(names, "OpenAI"), 1)
        self.assertEqual(provider_index_by_name(names, "Missing"), 0)

    def test_global_shortcut_conflict_finds_direct_preset_hotkey(self):
        options = {
            "Rewrite": {"hotkey": "ctrl+j"},
            "Summary": {},
        }
        self.assertEqual(find_hotkey_conflict(options, " CTRL+J "), "Rewrite")
        self.assertIsNone(find_hotkey_conflict(options, "ctrl+k"))

    def test_named_hotkey_conflicts_keep_main_and_prompt_isolated(self):
        options = {"Rewrite": {"hotkey": "ctrl+j"}}
        self.assertEqual(
            find_named_hotkey_conflict(
                "ctrl+space",
                main_shortcut="ctrl+space",
                prompt_shortcut="ctrl+shift+space",
                options=options,
                ignore="prompt",
            ),
            "main",
        )
        self.assertEqual(
            find_named_hotkey_conflict(
                "ctrl+shift+space",
                main_shortcut="ctrl+space",
                prompt_shortcut="ctrl+shift+space",
                options=options,
                ignore="main",
            ),
            "prompt",
        )
        self.assertEqual(
            find_named_hotkey_conflict("ctrl+j", options=options),
            "option:Rewrite",
        )


if __name__ == "__main__":
    unittest.main()
