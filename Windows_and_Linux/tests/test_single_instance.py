import os
import unittest
import uuid

from single_instance import SingleInstanceGuard


@unittest.skipUnless(os.name == "nt", "Windows named handles are required")
class SingleInstanceGuardTests(unittest.TestCase):
    def test_second_guard_detects_running_instance_and_signals_first(self):
        name = f"WritingToolsCN.Test.{uuid.uuid4()}"
        with SingleInstanceGuard(name) as first:
            self.assertFalse(first.already_running)
            with SingleInstanceGuard(name) as second:
                self.assertTrue(second.already_running)
                second.notify_existing()
                self.assertTrue(first.consume_activation_request())
                self.assertFalse(first.consume_activation_request())


if __name__ == "__main__":
    unittest.main()
