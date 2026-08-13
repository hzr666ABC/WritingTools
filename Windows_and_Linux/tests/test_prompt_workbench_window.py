import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtGui, QtWidgets
from PySide6.QtTest import QTest

from prompt_preferences import PromptPreferenceStore
from sharpinput_workflow import MAX_TARGET_INPUT_CHARS, WorkflowEvent
from ui.PromptWorkbenchWindow import PromptWorkbenchWindow


class _FakeApp:
    def __init__(self, directory):
        self.config = {
            "theme": "plain",
            "prompt_workbench": {
                "default_depth": "auto",
                "memory_enabled": False,
            },
        }
        self.prompt_preference_store = PromptPreferenceStore(
            os.path.join(directory, "prompt_preferences.json")
        )
        self.dispatched = []
        self.replacements = []
        self.prompt_workbench_window = None

    def prompt_provider_display(self):
        return "测试模型"

    def prompt_provider_is_configured(self):
        return True

    def dispatch_prompt_request(self, window, kind, messages):
        self.dispatched.append((window, kind, messages))

    def show_prompt_settings(self):
        pass

    def cancel_prompt_request(self, window=None):
        if window is not None:
            window.request_id = 0

    def preview_prompt_replacement(self, **values):
        self.replacements.append(values)


class PromptWorkbenchWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _holder(self, text="", handle=123):
        ready = threading.Event()
        ready.set()
        return SimpleNamespace(
            text=text,
            ready=ready,
            source_window_handle=handle,
        )

    def test_opening_with_selection_does_not_dispatch_until_confirmed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            window = PromptWorkbenchWindow(app, self._holder("模糊需求"))
            app.prompt_workbench_window = window
            self.qt_app.processEvents()
            self.assertEqual(window.initial_editor.toPlainText(), "模糊需求")
            self.assertEqual(app.dispatched, [])

            window.start_session()
            self.assertEqual(len(app.dispatched), 1)
            self.assertEqual(app.dispatched[0][1], "compiler")
            self.assertIn("模糊需求", app.dispatched[0][2][-1]["content"])
            window.close()

    def test_empty_capture_opens_a_blank_editable_workbench(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            window = PromptWorkbenchWindow(app, self._holder("", handle=None))
            app.prompt_workbench_window = window
            self.qt_app.processEvents()
            self.assertEqual(window.initial_editor.toPlainText(), "")
            self.assertIn("未读取到选区", window.status_label.text())
            self.assertEqual(app.dispatched, [])
            window.close()

    def test_ime_preedit_hides_placeholder_instead_of_overlapping_it(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            window = PromptWorkbenchWindow(app, self._holder(""))
            hint = window.answer_editor.placeholderText()
            self.assertTrue(hint)

            QtWidgets.QApplication.sendEvent(
                window.answer_editor,
                QtGui.QInputMethodEvent("woshi", []),
            )
            self.assertEqual(window.answer_editor.placeholderText(), "")
            QtWidgets.QApplication.sendEvent(
                window.answer_editor,
                QtGui.QInputMethodEvent("", []),
            )
            self.assertEqual(window.answer_editor.placeholderText(), hint)
            window.close()

    def test_stream_preview_types_user_facing_prompt_incrementally(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            window = PromptWorkbenchWindow(app, self._holder("需求"))
            window.note_generation_progress(
                '{"action":"final","prompt":"逐字显示结果"}'
            )
            self.assertFalse(window.stream_preview.isHidden())
            QTest.qWait(25)
            partial = window.stream_preview.toPlainText()
            self.assertGreaterEqual(len(partial), 1)
            self.assertLess(len(partial), len("逐字显示结果"))
            QTest.qWait(180)
            self.assertEqual(window.stream_preview.toPlainText(), "逐字显示结果")
            window.close()

    def test_oversized_input_is_not_dispatched(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            window = PromptWorkbenchWindow(app, self._holder(""))
            app.prompt_workbench_window = window
            window.initial_editor.setPlainText("需" * (MAX_TARGET_INPUT_CHARS + 1))

            window.start_session()

            self.assertEqual(app.dispatched, [])
            self.assertIn("安全上限", window.status_label.text())
            window.close()

    def test_failed_request_can_retry_without_losing_session(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            window = PromptWorkbenchWindow(app, self._holder("原始需求"))
            app.prompt_workbench_window = window
            window.session = SimpleNamespace(
                stage="compiling",
                compiler_messages=lambda: [{"role": "user", "content": "原始需求"}],
            )
            window.show_error("网络不可用")

            window.retry_request()

            self.assertEqual(app.dispatched[-1][1], "compiler")
            self.assertIn("原始需求", app.dispatched[-1][2][0]["content"])
            window.close()

    def test_final_prompt_is_locally_editable_before_copy(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            window = PromptWorkbenchWindow(app, self._holder("原文"))
            app.prompt_workbench_window = window
            window.session = SimpleNamespace()
            window.show_final(
                WorkflowEvent(
                    "final",
                    level=1,
                    payload={
                        "level": 1,
                        "prompt": "初版 Prompt",
                        "paths": [],
                        "summary": "",
                        "placeholders": [],
                        "tradeoff": "",
                        "judge": {},
                        "understanding": {
                            "goal": "形成可直接使用的 Prompt",
                            "constraints": ["保持中文"],
                            "assumptions": ["用于通用模型"],
                        },
                    },
                )
            )
            window._result_editors[0].setPlainText("手工修改后的 Prompt")
            window.copy_prompt()
            self.assertEqual(
                QtWidgets.QApplication.clipboard().text(), "手工修改后的 Prompt"
            )
            self.assertFalse(window.understanding_panel.isHidden())
            self.assertIn("形成可直接使用的 Prompt", window.understanding_panel.toPlainText())
            window.close()

    def test_replacement_uses_original_window_handle_and_never_auto_applies(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            window = PromptWorkbenchWindow(app, self._holder("原选区", handle=456))
            app.prompt_workbench_window = window
            window.session = SimpleNamespace()
            window.show_final(
                WorkflowEvent(
                    "final",
                    payload={
                        "level": 1,
                        "prompt": "最终 Prompt",
                        "paths": [],
                        "summary": "",
                        "placeholders": [],
                        "tradeoff": "",
                        "judge": {},
                    },
                )
            )
            self.assertEqual(app.replacements, [])
            window.replace_original()
            self.assertEqual(app.replacements[0]["original"], "原选区")
            self.assertEqual(app.replacements[0]["source_window_handle"], 456)
            window.close()

    def test_fallback_requires_confirmation_and_uses_configured_main_provider(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = _FakeApp(directory)
            provider = object()
            app.prompt_fallback_provider = lambda: provider
            app.dispatch_prompt_request = Mock()
            window = PromptWorkbenchWindow(app, self._holder("需求"))
            app.prompt_workbench_window = window
            with patch.object(
                QtWidgets.QMessageBox,
                "question",
                return_value=QtWidgets.QMessageBox.StandardButton.Yes,
            ):
                accepted = window.offer_fallback(
                    "compiler",
                    [{"role": "user", "content": "需求"}],
                    "timeout",
                )

            self.assertTrue(accepted)
            app.dispatch_prompt_request.assert_called_once_with(
                window,
                "compiler",
                [{"role": "user", "content": "需求"}],
                provider_override=provider,
                using_fallback=True,
            )
            window.close()


if __name__ == "__main__":
    unittest.main()
