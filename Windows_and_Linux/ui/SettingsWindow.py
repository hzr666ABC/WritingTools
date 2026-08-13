import os
import sys
import threading

from aiprovider import AIProvider, ClickActivatedComboBox, DropdownSetting, TextSetting
from prompting import option_display_name
from provider_studio import probe_provider, validate_base_url
from pynput import keyboard as pykeyboard
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QHBoxLayout, QRadioButton, QScrollArea
from settings_logic import (
    find_named_hotkey_conflict,
    provider_index_by_name,
)

from ui.AutostartManager import AutostartManager
from ui.ShortcutRecorder import ShortcutRecorder
from ui.UIUtils import UIUtils, colorMode
from ui.VisualSystem import (
    button_style,
    card_style,
    install_button_motion,
    palette,
)

_ = lambda x: x

class SettingsWindow(QtWidgets.QWidget):
    """
    The settings window for the application.
    Now with scrolling support for better usability on smaller screens.
    """
    close_signal = QtCore.Signal()
    provider_probe_ready = QtCore.Signal(object)

    def __init__(self, app, providers_only=False):
        super().__init__()
        self.app = app
        self.current_provider_layout = None
        self.provider_detail_widget = None
        self.provider_button_group = None
        self.provider_buttons = []
        self.provider_selector_widget = None
        self.selected_provider_index = 0
        self.active_provider_index = None
        self.provider_drafts = {}
        self.scroll_area = None
        self.scroll_content = None
        self.providers_only = providers_only
        self.gradient_radio = None
        self.plain_radio = None
        self.provider_container = None
        self.autostart_checkbox = None
        self.autostart_status = None
        self.shortcut_input = None
        self.remember_checkbox = None
        self.custom_radio = None
        self.custom_background_input = None
        self.background_preview = None
        self.safe_apply_checkbox = None
        self.history_checkbox = None
        self.provider_probe_button = None
        self.provider_probe_status = None
        self.provider_model_picker = None
        self.save_button = None
        self.provider_probe_ready.connect(self._finish_provider_probe)
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

    @staticmethod
    def _provider_card_text(provider_name):
        return {
            "Gemini (Recommended)": "Gemini\n推荐",
            "OpenAI Compatible (For Experts)": "OpenAI\n兼容接口",
            "Ollama (For Experts)": "Ollama\n本地模型",
        }.get(provider_name, provider_name)

    def init_provider_ui(self, provider: AIProvider):
        """Rebuild the selected provider details inside one stable container."""
        UIUtils.clear_layout(self.current_provider_layout)

        if provider.description:
            for description_line in provider.description.splitlines():
                description_label = QtWidgets.QLabel(description_line.strip())
                description_label.setStyleSheet(
                    f"font-size:12px;color:{palette(colorMode)['text_soft']};"
                )
                description_label.setWordWrap(True)
                self.current_provider_layout.addWidget(description_label)

        if hasattr(provider, 'ollama_button_text'):
            button_layout = QtWidgets.QHBoxLayout()
            ollama_button = QtWidgets.QPushButton(provider.ollama_button_text)
            ollama_button.setStyleSheet(self._provider_action_button_style())
            ollama_button.clicked.connect(provider.ollama_button_action)
            button_layout.addWidget(ollama_button)
            main_button = QtWidgets.QPushButton(provider.button_text)
            main_button.setStyleSheet(self._provider_action_button_style())
            main_button.clicked.connect(provider.button_action)
            button_layout.addWidget(main_button)
            self.current_provider_layout.addLayout(button_layout)
        else:
            if provider.button_text:
                button = QtWidgets.QPushButton(provider.button_text)
                button.setStyleSheet(self._provider_action_button_style())
                button.clicked.connect(provider.button_action)
                self.current_provider_layout.addWidget(
                    button, alignment=QtCore.Qt.AlignmentFlag.AlignLeft
                )

        detail_heading = QtWidgets.QLabel("连接设置")
        detail_heading.setStyleSheet(
            f"font-size: 14px; font-weight: 650; margin-top: 4px; color: {'#eef0ff' if colorMode == 'dark' else '#343746'};"
        )
        self.current_provider_layout.addWidget(detail_heading)

        # Initialize config if needed
        if "providers" not in self.app.config:
            self.app.config["providers"] = {}
        if provider.provider_name not in self.app.config["providers"]:
            self.app.config["providers"][provider.provider_name] = {}

        # Add provider settings
        provider_values = self.provider_drafts.get(
            provider.provider_name,
            self.app.config["providers"][provider.provider_name],
        )
        for setting in provider.settings:
            setting.set_value(provider_values.get(setting.name, setting.default_value))
            setting.render_to_layout(self.current_provider_layout)

        studio_heading = QtWidgets.QLabel("Provider Studio")
        studio_heading.setStyleSheet(
            f"font-size: 14px; font-weight: 650; margin-top: 8px; color: {'#eef0ff' if colorMode == 'dark' else '#343746'};"
        )
        self.current_provider_layout.addWidget(studio_heading)
        studio_hint = QtWidgets.QLabel(
            "验证地址与密钥，测量延迟，并从服务端读取可用模型。检测过程不会保存或上传密钥。"
        )
        studio_hint.setWordWrap(True)
        studio_hint.setStyleSheet(
            f"font-size: 12px; color: {'#b8bed4' if colorMode == 'dark' else '#6f7589'};"
        )
        self.current_provider_layout.addWidget(studio_hint)

        studio_row = QtWidgets.QHBoxLayout()
        self.provider_probe_button = QtWidgets.QPushButton("检测连接并获取模型")
        self.provider_probe_button.setStyleSheet(self._provider_action_button_style())
        self.provider_probe_button.clicked.connect(self._start_provider_probe)
        studio_row.addWidget(self.provider_probe_button)
        self.provider_probe_status = QtWidgets.QLabel("尚未检测")
        self.provider_probe_status.setWordWrap(True)
        self.provider_probe_status.setStyleSheet(
            f"font-size: 12px; color: {'#aeb4ca' if colorMode == 'dark' else '#778096'};"
        )
        studio_row.addWidget(self.provider_probe_status, 1)
        self.current_provider_layout.addLayout(studio_row)

        self.provider_model_picker = ClickActivatedComboBox()
        self.provider_model_picker.setPlaceholderText("检测成功后可从这里选择模型")
        self.provider_model_picker.setEnabled(False)
        self.provider_model_picker.activated.connect(self._apply_discovered_model)
        self.current_provider_layout.addWidget(self.provider_model_picker)

        self.provider_detail_widget.updateGeometry()
        self.scroll_content.updateGeometry()
        self.motion.reveal_widget(self.provider_detail_widget, duration=150)

    def _start_provider_probe(self):
        """Run provider discovery away from the UI thread."""
        provider = self.app.providers[self.selected_provider_index]
        values = {setting.name: setting.get_value() for setting in provider.settings}
        self.provider_probe_button.setEnabled(False)
        self.provider_probe_button.setText("正在检测…")
        self.provider_probe_status.setText("正在连接服务，请稍候。")
        self.provider_model_picker.clear()
        self.provider_model_picker.setEnabled(False)

        def worker():
            self.provider_probe_ready.emit(probe_provider(provider.provider_name, values))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_provider_probe(self, result):
        if self.provider_probe_button is None:
            return
        self.provider_probe_button.setEnabled(True)
        self.provider_probe_button.setText("重新检测")
        if result.provider_name != self.app.providers[self.selected_provider_index].provider_name:
            return

        color = palette(colorMode)["success"] if result.ok else palette(colorMode)["danger"]
        marker = "✓" if result.ok else "!"
        detail = f"{marker}  {result.message} · {result.latency_ms} ms"
        self.provider_probe_status.setText(detail)
        self.provider_probe_status.setStyleSheet(f"font-size: 12px; color: {color};")

        normalized_base = result.normalized_values.get("api_base")
        if normalized_base:
            base_setting = next(
                (setting for setting in self.app.providers[self.selected_provider_index].settings
                 if setting.name == "api_base"),
                None,
            )
            if isinstance(base_setting, TextSetting) and base_setting.input:
                base_setting.input.setText(normalized_base)

        self.provider_model_picker.clear()
        if result.ok and result.models:
            self.provider_model_picker.addItems(result.models)
            model_index = self.provider_model_picker.findText(result.configured_model)
            if model_index >= 0:
                self.provider_model_picker.setCurrentIndex(model_index)
            self.provider_model_picker.setEnabled(True)

    def _apply_discovered_model(self, index):
        model = self.provider_model_picker.itemText(index).strip()
        if not model:
            return
        provider = self.app.providers[self.selected_provider_index]
        model_setting = next(
            (setting for setting in provider.settings if setting.name in ("model_name", "api_model")),
            None,
        )
        if isinstance(model_setting, TextSetting) and model_setting.input:
            model_setting.input.setText(model)
        elif isinstance(model_setting, DropdownSetting) and model_setting.dropdown:
            preset_index = model_setting.dropdown.findData(model)
            if preset_index >= 0:
                model_setting.dropdown.setCurrentIndex(preset_index)
            elif model_setting.allow_custom:
                custom_index = model_setting.dropdown.findData(model_setting._CUSTOM_SENTINEL)
                model_setting.dropdown.setCurrentIndex(custom_index)
                model_setting.custom_input.setText(model)

    def select_provider(self, index, ensure_visible=True):
        """Switch providers only after an explicit service-card click."""
        if not 0 <= index < len(self.app.providers):
            return
        if self.active_provider_index == index:
            return
        if self.active_provider_index is not None:
            previous = self.app.providers[self.active_provider_index]
            self.provider_drafts[previous.provider_name] = {
                setting.name: setting.get_value()
                for setting in previous.settings
            }
        self.selected_provider_index = index
        self.active_provider_index = index
        self.provider_buttons[index].setChecked(True)
        self.init_provider_ui(self.app.providers[index])
        if ensure_visible:
            QtCore.QTimer.singleShot(
                0,
                lambda: self.scroll_area.ensureWidgetVisible(
                    self.provider_selector_widget, 0, 24
                ),
            )

    def init_ui(self):
        self.setWindowTitle("写作工具设置")
        self.setMinimumWidth(740)
        self.resize(820, 760)

        UIUtils.setup_window_and_layout(self)
        main_layout = QtWidgets.QVBoxLayout(self.background)
        main_layout.setContentsMargins(30, 26, 30, 24)
        main_layout.setSpacing(16)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(11)
        app_icon_label = QtWidgets.QLabel()
        app_icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
        if os.path.exists(app_icon_path):
            app_icon_label.setPixmap(
                QtGui.QPixmap(app_icon_path).scaled(
                    30,
                    30,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        title_row.addWidget(app_icon_label)
        title_label = QtWidgets.QLabel("设置")
        title_label.setStyleSheet(f"""
            color: {palette(colorMode)['text']};
            font-family: "Microsoft YaHei UI", "Segoe UI Variable";
            font-size: 26px;
            font-weight: 650;
        """)
        title_row.addWidget(title_label)
        title_row.addStretch()
        main_layout.addLayout(title_row)

        subtitle_label = QtWidgets.QLabel("保存后立即生效，无需重新启动。")
        subtitle_label.setStyleSheet(
            f"color:{palette(colorMode)['text_soft']};font-size:13px;"
        )
        main_layout.addWidget(subtitle_label)

        scroll_area = QScrollArea()
        self.scroll_area = scroll_area
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
        self.scroll_content = scroll_content
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 4, 8, 6)
        content_layout.setSpacing(12)

        section_style = card_style(colorMode, "settingsSection") + f"""
            QLabel {{ color: {palette(colorMode)['text']}; }}
            QLineEdit, QComboBox {{
                min-height: 38px;
                padding: 4px 11px;
                border: 1px solid {palette(colorMode)['border_strong']};
                border-radius: 10px;
                background: {palette(colorMode)['surface']};
                color: {palette(colorMode)['text']};
                font-size: 14px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border: 1px solid {palette(colorMode)['accent']}; }}
            QCheckBox, QRadioButton {{
                color: {palette(colorMode)['text_soft']};
                font-size: 14px;
                spacing: 8px;
            }}
        """

        def create_section(title, description):
            section = QtWidgets.QWidget()
            section.setObjectName("settingsSection")
            section.setStyleSheet(section_style)
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(20, 18, 20, 20)
            layout.setSpacing(11)
            heading = QtWidgets.QLabel(title)
            heading.setStyleSheet("font-size: 17px; font-weight: 650;")
            layout.addWidget(heading)
            helper = QtWidgets.QLabel(description)
            helper.setWordWrap(True)
            helper.setStyleSheet(
                f"color:{palette(colorMode)['text_soft']};font-size:13px;"
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
            self.shortcut_input = ShortcutRecorder(
                self.app.config.get('shortcut', 'ctrl+space')
            )
            general_layout.addWidget(self.shortcut_input)
            shortcut_hint = QtWidgets.QLabel(
                "点击输入框后直接按下新的组合键；Backspace/Delete 清除，Esc 取消。"
            )
            shortcut_hint.setStyleSheet(
                f"color: {'#aeb4ca' if colorMode == 'dark' else '#778096'}; font-size: 12px;"
            )
            general_layout.addWidget(shortcut_hint)

            self.remember_checkbox = QtWidgets.QCheckBox("记住上次操作并由主快捷键直接执行")
            self.remember_checkbox.setChecked(
                self.app.config.get('remember_last_action', False)
            )
            general_layout.addWidget(self.remember_checkbox)

            self.safe_apply_checkbox = QtWidgets.QCheckBox("应用前显示差异对比（推荐）")
            self.safe_apply_checkbox.setChecked(
                self.app.config.get('safe_apply_enabled', True)
            )
            self.safe_apply_checkbox.setToolTip("先预览增删内容，再决定应用、复制或恢复原文")
            general_layout.addWidget(self.safe_apply_checkbox)

            self.history_checkbox = QtWidgets.QCheckBox("保存本机加密历史与版本")
            self.history_checkbox.setChecked(
                self.app.config.get('history_enabled', True)
            )
            self.history_checkbox.setToolTip("正文使用 Windows 当前用户加密保护，默认最多保存 100 条")
            general_layout.addWidget(self.history_checkbox)

            tool_row = QHBoxLayout()
            history_button = QtWidgets.QPushButton("历史与版本")
            history_button.setStyleSheet(self._secondary_button_style())
            history_button.clicked.connect(self.app.show_history)
            tool_row.addWidget(history_button)
            diagnostics_button = QtWidgets.QPushButton("兼容性诊断")
            diagnostics_button.setStyleSheet(self._secondary_button_style())
            diagnostics_button.clicked.connect(self.app.show_diagnostics)
            tool_row.addWidget(diagnostics_button)
            tool_row.addStretch()
            general_layout.addLayout(tool_row)

            if AutostartManager.get_startup_path():
                self.autostart_checkbox = QtWidgets.QCheckBox(
                    "登录 Windows 后自动启动"
                )
                self.autostart_checkbox.setChecked(AutostartManager.check_autostart())
                self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
                general_layout.addWidget(self.autostart_checkbox)
                self.autostart_status = QtWidgets.QLabel()
                self.autostart_status.setWordWrap(True)
                general_layout.addWidget(self.autostart_status)
                self._refresh_autostart_status()

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

            self.background_preview = QtWidgets.QLabel()
            self.background_preview.setFixedHeight(78)
            self.background_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.background_preview.setStyleSheet(f"""
                QLabel {{
                    border: 1px solid {'#555c72' if colorMode == 'dark' else '#d7dae6'};
                    border-radius: 10px;
                    background: {'#2d303b' if colorMode == 'dark' else '#f8f9fc'};
                }}
            """)
            appearance_layout.addWidget(self.background_preview)
            self.update_background_preview(self.custom_background_input.text())
            content_layout.addWidget(appearance_section)

        provider_section, provider_layout = create_section(
            "AI 服务",
            "点击服务卡片进行切换；悬停和滚轮不会改变当前服务。",
        )
        self.provider_selector_widget = QtWidgets.QWidget()
        selector_layout = QtWidgets.QHBoxLayout(self.provider_selector_widget)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.setSpacing(8)
        self.provider_button_group = QtWidgets.QButtonGroup(self)
        self.provider_button_group.setExclusive(True)
        current_provider = self.app.config.get('provider', self.app.providers[0].provider_name)
        provider_names = [provider.provider_name for provider in self.app.providers]
        self.selected_provider_index = provider_index_by_name(
            provider_names, current_provider
        )
        for index, provider in enumerate(self.app.providers):
            button = QtWidgets.QPushButton(
                self._provider_card_text(provider.provider_name)
            )
            button.setCheckable(True)
            button.setMinimumHeight(58)
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(
                f"切换到{self._provider_display_name(provider.provider_name)}"
            )
            logo_path = os.path.join(
                os.path.dirname(sys.argv[0]),
                'icons',
                f"provider_{provider.logo}.png",
            )
            if os.path.exists(logo_path):
                button.setIcon(QtGui.QIcon(logo_path))
                button.setIconSize(QtCore.QSize(25, 25))
            button.setStyleSheet(self._provider_card_style())
            button.clicked.connect(
                lambda checked=False, provider_index=index: self.select_provider(
                    provider_index
                )
            )
            self.provider_button_group.addButton(button, index)
            self.provider_buttons.append(button)
            selector_layout.addWidget(button, 1)
        provider_layout.addWidget(self.provider_selector_widget)

        self.provider_detail_widget = QtWidgets.QWidget()
        self.provider_detail_widget.setObjectName("providerDetails")
        self.current_provider_layout = QtWidgets.QVBoxLayout(
            self.provider_detail_widget
        )
        self.current_provider_layout.setContentsMargins(2, 4, 2, 0)
        self.current_provider_layout.setSpacing(9)
        provider_layout.addWidget(self.provider_detail_widget)
        self.select_provider(self.selected_provider_index, ensure_visible=False)
        content_layout.addWidget(provider_section)
        content_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        save_button = QtWidgets.QPushButton(
            "完成 AI 设置" if self.providers_only else "保存设置"
        )
        self.save_button = save_button
        save_button.setFixedSize(148, 44)
        save_button.setStyleSheet(button_style(colorMode, primary=True))
        install_button_motion(save_button, colorMode, strong=True)
        save_button.clicked.connect(self.save_settings)
        action_row = QtWidgets.QHBoxLayout()
        action_row.setContentsMargins(2, 0, 0, 0)
        save_note = QtWidgets.QLabel("更改仅保存在本机 · 无需重新启动")
        save_note.setStyleSheet(
            f"color:{palette(colorMode)['muted']};font-size:12px;"
        )
        action_row.addWidget(save_note)
        action_row.addStretch()
        action_row.addWidget(save_button)
        main_layout.addLayout(action_row)

    @staticmethod
    def _secondary_button_style():
        return button_style(colorMode)

    @staticmethod
    def _provider_card_style():
        p = palette(colorMode)
        return f"""
            QPushButton {{
                padding: 7px 12px;
                border: 1px solid {p['border']};
                border-radius: 12px;
                background: {p['surface_alt']};
                color: {p['text_soft']};
                font-size: 13px;
                font-weight: 550;
                text-align: left;
            }}
            QPushButton:hover {{
                border-color: {p['accent']};
                background: {p['surface_soft']};
            }}
            QPushButton:checked {{
                border: 1px solid {p['accent']};
                background: {p['accent_soft']};
                color: {p['accent_text']};
                font-weight: 650;
            }}
            QPushButton:focus {{ border: 2px solid #7f8cff; }}
        """

    @staticmethod
    def _provider_action_button_style():
        return button_style(colorMode, compact=True)

    def update_background_preview(self, path):
        """Show a cropped preview only when a valid custom image exists."""
        if not self.background_preview:
            return
        if not path or not os.path.isfile(path):
            self.background_preview.clear()
            self.background_preview.hide()
            return
        pixmap = QtGui.QPixmap(path)
        if pixmap.isNull():
            self.background_preview.hide()
            return
        target_size = QtCore.QSize(640, 78)
        scaled = pixmap.scaled(
            target_size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - target_size.width()) // 2)
        y = max(0, (scaled.height() - target_size.height()) // 2)
        self.background_preview.setPixmap(
            scaled.copy(x, y, target_size.width(), target_size.height())
        )
        self.background_preview.show()

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
            self.update_background_preview(path)

    def clear_custom_background(self):
        self.custom_background_input.clear()
        self.update_background_preview("")
        if self.custom_radio.isChecked():
            self.plain_radio.setChecked(True)

    def _refresh_autostart_status(self):
        if self.autostart_status is None:
            return
        if AutostartManager.check_autostart():
            self.autostart_status.setText(
                "✓ 已加入当前用户启动项；登录后将在后台运行，无需管理员权限。"
            )
            self.autostart_status.setStyleSheet(
                f"color: {palette()['success']}; font-size: 12px;"
            )
        else:
            self.autostart_status.setText(
                "关闭时不会随 Windows 登录启动，仍可通过桌面快捷方式打开。"
            )
            self.autostart_status.setStyleSheet(
                f"color: {palette()['text_soft']}; font-size: 12px;"
            )

    def toggle_autostart(self, state):
        """Apply the requested startup state and roll back the UI on error."""

        requested = state == QtCore.Qt.CheckState.Checked.value
        if AutostartManager.set_autostart(requested):
            self._refresh_autostart_status()
            return

        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(not requested)
        self.autostart_checkbox.blockSignals(False)
        QtWidgets.QMessageBox.warning(
            self,
            "无法更新开机启动",
            AutostartManager.last_error or "请确认当前程序位于可访问的固定目录。",
        )
        self._refresh_autostart_status()

    def save_settings(self):
        """Save the current settings."""
        self.app.config['locale'] = 'zh_CN'

        if not self.providers_only:
            shortcut = self.shortcut_input.text().strip().lower()
            if not shortcut:
                QtWidgets.QMessageBox.warning(
                    self, "快捷键不能为空", "请输入主快捷键，例如 ctrl+space。"
                )
                self.shortcut_input.setFocus()
                return
            try:
                pykeyboard.HotKey.parse(self.app._to_pynput_hotkey(shortcut))
            except Exception:
                QtWidgets.QMessageBox.warning(
                    self,
                    "快捷键格式无效",
                    "按键之间请使用“+”，例如 ctrl+space 或 ctrl+shift+p。",
                )
                self.shortcut_input.setFocus()
                return
            options = getattr(self.app, 'options', {})
            conflict_owner = find_named_hotkey_conflict(
                shortcut,
                prompt_shortcut=(
                    self.app.config.get("prompt_workbench", {}).get("shortcut", "")
                ),
                options=options,
                ignore="main",
            )
            if conflict_owner == "prompt":
                QtWidgets.QMessageBox.warning(
                    self,
                    "快捷键冲突",
                    "该组合已经分配给“Prompt 工作台”，请换一个快捷键。",
                )
                self.shortcut_input.setFocus()
                return
            if conflict_owner and conflict_owner.startswith("option:"):
                conflict_key = conflict_owner.split(":", 1)[1]
                display_name = option_display_name(
                    conflict_key, options.get(conflict_key, {})
                )
                QtWidgets.QMessageBox.warning(
                    self,
                    "快捷键冲突",
                    f"该组合已经分配给“{display_name}”预设，请换一个快捷键。",
                )
                self.shortcut_input.setFocus()
                return
            self.app.config['shortcut'] = shortcut
            if self.custom_radio.isChecked() and self.custom_background_input.text():
                self.app.config['theme'] = 'custom'
            elif self.gradient_radio.isChecked():
                self.app.config['theme'] = 'gradient'
            else:
                self.app.config['theme'] = 'plain'
            self.app.config['custom_background_path'] = self.custom_background_input.text()
            self.app.config['remember_last_action'] = self.remember_checkbox.isChecked()
            self.app.config['safe_apply_enabled'] = self.safe_apply_checkbox.isChecked()
            self.app.config['history_enabled'] = self.history_checkbox.isChecked()
        else:
            self.app.create_tray_icon()

        self.app.config['streaming'] = False
        selected_provider = self.app.providers[self.selected_provider_index]

        base_setting = next(
            (setting for setting in selected_provider.settings if setting.name == "api_base"),
            None,
        )
        if isinstance(base_setting, TextSetting) and base_setting.input:
            try:
                normalized_base = validate_base_url(
                    selected_provider.provider_name, base_setting.input.text()
                )
            except ValueError as error:
                QtWidgets.QMessageBox.warning(self, "API 地址不安全", str(error))
                base_setting.input.setFocus()
                return
            base_setting.input.setText(normalized_base)
        self.app.config['provider'] = selected_provider.provider_name

        # Mark config as updated for v8 (new users start with this flag set)
        self.app.config['is_config_file_updated_for_v8'] = True

        selected_provider.save_config()
        self.app._ensure_custom_defaults()

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
