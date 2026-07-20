"""Compatibility diagnostics with a redacted support report."""

from __future__ import annotations

import json
import threading

from PySide6 import QtCore, QtWidgets

from diagnostics import (
    build_report,
    run_clipboard_roundtrip,
    run_local_diagnostics,
    run_provider_diagnostic,
)
from ui.UIUtils import UIUtils, colorMode


class DiagnosticsWindow(QtWidgets.QWidget):
    results_ready = QtCore.Signal(object, object)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.items = []
        self.report = None
        self.setWindowTitle("兼容性诊断中心")
        self.setMinimumSize(720, 500)
        self.resize(820, 600)
        self.results_ready.connect(self._show_results)
        self._build_ui()

    def _build_ui(self):
        UIUtils.setup_window_and_layout(self)
        layout = QtWidgets.QVBoxLayout(self.background)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(12)
        title = QtWidgets.QLabel("兼容性诊断中心")
        title.setStyleSheet(
            f"font-size:24px;font-weight:700;color:{'#f3f5ff' if colorMode == 'dark' else '#202638'};"
        )
        layout.addWidget(title)
        helper = QtWidgets.QLabel(
            "检查配置、预设、安装权限、剪贴板和当前 AI 服务。报告会自动隐藏所有密钥。"
        )
        helper.setWordWrap(True)
        helper.setStyleSheet(
            f"font-size:13px;color:{'#aeb5ce' if colorMode == 'dark' else '#747c91'};"
        )
        layout.addWidget(helper)
        self.status_label = QtWidgets.QLabel("点击下方按钮开始检测")
        layout.addWidget(self.status_label)
        self.results_list = QtWidgets.QListWidget()
        layout.addWidget(self.results_list, 1)
        actions = QtWidgets.QHBoxLayout()
        self.run_button = QtWidgets.QPushButton("运行完整诊断")
        self.run_button.clicked.connect(self.run_diagnostics)
        actions.addWidget(self.run_button)
        self.copy_button = QtWidgets.QPushButton("复制脱敏报告")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_report)
        actions.addWidget(self.copy_button)
        actions.addStretch()
        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def run_diagnostics(self):
        self.run_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.results_list.clear()
        self.status_label.setText("正在检测，请稍候…")
        provider = self.app.current_provider
        values = {
            setting.name: getattr(provider, setting.name, setting.default_value)
            for setting in provider.settings
        }

        def worker():
            items = run_local_diagnostics(self.app.config_path, self.app.options_path)
            items.append(run_clipboard_roundtrip())
            provider_item, probe = run_provider_diagnostic(provider.provider_name, values)
            items.append(provider_item)
            report = build_report(items, self.app.config)
            report["provider_probe"] = {
                "ok": probe.ok,
                "latency_ms": probe.latency_ms,
                "models_found": len(probe.models),
                "configured_model_found": probe.configured_model_found,
            }
            self.results_ready.emit(items, report)

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.Slot(object, object)
    def _show_results(self, items, report):
        self.items = items
        self.report = report
        passed = sum(1 for item in items if item.ok)
        for item in items:
            prefix = "通过" if item.ok else "异常"
            row = QtWidgets.QListWidgetItem(
                f"{prefix} · {item.name}\n{item.detail}"
            )
            row.setForeground(
                QtCore.Qt.GlobalColor.darkGreen if item.ok else QtCore.Qt.GlobalColor.darkRed
            )
            self.results_list.addItem(row)
        self.status_label.setText(f"检测完成：{passed}/{len(items)} 项通过")
        self.run_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def copy_report(self):
        if self.report:
            text = json.dumps(self.report, ensure_ascii=False, indent=2)
            QtWidgets.QApplication.clipboard().setText(text)
            self.status_label.setText("脱敏报告已复制，不包含 API Key。")


__all__ = ["DiagnosticsWindow"]
