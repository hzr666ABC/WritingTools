import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets

from ui.ResponseWindow import ResponseWindow


class FakeResponseApp(QtCore.QObject):
    followup_response_signal = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.config = {"response_window_zoom": 1.35}
        self.current_response_window = None

    def save_config(self, config):
        self.config = config

    def process_followup_question(self, window, question):
        pass


class ResponseWindowRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_followup_response_reaches_only_its_own_window(self):
        app = FakeResponseApp()
        first = ResponseWindow(app, "第一个结果")
        second = ResponseWindow(app, "第二个结果")
        first.chat_history = [{"role": "user", "content": "问题一"}]
        second.chat_history = [{"role": "user", "content": "问题二"}]

        app.followup_response_signal.emit(
            {"window": first, "response": "只属于第一个窗口"}
        )
        self.qt_app.processEvents()

        self.assertEqual(first.chat_history[-1]["content"], "只属于第一个窗口")
        self.assertEqual(second.chat_history, [{"role": "user", "content": "问题二"}])
        first.close()
        second.close()

    def test_closing_old_window_does_not_clear_new_current_window(self):
        app = FakeResponseApp()
        old_window = ResponseWindow(app, "旧结果")
        new_window = ResponseWindow(app, "新结果")
        app.current_response_window = new_window

        old_window.close()
        self.qt_app.processEvents()

        self.assertIs(app.current_response_window, new_window)
        new_window.close()

    def test_saved_zoom_is_applied_to_initial_response(self):
        app = FakeResponseApp()
        window = ResponseWindow(app, "结果")
        window.selected_text = "原文"

        window.set_text("回答")

        self.assertAlmostEqual(window.current_text_display.zoom_factor, 1.35)
        window.close()


if __name__ == "__main__":
    unittest.main()
