import os
import tempfile
import unittest

from history_store import HistoryStore


class HistoryStoreTests(unittest.TestCase):
    def test_encrypted_history_roundtrip_and_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "history.json")
            store = HistoryStore(path, max_entries=10)
            first = store.add_entry(
                option="改写",
                original="这是一段只用于测试的原文。",
                result="这是测试后的新文本。",
                provider="测试服务",
                model="model-a",
            )
            second = store.add_entry(
                option="改写",
                original="这是一段只用于测试的原文。",
                result="这是第二版测试文本。",
            )

            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read()
            self.assertNotIn("这是一段只用于测试的原文。", raw)
            self.assertNotIn("这是测试后的新文本。", raw)
            self.assertEqual(first["version"], 1)
            self.assertEqual(second["version"], 2)
            self.assertEqual(store.list_entries()[0]["result"], "这是第二版测试文本。")

            self.assertTrue(store.update_status(first["id"], "applied"))
            self.assertTrue(store.delete_entry(first["id"]))
            store.clear()
            self.assertEqual(store.list_entries(), [])


if __name__ == "__main__":
    unittest.main()
