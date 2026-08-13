import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from ui.VisualSystem import (
    ActivityIndicator,
    MotionController,
    animations_enabled,
    button_style,
    global_stylesheet,
    palette,
)


def _relative_luminance(hex_color):
    values = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in values
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first, second):
    bright, dark = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (bright + 0.05) / (dark + 0.05)


class VisualSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_light_small_text_color_has_readable_contrast(self):
        colors = palette("light")
        self.assertGreaterEqual(_contrast(colors["muted"], colors["canvas"]), 4.5)
        self.assertGreaterEqual(_contrast(colors["text_soft"], colors["surface"]), 4.5)

    def test_styles_include_keyboard_focus_and_shared_control_states(self):
        self.assertIn("QPushButton:focus", button_style("light"))
        stylesheet = global_stylesheet("dark")
        self.assertIn("QLineEdit:focus", stylesheet)
        self.assertIn("QTabBar::tab:selected", stylesheet)
        self.assertIn("QScrollBar::handle:vertical", stylesheet)

    def test_disable_animation_switch_is_deterministic(self):
        with patch.dict(os.environ, {"WRITINGTOOLS_DISABLE_ANIMATIONS": "1"}):
            self.assertFalse(animations_enabled())

    def test_stack_transition_and_activity_states_keep_function_without_motion(self):
        owner = QtWidgets.QWidget()
        stack = QtWidgets.QStackedWidget(owner)
        stack.addWidget(QtWidgets.QWidget())
        stack.addWidget(QtWidgets.QWidget())
        motion = MotionController(owner)
        with patch.dict(os.environ, {"WRITINGTOOLS_DISABLE_ANIMATIONS": "1"}):
            motion.transition(stack, 1)
        self.assertEqual(stack.currentIndex(), 1)

        indicator = ActivityIndicator("light")
        for state in ("busy", "success", "error", "idle"):
            indicator.set_state(state)
            self.assertEqual(indicator.state, state)
        indicator.timer.stop()


if __name__ == "__main__":
    unittest.main()
