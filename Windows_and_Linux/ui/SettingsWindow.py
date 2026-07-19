import os
import sys

from aiprovider import AIProvider
from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QHBoxLayout, QRadioButton, QScrollArea

from ui.AutostartManager import AutostartManager
from ui.UIUtils import UIUtils, colorMode

_ = lambda x: x

class SettingsWindow(QtWidgets.QWidget):
    """
    The settings window for the application.
    Now with scrolling support for better usability on smaller screens.
    """
    close_signal = QtCore.Signal()

    def __init__(self, app, providers_only=False):
        super().__init__()
        self.app = app
        self.current_provider_layout = None
        self.providers_only = providers_only
        self.gradient_radio = None
        self.plain_radio = None
        self.provider_dropdown = None
        self.provider_container = None
        self.autostart_checkbox = None
        self.shortcut_input = None
        self.remember_checkbox = None
        self.custom_radio = None
        self.custom_background_input = None
        self.init_ui()
        self.retranslate_ui()


    def retranslate_ui(self):
        self.setWindowTitle("写作工具设置")

    @staticmethod
    def _provider_display_name(provider_name):
        return {
            "Gemini (Recommended)": "Gemini（推荐）",
            "OpenAI Compatible (For Experts)": "OpenAI 兼容接口（高级）",
            "Ollama (For Experts)": "Ollama 本地模型（高级）",
        }.get(provider_name, provider_name)

    def init_provider_ui(self, provider: AIProvider, layout):
        """
        Initialize the user interface for the provider, including logo, name, description and all settings.
        """
        if self.current_provider_layout:
            self.current_provider_layout.setParent(None)
            UIUtils.clear_layout(self.current_provider_layout)
            self.current_provider_layout.deleteLater()

        self.current_provider_layout = QtWidgets.QVBoxLayout()

        # Create a horizontal layout for the logo and provider name
        provider_header_layout = QtWidgets.QHBoxLayout()
        provider_header_layout.setSpacing(10)
        provider_header_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        if provider.logo:
            logo_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', f"provider_{provider.logo}.png")
            if os.path.exists(logo_path):
                targetPixmap = UIUtils.resize_and_round_image(QImage(logo_path), 30, 15)
                logo_label = QtWidgets.QLabel()
                logo_label.setPixmap(targetPixmap)
                logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
                provider_header_layout.addWidget(logo_label)

        provider_name_label = QtWidgets.QLabel(self._provider_display_name(provider.provider_name))
        provider_name_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        provider_name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
        provider_header_layout.addWidget(provider_name_label)

        self.current_provider_layout.addLayout(provider_header_layout)

        if provider.description:
            description_label = QtWidgets.QLabel(provider.description)
            description_label.setStyleSheet(f"font-size: 16px; color: {'#ffffff' if colorMode == 'dark' else '#333333'}; text-align: center;")
            description_label.setWordWrap(True)
            self.current_provider_layout.addWidget(description_label)

        if hasattr(provider, 'ollama_button_text'):
            # Create container for buttons
            button_layout = QtWidgets.QHBoxLayout()
            
            # Add Ollama setup button
            ollama_button = QtWidgets.QPushButton(provider.ollama_button_text)
            ollama_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #5967e8;
                    color: white;
                    padding: 10px;
                    font-size: 16px;
                    border: none;
                    border-radius: 9px;
                }}
                QPushButton:hover {{
                    background-color: #4d5ad2;
                }}
            """)
            ollama_button.clicked.connect(provider.ollama_button_action)
            button_layout.addWidget(ollama_button)
            
            # Add original button
            main_button = QtWidgets.QPushButton(provider.button_text)
            main_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #5967e8;
                    color: white;
                    padding: 10px;
                    font-size: 16px;
                    border: none;
                    border-radius: 9px;
                }}
                QPushButton:hover {{
                    background-color: #4d5ad2;
                }}
            """)
            main_button.clicked.connect(provider.button_action)
            button_layout.addWidget(main_button)
            
            self.current_provider_layout.addLayout(button_layout)
        else:
            # Original single button logic
            if provider.button_text:
                button = QtWidgets.QPushButton(provider.button_text)
                button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #5967e8;
                        color: white;
                        padding: 10px;
                        font-size: 16px;
                        border: none;
                        border-radius: 9px;
                    }}
                    QPushButton:hover {{
                        background-color: #4d5ad2;
                    }}
                """)
                button.clicked.connect(provider.button_action)
                self.current_provider_layout.addWidget(button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # Initialize config if needed
        if "providers" not in self.app.config:
            self.app.config["providers"] = {}
        if provider.provider_name not in self.app.config["providers"]:
            self.app.config["providers"][provider.provider_name] = {}

        # Add provider settings
        for setting in provider.settings:
            setting.set_value(self.app.config["providers"][provider.provider_name].get(setting.name, setting.default_value))
            setting.render_to_layout(self.current_provider_layout)

        layout.addLayout(self.current_provider_layout)

    def init_ui(self):
        self.setWindowTitle("写作工具设置")
        self.setMinimumWidth(720)
        self.resize(760, 720)

        UIUtils.setup_window_and_layout(self)
        main_layout = QtWidgets.QVBoxLayout(self.background)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(14)

        title_label = QtWidgets.QLabel("设置")
        title_label.setStyleSheet(f"""
            color: {'#f7f8ff' if colorMode == 'dark' else '#242632'};
            font-family: "Microsoft YaHei UI", "Segoe UI Variable";
            font-size: 26px;
            font-weight: 650;
        """)
        main_layout.addWidget(title_label)

        subtitle_label = QtWidgets.QLabel("所有修改都会立即生效，无需重新启动。")
        subtitle_label.setStyleSheet(
            f"color: {'#b9bfd9' if colorMode == 'dark' else '#69708a'}; font-size: 13px;"
        )
        main_layout.addWidget(subtitle_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { background: transparent; width: 8px; }
            QScrollBar::handle:vertical { background: rgba(105,112,138,80); border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        scroll_content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 4, 8, 4)
        content_layout.setSpacing(14)

        section_style = f"""
            QWidget#settingsSection {{
                background: {'rgba(38,41,52,210)' if colorMode == 'dark' else 'rgba(255,255,255,215)'};
                border: 1px solid {'rgba(255,255,255,28)' if colorMode == 'dark' else 'rgba(66,76,110,24)'};
                border-radius: 14px;
            }}
            QLabel {{ color: {'#edf0ff' if colorMode == 'dark' else '#303341'}; }}
            QLineEdit, QComboBox {{
                min-height: 36px;
                padding: 4px 10px;
                border: 1px solid {'#555c72' if colorMode == 'dark' else '#d7dae6'};
                border-radius: 9px;
                background: {'#2d303b' if colorMode == 'dark' else '#ffffff'};
                color: {'#f7f8ff' if colorMode == 'dark' else '#242632'};
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border: 1px solid #7f8cff; }}
            QCheckBox, QRadioButton {{
                color: {'#e6e8f5' if colorMode == 'dark' else '#45495a'};
                font-size: 13px;
                spacing: 8px;
            }}
        """

        def create_section(title, description):
            section = QtWidgets.QWidget()
            section.setObjectName("settingsSection")
            section.setStyleSheet(section_style)
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(18, 16, 18, 18)
            layout.setSpacing(10)
            heading = QtWidgets.QLabel(title)
            heading.setStyleSheet("font-size: 17px; font-weight: 650;")
            layout.addWidget(heading)
            helper = QtWidgets.QLabel(description)
            helper.setWordWrap(True)
            helper.setStyleSheet(
                f"color: {'#aeb4ca' if colorMode == 'dark' else '#73798d'}; font-size: 12px;"
            )
            layout.addWidget(helper)
            return section, layout

        if not self.providers_only:
            general_section, general_layout = create_section(
                "常规",
                "设置全局快捷键，以及主快捷键是否直接执行上一次使用的预设。",
            )

            shortcut_label = QtWidgets.QLabel("主快捷键")
            general_layout.addWidget(shortcut_label)
            self.shortcut_input = QtWidgets.QLineEdit(
                self.app.config.get('shortcut', 'ctrl+space')
            )
            general_layout.addWidget(self.shortcut_input)

            self.remember_checkbox = QtWidgets.QCheckBox("记住上次操作并由主快捷键直接执行")
            self.remember_checkbox.setChecked(
                self.app.config.get('remember_last_action', False)
            )
            general_layout.addWidget(self.remember_checkbox)

            if AutostartManager.get_startup_path():
                self.autostart_checkbox = QtWidgets.QCheckBox("开机启动")
                self.autostart_checkbox.setChecked(AutostartManager.check_autostart())
                self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
                general_layout.addWidget(self.autostart_checkbox)

            content_layout.addWidget(general_section)

            appearance_section, appearance_layout = create_section(
                "外观",
                "选择轻盈背景，或者使用你自己的图片。自定义图片只保存在本机路径中。",
            )
            theme_layout = QHBoxLayout()
            self.gradient_radio = QRadioButton("柔光渐变")
            self.plain_radio = QRadioButton("纯色")
            self.custom_radio = QRadioButton("自定义背景")
            current_theme = self.app.config.get('theme', 'plain')
            self.gradient_radio.setChecked(current_theme == 'gradient')
            self.plain_radio.setChecked(current_theme == 'plain')
            self.custom_radio.setChecked(current_theme == 'custom')
            theme_layout.addWidget(self.gradient_radio)
            theme_layout.addWidget(self.plain_radio)
            theme_layout.addWidget(self.custom_radio)
            theme_layout.addStretch()
            appearance_layout.addLayout(theme_layout)

            background_row = QHBoxLayout()
            self.custom_background_input = QtWidgets.QLineEdit(
                self.app.config.get('custom_background_path', '')
            )
            self.custom_background_input.setReadOnly(True)
            self.custom_background_input.setPlaceholderText("尚未选择背景图片")
            background_row.addWidget(self.custom_background_input)
            choose_button = QtWidgets.QPushButton("选择图片")
            choose_button.setStyleSheet(self._secondary_button_style())
            choose_button.clicked.connect(self.choose_custom_background)
            background_row.addWidget(choose_button)
            clear_button = QtWidgets.QPushButton("清除")
            clear_button.setStyleSheet(self._secondary_button_style())
            clear_button.clicked.connect(self.clear_custom_background)
            background_row.addWidget(clear_button)
            appearance_layout.addLayout(background_row)
            content_layout.addWidget(appearance_section)

        provider_section, provider_layout = create_section(
            "AI 服务",
            "选择要使用的模型服务，并填写该服务所需的连接信息。",
        )
        self.provider_dropdown = QtWidgets.QComboBox()
        self.provider_dropdown.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        current_provider = self.app.config.get('provider', self.app.providers[0].provider_name)
        for provider in self.app.providers:
            self.provider_dropdown.addItem(
                self._provider_display_name(provider.provider_name),
                provider.provider_name,
            )
        self.provider_dropdown.setCurrentIndex(
            max(0, self.provider_dropdown.findData(current_provider))
        )
        provider_layout.addWidget(self.provider_dropdown)

        self.provider_container = QtWidgets.QVBoxLayout()
        provider_layout.addLayout(self.provider_container)
        provider_instance = self.app.providers[self.provider_dropdown.currentIndex()]
        self.init_provider_ui(provider_instance, self.provider_container)
        self.provider_dropdown.currentIndexChanged.connect(
            lambda: self.init_provider_ui(
                self.app.providers[self.provider_dropdown.currentIndex()],
                self.provider_container,
            )
        )
        content_layout.addWidget(provider_section)
        content_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        save_button = QtWidgets.QPushButton(
            "完成 AI 设置" if self.providers_only else "保存设置"
        )
        save_button.setFixedHeight(44)
        save_button.setStyleSheet("""
            QPushButton {
                background: #5967e8;
                color: white;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 650;
                border: none;
                border-radius: 11px;
            }
            QPushButton:hover { background: #4d5bd8; }
            QPushButton:pressed { background: #414ec4; }
        """)
        save_button.clicked.connect(self.save_settings)
        main_layout.addWidget(save_button)

    @staticmethod
    def _secondary_button_style():
        return f"""
            QPushButton {{
                min-height: 34px;
                padding: 4px 12px;
                border: 1px solid {'#555c72' if colorMode == 'dark' else '#d7dae6'};
                border-radius: 9px;
                background: {'#343844' if colorMode == 'dark' else '#f6f7fb'};
                color: {'#edf0ff' if colorMode == 'dark' else '#45495a'};
                font-size: 13px;
            }}
            QPushButton:hover {{
                border: 1px solid #7f8cff;
                background: {'#3d4251' if colorMode == 'dark' else '#eef1ff'};
            }}
        """

    def choose_custom_background(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择自定义背景",
            self.custom_background_input.text() or os.path.expanduser("~"),
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if path:
            self.custom_background_input.setText(path)
            self.custom_radio.setChecked(True)

    def clear_custom_background(self):
        self.custom_background_input.clear()
        if self.custom_radio.isChecked():
            self.plain_radio.setChecked(True)

    @staticmethod
    def toggle_autostart(state):
        """Toggle the autostart setting."""
        AutostartManager.set_autostart(state == 2)

    def save_settings(self):
        """Save the current settings."""
        self.app.config['locale'] = 'zh_CN'

        if not self.providers_only:
            self.app.config['shortcut'] = self.shortcut_input.text()
            if self.custom_radio.isChecked() and self.custom_background_input.text():
                self.app.config['theme'] = 'custom'
            elif self.gradient_radio.isChecked():
                self.app.config['theme'] = 'gradient'
            else:
                self.app.config['theme'] = 'plain'
            self.app.config['custom_background_path'] = self.custom_background_input.text()
            self.app.config['remember_last_action'] = self.remember_checkbox.isChecked()
        else:
            self.app.create_tray_icon()

        self.app.config['streaming'] = False
        self.app.config['provider'] = self.provider_dropdown.currentData()

        # Mark config as updated for v8 (new users start with this flag set)
        self.app.config['is_config_file_updated_for_v8'] = True

        self.app.providers[self.provider_dropdown.currentIndex()].save_config()

        provider_name = self.app.config.get('provider', 'Gemini')
        self.app.current_provider = next(
            (provider for provider in self.app.providers if provider.provider_name == provider_name),
            self.app.providers[0]
        )

        self.app.current_provider.load_config(
            self.app.config.get("providers", {}).get(provider_name, {})
        )

        self.app.register_hotkey()
        self.app.change_language('zh_CN')
        self.app.update_tray_menu()
        self.providers_only = False
        self.close()

    def closeEvent(self, event):
        """Handle window close event."""
        if self.providers_only:
            self.close_signal.emit()
        super().closeEvent(event)
