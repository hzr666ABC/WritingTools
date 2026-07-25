import unittest
from unittest.mock import patch

from text_application import activate_window, build_diff_html


class FakeUser32:
    def __init__(self, *, foreground=0, minimized=False, activates=True, valid=True):
        self.foreground = foreground
        self.minimized = minimized
        self.activates = activates
        self.valid = valid
        self.show_calls = []
        self.set_calls = []

    def IsWindow(self, handle):
        return self.valid

    def IsIconic(self, handle):
        return self.minimized

    def ShowWindow(self, handle, command):
        self.show_calls.append((handle, command))
        self.minimized = False
        return True

    def GetForegroundWindow(self):
        return self.foreground

    def SetForegroundWindow(self, handle):
        self.set_calls.append(handle)
        if self.activates:
            self.foreground = handle
        return self.activates


class TextApplicationTests(unittest.TestCase):
    def test_diff_marks_changes_and_escapes_html(self):
        output = build_diff_html("你好 <旧>", "你好，新世界 <新>")
        self.assertIn('class="deleted"', output)
        self.assertIn('class="inserted"', output)
        self.assertNotIn("<旧>", output)
        self.assertIn("&lt;", output)

    def test_activation_preserves_visible_fullscreen_or_maximized_window(self):
        user32 = FakeUser32(foreground=100, minimized=False)

        with patch("text_application.os.name", "nt"):
            result = activate_window(200, user32=user32)

        self.assertTrue(result)
        self.assertEqual(user32.show_calls, [])
        self.assertEqual(user32.set_calls, [200])

    def test_activation_restores_only_a_minimized_window(self):
        user32 = FakeUser32(foreground=100, minimized=True)

        with patch("text_application.os.name", "nt"):
            result = activate_window(200, user32=user32)

        self.assertTrue(result)
        self.assertEqual(user32.show_calls, [(200, 9)])

    def test_activation_failure_does_not_claim_focus(self):
        user32 = FakeUser32(foreground=100, minimized=False, activates=False)

        with patch("text_application.os.name", "nt"):
            result = activate_window(
                200,
                user32=user32,
                activation_timeout=0,
            )

        self.assertFalse(result)
        self.assertEqual(user32.show_calls, [])

    def test_invalid_or_destroyed_window_is_never_activated(self):
        user32 = FakeUser32(foreground=100, valid=False)

        with patch("text_application.os.name", "nt"):
            result = activate_window(200, user32=user32)

        self.assertFalse(result)
        self.assertEqual(user32.show_calls, [])
        self.assertEqual(user32.set_calls, [])

    def test_already_focused_window_needs_no_state_change(self):
        user32 = FakeUser32(foreground=200)

        with patch("text_application.os.name", "nt"):
            result = activate_window(200, user32=user32)

        self.assertTrue(result)
        self.assertEqual(user32.show_calls, [])
        self.assertEqual(user32.set_calls, [])

    def test_pointer_width_window_handle_is_not_truncated(self):
        large_handle = 0x1_0000_0200
        user32 = FakeUser32(foreground=100)

        with patch("text_application.os.name", "nt"):
            result = activate_window(large_handle, user32=user32)

        self.assertTrue(result)
        self.assertEqual(user32.set_calls, [large_handle])


if __name__ == "__main__":
    unittest.main()
