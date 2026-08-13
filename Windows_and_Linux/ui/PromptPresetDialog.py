"""Compact editor for encrypted custom Prompt scene presets."""

from __future__ import annotations

from PySide6 import QtWidgets

from ui.UIUtils import colorMode
from ui.VisualSystem import (
    MotionController,
    button_style,
    editor_style,
    global_stylesheet,
    install_button_motion,
    palette,
)


class PromptPresetDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, preset=None):
        super().__init__(parent)
        self.preset = preset
        self.setWindowTitle("自定义场景预设")
        self.resize(560, 520)
        self.setStyleSheet(global_stylesheet(colorMode))
        self.motion = MotionController(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("创建自己的场景")
        title.setStyleSheet(
            f"font-size:20px;font-weight:700;color:{palette(colorMode)['text']};"
        )
        layout.addWidget(title)
        help_text = QtWidgets.QLabel("场景规则告诉 Prompt 编译器应该优先澄清什么。模板中的 [变量] 会在使用时生成填写框。")
        help_text.setWordWrap(True)
        help_text.setStyleSheet(
            f"color:{palette(colorMode)['text_soft']};font-size:12px;"
        )
        layout.addWidget(help_text)

        form = QtWidgets.QFormLayout()
        form.setSpacing(9)
        self.name_input = QtWidgets.QLineEdit(getattr(preset, "name", ""))
        self.name_input.setPlaceholderText("例如：短视频脚本")
        form.addRow("名称", self.name_input)
        self.description_input = QtWidgets.QLineEdit(getattr(preset, "description", ""))
        self.description_input.setPlaceholderText("一句话说明适用场景")
        form.addRow("说明", self.description_input)
        layout.addLayout(form)

        layout.addWidget(QtWidgets.QLabel("场景规则"))
        self.instruction_input = QtWidgets.QPlainTextEdit(getattr(preset, "instruction", ""))
        self.instruction_input.setPlaceholderText("例如：优先澄清平台、受众、时长、前三秒钩子、镜头节奏和 CTA。")
        self.instruction_input.setMinimumHeight(110)
        self.instruction_input.setStyleSheet(editor_style(colorMode))
        layout.addWidget(self.instruction_input)
        layout.addWidget(QtWidgets.QLabel("变量模板（可选）"))
        self.template_input = QtWidgets.QPlainTextEdit(getattr(preset, "template", ""))
        self.template_input.setPlaceholderText("平台：[平台]\n受众：[受众]\n时长：[时长]")
        self.template_input.setMinimumHeight(100)
        self.template_input.setStyleSheet(editor_style(colorMode))
        layout.addWidget(self.template_input)

        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet("color:#C23A51;font-size:12px;")
        layout.addWidget(self.error_label)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Save
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._validate)
        cancel = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        save = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        cancel.setText("取消")
        save.setText("保存场景")
        cancel.setStyleSheet(button_style(colorMode))
        save.setStyleSheet(button_style(colorMode, primary=True))
        install_button_motion(save, colorMode, strong=True)
        layout.addWidget(buttons)

    def _validate(self):
        if not self.name_input.text().strip() or not self.instruction_input.toPlainText().strip():
            self.error_label.setText("名称和场景规则不能为空。")
            return
        self.accept()

    def values(self):
        return {
            "preset_id": getattr(self.preset, "preset_id", ""),
            "name": self.name_input.text().strip(),
            "description": self.description_input.text().strip(),
            "instruction": self.instruction_input.toPlainText().strip(),
            "template": self.template_input.toPlainText().strip(),
        }


__all__ = ["PromptPresetDialog"]
