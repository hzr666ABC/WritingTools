import logging
import os
import sys

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QHBoxLayout, QRadioButton

from ui.UIUtils import UIUtils, colorMode
from ui.ShortcutRecorder import ShortcutRecorder

_ = lambda x: x

class OnboardingWindow(QtWidgets.QWidget):
    # Closing signal
    close_signal = QtCore.Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.shortcut = 'ctrl+space'
        self.theme = 'gradient'
        self.content_layout = None
        self.shortcut_input = None
        self.init_ui()
        self.self_close = False

    def init_ui(self):
        logging.debug('Initializing onboarding UI')
        self.setWindowTitle(_('Welcome to Writing Tools'))
        self.resize(650, 580)

        UIUtils.setup_window_and_layout(self)

        self.content_layout = QtWidgets.QVBoxLayout()
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(20)

        self.background.setLayout(self.content_layout)

        self.show_welcome_screen()

    def show_welcome_screen(self):
        UIUtils.clear_layout(self.content_layout)

        icon_label = QtWidgets.QLabel()
        icon_path = os.path.join(os.path.dirname(sys.argv[0]), "icons", "app_icon.png")
        if os.path.exists(icon_path):
            icon_label.setPixmap(QtGui.QPixmap(icon_path).scaled(72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.content_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        title_label = QtWidgets.QLabel("欢迎使用写作工具")
        title_label.setStyleSheet(f"font-family: 'Microsoft YaHei UI'; font-size: 26px; font-weight: 650; color: {'#ffffff' if colorMode == 'dark' else '#242632'};")
        self.content_layout.addWidget(title_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        features_text = "选择任意文字，按下主快捷键即可校对、改写、总结或运行自己的预设。\n\n开启“记住上次操作”后，主快捷键会直接复用最近的预设；关闭时可用数字键快速选择。"
        features_label = QtWidgets.QLabel(features_text)
        features_label.setWordWrap(True)
        features_label.setStyleSheet(f"font-family: 'Microsoft YaHei UI'; font-size: 14px; line-height: 1.6; padding: 16px; border-radius: 12px; background: {'rgba(255,255,255,20)' if colorMode == 'dark' else 'rgba(241,243,255,220)'}; color: {'#e6e8f5' if colorMode == 'dark' else '#45495a'};")
        features_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.content_layout.addWidget(features_label)

        shortcut_label = QtWidgets.QLabel("设置主快捷键（默认 ctrl+space）")
        shortcut_label.setStyleSheet(f"font-size: 16px; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        self.content_layout.addWidget(shortcut_label)

        self.shortcut_input = ShortcutRecorder(self.shortcut)
        self.shortcut_input.setStyleSheet(f"""
            font-size: 16px;
            padding: 9px 12px;
            background-color: {'#444' if colorMode == 'dark' else 'white'};
            color: {'#ffffff' if colorMode == 'dark' else '#000000'};
            border: 1px solid {'#666' if colorMode == 'dark' else '#d9dce8'};
            border-radius: 9px;
        """)
        self.content_layout.addWidget(self.shortcut_input)
        shortcut_hint = QtWidgets.QLabel("点击输入框后直接按下快捷键；Backspace/Delete 可清除。")
        shortcut_hint.setStyleSheet(
            f"font-size: 12px; color: {'#b9bfd9' if colorMode == 'dark' else '#778096'};"
        )
        self.content_layout.addWidget(shortcut_hint)

        theme_label = QtWidgets.QLabel("选择界面主题")
        theme_label.setStyleSheet(f"font-size: 16px; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        self.content_layout.addWidget(theme_label)

        theme_layout = QHBoxLayout()
        gradient_radio = QRadioButton("柔光渐变")
        plain_radio = QRadioButton("简约纯色")
        gradient_radio.setStyleSheet(f"color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        plain_radio.setStyleSheet(f"color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        gradient_radio.setChecked(self.theme == 'gradient')
        plain_radio.setChecked(self.theme == 'plain')
        theme_layout.addWidget(gradient_radio)
        theme_layout.addWidget(plain_radio)
        self.content_layout.addLayout(theme_layout)

        next_button = QtWidgets.QPushButton('下一步：设置 AI 服务')
        next_button.setStyleSheet("""
            QPushButton {
                background-color: #5967e8;
                color: white;
                padding: 10px;
                font-size: 16px;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #4d5ad2;
            }
        """)
        next_button.clicked.connect(lambda: self.on_next_clicked(gradient_radio.isChecked()))
        self.content_layout.addWidget(next_button)

    def on_next_clicked(self, is_gradient):
        self.shortcut = self.shortcut_input.text()
        self.theme = 'gradient' if is_gradient else 'plain'
        logging.debug(f'User selected shortcut: {self.shortcut}, theme: {self.theme}')
        self.app.config = {
            'shortcut': self.shortcut,
            'theme': self.theme,
            'locale': 'zh_CN',
            'remember_last_action': False,
            'last_used_option': 'Proofread',
            'popup_position': 'bottom_right',
            'custom_background_path': '',
        }
        self.show_api_key_input()

    def show_api_key_input(self):
        self.app.show_settings(providers_only=True)
        self.self_close = True
        self.close()

    def closeEvent(self, event):
        # Emit the close signal
        if not self.self_close:
            self.close_signal.emit()
        super().closeEvent(event)
