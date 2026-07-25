import unittest

from prompting import (
    BASE_CUSTOM_PRESET_INSTRUCTION,
    compose_system_instruction,
    normalize_options,
    option_display_name,
)


class PromptingTests(unittest.TestCase):
    def test_custom_preset_combines_base_rules_and_user_objective(self):
        instruction = compose_system_instruction(
            {
                "instruction": "把文字改成适合小红书发布的语气。",
                "uses_base_instruction": True,
            }
        )

        self.assertIn(BASE_CUSTOM_PRESET_INSTRUCTION, instruction)
        self.assertIn("把文字改成适合小红书发布的语气。", instruction)
        self.assertIn("只输出修改后的最终文本", instruction)

    def test_legacy_custom_icon_automatically_receives_base_rules(self):
        instruction = compose_system_instruction(
            {"instruction": "Make it clearer.", "icon": "icons/custom"}
        )

        self.assertIn(BASE_CUSTOM_PRESET_INSTRUCTION, instruction)
        self.assertIn("Make it clearer.", instruction)

    def test_builtin_instruction_is_not_rewritten(self):
        instruction = "You are a proofreading assistant."
        self.assertEqual(
            compose_system_instruction({"instruction": instruction}),
            instruction,
        )

    def test_normalization_adds_chinese_labels_without_changing_keys(self):
        normalized = normalize_options(
            {
                "Proofread": {"instruction": "proofread"},
                "My Preset": {"instruction": "custom", "icon": "icons/custom"},
            }
        )

        self.assertEqual(option_display_name("Proofread", normalized["Proofread"]), "校对")
        self.assertEqual(option_display_name("My Preset", normalized["My Preset"]), "My Preset")
        self.assertTrue(normalized["My Preset"]["uses_base_instruction"])

    def test_normalization_rejects_invalid_root_and_entries(self):
        self.assertEqual(normalize_options(["not", "an", "object"]), {})
        normalized = normalize_options(
            {
                "": {"instruction": "empty key"},
                "Broken": "not an object",
                "Valid": {
                    "prefix": 123,
                    "instruction": None,
                    "open_in_window": "false",
                    "label": " ",
                },
            }
        )

        self.assertEqual(list(normalized), ["Valid"])
        self.assertEqual(normalized["Valid"]["prefix"], "123")
        self.assertEqual(normalized["Valid"]["instruction"], "")
        self.assertFalse(normalized["Valid"]["open_in_window"])
        self.assertEqual(normalized["Valid"]["label"], "Valid")


if __name__ == "__main__":
    unittest.main()
