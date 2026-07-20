import json
import logging
import os
import sys
from functools import partial

from pynput import keyboard as pykeyboard
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from prompting import normalize_options, option_display_name
from preset_share import export_preset_pack, load_preset_pack, merge_presets
from preset_icon_library import PRESET_ICON_CHOICES, normalize_preset_icon
from ui.ShortcutRecorder import ShortcutRecorder
from ui.UIUtils import ThemeBackground, colorMode
from quick_action_workflow import number_key_to_index

_ = lambda x: x

################################################################################
# Default `options.json` content to restore when the user presses "Reset"
################################################################################
DEFAULT_OPTIONS_JSON = r"""{
  "Proofread": {
    "prefix": "Proofread this:\n\n",
    "instruction": "You are a grammar proofreading assistant.\nOutput ONLY the corrected text without any additional comments.\nMaintain the original text structure and writing style.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with this (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/magnifying-glass",
    "open_in_window": false
  },
  "Rewrite": {
    "prefix": "Rewrite this:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to improve phrasing.\nOutput ONLY the rewritten text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with proofreading (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/rewrite",
    "open_in_window": false
  },
  "Friendly": {
    "prefix": "Make this more friendly:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more friendly.\nOutput ONLY the friendly text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/smiley-face",
    "open_in_window": false
  },
  "Professional": {
    "prefix": "Make this more professional:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more professional. Output ONLY the professional text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/briefcase",
    "open_in_window": false
  },
  "Concise": {
    "prefix": "Make this more concise:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more concise.\nOutput ONLY the concise text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/concise",
    "open_in_window": false
  },
  "Table": {
    "prefix": "Convert this into a table:\n\n",
    "instruction": "You are an assistant that converts text provided by the user into a Markdown table.\nOutput ONLY the table without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is completely incompatible with this with conversion, output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/table",
    "open_in_window": true
  },
  "Key Points": {
    "prefix": "Extract key points from this:\n\n",
    "instruction": "You are an assistant that extracts key points from text provided by the user. Output ONLY the key points without additional comments.\n\nYou should use Markdown formatting (lists, bold, italics, codeblocks, etc.) as appropriate to make it quite legible and readable.\n\nDon't be repetitive or too verbose.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with extracting key points (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/keypoints",
    "open_in_window": true
  },
  "Summary": {
    "prefix": "Summarize this:\n\n",
    "instruction": "You are a summarization assistant.\nProvide a succinct summary of the text provided by the user.\nThe summary should be succinct yet encompass all the key insightful points.\n\nTo make it quite legible and readable, you should use Markdown formatting (bold, italics, codeblocks...) as appropriate.\nYou should also add a little line spacing between your paragraphs as appropriate.\nAnd only if appropriate, you could also use headings (only the very small ones), lists, tables, etc.\n\nDon't be repetitive or too verbose.\nOutput ONLY the summary without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with summarisation (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/summary",
    "open_in_window": true
  },
  "Custom": {
    "prefix": "Make this change to the following text:\n\n",
    "instruction": "You are a writing and coding assistant. You MUST make the user\\'s described change to the text or code provided by the user. Output ONLY the appropriately modified text or code without additional comments. Respond in the same language as the input (e.g., English US, French). Do not answer or respond to the user\\'s text content. If the text or code is absolutely incompatible with the requested change, output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/summary",
    "open_in_window": false
  }
}"""

class PresetIconPicker(QWidget):
    """Compact visual library backed by the app's real PNG icon set."""

    def __init__(self, selected_icon, parent=None):
        super().__init__(parent)
        self.selected_icon = normalize_preset_icon(selected_icon)
        self.buttons_by_icon = {}
        self.button_group = QtWidgets.QButtonGroup(self)
        self.button_group.setExclusive(True)

        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)

        for index, (icon_id, label) in enumerate(PRESET_ICON_CHOICES):
            button = QtWidgets.QToolButton()
            button.setCheckable(True)
            button.setText(label)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(QtCore.QSize(22, 22))
            button.setFixedSize(82, 58)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(f"选择图标：{label}")
            button.setToolTip(f"使用“{label}”图标")
            icon_path = os.path.join(
                os.path.dirname(sys.argv[0]),
                f"{icon_id}_{'dark' if colorMode == 'dark' else 'light'}.png",
            )
            if os.path.exists(icon_path):
                button.setIcon(QtGui.QIcon(icon_path))
            button.setStyleSheet(f"""
                QToolButton {{
                    border: 1px solid {'#4f566a' if colorMode == 'dark' else '#e0e3eb'};
                    border-radius: 9px;
                    background: {'#2a2e39' if colorMode == 'dark' else '#fdfdff'};
                    color: {'#e8ebf7' if colorMode == 'dark' else '#485065'};
                    font-size: 11px;
                    padding: 4px;
                }}
                QToolButton:hover {{
                    border-color: #aab3f8;
                    background: {'#343a48' if colorMode == 'dark' else '#f4f6ff'};
                }}
                QToolButton:checked {{
                    border: 1px solid #6f7df0;
                    background: {'#3d466c' if colorMode == 'dark' else '#edf0ff'};
                    color: {'#ffffff' if colorMode == 'dark' else '#3042ad'};
                    font-weight: 600;
                }}
            """)
            button.clicked.connect(
                lambda checked=False, chosen_icon=icon_id: self.set_selected_icon(
                    chosen_icon
                )
            )
            self.button_group.addButton(button)
            self.buttons_by_icon[icon_id] = button
            grid.addWidget(button, index // 6, index % 6)

        self.set_selected_icon(self.selected_icon)

    def set_selected_icon(self, icon_name):
        self.selected_icon = normalize_preset_icon(icon_name)
        self.buttons_by_icon[self.selected_icon].setChecked(True)


class ButtonEditDialog(QDialog):
    """
    Dialog for editing or creating a button's properties
    (name/title, system instruction, open_in_window, etc.).
    """
    def __init__(self, parent=None, button_data=None, title="编辑预设"):
        super().__init__(parent)
        self.button_data = button_data if button_data else {
            "prefix": "Make this change to the following text:\n\n",
            "instruction": "",
            "icon": "icons/magnifying-glass",
            "open_in_window": False,
            "uses_base_instruction": True,
        }
        # The hotkey input is created in init_ui; tracked here so the
        # parent window can read it back from get_button_data().
        self.hotkey_input = None
        self.icon_picker = None
        self.setWindowTitle(title)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.resize(620, 730)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        intro = QLabel("预设只需描述目标；程序会自动附加稳定的基础指令，约束模型只输出处理后的文本、保持原语言和格式。")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #69708a; font-size: 12px; padding: 10px 12px; background: #f1f3ff; border-radius: 9px;")
        layout.addWidget(intro)

        # Name
        name_label = QLabel("预设名称")
        name_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold;")
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px;
                border: 1px solid {'#777' if colorMode == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if colorMode == 'dark' else 'white'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
            }}
        """)
        if "name" in self.button_data:
            self.name_input.setText(self.button_data["name"])
        layout.addWidget(name_label)
        layout.addWidget(self.name_input)

        icon_label = QLabel("预设图标")
        icon_label.setStyleSheet(
            f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold;"
        )
        layout.addWidget(icon_label)
        self.icon_picker = PresetIconPicker(
            self.button_data.get("icon", "icons/custom"), self
        )
        layout.addWidget(self.icon_picker)
        
        # Instruction (changed to a multiline QPlainTextEdit)
        instruction_label = QLabel("希望 AI 如何处理所选文本？")
        instruction_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold;")
        self.instruction_input = QPlainTextEdit()
        self.instruction_input.setStyleSheet(f"""
            QPlainTextEdit {{
                padding: 8px;
                border: 1px solid {'#777' if colorMode == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if colorMode == 'dark' else 'white'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
            }}
        """)
        self.instruction_input.setPlainText(self.button_data.get("instruction", ""))
        self.instruction_input.setMinimumHeight(100)
        self.instruction_input.setPlaceholderText("例如：翻译为中文；改成更温和的语气；提取待办事项；解释并修复这段代码。")
        layout.addWidget(instruction_label)
        layout.addWidget(self.instruction_input)
        
        # open_in_window
        display_label = QLabel("结果显示方式")
        display_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold;")
        layout.addWidget(display_label)
        
        radio_layout = QHBoxLayout()
        self.replace_radio = QRadioButton("直接替换所选文本")
        self.window_radio = QRadioButton("在结果窗口中显示（支持追问）")
        for r in (self.replace_radio, self.window_radio):
            r.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'};")
        
        self.replace_radio.setChecked(not self.button_data.get("open_in_window", False))
        self.window_radio.setChecked(self.button_data.get("open_in_window", False))

        radio_layout.addWidget(self.replace_radio)
        radio_layout.addWidget(self.window_radio)
        layout.addLayout(radio_layout)

        # Direct hotkey (optional). Lets the user fire this button from
        # anywhere without opening the popup first. Stored per-button in
        # options.json under a "hotkey" key; absent = no hotkey, which is
        # how every existing/legacy button starts.
        hotkey_label = QLabel("独立快捷键（可选）")
        hotkey_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold;")
        layout.addWidget(hotkey_label)

        self.hotkey_input = ShortcutRecorder()
        self.hotkey_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px;
                border: 1px solid {'#777' if colorMode == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if colorMode == 'dark' else 'white'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
            }}
        """)
        self.hotkey_input.setPlaceholderText("点击后直接按下组合键")
        self.hotkey_input.setText(self.button_data.get("hotkey", ""))
        layout.addWidget(self.hotkey_input)

        hotkey_hint = QLabel("点击输入框后直接按下组合键即可录入；Backspace/Delete 清除，Esc 取消。设置后可在任意位置直接运行此预设。")
        hotkey_hint.setStyleSheet(
            f"color: {'#bbb' if colorMode == 'dark' else '#555'}; font-size: 12px;"
        )
        hotkey_hint.setWordWrap(True)
        layout.addWidget(hotkey_hint)

        # Save & Cancel
        btn_layout = QHBoxLayout()
        ok_button = QPushButton("保存")
        cancel_button = QPushButton("取消")
        cancel_button.setStyleSheet("QPushButton { background: #f2f3f7; color: #45495a; border: none; border-radius: 9px; padding: 9px 18px; }")
        ok_button.setStyleSheet("QPushButton { background: #5967e8; color: white; border: none; border-radius: 9px; padding: 9px 22px; font-weight: 600; } QPushButton:hover { background: #4d5ad2; }")
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_button)
        btn_layout.addWidget(ok_button)
        layout.addLayout(btn_layout)
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {'#222' if colorMode == 'dark' else '#fbfbfd'};
                border-radius: 14px;
            }}
        """)

    def get_button_data(self):
        data = {
            "name": self.name_input.text(),
            "prefix": "Make this change to the following text:\n\n",
            # Retrieve multiline text
            "instruction": self.instruction_input.toPlainText(),
            "icon": self.icon_picker.selected_icon,
            "open_in_window": self.window_radio.isChecked(),
            "uses_base_instruction": True,
        }
        # Only include `hotkey` if the user actually typed one. Old
        # configs and buttons-without-hotkeys stay shaped exactly as
        # before — no empty-string clutter in options.json.
        hotkey = self.hotkey_input.text().strip().lower() if self.hotkey_input else ""
        if hotkey:
            data["hotkey"] = hotkey
        return data

class DraggableButton(QtWidgets.QPushButton):
    def __init__(self, parent_popup, key, text):
        super().__init__(text, parent_popup)
        self.popup = parent_popup
        self.key = key
        self.drag_start_position = None
        self.setAcceptDrops(True)
        self.icon_container = None

        # Enable mouse tracking and hover events, and styled background
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        # Dynamic properties drive hover and keyboard-selection states.
        self.setProperty("hover", False)
        self.setProperty("selected", False)
        self.shortcut_badge = QLabel(self)
        self.shortcut_badge.setAlignment(Qt.AlignCenter)
        self.shortcut_badge.setStyleSheet(self.badge_style())
        self.shortcut_badge.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self.setMinimumWidth(348)
        self.setFixedHeight(46)
        self.setIconSize(QtCore.QSize(19, 19))

        self.base_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-bottom: 1px solid {'rgba(255,255,255,18)' if colorMode == 'dark' else '#e8eaf1'};
                border-radius: 0;
                padding: 8px 42px 8px 10px;
                font-family: "Microsoft YaHei UI", "Segoe UI Variable";
                font-size: 14px;
                text-align: left;
                color: {"#f4f6ff" if colorMode=="dark" else "#202638"};
            }}
            QPushButton[hover="true"] {{
                background-color: {"rgba(82, 94, 145, 95)" if colorMode=="dark" else "rgba(240, 243, 255, 210)"};
            }}
            QPushButton[selected="true"] {{
                background-color: {"rgba(83, 99, 187, 118)" if colorMode=="dark" else "rgba(235, 239, 255, 235)"};
                border-left: 3px solid #6675ee;
                color: {"#ffffff" if colorMode=="dark" else "#26358d"};
                font-weight: 600;
            }}
        """
        self.setStyleSheet(self.base_style)
        logging.debug("DraggableButton initialized")

    @staticmethod
    def badge_style(selected=False):
        border = "#7482ef" if selected else ("#555d72" if colorMode == "dark" else "#d9dce6")
        text = "#7f8cff" if selected and colorMode == "dark" else (
            "#4d5fd1" if selected else ("#dfe2f3" if colorMode == "dark" else "#697084")
        )
        return f"""
            QLabel {{
                min-width: 23px;
                max-width: 23px;
                min-height: 23px;
                max-height: 23px;
                border: 1px solid {border};
                border-radius: 6px;
                background: {'rgba(255,255,255,16)' if colorMode == 'dark' else 'rgba(255,255,255,205)'};
                color: {text};
                font-size: 12px;
                font-weight: {600 if selected else 500};
            }}
        """

    def enterEvent(self, event):
        # Only update the hover property if NOT in edit mode.
        if not self.popup.edit_mode:
            self.popup.set_selected_index(self.popup.button_widgets.index(self))
            self.setProperty("hover", True)
            self.style().unpolish(self)
            self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.popup.edit_mode:
            self.setProperty("hover", False)
            self.style().unpolish(self)
            self.style().polish(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.popup.edit_mode:
                self.drag_start_position = event.pos()
                event.accept()
                return
        super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if not (event.buttons() & QtCore.Qt.LeftButton) or not self.drag_start_position:
            return

        distance = (event.pos() - self.drag_start_position).manhattanLength()
        if distance < QtWidgets.QApplication.startDragDistance():
            return

        if self.popup.edit_mode:
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            idx = self.popup.button_widgets.index(self)
            mime_data.setData("application/x-button-index", str(idx).encode())
            drag.setMimeData(mime_data)

            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())

            self.drag_start_position = None
            drop_action = drag.exec_(QtCore.Qt.MoveAction)
            logging.debug(f"Drag completed with action: {drop_action}")

    def dragEnterEvent(self, event):
        if self.popup.edit_mode and event.mimeData().hasFormat("application/x-button-index"):
            event.acceptProposedAction()
            self.setStyleSheet(self.base_style + """
                QPushButton {
                    border: 2px dashed #666;
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.base_style)
        event.accept()

    def dropEvent(self, event):
        if not self.popup.edit_mode or not event.mimeData().hasFormat("application/x-button-index"):
            event.ignore()
            return

        source_idx = int(event.mimeData().data("application/x-button-index").data().decode())
        target_idx = self.popup.button_widgets.index(self)

        if source_idx != target_idx:
            bw = self.popup.button_widgets
            bw[source_idx], bw[target_idx] = bw[target_idx], bw[source_idx]
            self.popup.rebuild_grid_layout()
            self.popup.update_json_from_grid()

        self.setStyleSheet(self.base_style)
        event.setDropAction(QtCore.Qt.MoveAction)
        event.acceptProposedAction()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.shortcut_badge.setGeometry(self.width() - 34, 11, 23, 23)
        self.shortcut_badge.raise_()
        if self.icon_container:
            self.icon_container.setGeometry(self.width() - 68, 7, 64, 32)


class ToggleSwitch(QtWidgets.QAbstractButton):
    """Compact keyboard-accessible switch used for quick-run mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(44, 24)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        track = QtCore.QRectF(0, 0, self.width(), self.height())
        if self.isChecked():
            track_color = QtGui.QColor("#5967e8")
            knob_x = self.width() - 21
        else:
            track_color = QtGui.QColor("#555b6e" if colorMode == "dark" else "#cfd3df")
            knob_x = 3
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 12, 12)
        painter.setBrush(QtGui.QColor("#ffffff"))
        painter.drawEllipse(QtCore.QRectF(knob_x, 3, 18, 18))

        if self.hasFocus():
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor("#8792ff"), 1))
            painter.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)

class CustomPopupWindow(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.edit_mode = False

        self.drag_label = None
        self.edit_button = None
        self.reset_button = None
        self.close_button = None
        self.custom_input = None
        self.input_area = None
        self.actions_container = None
        self.actions_layout = None
        self.preset_share_surface = None
        self.last_action_label = None
        self.remember_checkbox = None
        self.selected_index = 0

        self.button_widgets = []

        logging.debug('Initializing CustomPopupWindow')
        self.init_ui()

    def init_ui(self):
        logging.debug('Setting up CustomPopupWindow UI')
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowTitle("写作工具")
        self.setFixedWidth(404)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background = ThemeBackground(
            self,
            self.app.config.get('theme', 'plain'),
            is_popup=True,
            border_radius=20,
            custom_background_path=self.app.config.get('custom_background_path', ''),
        )
        main_layout.addWidget(self.background)

        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(22, 18, 22, 16)
        content_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        brand_icon = QLabel()
        pencil_icon = os.path.join(
            os.path.dirname(sys.argv[0]),
            'icons',
            'pencil' + ('_dark' if colorMode == 'dark' else '_light') + '.png',
        )
        app_icon = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
        if os.path.exists(app_icon):
            brand_icon.setPixmap(QtGui.QPixmap(app_icon).scaled(
                26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        top_bar.addWidget(brand_icon)

        title_label = QLabel("写作工具")
        title_label.setStyleSheet(f"""
            color: {'#f7f8ff' if colorMode == 'dark' else '#242632'};
            font-family: "Microsoft YaHei UI", "Segoe UI Variable";
            font-size: 21px;
            font-weight: 650;
        """)
        top_bar.addWidget(title_label)
        top_bar.addStretch()

        self.utility_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background: {'rgba(255,255,255,30)' if colorMode == 'dark' else 'rgba(61,70,110,18)'};
            }}
        """

        self.edit_button = QPushButton()
        self.edit_button.setIcon(QtGui.QIcon(pencil_icon))
        self.edit_button.setIconSize(QtCore.QSize(17, 17))
        self.edit_button.setFixedSize(28, 28)
        self.edit_button.setStyleSheet(self.utility_style)
        self.edit_button.setToolTip("编辑预设")
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        top_bar.addWidget(self.edit_button)

        self.reset_button = QPushButton()
        reset_icon_path = os.path.join(
            os.path.dirname(sys.argv[0]), 'icons',
            'restore' + ('_dark' if colorMode == 'dark' else '_light') + '.png',
        )
        if os.path.exists(reset_icon_path):
            self.reset_button.setIcon(QtGui.QIcon(reset_icon_path))
        self.reset_button.setFixedSize(28, 28)
        self.reset_button.setStyleSheet(self.utility_style)
        self.reset_button.setToolTip("恢复默认预设")
        self.reset_button.clicked.connect(self.on_reset_clicked)
        self.reset_button.hide()
        top_bar.addWidget(self.reset_button)

        self.close_button = QPushButton()
        self.close_button.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarCloseButton)
        )
        self.close_button.setFixedSize(28, 28)
        self.close_button.setStyleSheet(self.utility_style)
        self.close_button.setToolTip("关闭")
        self.close_button.clicked.connect(self.close)
        top_bar.addWidget(self.close_button)
        content_layout.addLayout(top_bar)

        self.drag_label = QLabel("拖动预设可调整顺序")
        self.drag_label.setAlignment(Qt.AlignCenter)
        self.drag_label.setStyleSheet(
            f"color: {'#cfd3ea' if colorMode == 'dark' else '#69708a'}; font-size: 12px;"
        )
        self.drag_label.hide()
        content_layout.addWidget(self.drag_label)

        remember_row = QHBoxLayout()
        remember_row.setContentsMargins(0, 0, 0, 0)
        remember_label = QLabel("记住上次操作")
        remember_label.setStyleSheet(
            f"color: {'#e6e8f5' if colorMode == 'dark' else '#45495a'}; font-size: 13px;"
        )
        remember_row.addWidget(remember_label)
        remember_row.addStretch()
        self.remember_checkbox = ToggleSwitch()
        self.remember_checkbox.setChecked(
            self.app.config.get('remember_last_action', False)
        )
        self.remember_checkbox.setToolTip("开启后，主快捷键会直接运行上一次使用的预设")
        self.remember_checkbox.setAccessibleName("记住上次操作")
        self.remember_checkbox.toggled.connect(self.on_remember_toggled)
        remember_row.addWidget(self.remember_checkbox)

        self.last_action_label = QLabel()
        self.last_action_label.setStyleSheet(
            f"color: {'#b9bfd9' if colorMode == 'dark' else '#69708a'}; font-size: 12px;"
        )

        self.input_area = QWidget()
        input_layout = QHBoxLayout(self.input_area)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("描述你想要的修改…")
        custom_icon_path = os.path.join(
            os.path.dirname(sys.argv[0]), 'icons',
            'custom' + ('_dark' if colorMode == 'dark' else '_light') + '.png',
        )
        if os.path.exists(custom_icon_path):
            self.custom_input.addAction(
                QtGui.QIcon(custom_icon_path),
                QLineEdit.ActionPosition.LeadingPosition,
            )
        self.custom_input.setMinimumHeight(46)
        self.custom_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 9px 13px;
                border: 1px solid {'rgba(255,255,255,35)' if colorMode == 'dark' else 'rgba(66,76,110,35)'};
                border-radius: 12px;
                background: {'rgba(31,35,46,225)' if colorMode == 'dark' else 'rgba(255,255,255,238)'};
                color: {'#f7f8ff' if colorMode == 'dark' else '#242632'};
                font-family: "Microsoft YaHei UI", "Segoe UI Variable";
                font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid #7f8cff; }}
        """)
        self.custom_input.returnPressed.connect(self.on_custom_change)
        input_layout.addWidget(self.custom_input)

        send_btn = QPushButton()
        send_icon = os.path.join(
            os.path.dirname(sys.argv[0]), 'icons',
            'send' + ('_dark' if colorMode == 'dark' else '_light') + '.png',
        )
        if os.path.exists(send_icon):
            send_btn.setIcon(QtGui.QIcon(send_icon))
        send_btn.setIconSize(QtCore.QSize(18, 18))
        send_btn.setFixedSize(46, 46)
        send_btn.setToolTip("执行自定义修改")
        send_btn.setStyleSheet("""
            QPushButton { background: #5b69e9; border: none; border-radius: 12px; }
            QPushButton:hover { background: #4f5edc; }
            QPushButton:pressed { background: #4452c7; }
        """)
        send_btn.clicked.connect(self.on_custom_change)
        input_layout.addWidget(send_btn)
        content_layout.addWidget(self.input_area)

        self.actions_container = QWidget()
        self.actions_layout = QtWidgets.QVBoxLayout(self.actions_container)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(0)
        content_layout.addWidget(self.actions_container)

        self.build_buttons_list()
        self.rebuild_grid_layout()
        self.update_last_action_label()

        self.preset_share_surface = QWidget()
        share_layout = QHBoxLayout(self.preset_share_surface)
        share_layout.setContentsMargins(0, 0, 0, 0)
        share_layout.setSpacing(8)
        import_button = QPushButton("导入预设包")
        export_button = QPushButton("导出并分享")
        share_button_style = f"""
            QPushButton {{
                min-height: 34px;
                padding: 4px 10px;
                border: 1px solid {'#555d72' if colorMode == 'dark' else '#dfe2ea'};
                border-radius: 9px;
                background: {'rgba(255,255,255,12)' if colorMode == 'dark' else '#f8f9fc'};
                color: {'#e8ebf8' if colorMode == 'dark' else '#51586f'};
                font-size: 12px;
            }}
            QPushButton:hover {{ border-color: #7f8cff; background: {'#373d4b' if colorMode == 'dark' else '#eef1ff'}; }}
        """
        import_button.setStyleSheet(share_button_style)
        export_button.setStyleSheet(share_button_style)
        import_button.clicked.connect(self.import_presets)
        export_button.clicked.connect(self.export_presets)
        share_layout.addWidget(import_button)
        share_layout.addWidget(export_button)
        self.preset_share_surface.hide()
        content_layout.addWidget(self.preset_share_surface)

        remember_surface = QWidget()
        remember_surface.setObjectName("rememberSurface")
        remember_surface.setStyleSheet(f"""
            QWidget#rememberSurface {{
                background: {'rgba(255,255,255,12)' if colorMode == 'dark' else 'rgba(245,247,252,210)'};
                border: 1px solid {'rgba(255,255,255,18)' if colorMode == 'dark' else '#e7e9f0'};
                border-radius: 10px;
            }}
        """)
        remember_surface_layout = QVBoxLayout(remember_surface)
        remember_surface_layout.setContentsMargins(12, 9, 12, 9)
        remember_surface_layout.setSpacing(3)
        remember_surface_layout.addLayout(remember_row)
        remember_surface_layout.addWidget(self.last_action_label)
        content_layout.addWidget(remember_surface)

        shortcut_help = QLabel("Esc 关闭  ·  ↑↓ 选择  ·  Enter 执行  ·  数字键快速选择")
        shortcut_help.setAlignment(Qt.AlignCenter)
        shortcut_help.setStyleSheet(
            f"color: {'#979eb6' if colorMode == 'dark' else '#858ca0'}; font-size: 11px;"
        )
        content_layout.addWidget(shortcut_help)

        if self.app.config.get("update_available", False):
            update_label = QLabel(
                '<a href="https://github.com/theJayTea/WritingTools/releases" '
                'style="color:#5967e8; text-decoration:none;">发现新版本，前往下载</a>'
            )
            update_label.setOpenExternalLinks(True)
            content_layout.addWidget(update_label, alignment=Qt.AlignCenter)

        logging.debug('CustomPopupWindow UI setup complete')
        self.installEventFilter(self)
        QtCore.QTimer.singleShot(0, self.setFocus)

    @staticmethod
    def load_options():
        options_path = os.path.join(os.path.dirname(sys.argv[0]), 'options.json')
        data = {}
        if os.path.exists(options_path):
            with open(options_path, 'r', encoding='utf-8') as f:
                data = normalize_options(json.load(f))
                logging.debug('Options loaded successfully')
        else:
            logging.debug('Options file not found')

        return data

    @staticmethod
    def save_options(options):
        options_path = os.path.join(os.path.dirname(sys.argv[0]), 'options.json')
        with open(options_path, 'w', encoding='utf-8') as f:
            json.dump(options, f, indent=2, ensure_ascii=False)

    def refresh_runtime_options(self):
        """Apply option and direct-hotkey changes immediately."""
        self.app.load_options()
        self.app.start_hotkey_listener()

    def build_buttons_list(self):
        """
        Reads options.json, creates DraggableButton for each (except "Custom"),
        storing them in self.button_widgets in the same order as the JSON file.
        """
        self.button_widgets.clear()
        data = self.load_options()

        for k,v in data.items():
            if k=="Custom":
                continue
            display_name = option_display_name(k, v)
            b = DraggableButton(self, k, display_name)
            b.display_name = display_name
            icon_path = os.path.join(os.path.dirname(sys.argv[0]),
                                    v["icon"] + ('_dark' if colorMode=='dark' else '_light') + '.png')
            if os.path.exists(icon_path):
                b.setIcon(QtGui.QIcon(icon_path))

            # Tooltip surfaces the direct hotkey (if any) for discoverability.
            # Buttons without a hotkey get no tooltip — keeps things uncluttered.
            hotkey = (v.get("hotkey") or "").strip()
            if hotkey:
                b.setToolTip(f"全局快捷键：{hotkey}")

            if not self.edit_mode:
                b.clicked.connect(partial(self.on_generic_instruction, k))
            self.button_widgets.append(b)

    def rebuild_grid_layout(self, parent_layout=None):
        """Rebuild the keyboard-first single-column action list."""
        if self.actions_layout is None:
            return

        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget and widget not in self.button_widgets:
                widget.deleteLater()

        for index, button in enumerate(self.button_widgets):
            button.setText(f"{index + 1}    {button.display_name}")
            button.shortcut_badge.setText(str(index + 1))
            self.actions_layout.addWidget(button)

        if self.edit_mode:
            add_btn = QPushButton("＋ 新增预设")
            add_btn.setFixedHeight(42)
            add_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px dashed {'#7b83a8' if colorMode=='dark' else '#9aa2c4'};
                    border-radius: 11px;
                    padding: 8px;
                    font-size: 13px;
                    text-align: center;
                    color: {'#d8dbea' if colorMode=='dark' else '#596079'};
                }}
                QPushButton:hover {{
                    background: {'rgba(255,255,255,22)' if colorMode=='dark' else 'rgba(89,103,232,14)'};
                }}
            """)
            add_btn.clicked.connect(self.add_new_button_clicked)
            self.actions_layout.addWidget(add_btn)

        self.set_selected_index(min(self.selected_index, max(0, len(self.button_widgets) - 1)))

    def add_edit_delete_icons(self, btn):
        """Place edit actions in a dedicated right-side rail."""
        if hasattr(btn, 'icon_container') and btn.icon_container:
            btn.icon_container.deleteLater()
        
        btn.icon_container = QtWidgets.QWidget(btn)
        btn.icon_container.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        btn.icon_container.setGeometry(btn.width() - 68, 7, 64, 32)
        
        circle_style = f"""
            QPushButton {{
                background-color: {'rgba(255,255,255,12)' if colorMode=='dark' else 'rgba(255,255,255,210)'};
                border: 1px solid {'#555d72' if colorMode=='dark' else '#dfe2ea'};
                border-radius: 7px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background-color: {'#3d466c' if colorMode=='dark' else '#edf0ff'};
                border-color: #8e99ef;
            }}
        """
        
        edit_btn = QPushButton(btn.icon_container)
        edit_btn.setGeometry(2, 3, 26, 26)
        edit_btn.setIconSize(QtCore.QSize(15, 15))
        pencil_icon = os.path.join(os.path.dirname(sys.argv[0]),
                        'icons', 'pencil' + ('_dark' if colorMode=='dark' else '_light') + '.png')
        if os.path.exists(pencil_icon):
            edit_btn.setIcon(QtGui.QIcon(pencil_icon))
        edit_btn.setStyleSheet(circle_style)
        edit_btn.setToolTip("编辑预设")
        edit_btn.setAccessibleName(f"编辑{btn.display_name}")
        edit_btn.clicked.connect(partial(self.edit_button_clicked, btn))
        edit_btn.show()
        
        delete_btn = QPushButton(btn.icon_container)
        delete_btn.setGeometry(34, 3, 26, 26)
        delete_btn.setIconSize(QtCore.QSize(15, 15))
        del_icon = os.path.join(os.path.dirname(sys.argv[0]),
                                'icons', 'cross' + ('_dark' if colorMode=='dark' else '_light') + '.png')
        if os.path.exists(del_icon):
            delete_btn.setIcon(QtGui.QIcon(del_icon))
        delete_btn.setStyleSheet(circle_style)
        delete_btn.setToolTip("删除预设")
        delete_btn.setAccessibleName(f"删除{btn.display_name}")
        delete_btn.clicked.connect(partial(self.delete_button_clicked, btn))
        delete_btn.show()
        
        btn.icon_container.raise_()
        btn.icon_container.show()

    def toggle_edit_mode(self):
        """Toggle edit mode with improved button labels and state handling."""
        self.edit_mode = not self.edit_mode
        logging.debug(f'Edit mode toggled: {self.edit_mode}')

        if self.edit_mode:
            # Switch to edit mode:
            icon_name = "check"
            # No text, just the check icon, a bit bigger:
            self.edit_button.setText("")
            self.edit_button.setFixedSize(28, 28)
            self.edit_button.setStyleSheet(self.utility_style)
            self.edit_button.setToolTip("完成编辑")
            # Hide close, show reset button & drag label
            self.close_button.hide()
            self.reset_button.show()
            self.drag_label.show()
            self.preset_share_surface.show()

        else:
            # Switch back to normal (non-edit) mode:
            icon_name = "pencil"
            self.edit_button.setText("")
            self.edit_button.setFixedSize(28, 28)
            self.edit_button.setStyleSheet(self.utility_style)
            self.edit_button.setToolTip("编辑预设")
            # Show close, hide reset & drag label
            self.close_button.show()
            self.reset_button.hide()
            self.drag_label.hide()
            self.preset_share_surface.hide()

            self.refresh_runtime_options()


        # Update the edit button icon now that icon_name is defined
        icon_path = os.path.join(
            os.path.dirname(sys.argv[0]),
            'icons',
            f"{icon_name}_{'dark' if colorMode=='dark' else 'light'}.png"
        )
        if os.path.exists(icon_path):
            self.edit_button.setIcon(QtGui.QIcon(icon_path))

        # Toggle the main input area
        self.input_area.setVisible(not self.edit_mode)

        # Update button overlays
        for btn in self.button_widgets:
            btn.shortcut_badge.setVisible(not self.edit_mode)
            try:
                btn.clicked.disconnect()
            except (RuntimeError, TypeError):
                logging.debug("Preset button had no signal connection to disconnect")

            if not self.edit_mode:
                btn.clicked.connect(partial(self.on_generic_instruction, btn.key))
                if hasattr(btn, 'icon_container') and btn.icon_container:
                    btn.icon_container.deleteLater()
                    btn.icon_container = None
            else:
                self.add_edit_delete_icons(btn)

            btn.setStyleSheet(
                btn.base_style
                + ("QPushButton { padding-right: 82px; }" if self.edit_mode else "")
            )

        # Rebuild grid layout
        self.rebuild_grid_layout()

    def export_presets(self):
        """Export a versioned, secret-free preset pack as UTF-8 JSON."""
        default_path = os.path.join(
            QtCore.QStandardPaths.writableLocation(
                QtCore.QStandardPaths.StandardLocation.DocumentsLocation
            ),
            "写作工具预设包.json",
        )
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出预设包", default_path, "Writing Tools 预设包 (*.json)"
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    export_preset_pack(self.load_options()),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.write("\n")
            QtWidgets.QMessageBox.information(
                self,
                "导出完成",
                "预设包已保存。文件只包含预设名称、提示词、图标和快捷键，不包含 API 密钥。",
            )
        except Exception as error:
            QtWidgets.QMessageBox.warning(self, "导出失败", str(error))

    def import_presets(self):
        """Validate and merge a shared preset pack without overwriting local presets."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "导入预设包",
            QtCore.QStandardPaths.writableLocation(
                QtCore.QStandardPaths.StandardLocation.DocumentsLocation
            ),
            "Writing Tools 预设包 (*.json);;JSON 文件 (*.json)",
        )
        if not path:
            return
        try:
            imported = load_preset_pack(path)
            merged, notices = merge_presets(
                self.load_options(),
                imported,
                self.app.config.get("shortcut", "ctrl+space"),
            )
            self.save_options(merged)
            self.refresh_runtime_options()
            self.build_buttons_list()
            self.rebuild_grid_layout()
            summary = f"已安全导入 {len(imported)} 个预设；同名预设会自动重命名。"
            if notices:
                summary += "\n\n" + "\n".join(notices[:6])
                if len(notices) > 6:
                    summary += f"\n另有 {len(notices) - 6} 条快捷键冲突已自动处理。"
            QtWidgets.QMessageBox.information(self, "导入完成", summary)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "导入失败", str(error))


    def on_reset_clicked(self):
        """
        Reset `options.json` to the defaults and apply it immediately.
        """
        confirm_box = QtWidgets.QMessageBox()
        confirm_box.setWindowTitle("恢复默认预设？")
        confirm_box.setText("这会恢复内置预设并移除自定义排序。是否继续？")
        confirm_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        confirm_box.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if confirm_box.exec_() == QtWidgets.QMessageBox.Yes:
            try:
                logging.debug('Resetting to default options.json')
                default_data = json.loads(DEFAULT_OPTIONS_JSON)
                self.save_options(default_data)

                self.refresh_runtime_options()
                self.build_buttons_list()
                self.rebuild_grid_layout()
                QtWidgets.QMessageBox.information(self, "已恢复", "默认预设已恢复并立即生效。")
            
            except Exception as e:
                logging.error(f"Error resetting options.json: {e}")
                error_msg = QtWidgets.QMessageBox()
                error_msg.setWindowTitle("恢复失败")
                error_msg.setText(f"恢复默认预设时发生错误：{str(e)}")
                error_msg.exec_()

    def _validate_hotkey(self, hotkey, exclude_button=None):
        """
        Check a button hotkey string for validity and conflicts.

        Returns (ok, error_message). Empty hotkey is always ok — the dialog
        omits the field on save, which means "no direct hotkey for this
        button". This is also how every legacy/old options.json entry
        looks, so absence is always safe.

        `exclude_button` skips the named button when checking conflicts —
        used during edit so a button doesn't conflict with its own
        previously-saved hotkey.
        """
        if not hotkey:
            return True, None

        # Authoritative format check: try parsing it the same way the
        # listener will. Catches typos, unknown key names, missing
        # modifiers, etc. without us having to maintain a regex.
        try:
            pykeyboard.HotKey.parse(self.app._to_pynput_hotkey(hotkey))
        except Exception as e:
            return False, (
                f"“{hotkey}”不是有效的快捷键。\n\n"
                f"按键之间请使用“+”，例如 ctrl+j 或 ctrl+shift+p。\n"
                f"({e})"
            )

        # Conflict with the global Writing Tools shortcut. Same combination
        # can't dispatch to both the popup and a direct fire.
        global_shortcut = (self.app.config.get('shortcut') or 'ctrl+space').strip().lower()
        if hotkey == global_shortcut:
            return False, (
                f"“{hotkey}”已经被主快捷键使用，请换一个组合。"
            )

        # Conflict with another button's hotkey.
        data = self.load_options()
        for k, v in data.items():
            if k == exclude_button:
                continue
            other = (v.get('hotkey') or '').strip().lower()
            if other and other == hotkey:
                return False, (
                    f"“{hotkey}”已经被“{option_display_name(k, v)}”预设使用，请换一个组合。"
                )

        return True, None

    @staticmethod
    def _build_button_entry(bd, existing=None):
        """
        Assemble the options.json entry for a button from dialog output.
        Preserves any non-dialog fields already on the existing entry, and
        only writes `hotkey` when the user provided one (legacy-clean).
        """
        entry = dict(existing) if existing else {}
        entry["prefix"] = bd["prefix"]
        entry["instruction"] = bd["instruction"]
        entry["icon"] = bd["icon"]
        entry["open_in_window"] = bd["open_in_window"]
        entry["uses_base_instruction"] = bd.get("uses_base_instruction", True)
        if bd.get("hotkey"):
            entry["hotkey"] = bd["hotkey"]
        else:
            # User cleared the hotkey field — drop the key so re-saving
            # doesn't leave a stale binding behind.
            entry.pop("hotkey", None)
        return entry

    def add_new_button_clicked(self):
        dialog = ButtonEditDialog(self, title="新增预设")
        while dialog.exec_():
            bd = dialog.get_button_data()
            if not bd["name"].strip():
                QtWidgets.QMessageBox.warning(self, "名称不能为空", "请填写预设名称。")
                continue
            ok, err = self._validate_hotkey(bd.get("hotkey", ""))
            if not ok:
                QtWidgets.QMessageBox.warning(self, "快捷键无效", err)
                # Re-open the dialog with the user's entries preserved so
                # they can fix the hotkey instead of starting over.
                continue
            data = self.load_options()
            if bd["name"] in data:
                QtWidgets.QMessageBox.warning(self, "名称已存在", "请换一个预设名称。")
                continue
            data[bd["name"]] = self._build_button_entry(bd)
            self.save_options(data)

            self.refresh_runtime_options()
            self.build_buttons_list()
            self.rebuild_grid_layout()
            QtWidgets.QMessageBox.information(
                self,
                "预设已添加",
                "新预设已经保存并立即生效。"
            )
            return


    def edit_button_clicked(self, btn):
        """User clicked the small pencil icon over a button."""
        key = btn.key
        data = self.load_options()
        bd = data[key]
        bd["name"] = key

        dialog = ButtonEditDialog(self, bd, title="编辑预设")
        while dialog.exec_():
            new_data = dialog.get_button_data()
            if not new_data["name"].strip():
                QtWidgets.QMessageBox.warning(self, "名称不能为空", "请填写预设名称。")
                continue
            # Pass `exclude_button=key` so we don't flag the button's own
            # current hotkey as a conflict with itself.
            ok, err = self._validate_hotkey(new_data.get("hotkey", ""), exclude_button=key)
            if not ok:
                QtWidgets.QMessageBox.warning(self, "快捷键无效", err)
                continue
            data = self.load_options()
            if new_data["name"] != key and new_data["name"] in data:
                QtWidgets.QMessageBox.warning(self, "名称已存在", "请换一个预设名称。")
                continue
            existing = data.get(key)
            if new_data["name"] != key:
                del data[key]
            data[new_data["name"]] = self._build_button_entry(new_data, existing=existing)
            self.save_options(data)

            self.refresh_runtime_options()
            self.build_buttons_list()
            self.rebuild_grid_layout()
            QtWidgets.QMessageBox.information(
                self,
                "预设已更新",
                "修改已经保存并立即生效。"
            )
            return

    def delete_button_clicked(self, btn):
        """Handle deletion of a button."""
        key = btn.key
        confirm = QtWidgets.QMessageBox()
        confirm.setWindowTitle("删除预设？")
        confirm.setText(f"确定要删除“{option_display_name(key, self.load_options().get(key, {}))}”吗？")
        confirm.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        confirm.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if confirm.exec_() == QtWidgets.QMessageBox.Yes:
            try:
                data = self.load_options()
                del data[key]
                self.save_options(data)

                # Clean up UI elements
                for btn_ in self.button_widgets[:]:
                    if btn_.key == key:
                        if hasattr(btn_, 'icon_container') and btn_.icon_container:
                            btn_.icon_container.deleteLater()
                        btn_.deleteLater()
                        self.button_widgets.remove(btn_)
                
                self.refresh_runtime_options()
                self.build_buttons_list()
                self.rebuild_grid_layout()
                
            except Exception as e:
                logging.error(f"Error deleting button: {e}")
                error_msg = QtWidgets.QMessageBox()
                error_msg.setWindowTitle("删除失败")
                error_msg.setText(f"删除预设时发生错误：{str(e)}")
                error_msg.exec_()

    def update_json_from_grid(self):
        """
        Called after a drop reorder. Reflect the new order in options.json,
        so that user's custom arrangement persists.
        """
        data = self.load_options()
        new_data = {"Custom": data["Custom"]} if "Custom" in data else {}
        for b in self.button_widgets:
            new_data[b.key] = data[b.key]
        self.save_options(new_data)
        self.refresh_runtime_options()

    def set_selected_index(self, index):
        """Move the keyboard selection and refresh the visible state."""
        if not self.button_widgets:
            self.selected_index = 0
            return

        self.selected_index = index % len(self.button_widgets)
        for current_index, button in enumerate(self.button_widgets):
            selected = current_index == self.selected_index
            button.setProperty("selected", selected)
            button.shortcut_badge.setStyleSheet(button.badge_style(selected))
            button.style().unpolish(button)
            button.style().polish(button)

    def update_last_action_label(self):
        """Explain what the main shortcut will do in remember mode."""
        data = self.load_options()
        option_key = self.app.config.get('last_used_option', 'Proofread')
        if option_key not in data or option_key == 'Custom':
            option_key = next((key for key in data if key != 'Custom'), '')
        display_name = option_display_name(option_key, data.get(option_key, {})) if option_key else "未选择"
        shortcut = self.app.config.get('shortcut', 'ctrl+space')
        if self.app.config.get('remember_last_action', False):
            text = f"下次按 {shortcut} 直接执行：<b style='color:#5967e8'>{display_name}</b>"
        else:
            text = f"开启后，{shortcut} 将直接执行：<b style='color:#5967e8'>{display_name}</b>"
        self.last_action_label.setText(text)

    def on_remember_toggled(self, checked):
        self.app.set_remember_last_action(checked)
        self.update_last_action_label()

    def on_custom_change(self):
        txt = self.custom_input.text().strip()
        if txt:
            self.app.process_option('Custom', txt)
            self.close()

    def on_generic_instruction(self, instruction):
        if not self.edit_mode:
            self.app.process_option(instruction)
            self.close()

    def eventFilter(self, obj, event):
        # Hide on deactivate only if NOT in edit mode
        if event.type()==QtCore.QEvent.WindowDeactivate:
            if not self.edit_mode:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
            return

        # Once the user clicks into the free-form field, number keys should be
        # typed normally instead of selecting presets.
        if self.custom_input.hasFocus():
            super().keyPressEvent(event)
            return

        number_keys = [
            QtCore.Qt.Key_1,
            QtCore.Qt.Key_2,
            QtCore.Qt.Key_3,
            QtCore.Qt.Key_4,
            QtCore.Qt.Key_5,
            QtCore.Qt.Key_6,
            QtCore.Qt.Key_7,
            QtCore.Qt.Key_8,
            QtCore.Qt.Key_9,
        ]
        if event.key() in number_keys:
            key_number = number_keys.index(event.key()) + 1
            index = number_key_to_index(key_number, len(self.button_widgets))
            if index is not None:
                self.set_selected_index(index)
                self.button_widgets[index].click()
            return

        if event.key() in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Right):
            self.set_selected_index(self.selected_index + 1)
            return
        if event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Left):
            self.set_selected_index(self.selected_index - 1)
            return
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if self.button_widgets:
                self.button_widgets[self.selected_index].click()
            return

        super().keyPressEvent(event)
