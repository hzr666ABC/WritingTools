import tempfile
import unittest
from pathlib import Path

from prompt_library import PromptLibraryStore


class PromptLibraryTests(unittest.TestCase):
    def test_encrypted_searchable_favorite_and_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "prompt_library.json")
            store = PromptLibraryStore(str(path))
            entry = store.save(title="产品评审", prompt="第一版 Prompt", tags=["产品", "评审"], preset_id="product")
            store.save(entry_id=entry["id"], title="产品评审", prompt="第二版 Prompt", tags=["产品", "评审"], preset_id="product")
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("产品评审", raw)
            self.assertNotIn("第二版 Prompt", raw)
            results = store.list("第二版")
            self.assertEqual(len(results), 1)
            self.assertEqual(len(results[0]["versions"]), 2)
            self.assertTrue(store.delete(entry["id"]))
            self.assertEqual(store.list(), [])


if __name__ == "__main__":
    unittest.main()
