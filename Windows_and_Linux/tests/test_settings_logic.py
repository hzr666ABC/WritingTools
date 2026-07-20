import unittest

from settings_logic import find_hotkey_conflict, provider_index_by_name


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


if __name__ == "__main__":
    unittest.main()
