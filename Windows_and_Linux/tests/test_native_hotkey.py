import ctypes
import threading
import unittest
from ctypes import wintypes

from native_hotkey import WindowsCtrlSpaceHotkey


class _Kernel32:
    @staticmethod
    def GetCurrentThreadId():
        return 42


class _User32:
    def __init__(self, expected_id, expected_modifiers, expected_key):
        self.messages = 0
        self.unregistered = False
        self.quit = threading.Event()
        self.expected_id = expected_id
        self.expected_modifiers = expected_modifiers
        self.expected_key = expected_key

    def RegisterHotKey(self, hwnd, hotkey_id, modifiers, key):
        del hwnd
        return int(
            hotkey_id == self.expected_id
            and modifiers == self.expected_modifiers
            and key == self.expected_key
        )

    def GetMessageW(self, pointer, hwnd, minimum, maximum):
        del hwnd, minimum, maximum
        if self.messages:
            self.quit.wait(2.0)
            return 0
        message = ctypes.cast(pointer, ctypes.POINTER(wintypes.MSG)).contents
        message.message = WindowsCtrlSpaceHotkey.WM_HOTKEY
        message.wParam = self.expected_id
        self.messages += 1
        return 1

    def UnregisterHotKey(self, hwnd, hotkey_id):
        del hwnd, hotkey_id
        self.unregistered = True
        return 1

    def PostThreadMessageW(self, thread_id, message, wparam, lparam):
        del thread_id, message, wparam, lparam
        self.quit.set()
        return 1


class NativeHotkeyTests(unittest.TestCase):
    def test_native_registration_consumes_ctrl_space_and_dispatches(self):
        fired = threading.Event()
        user32 = _User32(
            WindowsCtrlSpaceHotkey.HOTKEY_ID,
            WindowsCtrlSpaceHotkey.MOD_CONTROL | WindowsCtrlSpaceHotkey.MOD_NOREPEAT,
            WindowsCtrlSpaceHotkey.VK_SPACE,
        )
        listener = WindowsCtrlSpaceHotkey(
            fired.set,
            user32=user32,
            kernel32=_Kernel32(),
        )

        self.assertTrue(listener.start())
        self.assertTrue(fired.wait(1.0))
        listener.stop()
        listener.thread.join(1.0)
        self.assertTrue(user32.unregistered)

    def test_custom_native_registration_dispatches_prompt_shortcut(self):
        fired = threading.Event()
        modifiers = (
            WindowsCtrlSpaceHotkey.MOD_CONTROL
            | WindowsCtrlSpaceHotkey.MOD_SHIFT
            | WindowsCtrlSpaceHotkey.MOD_NOREPEAT
        )
        hotkey_id = WindowsCtrlSpaceHotkey.HOTKEY_ID + 1
        user32 = _User32(hotkey_id, modifiers, ord("P"))
        listener = WindowsCtrlSpaceHotkey(
            fired.set,
            modifiers=modifiers,
            virtual_key=ord("P"),
            hotkey_id=hotkey_id,
            label="Ctrl+Shift+P",
            user32=user32,
            kernel32=_Kernel32(),
        )

        self.assertTrue(listener.start())
        self.assertTrue(fired.wait(1.0))
        listener.stop()
        listener.thread.join(1.0)
        self.assertTrue(user32.unregistered)


if __name__ == "__main__":
    unittest.main()
