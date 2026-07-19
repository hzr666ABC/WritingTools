import unittest
from pathlib import Path

from preset_icon_library import (
    DEFAULT_PRESET_ICON,
    PRESET_ICON_CHOICES,
    normalize_preset_icon,
)


class PresetIconLibraryTests(unittest.TestCase):
    def test_library_has_unique_ids_and_chinese_labels(self):
        ids = [icon_id for icon_id, _label in PRESET_ICON_CHOICES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 10)
        self.assertTrue(all(label.strip() for _icon_id, label in PRESET_ICON_CHOICES))

    def test_normalization_preserves_supported_icon_and_falls_back(self):
        self.assertEqual(normalize_preset_icon("icons/table"), "icons/table")
        self.assertEqual(normalize_preset_icon("icons/unknown"), DEFAULT_PRESET_ICON)
        self.assertEqual(normalize_preset_icon(None), DEFAULT_PRESET_ICON)

    def test_every_library_icon_has_light_and_dark_assets(self):
        project_root = Path(__file__).resolve().parents[1]
        for icon_id, _label in PRESET_ICON_CHOICES:
            for theme in ("light", "dark"):
                asset = project_root / f"{icon_id}_{theme}.png"
                self.assertTrue(asset.is_file(), asset)


if __name__ == "__main__":
    unittest.main()
