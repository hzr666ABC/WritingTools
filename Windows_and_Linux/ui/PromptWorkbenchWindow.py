"""Dedicated conversation UI for SharpInput prompt compilation."""

from __future__ import annotations

import html
import time

from PySide6 import QtCore, QtGui, QtWidgets

from sharpinput_workflow import (
    MAX_TARGET_INPUT_CHARS,
    SharpInputSession,
    WorkflowEvent,
    stream_visible_text,
)
from prompt_presets import BUILTIN_PRESETS, preset_variables, render_preset_input
from ui.PromptPresetDialog import PromptPresetDialog
from ui.UIUtils import UIUtils, colorMode
from ui.VisualSystem import (
    ActivityIndicator,
    button_style,
    card_style,
    editor_style,
    install_button_motion,
    install_focus_glow,
    palette,
)


class ImeFriendlyPlainTextEdit(QtWidgets.QPlainTextEdit):
    """Hide placeholder text while a Chinese IME preedit string is visible."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ime_placeholder = ""

    def set_ime_placeholder(self, text):
        self._ime_placeholder = str(text or "")
        self.setPlaceholderText(self._ime_placeholder)

    def inputMethodEvent(self, event):
        composing = bool(event.preeditString())
        if composing:
            self.setPlaceholderText("")
        super().inputMethodEvent(event)
        if not composing and not self.toPlainText():
            self.setPlaceholderText(self._ime_placeholder)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if not self.toPlainText():
            self.setPlaceholderText(self._ime_placeholder)


class PromptWorkbenchWindow(QtWidgets.QWidget):
    """One in-memory Prompt Workbench session."""

    def __init__(self, app, capture_holder=None):
        super().__init__()
        self.app = app
        self.capture_holder = capture_holder
        self.source_window_handle = getattr(capture_holder, "source_window_handle", None)
        self.source_ime_state = getattr(capture_holder, "ime_state", None)
        self.original_selected_text = ""
        self.session: SharpInputSession | None = None
        self.request_id = 0
        self._closed = False
        self._capture_loaded = False
        self._transcript = []
        self._result_editors = []
        self._variable_inputs = {}
        self.generation_strategy = "balanced"
        self._session_started_at = None
        self._first_token_at = None
        self._stream_target = ""
        self._stream_rendered = ""
        self.status_indicator = None
        self.char_counter = None
        self._build_ui()
        self._stream_timer = QtCore.QTimer(self)
        self._stream_timer.setInterval(18)
        self._stream_timer.timeout.connect(self._stream_tick)
        self._poll_capture()

    @staticmethod
    def _button_style(primary=False, danger=False):
        return button_style(colorMode, primary=primary, danger=danger)

    @staticmethod
    def _editor_style():
        return editor_style(colorMode, prominent=True)

    def _build_ui(self):
        self.setWindowTitle("Prompt 工作台")
        self.setMinimumSize(760, 600)
        self.resize(900, 760)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.WindowCloseButtonHint
            | QtCore.Qt.WindowType.WindowMinimizeButtonHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
        )
        UIUtils.setup_window_and_layout(self)
        root = QtWidgets.QVBoxLayout(self.background)
        root.setContentsMargins(34, 28, 34, 24)
        root.setSpacing(15)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(10)
        brand = QtWidgets.QVBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(1)
        eyebrow = QtWidgets.QLabel("PROMPT  STUDIO")
        eyebrow.setStyleSheet(
            f"color:{palette(colorMode)['accent']};font-size:10px;font-weight:700;letter-spacing:1.6px;"
        )
        title = QtWidgets.QLabel("把模糊想法，变成清晰指令")
        title.setStyleSheet(
            f"font-size:25px;font-weight:700;letter-spacing:.2px;color:{palette(colorMode)['text']};"
        )
        brand.addWidget(eyebrow)
        brand.addWidget(title)
        header.addLayout(brand)
        header.addStretch()
        self.provider_label = QtWidgets.QLabel(self.app.prompt_provider_display())
        self.provider_label.setStyleSheet(
            f"padding:6px 10px;border:1px solid {palette(colorMode)['border']};"
            f"border-radius:9px;background:{palette(colorMode)['surface_alt']};"
            f"color:{palette(colorMode)['text_soft']};font-size:11px;"
        )
        header.addWidget(self.provider_label)
        settings_button = QtWidgets.QPushButton("设置")
        settings_button.setStyleSheet(button_style(colorMode, compact=True))
        settings_button.clicked.connect(self.app.show_prompt_settings)
        header.addWidget(settings_button)
        library_button = QtWidgets.QPushButton("收藏库")
        library_button.setStyleSheet(button_style(colorMode, compact=True))
        library_button.clicked.connect(
            lambda: getattr(self.app, "show_prompt_library", lambda: None)()
        )
        header.addWidget(library_button)
        root.addLayout(header)

        privacy = QtWidgets.QLabel(
            "  ◈  内容仅在确认生成后发送  ·  结果可编辑、收藏或安全替换原选区"
        )
        privacy.setObjectName("privacyNotice")
        privacy.setWordWrap(True)
        privacy.setStyleSheet(
            f"QLabel#privacyNotice{{padding:10px 12px;border:1px solid {palette(colorMode)['border']};"
            f"border-radius:11px;background:{palette(colorMode)['surface_alt']};"
            f"color:{palette(colorMode)['muted']};font-size:12px;}}"
        )
        root.addWidget(privacy)

        self.stack = QtWidgets.QStackedWidget()
        root.addWidget(self.stack, 1)
        self._build_input_page()
        self._build_conversation_page()
        self._build_result_page()

        status_surface = QtWidgets.QWidget()
        status_surface.setObjectName("statusSurface")
        status_surface.setStyleSheet(card_style(colorMode, "statusSurface"))
        status_layout = QtWidgets.QHBoxLayout(status_surface)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(8)
        self.status_indicator = ActivityIndicator(colorMode)
        status_layout.addWidget(self.status_indicator)
        self.status_label = QtWidgets.QLabel("正在读取当前选区…")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"color:{palette(colorMode)['text_soft']};font-size:12px;"
        )
        status_layout.addWidget(self.status_label, 1)
        root.addWidget(status_surface)

    def _build_input_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(11)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("inputToolbar")
        toolbar.setStyleSheet(card_style(colorMode, "inputToolbar"))
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(12, 9, 12, 9)
        scene_label = QtWidgets.QLabel("场景")
        scene_label.setStyleSheet(
            f"color:{palette(colorMode)['muted']};font-size:11px;font-weight:650;"
        )
        row.addWidget(scene_label)
        self.scene_combo = QtWidgets.QComboBox()
        self.scene_combo.setMinimumWidth(190)
        self._reload_scene_combo()
        self.scene_combo.currentIndexChanged.connect(self._scene_changed)
        row.addWidget(self.scene_combo)
        self.custom_preset_button = QtWidgets.QPushButton("新建场景")
        self.custom_preset_button.setStyleSheet(self._button_style())
        self.custom_preset_button.clicked.connect(self.create_custom_preset)
        row.addWidget(self.custom_preset_button)
        self.manage_preset_button = QtWidgets.QPushButton("管理")
        self.manage_preset_button.setStyleSheet(self._button_style())
        self.manage_preset_button.clicked.connect(self.manage_custom_preset)
        self.manage_preset_button.hide()
        row.addWidget(self.manage_preset_button)
        row.addStretch()
        strategy_label = QtWidgets.QLabel("策略")
        strategy_label.setStyleSheet(
            f"color:{palette(colorMode)['muted']};font-size:11px;font-weight:650;"
        )
        row.addWidget(strategy_label)
        self.depth_combo = QtWidgets.QComboBox()
        self.depth_combo.addItem("极速", "fast")
        self.depth_combo.addItem("平衡", "balanced")
        self.depth_combo.addItem("深度", "deep")
        prompt_config = self.app.config.get("prompt_workbench", {})
        default_strategy = prompt_config.get("default_strategy") or {
            "quick": "fast", "auto": "balanced", "deep": "deep"
        }.get(prompt_config.get("default_depth", "auto"), "balanced")
        index = self.depth_combo.findData(default_strategy)
        self.depth_combo.setCurrentIndex(max(0, index))
        self.depth_combo.setAccessibleName("Prompt 生成策略")
        row.addWidget(self.depth_combo)
        toolbar.setLayout(row)
        layout.addWidget(toolbar)

        self.scene_description = QtWidgets.QLabel()
        self.scene_description.setWordWrap(True)
        self.scene_description.setStyleSheet(
            f"color:{palette(colorMode)['muted']};font-size:12px;padding:0 3px;"
        )
        layout.addWidget(self.scene_description)

        self.variable_box = QtWidgets.QGroupBox("模板变量")
        self.variable_layout = QtWidgets.QFormLayout(self.variable_box)
        self.variable_layout.setContentsMargins(14, 14, 14, 12)
        self.variable_box.hide()
        layout.addWidget(self.variable_box)

        self.initial_editor = ImeFriendlyPlainTextEdit()
        self.initial_editor.setStyleSheet(self._editor_style())
        self.initial_editor.set_ime_placeholder(
            "写下还不够清晰的需求、问题或想法…"
        )
        self.initial_editor.setAccessibleName("待梳理的初始输入")
        install_focus_glow(self.initial_editor, colorMode)
        layout.addWidget(self.initial_editor, 1)

        editor_meta = QtWidgets.QHBoxLayout()
        editor_meta.setContentsMargins(3, 0, 3, 0)
        editor_meta.addStretch()
        self.char_counter = QtWidgets.QLabel()
        self.char_counter.setStyleSheet(
            f"color:{palette(colorMode)['muted']};font-size:11px;"
        )
        editor_meta.addWidget(self.char_counter)
        layout.addLayout(editor_meta)
        self.initial_editor.textChanged.connect(self._update_char_counter)
        self._update_char_counter()

        hint = QtWidgets.QLabel(
            "极速关闭模型思考且不追问；平衡只补充关键缺口；深度启用严格复审，耗时更长。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{palette(colorMode)['muted']};font-size:11px;padding:2px 3px;"
        )
        layout.addWidget(hint)
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        self.start_button = QtWidgets.QPushButton("开始生成")
        self.start_button.setStyleSheet(self._button_style(primary=True))
        self.start_button.clicked.connect(self.start_session)
        self.start_button.setShortcut(QtGui.QKeySequence("Ctrl+Return"))
        install_button_motion(self.start_button, colorMode, strong=True)
        actions.addWidget(self.start_button)
        layout.addLayout(actions)
        self.stack.addWidget(page)
        self._scene_changed(self.scene_combo.currentIndex())

    def _build_conversation_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        self.transcript = QtWidgets.QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        self.transcript.setStyleSheet(
            editor_style(colorMode, prominent=True)
        )
        layout.addWidget(self.transcript, 1)
        self.stream_preview_label = QtWidgets.QLabel("实时生成 · 内容会逐字出现")
        self.stream_preview_label.setStyleSheet(
            f"color:{palette(colorMode)['accent_text']};font-size:11px;font-weight:650;"
        )
        self.stream_preview_label.hide()
        layout.addWidget(self.stream_preview_label)
        self.stream_preview = QtWidgets.QPlainTextEdit()
        self.stream_preview.setReadOnly(True)
        self.stream_preview.setMaximumHeight(170)
        self.stream_preview.setStyleSheet(self._editor_style())
        self.stream_preview.setAccessibleName("Prompt 实时生成预览")
        self.stream_preview.hide()
        layout.addWidget(self.stream_preview)
        self.answer_editor = ImeFriendlyPlainTextEdit()
        self.answer_editor.setStyleSheet(self._editor_style())
        self.answer_editor.setMaximumHeight(120)
        self.answer_editor.set_ime_placeholder("回答关键问题；也可以选择跳过并使用占位符。")
        self.answer_editor.setAccessibleName("澄清问题回答")
        install_focus_glow(self.answer_editor, colorMode)
        layout.addWidget(self.answer_editor)
        actions = QtWidgets.QHBoxLayout()
        self.cancel_button = QtWidgets.QPushButton("取消请求")
        self.cancel_button.setStyleSheet(self._button_style(danger=True))
        self.cancel_button.clicked.connect(self.cancel_request)
        actions.addWidget(self.cancel_button)
        self.retry_button = QtWidgets.QPushButton("重试请求")
        self.retry_button.setStyleSheet(self._button_style())
        self.retry_button.clicked.connect(self.retry_request)
        self.retry_button.hide()
        actions.addWidget(self.retry_button)
        actions.addStretch()
        self.skip_button = QtWidgets.QPushButton("跳过，用占位符")
        self.skip_button.setStyleSheet(self._button_style())
        self.skip_button.clicked.connect(lambda: self.submit_answer(skipped=True))
        actions.addWidget(self.skip_button)
        self.answer_button = QtWidgets.QPushButton("继续编译")
        self.answer_button.setStyleSheet(self._button_style(primary=True))
        self.answer_button.clicked.connect(self.submit_answer)
        install_button_motion(self.answer_button, colorMode, strong=True)
        actions.addWidget(self.answer_button)
        layout.addLayout(actions)
        self.stack.addWidget(page)

    def _build_result_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(9)
        self.result_meta = QtWidgets.QLabel()
        self.result_meta.setWordWrap(True)
        self.result_meta.setStyleSheet(
            f"color:{palette(colorMode)['muted']};font-size:11px;"
        )
        layout.addWidget(self.result_meta)
        self.understanding_title = QtWidgets.QLabel("需求梳理")
        self.understanding_title.setStyleSheet(
            f"font-size:13px;font-weight:650;color:{palette(colorMode)['text']};"
        )
        self.understanding_title.hide()
        layout.addWidget(self.understanding_title)
        self.understanding_panel = QtWidgets.QTextBrowser()
        self.understanding_panel.setOpenExternalLinks(False)
        self.understanding_panel.setMaximumHeight(180)
        self.understanding_panel.setStyleSheet(
            editor_style(colorMode)
        )
        self.understanding_panel.hide()
        layout.addWidget(self.understanding_panel)
        self.result_tabs = QtWidgets.QTabWidget()
        self.result_tabs.setDocumentMode(True)
        self.result_tabs.currentChanged.connect(self._update_replace_state)
        layout.addWidget(self.result_tabs, 1)
        self.result_notes = QtWidgets.QLabel()
        self.result_notes.setWordWrap(True)
        self.result_notes.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.result_notes)

        primary_actions = QtWidgets.QHBoxLayout()
        self.new_button = QtWidgets.QPushButton("重新开始")
        self.new_button.setStyleSheet(self._button_style())
        self.new_button.clicked.connect(self.reset_session)
        primary_actions.addWidget(self.new_button)
        primary_actions.addStretch()
        self.replace_button = QtWidgets.QPushButton("替换原选区…")
        self.replace_button.setStyleSheet(self._button_style())
        self.replace_button.clicked.connect(self.replace_original)
        primary_actions.addWidget(self.replace_button)
        self.favorite_button = QtWidgets.QPushButton("收藏")
        self.favorite_button.setStyleSheet(self._button_style())
        self.favorite_button.clicked.connect(self.save_favorite)
        primary_actions.addWidget(self.favorite_button)
        self.copy_button = QtWidgets.QPushButton("复制 Prompt")
        self.copy_button.setStyleSheet(self._button_style(primary=True))
        self.copy_button.clicked.connect(self.copy_prompt)
        install_button_motion(self.copy_button, colorMode, strong=True)
        primary_actions.addWidget(self.copy_button)
        layout.addLayout(primary_actions)

        refinement_label = QtWidgets.QLabel("继续修改（会调用当前 Prompt 模型）")
        layout.addWidget(refinement_label)
        refine_row = QtWidgets.QHBoxLayout()
        self.refinement_input = QtWidgets.QLineEdit()
        self.refinement_input.setPlaceholderText("例如：更简洁；增加验收标准；不要使用角色设定")
        self.refinement_input.returnPressed.connect(self.refine_prompt)
        refine_row.addWidget(self.refinement_input, 1)
        self.refine_button = QtWidgets.QPushButton("继续修改")
        self.refine_button.setStyleSheet(self._button_style())
        self.refine_button.clicked.connect(self.refine_prompt)
        refine_row.addWidget(self.refine_button)
        layout.addLayout(refine_row)
        self.stack.addWidget(page)

    def _show_page(self, index):
        """Switch pages with one consistent, presentation-only transition."""

        self.motion.transition(self.stack, int(index))

    def _update_char_counter(self):
        if self.char_counter is None:
            return
        count = len(self.initial_editor.toPlainText())
        self.char_counter.setText(f"{count:,} / {MAX_TARGET_INPUT_CHARS:,}")
        color = (
            palette(colorMode)["danger"]
            if count > MAX_TARGET_INPUT_CHARS
            else palette(colorMode)["muted"]
        )
        self.char_counter.setStyleSheet(f"color:{color};font-size:11px;")

    def _available_presets(self):
        store = getattr(self.app, "prompt_preset_store", None)
        return store.list_all() if store is not None else list(BUILTIN_PRESETS)

    def _reload_scene_combo(self, selected_id=None):
        if selected_id is None and hasattr(self, "scene_combo"):
            selected_id = self.scene_combo.currentData()
        selected_id = selected_id or self.app.config.get("prompt_workbench", {}).get(
            "default_scene", "smart"
        )
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        for preset in self._available_presets():
            self.scene_combo.addItem(preset.name, preset.preset_id)
            index = self.scene_combo.count() - 1
            self.scene_combo.setItemData(index, preset.description, QtCore.Qt.ItemDataRole.ToolTipRole)
        index = self.scene_combo.findData(selected_id)
        self.scene_combo.setCurrentIndex(max(0, index))
        self.scene_combo.blockSignals(False)

    def current_preset(self):
        preset_id = self.scene_combo.currentData() if hasattr(self, "scene_combo") else "smart"
        return next(
            (preset for preset in self._available_presets() if preset.preset_id == preset_id),
            BUILTIN_PRESETS[0],
        )

    def _scene_changed(self, index):
        del index
        preset = self.current_preset()
        self.scene_description.setText(preset.description)
        while self.variable_layout.rowCount():
            self.variable_layout.removeRow(0)
        self._variable_inputs = {}
        for variable in preset_variables(preset):
            editor = QtWidgets.QLineEdit()
            editor.setPlaceholderText(f"填写 {variable}；留空则保留 [{variable}]")
            self._variable_inputs[variable] = editor
            self.variable_layout.addRow(variable, editor)
        self.variable_box.setVisible(bool(self._variable_inputs))
        self.manage_preset_button.setVisible(not preset.builtin)
        if preset.preset_id == "review" and self.depth_combo.currentData() == "balanced":
            self.depth_combo.setCurrentIndex(self.depth_combo.findData("deep"))

    def create_custom_preset(self):
        store = getattr(self.app, "prompt_preset_store", None)
        if store is None:
            return
        dialog = PromptPresetDialog(self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        try:
            preset = store.save(**dialog.values())
        except ValueError as error:
            QtWidgets.QMessageBox.warning(self, "无法保存预设", str(error))
            return
        self._reload_scene_combo(preset.preset_id)
        self._scene_changed(self.scene_combo.currentIndex())

    def manage_custom_preset(self):
        preset = self.current_preset()
        store = getattr(self.app, "prompt_preset_store", None)
        if preset.builtin or store is None:
            return
        dialog = PromptPresetDialog(self, preset=preset)
        delete_button = QtWidgets.QPushButton("删除这个预设", dialog)
        delete_button.setStyleSheet(self._button_style(danger=True))
        dialog.layout().insertWidget(dialog.layout().count() - 1, delete_button)
        delete_button.clicked.connect(lambda: dialog.done(2))
        result = dialog.exec()
        if result == 2:
            answer = QtWidgets.QMessageBox.question(
                self, "删除场景", f"确定删除“{preset.name}”吗？"
            )
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                store.delete(preset.preset_id)
                self._reload_scene_combo("smart")
                self._scene_changed(self.scene_combo.currentIndex())
            return
        if result != QtWidgets.QDialog.DialogCode.Accepted:
            return
        updated = store.save(**dialog.values())
        self._reload_scene_combo(updated.preset_id)
        self._scene_changed(self.scene_combo.currentIndex())

    def load_library_prompt(self, prompt):
        if self.session:
            self.reset_session(confirm=False)
        self.initial_editor.setPlainText(str(prompt or ""))
        self.initial_editor.setFocus()
        self.initial_editor.selectAll()
        self.status_label.setText("已从收藏库载入；确认后再开始生成。")

    def _poll_capture(self):
        if self._capture_loaded:
            return
        holder = self.capture_holder
        if holder is None:
            self._finish_capture("")
            return
        if holder.ready.is_set():
            self._finish_capture(holder.text or "")
            return
        QtCore.QTimer.singleShot(50, self._poll_capture)

    def _finish_capture(self, text):
        if self._capture_loaded:
            return
        self._capture_loaded = True
        self.original_selected_text = str(text or "")
        if self.original_selected_text:
            self.initial_editor.setPlainText(self.original_selected_text)
            self.initial_editor.selectAll()
            self.status_label.setText("已带入当前选区；确认内容后再开始。")
            self.status_indicator.set_state("success")
        else:
            self.status_label.setText("未读取到选区，可以直接输入或粘贴。")
            self.status_indicator.set_state("idle")
        self.initial_editor.setFocus()

    def offer_new_capture(self, holder):
        """Bring the existing window forward without overwriting a session."""

        if self.session or self.initial_editor.toPlainText().strip():
            self.status_label.setText("工作台已有内容；请先重新开始，再带入新的选区。")
            return
        self.capture_holder = holder
        self.source_window_handle = getattr(holder, "source_window_handle", None)
        self.source_ime_state = getattr(holder, "ime_state", None)
        self._capture_loaded = False
        self._poll_capture()

    def start_session(self):
        text = self.initial_editor.toPlainText().strip()
        if not text:
            self.status_label.setText("请输入想优化的问题、需求或想法。")
            self.initial_editor.setFocus()
            return
        if len(text) > MAX_TARGET_INPUT_CHARS:
            self.status_label.setText(
                f"输入有 {len(text):,} 个字符，超过 {MAX_TARGET_INPUT_CHARS:,} 字符的安全上限；"
                "请缩短内容或改用支持更大上下文的模型。"
            )
            self.initial_editor.setFocus()
            return
        if not self.app.prompt_provider_is_configured():
            self.status_label.setText("Prompt AI 尚未配置。请先完成独立模型设置。")
            self.app.show_prompt_settings()
            return
        preferences = self.app.prompt_preference_store.load(
            enabled=bool(
                self.app.config.get("prompt_workbench", {}).get("memory_enabled", False)
            )
        )
        strategy = self.depth_combo.currentData() or "balanced"
        self.generation_strategy = strategy
        mode = {"fast": "quick", "balanced": "auto", "deep": "deep"}.get(
            strategy, "auto"
        )
        preset = self.current_preset()
        variable_values = {
            name: editor.text().strip()
            for name, editor in self._variable_inputs.items()
            if editor.text().strip()
        }
        compiled_input = render_preset_input(preset, text, variable_values)
        self.session = SharpInputSession(
            compiled_input,
            mode=mode,
            preferences=preferences,
            scene={
                "id": preset.preset_id,
                "name": preset.name,
                "instruction": preset.instruction,
            },
        )
        self._session_started_at = time.perf_counter()
        self._first_token_at = None
        self._transcript = [("你", f"{preset.name} · {text}")]
        self._render_transcript()
        self._show_page(1)
        self._set_processing("正在分析意图、场景和关键缺口…")
        self.app.dispatch_prompt_request(self, "compiler", self.session.start())

    def _set_processing(self, message):
        self._reset_stream_preview()
        self.status_label.setText(message)
        self.status_indicator.set_state("busy")
        self.retry_button.hide()
        self.answer_editor.setEnabled(False)
        self.answer_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

    def show_clarification(self, event: WorkflowEvent):
        self._reset_stream_preview()
        questions = []
        for item in event.questions:
            text = item.get("text", "")
            why = item.get("why", "")
            questions.append(text + (f"\n为什么要问：{why}" if why else ""))
        question_text = "\n\n".join(questions)
        self._transcript.append(("Prompt 编译器", question_text))
        self._render_transcript()
        self.answer_editor.clear()
        self.answer_editor.setEnabled(True)
        self.answer_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.answer_editor.setFocus()
        self.status_indicator.set_state("idle")
        self.status_label.setText(
            f"Level {event.level} · 只补充会显著影响最终 Prompt 的信息。"
        )

    def submit_answer(self, checked=False, *, skipped=False):
        del checked
        if not self.session:
            return
        answer = self.answer_editor.toPlainText().strip()
        if not skipped and not answer:
            self.status_label.setText("请输入回答，或选择“跳过，用占位符”。")
            return
        shown = "跳过，其余使用占位符" if skipped else answer
        self._transcript.append(("你", shown))
        self._render_transcript()
        self._set_processing("正在编译完整 Prompt…")
        messages = self.session.answer(answer, skipped=skipped)
        self.app.dispatch_prompt_request(self, "compiler", messages)

    def handle_workflow_event(self, event: WorkflowEvent):
        if self._closed:
            return
        if event.kind == "clarify":
            self.show_clarification(event)
        elif event.kind == "final":
            self.show_final(event)
        elif event.kind == "error":
            self.show_error(event.message)

    def show_final(self, event: WorkflowEvent):
        self._reset_stream_preview()
        payload = event.payload
        self._result_editors = []
        while self.result_tabs.count():
            widget = self.result_tabs.widget(0)
            self.result_tabs.removeTab(0)
            widget.deleteLater()
        paths = payload.get("paths") or []
        if len(paths) >= 2:
            for path in paths:
                self._add_result_editor(path.get("label", "路径"), path.get("prompt", ""))
        else:
            self._add_result_editor("最终 Prompt", payload.get("prompt", ""))
        judge = payload.get("judge") or {}
        meta = [f"Level {payload.get('level', event.level)}", "可直接编辑后复制"]
        if self._session_started_at is not None:
            total = time.perf_counter() - self._session_started_at
            if self._first_token_at is not None:
                meta.append(f"首字 {self._first_token_at - self._session_started_at:.1f}s")
            meta.append(f"完成 {total:.1f}s")
        if judge:
            meta.append(
                f"已完成质量复审：{judge.get('verdict', 'pass')} / 风险 {judge.get('risk_level', 'conditional')}"
            )
        self.result_meta.setText(" · ".join(meta))
        self._show_understanding(payload.get("understanding") or {})
        notes = []
        if payload.get("summary"):
            notes.append(payload["summary"])
        if payload.get("placeholders"):
            notes.append("待替换信息：" + "、".join(payload["placeholders"]))
        if payload.get("tradeoff"):
            notes.append("取舍：" + payload["tradeoff"])
        if judge.get("flip_condition"):
            notes.append("翻转条件：" + judge["flip_condition"])
        self.result_notes.setText("\n".join(notes))
        self._show_page(2)
        self.status_indicator.set_state("success")
        self.status_label.setText("Prompt 已生成；默认不会修改或发送到其他应用。")
        self.motion.stagger(
            [self.result_meta, self.understanding_title, self.result_tabs],
            interval=38,
            duration=170,
        )
        self._update_replace_state()

    def _add_result_editor(self, label, text):
        editor = QtWidgets.QPlainTextEdit(str(text or ""))
        editor.setStyleSheet(self._editor_style())
        editor.setAccessibleName(label)
        self._result_editors.append(editor)
        self.result_tabs.addTab(editor, label)

    def _show_understanding(self, understanding):
        if not isinstance(understanding, dict) or not understanding:
            self.understanding_title.hide()
            self.understanding_panel.hide()
            self.understanding_panel.clear()
            return
        labels = {
            "goal": "目标",
            "audience": "对象",
            "context": "已知背景",
            "constraints": "约束",
            "success_criteria": "成功标准",
            "assumptions": "当前假设",
            "open_items": "待补信息",
        }
        blocks = []
        for key, label in labels.items():
            value = understanding.get(key)
            if isinstance(value, (list, tuple)):
                value = "；".join(str(item) for item in value if str(item).strip())
            value = str(value or "").strip()
            if value:
                blocks.append(
                    f"<div style='margin:4px 0;'><b>{html.escape(label)}：</b>"
                    f"{html.escape(value)}</div>"
                )
        if not blocks:
            self.understanding_title.hide()
            self.understanding_panel.hide()
            return
        self.understanding_panel.setHtml("".join(blocks))
        self.understanding_title.show()
        self.understanding_panel.show()

    def current_prompt(self):
        index = self.result_tabs.currentIndex()
        if 0 <= index < len(self._result_editors):
            return self._result_editors[index].toPlainText().strip()
        return ""

    def copy_prompt(self):
        prompt = self.current_prompt()
        if not prompt:
            self.status_label.setText("当前 Prompt 为空，未复制。")
            return
        QtWidgets.QApplication.clipboard().setText(prompt)
        self.status_label.setText("Prompt 已复制到剪贴板。")
        self.status_indicator.set_state("success")

    def _update_replace_state(self, index=0):
        del index
        self.replace_button.setEnabled(
            bool(self.original_selected_text and self.source_window_handle and self.current_prompt())
        )
        self.replace_button.setToolTip(
            "先显示差异预览，再尝试回到原窗口应用。"
            if self.replace_button.isEnabled()
            else "只有从有效选区打开工作台时才能替换；仍可复制 Prompt。"
        )

    def replace_original(self):
        prompt = self.current_prompt()
        if not prompt:
            return
        self.app.preview_prompt_replacement(
            original=self.original_selected_text,
            result=prompt,
            source_window_handle=self.source_window_handle,
            ime_state=self.source_ime_state,
        )

    def save_favorite(self):
        prompt = self.current_prompt()
        store = getattr(self.app, "prompt_library_store", None)
        if not prompt or store is None:
            self.status_label.setText("当前 Prompt 为空，无法收藏。")
            return
        preset = self.current_preset()
        default_title = (self.initial_editor.toPlainText().strip().splitlines() or [preset.name])[0][:40]
        title, accepted = QtWidgets.QInputDialog.getText(
            self, "收藏 Prompt", "标题", text=default_title or preset.name
        )
        if not accepted or not title.strip():
            return
        tags_text, accepted = QtWidgets.QInputDialog.getText(
            self, "收藏 Prompt", "标签（可选，用逗号分隔）", text=preset.name
        )
        if not accepted:
            return
        tags = [item.strip() for item in tags_text.replace("，", ",").split(",") if item.strip()]
        existing = next(
            (item for item in store.list() if item.get("title") == title.strip()),
            None,
        )
        store.save(
            entry_id=existing.get("id", "") if existing else "",
            title=title.strip(),
            prompt=prompt,
            tags=tags,
            preset_id=preset.preset_id,
        )
        self.status_label.setText("已加密收藏到本机 Prompt 库。")

    def offer_fallback(self, kind, messages, error):
        config = self.app.config.get("prompt_workbench", {})
        if not config.get("fallback_enabled", True):
            return False
        provider_getter = getattr(self.app, "prompt_fallback_provider", None)
        provider = provider_getter() if provider_getter else None
        if provider is None:
            return False
        answer = QtWidgets.QMessageBox.question(
            self,
            "主模型暂时不可用",
            "当前 Prompt 模型请求失败。是否改用已配置的主写作模型重试？\n\n"
            "只有确认后才会发送，不会自动产生额外调用。\n"
            f"错误：{str(error)[:240]}",
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return False
        self._set_processing("正在切换备用模型…")
        self.app.dispatch_prompt_request(
            self,
            kind,
            messages,
            provider_override=provider,
            using_fallback=True,
        )
        return True

    def refine_prompt(self):
        instruction = self.refinement_input.text().strip()
        if not instruction or not self.session:
            self.status_label.setText("请输入具体修改要求。")
            return
        self.refinement_input.clear()
        self._show_page(1)
        self._transcript.append(("你", "继续修改：" + instruction))
        self._render_transcript()
        self._set_processing("正在按修改要求更新 Prompt…")
        messages = self.session.request_revision(instruction)
        self.app.dispatch_prompt_request(self, "compiler", messages)

    def cancel_request(self):
        self.app.cancel_prompt_request(self)
        self.status_label.setText("请求已取消；当前输入仍保留。")
        self.reset_session(confirm=False)

    def retry_request(self):
        if not self.session:
            return
        self._set_processing("正在重试 Prompt 请求…")
        kind = "judge" if self.session.stage == "judging" else "compiler"
        messages = (
            self.session.judge_messages()
            if kind == "judge"
            else self.session.compiler_messages()
        )
        self.app.dispatch_prompt_request(self, kind, messages)

    def reset_session(self, checked=False, *, confirm=True):
        del checked
        if confirm and self.session:
            answer = QtWidgets.QMessageBox.question(
                self,
                "重新开始",
                "确定清空当前内存会话并重新开始吗？",
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.app.cancel_prompt_request(self)
        self.session = None
        self._session_started_at = None
        self._first_token_at = None
        self.request_id = 0
        self._transcript = []
        self._result_editors = []
        self._reset_stream_preview()
        self._show_understanding({})
        self.answer_editor.clear()
        self.refinement_input.clear()
        self.retry_button.hide()
        self._show_page(0)
        self.initial_editor.setFocus()
        self.status_indicator.set_state("idle")
        self.status_label.setText("当前会话已清空；完整对话不会写入磁盘。")

    def show_error(self, message):
        self.answer_editor.setEnabled(False)
        self.answer_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.retry_button.show()
        self.status_indicator.set_state("error")
        self.status_label.setText(
            "Prompt 编译失败：" + str(message or "未知错误") + "。输入仍保留，可重新开始或检查设置。"
        )

    def note_generation_progress(self, preview=""):
        if self._first_token_at is None:
            self._first_token_at = time.perf_counter()
        visible = stream_visible_text(preview)
        if not visible:
            return
        if not visible.startswith(self._stream_rendered):
            self._stream_rendered = ""
            self.stream_preview.clear()
        self._stream_target = visible
        self.stream_preview_label.show()
        self.stream_preview.show()
        if not self._stream_rendered:
            self._stream_tick()
        if not self._stream_timer.isActive():
            self._stream_timer.start()

    def _stream_tick(self):
        if len(self._stream_rendered) >= len(self._stream_target):
            self._stream_timer.stop()
            return
        character = self._stream_target[len(self._stream_rendered)]
        self._stream_rendered += character
        self.stream_preview.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self.stream_preview.insertPlainText(character)
        bar = self.stream_preview.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _reset_stream_preview(self):
        timer = getattr(self, "_stream_timer", None)
        if timer is not None:
            timer.stop()
        self._stream_target = ""
        self._stream_rendered = ""
        preview = getattr(self, "stream_preview", None)
        label = getattr(self, "stream_preview_label", None)
        if preview is not None:
            preview.clear()
            preview.hide()
        if label is not None:
            label.hide()

    def _render_transcript(self):
        blocks = []
        for role, text in self._transcript:
            safe_role = html.escape(str(role))
            safe_text = html.escape(str(text)).replace("\n", "<br>")
            accent = "#8290ff" if role == "你" else "#5b69e9"
            blocks.append(
                f'<div style="margin:8px 0 14px 0;">'
                f'<div style="font-weight:650;color:{accent};margin-bottom:4px;">{safe_role}</div>'
                f'<div style="line-height:1.55;">{safe_text}</div></div>'
            )
        self.transcript.setHtml("".join(blocks))
        bar = self.transcript.verticalScrollBar()
        bar.setValue(bar.maximum())

    def closeEvent(self, event):
        self._closed = True
        self.app.cancel_prompt_request(self)
        self.session = None
        self._transcript = []
        for editor in self._result_editors:
            editor.clear()
        self._result_editors = []
        if getattr(self.app, "prompt_workbench_window", None) is self:
            self.app.prompt_workbench_window = None
        event.accept()


__all__ = ["PromptWorkbenchWindow"]
