import json
import unittest
from pathlib import Path


class DefaultOptionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.options_path = Path(__file__).resolve().parents[1] / "options.json"
        cls.raw = cls.options_path.read_text(encoding="utf-8")
        cls.options = json.loads(cls.raw)

    def test_curated_preset_order(self):
        self.assertEqual(
            list(self.options),
            [
                "Custom",
                "Agent 任务描述改写",
                "Rewrite",
                "正式消息改写",
                "问题排查描述",
                "Obsidian 学习笔记",
                "Obsidian 公式助手",
                "Concise",
                "Summary",
            ],
        )

    def test_removed_overlapping_presets_do_not_return(self):
        self.assertTrue(
            {"Proofread", "Friendly", "Professional", "Key Points", "Table"}.isdisjoint(
                self.options
            )
        )

    def test_every_preset_has_valid_ui_metadata_and_prompt(self):
        icons_dir = self.options_path.parent / "icons"
        for key, option in self.options.items():
            with self.subTest(preset=key):
                self.assertTrue(option["label"].strip())
                self.assertTrue(option["instruction"].strip())
                self.assertIsInstance(option["open_in_window"], bool)
                icon_name = option["icon"].removeprefix("icons/")
                self.assertTrue((icons_dir / f"{icon_name}_light.png").is_file())
                self.assertTrue((icons_dir / f"{icon_name}_dark.png").is_file())

    def test_chinese_is_utf8_and_contains_no_common_mojibake(self):
        self.assertIn("问题排查描述", self.raw)
        self.assertIn("Obsidian 学习笔记", self.raw)
        for marker in (
            chr(0xFFFD),
            chr(0x9225),
            chr(0x951F),
            chr(0x6D63),
            chr(0x00C3),
        ):
            self.assertNotIn(marker, self.raw)


if __name__ == "__main__":
    unittest.main()
