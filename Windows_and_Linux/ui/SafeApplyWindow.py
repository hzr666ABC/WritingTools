"""Preview, compare, apply, undo, and restore generated text safely."""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

from text_application import build_diff_html
from ui.UIUtils import UIUtils, colorMode


class SafeApplyWindow(QtWidgets.QWidget):
    def __init__(self, app, entry: dict):
        super().__init__()
        self.app = app
        self.entry = entry
        self.original = entry.get("original", "")
        self.result = entry.get("result", "")
        self.current_text = self.original
        self.previous_text = self.original
        self.setWindowTitle("安全应用 · 对比修改")
        self.setMinimumSize(760, 540)
        self.resize(880, 660)
        self._build_ui()

    @staticmethod
    def _button_style(primary=False, danger=False):
        if primary:
            background, hover, foreground = "#5b69e9", "#4d5bd7", "white"
        elif danger:
            background, hover, foreground = (
                ("#4a2f37", "#5b3843", "#ffdfe5") if colorMode == "dark"
                else ("#fff2f4", "#ffe4e9", "#a52c42")
            )
        else:
            background, hover, foreground = (
                ("#303541", "#3b4150", "#edf0ff") if colorMode == "dark"
                else ("#f7f8fc", "#eceffd", "#42485a")
            )
        return f"""
            QPushButton {{ min-height: 38px; padding: 3px 15px; border: none;
                border-radius: 10px; background: {background}; color: {foreground};
                font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ background: {hover}; }}
            QPushButton:disabled {{ background: #d8dbe6; color: #9298a8; }}
        """

    def _build_ui(self):
        UIUtils.setup_window_and_layout(self)
        layout = QtWidgets.QVBoxLayout(self.background)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(13)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("确认 AI 修改")
        title.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {'#f4f6ff' if colorMode == 'dark' else '#202638'};"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        version = QtWidgets.QLabel(
            f"{self.entry.get('option', '写作')} · 版本 {self.entry.get('version', 1)}"
        )
        version.setStyleSheet(
            f"color: {'#aeb5ce' if colorMode == 'dark' else '#747c91'}; font-size: 12px;"
        )
        title_row.addWidget(version)
        layout.addLayout(title_row)

        helper = QtWidgets.QLabel("先查看变化，再决定应用。关闭窗口不会修改原文。")
        helper.setStyleSheet(
            f"color: {'#aeb5ce' if colorMode == 'dark' else '#687087'}; font-size: 13px;"
        )
        layout.addWidget(helper)

        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {'#4a5060' if colorMode == 'dark' else '#dfe2eb'};
                border-radius: 11px; background: {'#242833' if colorMode == 'dark' else '#ffffff'}; }}
            QTabBar::tab {{ padding: 8px 18px; color: {'#cfd4e8' if colorMode == 'dark' else '#596075'}; }}
            QTabBar::tab:selected {{ color: #5b69e9; font-weight: 650; }}
        """)
        diff_view = QtWidgets.QTextBrowser()
        diff_view.setOpenExternalLinks(False)
        diff_view.setHtml(build_diff_html(self.original, self.result, colorMode == "dark"))
        tabs.addTab(diff_view, "差异")
        for label, text in (("原文", self.original), ("修改结果", self.result)):
            editor = QtWidgets.QPlainTextEdit(text)
            editor.setReadOnly(True)
            editor.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
            editor.setStyleSheet(
                f"border:none;padding:12px;font-size:14px;line-height:1.6;background:{'#242833' if colorMode == 'dark' else 'white'};color:{'#f0f2ff' if colorMode == 'dark' else '#202638'};"
            )
            tabs.addTab(editor, label)
        layout.addWidget(tabs, 1)

        self.status_label = QtWidgets.QLabel("尚未应用")
        self.status_label.setStyleSheet(
            f"color: {'#aeb5ce' if colorMode == 'dark' else '#687087'}; font-size: 12px;"
        )
        layout.addWidget(self.status_label)

        actions = QtWidgets.QHBoxLayout()
        copy_button = QtWidgets.QPushButton("复制结果")
        copy_button.setStyleSheet(self._button_style())
        copy_button.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(self.result)
        )
        actions.addWidget(copy_button)

        history_button = QtWidgets.QPushButton("打开历史")
        history_button.setStyleSheet(self._button_style())
        history_button.clicked.connect(self.app.show_history)
        actions.addWidget(history_button)
        actions.addStretch()

        self.restore_button = QtWidgets.QPushButton("恢复原文")
        self.restore_button.setStyleSheet(self._button_style(danger=True))
        self.restore_button.clicked.connect(self.restore_original)
        actions.addWidget(self.restore_button)

        self.undo_button = QtWidgets.QPushButton("撤销")
        self.undo_button.setStyleSheet(self._button_style())
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.undo_last_apply)
        actions.addWidget(self.undo_button)

        self.apply_button = QtWidgets.QPushButton("应用修改")
        self.apply_button.setStyleSheet(self._button_style(primary=True))
        self.apply_button.clicked.connect(self.apply_result)
        actions.addWidget(self.apply_button)
        layout.addLayout(actions)

    def _apply(self, text: str, status: str, message: str):
        prior = self.current_text
        self.hide()
        success = self.app.apply_text_to_source(text)
        if success:
            self.previous_text = prior
            self.current_text = text
            if self.entry.get("id"):
                try:
                    self.app.history_store.update_status(self.entry["id"], status)
                except Exception as error:
                    # Applying text is the primary action. A locked/unavailable
                    # history file must not turn a successful paste into a
                    # failed operation.
                    logging.error(f"Unable to update history status: {error}")
            self.status_label.setText(message)
            self.undo_button.setEnabled(self.previous_text != self.current_text)
            self.apply_button.setEnabled(self.current_text != self.result)
        else:
            self.status_label.setText("无法激活原窗口，结果已复制到剪贴板。")
        QtCore.QTimer.singleShot(320, self._show_after_apply)

    def _show_after_apply(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def apply_result(self):
        self._apply(self.result, "applied", "修改已经应用；可立即撤销或恢复原文。")

    def restore_original(self):
        self._apply(self.original, "restored", "已经恢复到最初原文。")

    def undo_last_apply(self):
        target = self.previous_text
        status = "undone" if target == self.original else "applied"
        self._apply(target, status, "已撤销上一次应用；再次点击可在两个版本间切换。")


__all__ = ["SafeApplyWindow"]
