import unittest
import tempfile
from pathlib import Path

from preset_share import (
    MAX_PACK_BYTES,
    export_preset_pack,
    load_preset_pack,
    merge_presets,
    validate_preset_pack,
)


class PresetShareTests(unittest.TestCase):
    def test_export_is_versioned_and_excludes_unknown_fields(self):
        pack = export_preset_pack({
            "我的预设": {
                "instruction": "请改写",
                "prefix": "文本：",
                "icon": "icons/sparkles",
                "api_key": "must-not-export",
            }
        })
        self.assertEqual(pack["format"], "writing-tools-preset-pack")
        self.assertNotIn("api_key", pack["presets"]["我的预设"])
        validated = validate_preset_pack(pack)
        self.assertEqual(validated["我的预设"]["instruction"], "请改写")

    def test_merge_preserves_existing_and_resolves_conflicts(self):
        existing = {"改写": {"instruction": "旧", "hotkey": "ctrl+1"}}
        imported = {"改写": {"instruction": "新", "hotkey": "ctrl+1"}}
        merged, notices = merge_presets(existing, imported, "ctrl+space")
        self.assertEqual(merged["改写"]["instruction"], "旧")
        self.assertIn("改写（导入 2）", merged)
        self.assertNotIn("hotkey", merged["改写（导入 2）"])
        self.assertTrue(notices)

    def test_rejects_oversized_or_malformed_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.json"
            path.write_bytes(b"{" + (b" " * MAX_PACK_BYTES) + b"}")
            with self.assertRaisesRegex(ValueError, "不能超过"):
                load_preset_pack(str(path))

        pack = export_preset_pack({"正常": {"instruction": "测试"}})
        pack["presets"][("x" * 81)] = {"instruction": "测试"}
        with self.assertRaisesRegex(ValueError, "名称"):
            validate_preset_pack(pack)


if __name__ == "__main__":
    unittest.main()
