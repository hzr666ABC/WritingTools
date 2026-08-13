"""Independent settings for the SharpInput Prompt Workbench."""

from __future__ import annotations

import threading

from aiprovider import ClickActivatedComboBox, DropdownSetting, TextSetting
from provider_studio import probe_provider, validate_base_url
from pynput import keyboard as pykeyboard
from PySide6 import QtCore, QtWidgets

from settings_logic import find_named_hotkey_conflict, provider_index_by_name
from secure_storage import unprotect_secret
from prompt_presets import BUILTIN_PRESETS
from ui.ShortcutRecorder import ShortcutRecorder
from ui.UIUtils import UIUtils, colorMode
from ui.VisualSystem import button_style, install_button_motion, palette


class PromptSettingsWindow(QtWidgets.QWidget):
    """Keep Prompt AI credentials and behavior separate from writing settings."""

    provider_probe_ready = QtCore.Signal(object)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.providers = app.prompt_providers
        self.selected_provider_index = 0
        self.active_provider_index = None
        self.provider_drafts = {}
        self.provider_detail_layout = None
        self.provider_probe_button = None
        self.provider_probe_status = None
        self.provider_model_picker = None
        self.preference_inputs = {}
        self.provider_probe_ready.connect(self._finish_provider_probe)
        self._build_ui()

    @staticmethod
    def _provider_display_name(provider_name):
        return {
            "Gemini (Recommended)": "Gemini（推荐）",
            "OpenAI Compatible (For Experts)": "OpenAI 兼容接口（高级）",
            "Ollama (For Experts)": "Ollama 本地模型（高级）",
        }.get(provider_name, provider_name)

    @staticmethod
    def _section_style():
        p = palette(colorMode)
        return f"""
            QGroupBox {{
                font-size: 15px; font-weight: 650;
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 14px; margin-top: 10px; padding-top: 12px;
                background: {p['surface']};
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 5px; }}
            QLabel, QCheckBox {{ color: {p['text_soft']}; font-size: 13px; }}
            QLineEdit, QComboBox {{
                min-height: 36px; padding: 3px 10px;
                border: 1px solid {p['border_strong']};
                border-radius: 9px; background: {p['surface_alt']};
                color: {p['text']}; font-size: 13px;
            }}
        """

    @staticmethod
    def _button_style(primary=False, danger=False):
        return button_style(colorMode, primary=primary, danger=danger)

    def _build_ui(self):
        prompt_config = self.app.config.setdefault("prompt_workbench", {})
        self.app.config.setdefault("prompt_providers", {})

        self.setWindowTitle("Prompt 工作台设置")
        self.setMinimumSize(720, 640)
        self.resize(780, 760)
        UIUtils.setup_window_and_layout(self)
        root = QtWidgets.QVBoxLayout(self.background)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(12)

        title = QtWidgets.QLabel("Prompt 工作台设置")
        title.setStyleSheet(
            f"font-size:24px;font-weight:700;color:{palette(colorMode)['text']};"
        )
        root.addWidget(title)
        intro = QtWidgets.QLabel(
            "这套快捷键、模型和密钥只用于需求澄清与 Prompt 编译，不会覆盖主写作 AI。"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color:{palette(colorMode)['text_soft']};font-size:13px;"
        )
        root.addWidget(intro)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 8, 8)
        content_layout.setSpacing(12)

        behavior = QtWidgets.QGroupBox("入口与生成策略")
        behavior.setStyleSheet(self._section_style())
        behavior_layout = QtWidgets.QVBoxLayout(behavior)
        behavior_layout.setContentsMargins(18, 20, 18, 18)
        behavior_layout.addWidget(QtWidgets.QLabel("Prompt 模式快捷键"))
        self.shortcut_input = ShortcutRecorder(
            prompt_config.get("shortcut", "ctrl+shift+p")
        )
        behavior_layout.addWidget(self.shortcut_input)
        shortcut_help = QtWidgets.QLabel(
            "有选区时带入文本；无选区时打开空白工作台。打开窗口本身不会上传内容。"
        )
        shortcut_help.setWordWrap(True)
        behavior_layout.addWidget(shortcut_help)
        behavior_layout.addWidget(QtWidgets.QLabel("默认场景"))
        self.scene_combo = ClickActivatedComboBox()
        presets = (
            self.app.prompt_preset_store.list_all()
            if hasattr(self.app, "prompt_preset_store")
            else BUILTIN_PRESETS
        )
        for preset in presets:
            self.scene_combo.addItem(preset.name, preset.preset_id)
        scene_index = self.scene_combo.findData(prompt_config.get("default_scene", "smart"))
        self.scene_combo.setCurrentIndex(max(0, scene_index))
        behavior_layout.addWidget(self.scene_combo)
        behavior_layout.addWidget(QtWidgets.QLabel("默认生成策略"))
        self.depth_combo = ClickActivatedComboBox()
        self.depth_combo.addItem("极速 · 关闭思考，不追问", "fast")
        self.depth_combo.addItem("平衡 · 只补充关键缺口", "balanced")
        self.depth_combo.addItem("深度 · 思考与严格质量复审", "deep")
        default_strategy = prompt_config.get("default_strategy") or {
            "quick": "fast", "auto": "balanced", "deep": "deep"
        }.get(prompt_config.get("default_depth", "auto"), "balanced")
        depth_index = self.depth_combo.findData(default_strategy)
        self.depth_combo.setCurrentIndex(max(0, depth_index))
        behavior_layout.addWidget(self.depth_combo)
        self.fallback_checkbox = QtWidgets.QCheckBox(
            "Prompt 模型失败时，询问是否改用主写作模型重试"
        )
        self.fallback_checkbox.setChecked(bool(prompt_config.get("fallback_enabled", True)))
        behavior_layout.addWidget(self.fallback_checkbox)
        content_layout.addWidget(behavior)

        memory = QtWidgets.QGroupBox("长期偏好（默认关闭）")
        memory.setStyleSheet(self._section_style())
        memory_layout = QtWidgets.QVBoxLayout(memory)
        memory_layout.setContentsMargins(18, 20, 18, 18)
        self.memory_checkbox = QtWidgets.QCheckBox(
            "允许读取并加密保存下列结构化偏好"
        )
        self.memory_checkbox.setChecked(bool(prompt_config.get("memory_enabled", False)))
        memory_layout.addWidget(self.memory_checkbox)
        memory_help = QtWidgets.QLabel(
            "不会保存原始输入、完整 Prompt 或对话正文。取消勾选会停止读取；“清除偏好”会删除本地文件。"
        )
        memory_help.setWordWrap(True)
        memory_layout.addWidget(memory_help)
        preferences = self.app.prompt_preference_store.load(
            enabled=self.memory_checkbox.isChecked()
        )
        form = QtWidgets.QFormLayout()
        form.setSpacing(8)
        fields = (
            ("role", "常用角色", "例如：产品经理"),
            ("domain", "常用领域", "例如：SaaS / 教育"),
            ("tech_stack", "技术栈", "例如：Python + PySide6"),
            ("common_constraints", "常用约束", "例如：中文优先、不要泛泛建议"),
            ("preferred_language", "Prompt 语言", "例如：跟随输入 / 中文"),
            ("pressure_strength", "压力强度", "例如：适中"),
        )
        for key, label, placeholder in fields:
            editor = QtWidgets.QLineEdit(preferences.get(key, ""))
            editor.setPlaceholderText(placeholder)
            self.preference_inputs[key] = editor
            form.addRow(label, editor)
        memory_layout.addLayout(form)
        clear_memory = QtWidgets.QPushButton("清除偏好文件")
        clear_memory.setStyleSheet(self._button_style(danger=True))
        clear_memory.clicked.connect(self._clear_preferences)
        memory_layout.addWidget(clear_memory, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(memory)

        provider_group = QtWidgets.QGroupBox("独立 Prompt AI")
        provider_group.setStyleSheet(self._section_style())
        provider_layout = QtWidgets.QVBoxLayout(provider_group)
        provider_layout.setContentsMargins(18, 20, 18, 18)
        provider_layout.addWidget(QtWidgets.QLabel("服务"))
        self.provider_combo = ClickActivatedComboBox()
        for provider in self.providers:
            self.provider_combo.addItem(
                self._provider_display_name(provider.provider_name), provider.provider_name
            )
        names = [provider.provider_name for provider in self.providers]
        self.selected_provider_index = provider_index_by_name(
            names, prompt_config.get("provider")
        )
        self.provider_combo.setCurrentIndex(self.selected_provider_index)
        self.provider_combo.currentIndexChanged.connect(self.select_provider)
        provider_layout.addWidget(self.provider_combo)

        self.provider_detail = QtWidgets.QWidget()
        self.provider_detail_layout = QtWidgets.QVBoxLayout(self.provider_detail)
        self.provider_detail_layout.setContentsMargins(0, 6, 0, 0)
        self.provider_detail_layout.setSpacing(8)
        provider_layout.addWidget(self.provider_detail)
        content_layout.addWidget(provider_group)
        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        action_row = QtWidgets.QHBoxLayout()
        action_row.addStretch()
        cancel = QtWidgets.QPushButton("取消")
        cancel.setStyleSheet(self._button_style())
        cancel.clicked.connect(self.close)
        action_row.addWidget(cancel)
        save = QtWidgets.QPushButton("保存 Prompt 设置")
        save.setStyleSheet(self._button_style(primary=True))
        save.clicked.connect(self.save_settings)
        install_button_motion(save, colorMode, strong=True)
        action_row.addWidget(save)
        root.addLayout(action_row)

        self.select_provider(self.selected_provider_index)

    def _capture_provider_values(self, index):
        if not 0 <= index < len(self.providers):
            return
        provider = self.providers[index]
        try:
            self.provider_drafts[provider.provider_name] = {
                setting.name: setting.get_value() for setting in provider.settings
            }
        except RuntimeError:
            pass

    @QtCore.Slot(int)
    def select_provider(self, index):
        if not 0 <= index < len(self.providers):
            return
        if self.active_provider_index is not None and self.active_provider_index != index:
            self._capture_provider_values(self.active_provider_index)
        self.selected_provider_index = index
        self.active_provider_index = index
        self.provider_combo.blockSignals(True)
        self.provider_combo.setCurrentIndex(index)
        self.provider_combo.blockSignals(False)
        UIUtils.clear_layout(self.provider_detail_layout)

        provider = self.providers[index]
        stored = self.app.config.setdefault("prompt_providers", {}).setdefault(
            provider.provider_name, {}
        )
        values = self.provider_drafts.get(provider.provider_name, stored)
        for setting in provider.settings:
            value = values.get(setting.name, setting.default_value)
            if setting.name == "api_key":
                try:
                    value = unprotect_secret(value)
                except Exception:
                    value = ""
            setting.set_value(value)
            setting.render_to_layout(self.provider_detail_layout)

        probe_row = QtWidgets.QHBoxLayout()
        self.provider_probe_button = QtWidgets.QPushButton("检测连接并获取模型")
        self.provider_probe_button.setStyleSheet(self._button_style())
        self.provider_probe_button.clicked.connect(self._start_provider_probe)
        probe_row.addWidget(self.provider_probe_button)
        self.provider_probe_status = QtWidgets.QLabel("尚未检测")
        self.provider_probe_status.setWordWrap(True)
        probe_row.addWidget(self.provider_probe_status, 1)
        self.provider_detail_layout.addLayout(probe_row)
        self.provider_model_picker = ClickActivatedComboBox()
        self.provider_model_picker.setPlaceholderText("检测成功后可选择模型")
        self.provider_model_picker.setEnabled(False)
        self.provider_model_picker.activated.connect(self._apply_discovered_model)
        self.provider_detail_layout.addWidget(self.provider_model_picker)
        self.motion.reveal_widget(self.provider_detail, duration=150)

    def _start_provider_probe(self):
        provider = self.providers[self.selected_provider_index]
        values = {setting.name: setting.get_value() for setting in provider.settings}
        self.provider_probe_button.setEnabled(False)
        self.provider_probe_button.setText("正在检测…")
        self.provider_probe_status.setText("正在连接服务，请稍候。")

        def worker():
            self.provider_probe_ready.emit(probe_provider(provider.provider_name, values))

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.Slot(object)
    def _finish_provider_probe(self, result):
        if self.provider_probe_button is None:
            return
        current = self.providers[self.selected_provider_index]
        if result.provider_name != current.provider_name:
            return
        self.provider_probe_button.setEnabled(True)
        self.provider_probe_button.setText("重新检测")
        color = palette(colorMode)["success"] if result.ok else palette(colorMode)["danger"]
        self.provider_probe_status.setText(
            f"{'✓' if result.ok else '!'}  {result.message} · {result.latency_ms} ms"
        )
        self.provider_probe_status.setStyleSheet(f"color:{color};font-size:12px;")
        normalized_base = result.normalized_values.get("api_base")
        if normalized_base:
            setting = next(
                (item for item in current.settings if item.name == "api_base"), None
            )
            if isinstance(setting, TextSetting) and setting.input:
                setting.input.setText(normalized_base)
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
        provider = self.providers[self.selected_provider_index]
        setting = next(
            (item for item in provider.settings if item.name in ("model_name", "api_model")),
            None,
        )
        if isinstance(setting, TextSetting) and setting.input:
            setting.input.setText(model)
        elif isinstance(setting, DropdownSetting) and setting.dropdown:
            preset_index = setting.dropdown.findData(model)
            if preset_index >= 0:
                setting.dropdown.setCurrentIndex(preset_index)
            elif setting.allow_custom:
                custom_index = setting.dropdown.findData(setting._CUSTOM_SENTINEL)
                setting.dropdown.setCurrentIndex(custom_index)
                setting.custom_input.setText(model)

    def _clear_preferences(self):
        answer = QtWidgets.QMessageBox.question(
            self,
            "清除长期偏好",
            "确定删除 Prompt 工作台保存的结构化偏好吗？完整对话本来就不会保存。",
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.app.prompt_preference_store.clear()
        self.app.config.setdefault("prompt_workbench", {})["memory_enabled"] = False
        self.app.save_config(self.app.config)
        for editor in self.preference_inputs.values():
            editor.clear()
        self.memory_checkbox.setChecked(False)

    def save_settings(self):
        shortcut = self.shortcut_input.text().strip().lower()
        if not shortcut:
            QtWidgets.QMessageBox.warning(self, "快捷键不能为空", "请录制 Prompt 模式快捷键。")
            return
        try:
            pykeyboard.HotKey.parse(self.app._to_pynput_hotkey(shortcut))
        except Exception:
            QtWidgets.QMessageBox.warning(self, "快捷键格式无效", "请重新录制组合键。")
            return
        conflict = find_named_hotkey_conflict(
            shortcut,
            main_shortcut=self.app.config.get("shortcut", "ctrl+space"),
            prompt_shortcut=self.app.config.get("prompt_workbench", {}).get("shortcut", ""),
            options=getattr(self.app, "options", {}),
            ignore="prompt",
        )
        if conflict:
            label = "主写作快捷键" if conflict == "main" else "某个预设直达快捷键"
            QtWidgets.QMessageBox.warning(
                self, "快捷键冲突", f"该组合已经分配给{label}，请换一个快捷键。"
            )
            return

        provider = self.providers[self.selected_provider_index]
        base_setting = next(
            (item for item in provider.settings if item.name == "api_base"), None
        )
        if isinstance(base_setting, TextSetting) and base_setting.input:
            try:
                normalized = validate_base_url(provider.provider_name, base_setting.input.text())
            except ValueError as error:
                QtWidgets.QMessageBox.warning(self, "API 地址不安全", str(error))
                return
            base_setting.input.setText(normalized)

        config = self.app.config.setdefault("prompt_workbench", {})
        config["shortcut"] = shortcut
        strategy = self.depth_combo.currentData()
        config["default_strategy"] = strategy
        config["default_depth"] = {
            "fast": "quick", "balanced": "auto", "deep": "deep"
        }.get(strategy, "auto")
        config["default_scene"] = self.scene_combo.currentData()
        config["fallback_enabled"] = self.fallback_checkbox.isChecked()
        config["provider"] = provider.provider_name
        config["memory_enabled"] = self.memory_checkbox.isChecked()
        provider.save_config()

        if self.memory_checkbox.isChecked():
            preferences = {
                key: editor.text().strip()
                for key, editor in self.preference_inputs.items()
                if editor.text().strip()
            }
            preferences["default_depth"] = config["default_depth"]
            self.app.prompt_preference_store.save(preferences, enabled=True)

        self.app.save_config(self.app.config)
        self.app.reload_prompt_provider()
        self.app.register_hotkey()
        self.app.update_tray_menu()
        self.close()


__all__ = ["PromptSettingsWindow"]
