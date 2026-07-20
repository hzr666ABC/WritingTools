import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets
from PySide6.QtTest import QTest

from ui.ShortcutRecorder import ShortcutRecorder, normalize_shortcut_text


class ShortcutRecorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_normalization_accepts_qt_and_legacy_spellings(self):
        self.assertEqual(normalize_shortcut_text("Ctrl+Shift+P"), "ctrl+shift+p")
        self.assertEqual(normalize_shortcut_text("Control + Space"), "ctrl+space")
        self.assertEqual(normalize_shortcut_text("Meta+Return"), "win+enter")

    def test_records_pressed_combination(self):
        recorder = ShortcutRecorder("ctrl+space")
        recorder.show()
        recorder.setFocus()
        QTest.keyClick(
            recorder,
            QtCore.Qt.Key.Key_P,
            QtCore.Qt.KeyboardModifier.ControlModifier
            | QtCore.Qt.KeyboardModifier.ShiftModifier,
        )
        self.assertEqual(recorder.text(), "ctrl+shift+p")
        QTest.keyClick(
            recorder,
            QtCore.Qt.Key.Key_Space,
            QtCore.Qt.KeyboardModifier.ControlModifier,
        )
        self.assertEqual(recorder.text(), "ctrl+space")
        recorder.close()

    def test_backspace_clears_and_escape_preserves(self):
        recorder = ShortcutRecorder("ctrl+j")
        recorder.show()
        recorder.setFocus()
        QTest.keyClick(recorder, QtCore.Qt.Key.Key_Escape)
        self.assertEqual(recorder.text(), "ctrl+j")
        recorder.setFocus()
        QTest.keyClick(recorder, QtCore.Qt.Key.Key_Backspace)
        self.assertEqual(recorder.text(), "")
        recorder.close()


if __name__ == "__main__":
    unittest.main()
