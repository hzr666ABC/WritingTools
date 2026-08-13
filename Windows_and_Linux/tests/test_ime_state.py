import unittest
from unittest.mock import patch

import ime_state


class ImeStateTests(unittest.TestCase):
    def test_non_windows_capture_and_restore_are_safe_noops(self):
        with patch("ime_state.os.name", "posix"):
            self.assertIsNone(ime_state.capture_ime_state(123))
            self.assertFalse(ime_state.restore_ime_state({"open": True}, 123))

    def test_missing_window_is_safe(self):
        self.assertIsNone(ime_state.capture_ime_state(None))
        self.assertFalse(ime_state.restore_ime_state(None, None))


if __name__ == "__main__":
    unittest.main()
