import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from WritingToolApp import WritingToolApp
from ui.SettingsWindow import SettingsWindow


class _SignalProbe:
    def __init__(self):
        self.count = 0
        self.event = threading.Event()

    def emit(self):
        self.count += 1
        self.event.set()


class _ListenerProbe:
    instances = []

    def __init__(self, hotkey_map):
        self.hotkey_map = dict(hotkey_map)
        self.started = False
        self.stopped = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class _NativeProbe:
    instances = []
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000
    HOTKEY_ID = 0x5754

    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.kwargs = kwargs
        self.error = ""
        self.started = False
        self.stopped = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True
        return True

    def stop(self):
        self.stopped = True


class HotkeyRegistrationTests(unittest.TestCase):
    def setUp(self):
        _ListenerProbe.instances.clear()
        _NativeProbe.instances.clear()

    def test_main_and_prompt_chords_dispatch_only_their_own_signals(self):
        main_signal = _SignalProbe()
        prompt_signal = _SignalProbe()
        app = SimpleNamespace(
            hotkey_listener=None,
            native_main_hotkey=None,
            native_prompt_hotkey=None,
            config={
                "shortcut": "ctrl+space",
                "prompt_workbench": {"shortcut": "ctrl+shift+p"},
            },
            options={},
            paused=False,
            registered_hotkey=None,
            hotkey_triggered_signal=main_signal,
            prompt_hotkey_triggered_signal=prompt_signal,
            _to_pynput_hotkey=WritingToolApp._to_pynput_hotkey,
        )

        with (
            patch("WritingToolApp.pykeyboard.GlobalHotKeys", _ListenerProbe),
            patch("WritingToolApp.WindowsCtrlSpaceHotkey", _NativeProbe),
            patch("WritingToolApp.hotkey_has_extra_modifiers", return_value=False),
            patch("WritingToolApp.hotkey_modifiers_match_exactly", return_value=True),
            patch("WritingToolApp.wait_for_hotkey_modifiers_release", return_value=True),
        ):
            WritingToolApp.start_hotkey_listener(app)
            self.assertEqual(_ListenerProbe.instances, [])

            main_native, prompt_native = _NativeProbe.instances
            self.assertTrue(main_native.started)
            self.assertTrue(prompt_native.started)
            self.assertEqual(prompt_native.kwargs["virtual_key"], ord("P"))

            main_native.callback()
            self.assertTrue(main_signal.event.wait(1.0))
            self.assertEqual(main_signal.count, 1)
            self.assertEqual(prompt_signal.count, 0)

            prompt_native.callback()
            self.assertTrue(prompt_signal.event.wait(1.0))
            self.assertEqual(main_signal.count, 1)
            self.assertEqual(prompt_signal.count, 1)

    def test_main_settings_accept_original_ctrl_space_shortcut(self):
        provider = SimpleNamespace(
            provider_name="OpenAI Compatible (For Experts)",
            settings=[],
            save_config=Mock(),
            load_config=Mock(),
        )
        app = SimpleNamespace(
            config={
                "prompt_workbench": {"shortcut": "ctrl+shift+p"},
                "providers": {},
            },
            options={},
            providers=[provider],
            _to_pynput_hotkey=WritingToolApp._to_pynput_hotkey,
            _ensure_custom_defaults=Mock(),
            register_hotkey=Mock(),
            change_language=Mock(),
            update_tray_menu=Mock(),
        )
        field = lambda value: SimpleNamespace(text=lambda: value, setFocus=Mock())
        checked = lambda value: SimpleNamespace(isChecked=lambda: value)
        window = SimpleNamespace(
            app=app,
            providers_only=False,
            shortcut_input=field("ctrl+space"),
            custom_radio=checked(False),
            gradient_radio=checked(False),
            custom_background_input=field(""),
            remember_checkbox=checked(False),
            safe_apply_checkbox=checked(True),
            history_checkbox=checked(True),
            selected_provider_index=0,
            close=Mock(),
        )

        with patch("ui.SettingsWindow.QtWidgets.QMessageBox.warning") as warning:
            SettingsWindow.save_settings(window)

        warning.assert_not_called()
        self.assertEqual(app.config["shortcut"], "ctrl+space")
        app.register_hotkey.assert_called_once()


if __name__ == "__main__":
    unittest.main()
