import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from WritingToolApp import WritingToolApp, _SelectedTextHolder


class TextApplyWorkflowTests(unittest.TestCase):
    def _app(self, source_window_handle=200):
        return SimpleNamespace(source_window_handle=source_window_handle)

    @patch("WritingToolApp.time.sleep")
    @patch("WritingToolApp.send_modified_key")
    @patch("WritingToolApp.pykeyboard.Controller")
    @patch("WritingToolApp.activate_window", return_value=True)
    @patch("WritingToolApp.pyperclip")
    def test_success_restores_previous_clipboard(
        self,
        clipboard,
        activate,
        controller,
        send_key,
        sleep,
    ):
        clipboard.paste.return_value = "之前的剪贴板"

        result = WritingToolApp.apply_text_to_source(self._app(), "改写结果")

        self.assertTrue(result)
        self.assertEqual(clipboard.copy.call_args_list[0].args, ("改写结果",))
        self.assertEqual(clipboard.copy.call_args_list[-1].args, ("之前的剪贴板",))
        activate.assert_called_once_with(200)
        send_key.assert_called_once()
        sleep.assert_called_once_with(0.12)

    @patch("WritingToolApp.send_modified_key")
    @patch("WritingToolApp.pykeyboard.Controller")
    @patch("WritingToolApp.activate_window", return_value=False)
    @patch("WritingToolApp.pyperclip")
    def test_activation_failure_keeps_result_without_pasting(
        self,
        clipboard,
        activate,
        controller,
        send_key,
    ):
        clipboard.paste.return_value = "之前的剪贴板"

        result = WritingToolApp.apply_text_to_source(self._app(), "改写结果")

        self.assertFalse(result)
        clipboard.copy.assert_called_once_with("改写结果")
        controller.assert_not_called()
        send_key.assert_not_called()

    @patch("WritingToolApp.send_modified_key", side_effect=RuntimeError("paste failed"))
    @patch("WritingToolApp.pykeyboard.Controller")
    @patch("WritingToolApp.activate_window", return_value=True)
    @patch("WritingToolApp.pyperclip")
    def test_paste_failure_retains_generated_text(
        self,
        clipboard,
        activate,
        controller,
        send_key,
    ):
        clipboard.paste.return_value = "之前的剪贴板"

        result = WritingToolApp.apply_text_to_source(self._app(), "改写结果")

        self.assertFalse(result)
        self.assertEqual(
            [call.args[0] for call in clipboard.copy.call_args_list],
            ["改写结果", "改写结果"],
        )

    @patch("WritingToolApp.activate_window", side_effect=OSError("window disappeared"))
    @patch("WritingToolApp.pyperclip")
    def test_destroyed_window_is_a_safe_clipboard_fallback(self, clipboard, activate):
        clipboard.paste.return_value = "之前的剪贴板"

        result = WritingToolApp.apply_text_to_source(self._app(), "改写结果")

        self.assertFalse(result)
        clipboard.copy.assert_called_once_with("改写结果")

    @patch("WritingToolApp.pyperclip")
    def test_clipboard_write_failure_does_not_raise(self, clipboard):
        clipboard.paste.return_value = "之前的剪贴板"
        clipboard.copy.side_effect = OSError("clipboard busy")

        result = WritingToolApp.apply_text_to_source(self._app(), "改写结果")

        self.assertFalse(result)


class SelectionCaptureWorkflowTests(unittest.TestCase):
    def _harness(self):
        return SimpleNamespace(
            _capture_lock=threading.Lock(),
            clear_clipboard=lambda: True,
        )

    @patch("WritingToolApp.threading.Thread")
    @patch("WritingToolApp.send_modified_key")
    @patch("WritingToolApp.pykeyboard.Controller")
    @patch("WritingToolApp.pyperclip")
    def test_second_capture_is_rejected_before_clipboard_mutation(
        self,
        clipboard,
        controller,
        send_key,
        thread_class,
    ):
        clipboard.paste.return_value = "之前的剪贴板"
        thread_class.return_value.start.return_value = None
        app = self._harness()

        first = WritingToolApp._fire_ctrl_c_and_capture_async(
            app,
            _SelectedTextHolder(),
        )
        second = WritingToolApp._fire_ctrl_c_and_capture_async(
            app,
            _SelectedTextHolder(),
        )

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(send_key.call_count, 1)
        self.assertEqual(clipboard.paste.call_count, 1)

    @patch("WritingToolApp.send_modified_key", side_effect=RuntimeError("copy failed"))
    @patch("WritingToolApp.pykeyboard.Controller")
    @patch("WritingToolApp.pyperclip")
    def test_copy_injection_failure_releases_capture_lock(
        self,
        clipboard,
        controller,
        send_key,
    ):
        clipboard.paste.return_value = "之前的剪贴板"
        app = self._harness()
        holder = _SelectedTextHolder()

        result = WritingToolApp._fire_ctrl_c_and_capture_async(app, holder)

        self.assertFalse(result)
        self.assertTrue(holder.ready.is_set())
        self.assertFalse(app._capture_lock.locked())
        clipboard.copy.assert_called_with("之前的剪贴板")


if __name__ == "__main__":
    unittest.main()
