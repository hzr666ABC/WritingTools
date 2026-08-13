"""Searchable encrypted Prompt favorites and their local versions."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ui.UIUtils import UIUtils, colorMode
from ui.VisualSystem import (
    button_style,
    editor_style,
    install_button_motion,
    install_focus_glow,
    palette,
)


class PromptLibraryWindow(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.entries = []
        self._build_ui()
        self.refresh()

    @staticmethod
    def _button_style(primary=False, danger=False):
        return button_style(colorMode, primary=primary, danger=danger)

    def _build_ui(self):
        self.setWindowTitle("Prompt 收藏库")
        self.resize(900, 620)
        self.setMinimumSize(720, 480)
        UIUtils.setup_window_and_layout(self)
        root = QtWidgets.QVBoxLayout(self.background)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        title = QtWidgets.QLabel("Prompt 收藏库")
        title.setStyleSheet(
            f"font-size:24px;font-weight:700;letter-spacing:.2px;color:{palette(colorMode)['text']};"
        )
        root.addWidget(title)
        subtitle = QtWidgets.QLabel("仅保存你主动收藏的最终 Prompt；内容使用本机加密，并保留最近 20 个版本。")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color:{palette(colorMode)['text_soft']};font-size:12px;"
        )
        root.addWidget(subtitle)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("搜索标题、标签或 Prompt 内容…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.search.setMinimumHeight(42)
        install_focus_glow(self.search, colorMode)
        root.addWidget(self.search)

        splitter = QtWidgets.QSplitter()
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setMinimumWidth(240)
        self.list_widget.currentRowChanged.connect(self._show_entry)
        p = palette(colorMode)
        self.list_widget.setStyleSheet(f"""
            QListWidget{{border:1px solid {p['border']};border-radius:13px;
                padding:7px;background:{p['surface']};outline:none;}}
            QListWidget::item{{padding:11px;border-radius:9px;color:{p['text_soft']};}}
            QListWidget::item:hover{{background:{p['surface_alt']};}}
            QListWidget::item:selected{{background:{p['accent_soft']};color:{p['accent_text']};font-weight:600;}}
        """)
        splitter.addWidget(self.list_widget)

        detail = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(detail)
        detail_layout.setContentsMargins(14, 0, 0, 0)
        self.entry_title = QtWidgets.QLabel("选择一个收藏")
        self.entry_title.setStyleSheet("font-size:18px;font-weight:650;")
        detail_layout.addWidget(self.entry_title)
        self.version_combo = QtWidgets.QComboBox()
        self.version_combo.currentIndexChanged.connect(self._show_version)
        detail_layout.addWidget(self.version_combo)
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(editor_style(colorMode, prominent=True))
        detail_layout.addWidget(self.preview, 1)
        row = QtWidgets.QHBoxLayout()
        self.delete_button = QtWidgets.QPushButton("删除")
        self.delete_button.setStyleSheet(self._button_style(danger=True))
        self.delete_button.clicked.connect(self.delete_current)
        row.addWidget(self.delete_button)
        row.addStretch()
        self.use_button = QtWidgets.QPushButton("放入工作台")
        self.use_button.setStyleSheet(self._button_style())
        self.use_button.clicked.connect(self.use_current)
        row.addWidget(self.use_button)
        self.copy_button = QtWidgets.QPushButton("复制")
        self.copy_button.setStyleSheet(self._button_style(primary=True))
        self.copy_button.clicked.connect(self.copy_current)
        install_button_motion(self.copy_button, colorMode, strong=True)
        row.addWidget(self.copy_button)
        detail_layout.addLayout(row)
        splitter.addWidget(detail)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    @QtCore.Slot()
    def refresh(self):
        selected_id = None
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.entries):
            selected_id = self.entries[row]["id"]
        self.entries = self.app.prompt_library_store.list(self.search.text())
        self.list_widget.clear()
        selected_row = 0
        for index, entry in enumerate(self.entries):
            label = entry["title"]
            if entry.get("tags"):
                label += "\n" + " · ".join(entry["tags"][:3])
            self.list_widget.addItem(label)
            if entry["id"] == selected_id:
                selected_row = index
        if self.entries:
            self.list_widget.setCurrentRow(selected_row)
        else:
            self.entry_title.setText("暂无收藏")
            self.version_combo.clear()
            self.preview.clear()

    def _show_entry(self, row):
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        if not 0 <= row < len(self.entries):
            self.version_combo.blockSignals(False)
            return
        entry = self.entries[row]
        self.entry_title.setText(entry["title"])
        versions = list(reversed(entry["versions"]))
        for index, version in enumerate(versions):
            self.version_combo.addItem(f"版本 {len(versions) - index} · {version.get('saved_at', '')}", version["prompt"])
        self.version_combo.blockSignals(False)
        self._show_version(0)
        self.motion.reveal_widget(self.preview, duration=150)

    def _show_version(self, index):
        self.preview.setPlainText(self.version_combo.itemData(index) or "")

    def current_prompt(self):
        return self.preview.toPlainText().strip()

    def copy_current(self):
        if self.current_prompt():
            QtWidgets.QApplication.clipboard().setText(self.current_prompt())
            original = self.copy_button.text()
            self.copy_button.setText("✓ 已复制")
            QtCore.QTimer.singleShot(
                950,
                lambda: self.copy_button.setText(original)
                if self.copy_button is not None
                else None,
            )

    def use_current(self):
        prompt = self.current_prompt()
        if not prompt:
            return
        opener = getattr(self.app, "open_prompt_with_text", None)
        if callable(opener):
            opener(prompt)
            return
        workbench = getattr(self.app, "prompt_workbench_window", None)
        if workbench is not None:
            workbench.load_library_prompt(prompt)
            workbench.showNormal()
            workbench.raise_()
            workbench.activateWindow()

    def delete_current(self):
        row = self.list_widget.currentRow()
        if not 0 <= row < len(self.entries):
            return
        answer = QtWidgets.QMessageBox.question(self, "删除收藏", "确定删除这个 Prompt 及其全部本地版本吗？")
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self.app.prompt_library_store.delete(self.entries[row]["id"])
            self.refresh()

    def closeEvent(self, event):
        if getattr(self.app, "prompt_library_window", None) is self:
            self.app.prompt_library_window = None
        event.accept()


__all__ = ["PromptLibraryWindow"]
