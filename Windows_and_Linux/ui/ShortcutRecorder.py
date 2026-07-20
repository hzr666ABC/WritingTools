"""Click-to-record shortcut input used across setup and settings screens."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


_TOKEN_ALIASES = {
    "control": "ctrl",
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "meta": "win",
    "win": "win",
    "windows": "win",
    "space": "space",
    "return": "enter",
    "enter": "enter",
    "esc": "esc",
    "escape": "esc",
    "del": "delete",
    "delete": "delete",
    "ins": "insert",
    "pgup": "page_up",
    "pgdown": "page_down",
}


def normalize_shortcut_text(value):
    """Normalize Qt/legacy shortcut text to the app's lowercase format."""

    if not value:
        return ""
    tokens = []
    for raw_token in str(value).replace(" ", "").split("+"):
        if not raw_token:
            continue
        lowered = raw_token.casefold()
        tokens.append(_TOKEN_ALIASES.get(lowered, lowered))
    return "+".join(tokens)


class ShortcutRecorder(QtWidgets.QLineEdit):
    """A read-only line edit that records the next pressed key combination."""

    shortcut_recorded = QtCore.Signal(str)

    _MODIFIER_KEYS = {
        QtCore.Qt.Key.Key_Control,
        QtCore.Qt.Key.Key_Shift,
        QtCore.Qt.Key.Key_Alt,
        QtCore.Qt.Key.Key_Meta,
    }

    def __init__(self, shortcut="", parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setText(normalize_shortcut_text(shortcut))
        self.setPlaceholderText("点击后直接按下组合键")
        self.setToolTip("点击后按下新的快捷键；Backspace/Delete 清除，Esc 取消")
        self.setAccessibleName("快捷键录制框")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            event.accept()
            return

        key = event.key()
        modifiers = event.modifiers()
        if key in self._MODIFIER_KEYS:
            event.accept()
            return
        if key == QtCore.Qt.Key.Key_Escape and modifiers == QtCore.Qt.KeyboardModifier.NoModifier:
            self.clearFocus()
            event.accept()
            return
        if key in (QtCore.Qt.Key.Key_Backspace, QtCore.Qt.Key.Key_Delete) and modifiers == QtCore.Qt.KeyboardModifier.NoModifier:
            self.clear()
            self.shortcut_recorded.emit("")
            event.accept()
            return

        portable = QtGui.QKeySequence(event.keyCombination()).toString(
            QtGui.QKeySequence.SequenceFormat.PortableText
        )
        shortcut = normalize_shortcut_text(portable)
        if shortcut:
            self.setText(shortcut)
            self.selectAll()
            self.shortcut_recorded.emit(shortcut)
        event.accept()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selectAll()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()
