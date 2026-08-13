import tempfile
import unittest
from pathlib import Path

from prompt_presets import BUILTIN_PRESETS, PromptPresetStore, preset_variables, render_preset_input


class PromptPresetTests(unittest.TestCase):
    def test_builtin_catalog_is_complete_and_unique(self):
        self.assertEqual(len(BUILTIN_PRESETS), 9)
        self.assertEqual(len({item.preset_id for item in BUILTIN_PRESETS}), 9)
        self.assertEqual(BUILTIN_PRESETS[0].preset_id, "smart")

    def test_custom_template_variables_render_and_remain_visible_when_blank(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "prompt_presets.json")
            store = PromptPresetStore(str(path))
            preset = store.save(name="短视频脚本", description="视频", instruction="补齐平台和受众", template="平台：[平台]\n受众：[受众]")
            self.assertEqual(preset_variables(preset), ("平台", "受众"))
            rendered = render_preset_input(preset, "做一个脚本", {"平台": "抖音"})
            self.assertIn("平台：抖音", rendered)
            self.assertIn("受众：[受众]", rendered)
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("短视频脚本", raw)
            self.assertEqual(store.list_custom()[0].name, "短视频脚本")

    def test_custom_preset_update_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PromptPresetStore(str(Path(directory, "presets.json")))
            first = store.save(name="场景", instruction="规则")
            updated = store.save(preset_id=first.preset_id, name="更新场景", instruction="更新规则")
            self.assertEqual(len(store.list_custom()), 1)
            self.assertEqual(updated.name, "更新场景")
            self.assertTrue(store.delete(first.preset_id))
            self.assertEqual(store.list_custom(), [])


if __name__ == "__main__":
    unittest.main()
