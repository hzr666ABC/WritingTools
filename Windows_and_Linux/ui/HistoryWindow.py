"""Encrypted generation history and version browser."""

from __future__ import annotations

from datetime import datetime

from PySide6 import QtCore, QtWidgets

from text_application import build_diff_html
from ui.UIUtils import UIUtils, colorMode


class HistoryWindow(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.entries = []
        self.current_entry = None
        self.setWindowTitle("历史与版本")
        self.setMinimumSize(900, 580)
        self.resize(1040, 680)
        self._build_ui()
        self.reload()

    def _build_ui(self):
        UIUtils.setup_window_and_layout(self)
        root = QtWidgets.QVBoxLayout(self.background)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)
        title = QtWidgets.QLabel("历史与版本")
        title.setStyleSheet(
            f"font-size:24px;font-weight:700;color:{'#f3f5ff' if colorMode == 'dark' else '#202638'};"
        )
        root.addWidget(title)
        note = QtWidgets.QLabel("正文使用本机安全密钥加密；最多保存最近 100 条，可随时清空。")
        note.setStyleSheet(
            f"font-size:12px;color:{'#aeb5ce' if colorMode == 'dark' else '#747c91'};"
        )
        root.addWidget(note)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setMinimumWidth(285)
        self.list_widget.currentRowChanged.connect(self._select_row)
        splitter.addWidget(self.list_widget)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(12, 0, 0, 0)
        self.meta_label = QtWidgets.QLabel("选择一条历史记录")
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet("font-size:13px;font-weight:600;")
        right_layout.addWidget(self.meta_label)
        self.tabs = QtWidgets.QTabWidget()
        self.diff_view = QtWidgets.QTextBrowser()
        self.original_view = QtWidgets.QPlainTextEdit()
        self.result_view = QtWidgets.QPlainTextEdit()
        for widget in (self.original_view, self.result_view):
            widget.setReadOnly(True)
        self.tabs.addTab(self.diff_view, "差异")
        self.tabs.addTab(self.original_view, "原文")
        self.tabs.addTab(self.result_view, "结果")
        right_layout.addWidget(self.tabs, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        actions = QtWidgets.QHBoxLayout()
        for text, handler in (
            ("复制结果", self.copy_result),
            ("应用此版本", self.apply_result),
            ("恢复原文", self.restore_original),
            ("导出 Markdown", self.export_markdown),
            ("删除此条", self.delete_current),
        ):
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        clear_button = QtWidgets.QPushButton("清空历史")
        clear_button.clicked.connect(self.clear_history)
        actions.addWidget(clear_button)
        root.addLayout(actions)

    def reload(self):
        self.entries = self.app.history_store.list_entries()
        self.list_widget.clear()
        for entry in self.entries:
            timestamp = entry.get("created_at", "")
            try:
                display_time = datetime.fromisoformat(timestamp).astimezone().strftime("%m-%d %H:%M")
            except ValueError:
                display_time = timestamp[:16]
            item = QtWidgets.QListWidgetItem(
                f"{entry.get('option', '写作')} · 版本 {entry.get('version', 1)}\n"
                f"{display_time} · {entry.get('status', 'preview')}"
            )
            item.setToolTip(entry.get("result", "")[:240])
            self.list_widget.addItem(item)
        if self.entries:
            self.list_widget.setCurrentRow(0)
        else:
            self.current_entry = None
            self.meta_label.setText("还没有历史记录")
            self.diff_view.clear()
            self.original_view.clear()
            self.result_view.clear()

    def _select_row(self, row: int):
        if not 0 <= row < len(self.entries):
            return
        entry = self.entries[row]
        self.current_entry = entry
        self.meta_label.setText(
            f"{entry.get('option', '写作')} · 版本 {entry.get('version', 1)} · "
            f"{entry.get('provider', '')} · {entry.get('model', '')}"
        )
        self.original_view.setPlainText(entry.get("original", ""))
        self.result_view.setPlainText(entry.get("result", ""))
        self.diff_view.setHtml(build_diff_html(
            entry.get("original", ""), entry.get("result", ""), colorMode == "dark"
        ))

    def copy_result(self):
        if self.current_entry:
            QtWidgets.QApplication.clipboard().setText(self.current_entry.get("result", ""))

    def _apply(self, key: str, status: str):
        if not self.current_entry:
            return
        self.hide()
        self.app.apply_text_to_source(self.current_entry.get(key, ""))
        self.app.history_store.update_status(self.current_entry["id"], status)
        QtCore.QTimer.singleShot(320, self.show)
        self.reload()

    def apply_result(self):
        self._apply("result", "applied")

    def restore_original(self):
        self._apply("original", "restored")

    def export_markdown(self):
        if not self.current_entry:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出历史记录", "writing-tools-history.md", "Markdown (*.md)"
        )
        if not path:
            return
        entry = self.current_entry
        content = (
            f"# {entry.get('option', '写作')} · 版本 {entry.get('version', 1)}\n\n"
            f"## 原文\n\n{entry.get('original', '')}\n\n"
            f"## 修改结果\n\n{entry.get('result', '')}\n"
        )
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def delete_current(self):
        if self.current_entry and self.app.history_store.delete_entry(self.current_entry["id"]):
            self.reload()

    def clear_history(self):
        answer = QtWidgets.QMessageBox.question(
            self, "清空历史", "确定清空全部加密历史记录吗？此操作无法撤销。"
        )
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self.app.history_store.clear()
            self.reload()


__all__ = ["HistoryWindow"]
