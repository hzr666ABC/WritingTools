import json
import os
import tempfile
import unittest

from prompt_preferences import PromptPreferenceStore


class PromptPreferenceStoreTests(unittest.TestCase):
    def test_disabled_store_neither_reads_nor_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "prompt_preferences.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not json")
            store = PromptPreferenceStore(path)
            self.assertEqual(store.load(enabled=False), {})
            self.assertFalse(store.save({"role": "产品经理"}, enabled=False))
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "not json")

    def test_roundtrip_is_encrypted_and_allow_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "prompt_preferences.json")
            store = PromptPreferenceStore(path)
            self.assertTrue(
                store.save(
                    {
                        "role": "产品经理",
                        "domain": "SaaS",
                        "raw_input": "绝不能保存的原始对话",
                    },
                    enabled=True,
                )
            )
            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read()
            envelope = json.loads(raw)
            self.assertIn("payload", envelope)
            self.assertNotIn("产品经理", raw)
            self.assertNotIn("绝不能保存", raw)
            self.assertEqual(
                store.load(enabled=True),
                {"role": "产品经理", "domain": "SaaS"},
            )

    def test_clear_removes_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "prompt_preferences.json")
            store = PromptPreferenceStore(path)
            store.save({"tech_stack": "Python"}, enabled=True)
            self.assertTrue(store.has_data())
            self.assertTrue(store.clear())
            self.assertFalse(store.has_data())
            self.assertEqual(store.load(enabled=True), {})

    def test_corrupt_or_oversized_file_falls_back_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "prompt_preferences.json")
            store = PromptPreferenceStore(path)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{")
            self.assertEqual(store.load(enabled=True), {})
            with open(path, "wb") as handle:
                handle.write(b"x" * (store.MAX_FILE_BYTES + 1))
            self.assertEqual(store.load(enabled=True), {})


if __name__ == "__main__":
    unittest.main()
