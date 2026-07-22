import unittest

from hotkey_guard import (
    hotkey_modifiers_are_physically_active,
    modifier_is_physically_down,
    send_modified_key,
)


class _FakeController:
    def __init__(self, fail_on_press=None):
        self.events = []
        self.fail_on_press = fail_on_press

    def press(self, key):
        self.events.append(("press", key))
        if key == self.fail_on_press:
            raise RuntimeError("simulated press failure")

    def release(self, key):
        self.events.append(("release", key))


class HotkeyGuardTests(unittest.TestCase):
    @staticmethod
    def _reader(*pressed_keys):
        pressed = set(pressed_keys)
        return lambda virtual_key: 0x8000 if virtual_key in pressed else 0

    def test_plain_space_cannot_satisfy_stale_ctrl_space(self):
        self.assertFalse(
            hotkey_modifiers_are_physically_active(
                "ctrl+space",
                platform_name="nt",
                state_reader=self._reader(),
            )
        )
        self.assertTrue(
            hotkey_modifiers_are_physically_active(
                "ctrl+space",
                platform_name="nt",
                state_reader=self._reader(0x11),
            )
        )

    def test_modifier_aliases_and_windows_keys_are_supported(self):
        self.assertTrue(
            hotkey_modifiers_are_physically_active(
                "control+shift+p",
                platform_name="nt",
                state_reader=self._reader(0x11, 0x10),
            )
        )
        self.assertTrue(
            hotkey_modifiers_are_physically_active(
                "win+enter",
                platform_name="nt",
                state_reader=self._reader(0x5C),
            )
        )

    def test_non_windows_and_unmodified_hotkeys_fail_open(self):
        self.assertTrue(
            hotkey_modifiers_are_physically_active(
                "ctrl+space", platform_name="posix", state_reader=self._reader()
            )
        )
        self.assertTrue(
            hotkey_modifiers_are_physically_active(
                "space", platform_name="nt", state_reader=self._reader()
            )
        )

    def test_modifier_probe_reports_real_windows_state(self):
        self.assertTrue(
            modifier_is_physically_down(
                "ctrl", platform_name="nt", state_reader=self._reader(0x11)
            )
        )
        self.assertFalse(
            modifier_is_physically_down(
                "ctrl", platform_name="nt", state_reader=self._reader()
            )
        )

    def test_modified_key_does_not_release_a_user_held_modifier(self):
        controller = _FakeController()
        send_modified_key(
            controller, "ctrl", "c", modifier_already_down=True
        )
        self.assertEqual(
            controller.events,
            [("press", "c"), ("release", "c")],
        )

    def test_injected_modifier_is_released_after_success_or_failure(self):
        controller = _FakeController()
        send_modified_key(controller, "ctrl", "c")
        self.assertEqual(
            controller.events,
            [
                ("press", "ctrl"),
                ("press", "c"),
                ("release", "c"),
                ("release", "ctrl"),
            ],
        )

        failing = _FakeController(fail_on_press="c")
        with self.assertRaises(RuntimeError):
            send_modified_key(failing, "ctrl", "c")
        self.assertEqual(
            failing.events,
            [
                ("press", "ctrl"),
                ("press", "c"),
                ("release", "ctrl"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
