import json
import os
import tempfile
import threading
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets
from PySide6.QtTest import QTest

from aiprovider import GeminiProvider
from prompt_preferences import PromptPreferenceStore
from prompt_presets import PromptPresetStore
from prompt_library import PromptLibraryStore
from secure_storage import protect_secret, unprotect_secret
from ui.PromptSettingsWindow import PromptSettingsWindow
from ui.PromptWorkbenchWindow import PromptWorkbenchWindow
from ui.SafeApplyWindow import SafeApplyWindow
from WritingToolApp import WritingToolApp


class _WorkbenchApp:
    def __init__(self, directory):
        self.config = {
            "theme": "plain",
            "prompt_workbench": {
                "default_depth": "auto",
                "memory_enabled": False,
            },
        }
        self.prompt_preference_store = PromptPreferenceStore(
            os.path.join(directory, "prompt_preferences.json")
        )
        self.prompt_preset_store = PromptPresetStore(
            os.path.join(directory, "prompt_presets.json")
        )
        self.prompt_library_store = PromptLibraryStore(
            os.path.join(directory, "prompt_library.json")
        )
        self.dispatched = []
        self.replacements = []
        self.prompt_workbench_window = None

    def prompt_provider_display(self):
        return "模拟 Prompt 模型"

    def prompt_provider_is_configured(self):
        return True

    def dispatch_prompt_request(self, window, kind, messages):
        self.dispatched.append((window, kind, messages))

    def show_prompt_settings(self):
        pass

    def show_prompt_library(self):
        pass

    def prompt_fallback_provider(self):
        return None

    def cancel_prompt_request(self, window=None):
        if window is not None:
            window.request_id = 0

    def preview_prompt_replacement(self, **values):
        self.replacements.append(values)


class _SettingsApp:
    def __init__(self, directory):
        main_key = protect_secret("main-provider-secret")
        self.config = {
            "theme": "plain",
            "shortcut": "ctrl+space",
            "providers": {
                "Gemini (Recommended)": {
                    "api_key": main_key,
                    "model_name": "main-model",
                }
            },
            "prompt_workbench": {
                "shortcut": "ctrl+shift+p",
                "provider": "Gemini (Recommended)",
                "default_depth": "auto",
                "memory_enabled": False,
            },
            "prompt_providers": {},
        }
        self.main_profile_before = deepcopy(self.config["providers"])
        self.options = {}
        self.prompt_preference_store = PromptPreferenceStore(
            os.path.join(directory, "prompt_preferences.json")
        )
        self.prompt_providers = [
            GeminiProvider(self).set_config_namespace("prompt_providers")
        ]
        self.save_count = 0
        self.reload_count = 0
        self.register_count = 0
        self.menu_count = 0

    @staticmethod
    def _to_pynput_hotkey(value):
        return WritingToolApp._to_pynput_hotkey(value)

    def save_config(self, config):
        self.config = config
        self.save_count += 1

    def reload_prompt_provider(self):
        self.reload_count += 1

    def register_hotkey(self):
        self.register_count += 1

    def update_tray_menu(self):
        self.menu_count += 1


class PromptClickthroughTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    @staticmethod
    def _holder(text="", handle=456):
        ready = threading.Event()
        ready.set()
        return SimpleNamespace(text=text, ready=ready, source_window_handle=handle)

    def _show_workbench(self, directory, text="模糊需求", handle=456):
        app = _WorkbenchApp(directory)
        window = PromptWorkbenchWindow(app, self._holder(text, handle))
        app.prompt_workbench_window = window
        window.show()
        self.qt_app.processEvents()
        return app, window

    @staticmethod
    def _deliver_compiler(app, window, payload):
        event = window.session.consume_compiler_response(
            json.dumps(payload, ensure_ascii=False)
        )
        if event.kind == "judge_required":
            app.dispatch_prompt_request(window, "judge", window.session.judge_messages())
        else:
            window.handle_workflow_event(event)
        return event

    @staticmethod
    def _deliver_judge(window, payload):
        event = window.session.consume_judge_response(
            json.dumps(payload, ensure_ascii=False)
        )
        window.handle_workflow_event(event)
        return event

    def test_full_clarify_edit_copy_refine_replace_and_reset_click_path(self):
        with tempfile.TemporaryDirectory() as directory:
            app, window = self._show_workbench(directory)
            self.assertEqual(app.dispatched, [])

            QTest.mouseClick(window.start_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(app.dispatched[-1][1], "compiler")

            self._deliver_compiler(
                app,
                window,
                {
                    "action": "clarify",
                    "level": 2,
                    "route": "pressure_prompt",
                    "questions": [
                        {"text": "最重要的成功标准是什么？", "why": "会改变取舍"}
                    ],
                },
            )
            self.assertTrue(window.answer_button.isEnabled())
            window.answer_editor.setPlainText("必须给出明确推荐")
            QTest.mouseClick(window.answer_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(app.dispatched[-1][1], "compiler")

            self._deliver_compiler(
                app,
                window,
                {
                    "action": "final",
                    "level": 2,
                    "route": "pressure_prompt",
                    "prompt": "请给出明确推荐、取舍和下一步。",
                    "paths": [],
                    "summary": "补全了决策标准",
                    "placeholders": [],
                    "tradeoff": "速度与完整性",
                },
            )
            editor = window._result_editors[0]
            editor.setFocus()
            QTest.keyClick(editor, QtCore.Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(editor, "Edited prompt ready to copy")
            QTest.mouseClick(window.copy_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(
                QtWidgets.QApplication.clipboard().text(),
                "Edited prompt ready to copy",
            )

            QTest.mouseClick(window.replace_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(app.replacements[-1]["source_window_handle"], 456)
            self.assertEqual(app.replacements[-1]["result"], "Edited prompt ready to copy")

            window.refinement_input.setText("增加验收标准")
            QTest.mouseClick(window.refine_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(app.dispatched[-1][1], "compiler")
            self.assertIn("增加验收标准", app.dispatched[-1][2][-1]["content"])

            self._deliver_compiler(
                app,
                window,
                {
                    "action": "final",
                    "level": 2,
                    "route": "pressure_prompt",
                    "prompt": "修订后 Prompt",
                    "paths": [],
                    "summary": "",
                    "placeholders": [],
                    "tradeoff": "",
                },
            )
            with patch.object(
                QtWidgets.QMessageBox,
                "question",
                return_value=QtWidgets.QMessageBox.StandardButton.Yes,
            ):
                QTest.mouseClick(window.new_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertIsNone(window.session)
            self.assertEqual(window.stack.currentIndex(), 0)
            window.close()

    def test_deep_mode_click_runs_judge_before_showing_result(self):
        with tempfile.TemporaryDirectory() as directory:
            app, window = self._show_workbench(directory, "评审高风险方案")
            window.depth_combo.setFocus()
            QTest.keyClick(window.depth_combo, QtCore.Qt.Key.Key_End)
            self.assertEqual(window.depth_combo.currentData(), "deep")
            QTest.mouseClick(window.start_button, QtCore.Qt.MouseButton.LeftButton)

            event = self._deliver_compiler(
                app,
                window,
                {
                    "action": "final",
                    "level": 3,
                    "route": "judge_mode",
                    "prompt": "Level 3 草稿",
                    "paths": [],
                    "summary": "",
                    "placeholders": [],
                    "tradeoff": "可逆性",
                },
            )
            self.assertEqual(event.kind, "judge_required")
            self.assertEqual(app.dispatched[-1][1], "judge")
            self.assertNotEqual(window.stack.currentIndex(), 2)

            self._deliver_judge(
                window,
                {
                    "verdict": "pass",
                    "main_problem": "",
                    "fix_instruction": "",
                    "flip_condition": "成本超过预算",
                    "risk_level": "conditional",
                    "evidence_status": "unverified",
                },
            )
            self.assertEqual(window.stack.currentIndex(), 2)
            self.assertIn("质量复审", window.result_meta.text())
            window.close()

    def test_empty_and_failed_request_click_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            app, window = self._show_workbench(directory, "", handle=None)
            QTest.mouseClick(window.start_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(app.dispatched, [])
            self.assertIn("请输入", window.status_label.text())

            window.initial_editor.setFocus()
            QTest.keyClicks(window.initial_editor, "Need a better prompt")
            QTest.mouseClick(window.start_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(app.dispatched[-1][1], "compiler")
            window.show_error("simulated offline")
            self.assertTrue(window.retry_button.isVisible())
            QTest.mouseClick(window.retry_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(app.dispatched[-1][1], "compiler")
            self.assertGreaterEqual(len(app.dispatched), 2)
            window.close()

    def test_safe_apply_buttons_keep_original_window_handle(self):
        app = SimpleNamespace(
            config={"theme": "plain"},
            apply_text_to_source=Mock(return_value=True),
            show_history=Mock(),
            history_store=SimpleNamespace(update_status=Mock()),
        )
        window = SafeApplyWindow(
            app,
            {
                "id": "",
                "option": "Prompt 工作台",
                "original": "原文",
                "result": "最终 Prompt",
                "version": 1,
                "source_window_handle": 987,
            },
        )
        window.show()
        self.qt_app.processEvents()

        QTest.mouseClick(window.apply_button, QtCore.Qt.MouseButton.LeftButton)
        self.assertEqual(
            app.apply_text_to_source.call_args.args,
            ("最终 Prompt",),
        )
        self.assertEqual(
            app.apply_text_to_source.call_args.kwargs["source_window_handle"],
            987,
        )
        QTest.qWait(350)
        QTest.mouseClick(window.undo_button, QtCore.Qt.MouseButton.LeftButton)
        self.assertEqual(app.apply_text_to_source.call_args.args, ("原文",))
        window.close()

    def test_multiple_path_tab_click_copies_the_selected_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            app, window = self._show_workbench(directory)
            window.session = SimpleNamespace()
            from sharpinput_workflow import WorkflowEvent

            window.show_final(
                WorkflowEvent(
                    "final",
                    level=3,
                    payload={
                        "level": 3,
                        "prompt": "",
                        "paths": [
                            {"label": "稳健路径", "prompt": "Prompt A", "tradeoff": ""},
                            {"label": "快速路径", "prompt": "Prompt B", "tradeoff": ""},
                        ],
                        "summary": "",
                        "placeholders": [],
                        "tradeoff": "",
                        "judge": {},
                    },
                )
            )
            tab_bar = window.result_tabs.tabBar()
            QTest.mouseClick(
                tab_bar,
                QtCore.Qt.MouseButton.LeftButton,
                pos=tab_bar.tabRect(1).center(),
            )
            QTest.mouseClick(window.copy_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(QtWidgets.QApplication.clipboard().text(), "Prompt B")
            window.close()

    def test_custom_scene_variables_and_favorite_click_path(self):
        with tempfile.TemporaryDirectory() as directory:
            app, window = self._show_workbench(directory, "做一个宣传脚本")
            preset = app.prompt_preset_store.save(
                name="短视频脚本",
                description="平台短视频",
                instruction="补齐平台和受众",
                template="平台：[平台]\n受众：[受众]",
            )
            window._reload_scene_combo(preset.preset_id)
            window._scene_changed(window.scene_combo.currentIndex())
            window._variable_inputs["平台"].setText("抖音")

            QTest.mouseClick(window.start_button, QtCore.Qt.MouseButton.LeftButton)

            request = app.dispatched[-1][2][-1]["content"]
            self.assertIn("短视频脚本", request)
            self.assertIn("平台：抖音", request)
            self.assertIn("受众：[受众]", request)

            self._deliver_compiler(
                app,
                window,
                {
                    "action": "final",
                    "level": 1,
                    "route": "quick_rewrite",
                    "prompt": "收藏用 Prompt",
                    "paths": [],
                    "summary": "",
                    "placeholders": [],
                    "tradeoff": "",
                },
            )
            with patch.object(
                QtWidgets.QInputDialog,
                "getText",
                side_effect=[("短视频收藏", True), ("视频,脚本", True)],
            ):
                QTest.mouseClick(window.favorite_button, QtCore.Qt.MouseButton.LeftButton)

            saved = app.prompt_library_store.list("短视频收藏")
            self.assertEqual(saved[0]["versions"][-1]["prompt"], "收藏用 Prompt")
            self.assertEqual(saved[0]["tags"], ["视频", "脚本"])
            window.close()

    def test_prompt_settings_click_save_isolated_key_shortcut_and_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            app = _SettingsApp(directory)
            window = PromptSettingsWindow(app)
            window.show()
            self.qt_app.processEvents()

            window.shortcut_input.setFocus()
            QTest.keyClick(
                window.shortcut_input,
                QtCore.Qt.Key.Key_L,
                QtCore.Qt.KeyboardModifier.ControlModifier
                | QtCore.Qt.KeyboardModifier.ShiftModifier,
            )
            self.assertEqual(window.shortcut_input.text(), "ctrl+shift+l")

            provider = app.prompt_providers[0]
            key_setting = next(item for item in provider.settings if item.name == "api_key")
            key_setting.input.setFocus()
            QTest.keyClicks(key_setting.input, "prompt-only-secret")
            scroll = window.findChild(QtWidgets.QScrollArea)
            scroll.ensureWidgetVisible(window.memory_checkbox, 20, 20)
            self.qt_app.processEvents()
            QTest.mouseClick(
                window.memory_checkbox,
                QtCore.Qt.MouseButton.LeftButton,
                pos=QtCore.QPoint(8, window.memory_checkbox.height() // 2),
            )
            self.assertTrue(window.memory_checkbox.isChecked())
            window.preference_inputs["role"].setFocus()
            QTest.keyClicks(window.preference_inputs["role"], "Product manager")
            save_button = next(
                button
                for button in window.findChildren(QtWidgets.QPushButton)
                if button.text() == "保存 Prompt 设置"
            )
            QTest.mouseClick(save_button, QtCore.Qt.MouseButton.LeftButton)

            self.assertEqual(app.config["providers"], app.main_profile_before)
            saved = app.config["prompt_providers"]["Gemini (Recommended)"]
            self.assertEqual(unprotect_secret(saved["api_key"]), "prompt-only-secret")
            self.assertEqual(
                app.config["prompt_workbench"]["shortcut"], "ctrl+shift+l"
            )
            self.assertTrue(app.config["prompt_workbench"]["memory_enabled"])
            self.assertEqual(
                app.prompt_preference_store.load(enabled=True)["role"],
                "Product manager",
            )
            self.assertEqual(app.reload_count, 1)
            self.assertEqual(app.register_count, 1)
            self.assertEqual(app.menu_count, 1)

    def test_prompt_settings_click_blocks_main_shortcut_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            app = _SettingsApp(directory)
            window = PromptSettingsWindow(app)
            window.show()
            self.qt_app.processEvents()
            window.shortcut_input.setFocus()
            QTest.keyClick(
                window.shortcut_input,
                QtCore.Qt.Key.Key_Space,
                QtCore.Qt.KeyboardModifier.ControlModifier,
            )
            save_button = next(
                button
                for button in window.findChildren(QtWidgets.QPushButton)
                if button.text() == "保存 Prompt 设置"
            )
            with patch.object(QtWidgets.QMessageBox, "warning") as warning:
                QTest.mouseClick(save_button, QtCore.Qt.MouseButton.LeftButton)

            warning.assert_called_once()
            self.assertIn("快捷键冲突", warning.call_args.args[1])
            self.assertEqual(
                app.config["prompt_workbench"]["shortcut"], "ctrl+shift+p"
            )
            self.assertEqual(app.save_count, 0)
            window.close()

    def test_prompt_settings_click_clears_encrypted_preferences_and_consent(self):
        with tempfile.TemporaryDirectory() as directory:
            app = _SettingsApp(directory)
            app.config["prompt_workbench"]["memory_enabled"] = True
            app.prompt_preference_store.save(
                {"role": "Product manager"}, enabled=True
            )
            window = PromptSettingsWindow(app)
            window.show()
            self.qt_app.processEvents()
            clear_button = next(
                button
                for button in window.findChildren(QtWidgets.QPushButton)
                if button.text() == "清除偏好文件"
            )
            scroll = window.findChild(QtWidgets.QScrollArea)
            scroll.ensureWidgetVisible(clear_button, 20, 20)
            self.qt_app.processEvents()
            with patch.object(
                QtWidgets.QMessageBox,
                "question",
                return_value=QtWidgets.QMessageBox.StandardButton.Yes,
            ):
                QTest.mouseClick(clear_button, QtCore.Qt.MouseButton.LeftButton)

            self.assertFalse(app.prompt_preference_store.has_data())
            self.assertFalse(app.config["prompt_workbench"]["memory_enabled"])
            self.assertFalse(window.memory_checkbox.isChecked())
            self.assertEqual(window.preference_inputs["role"].text(), "")
            window.close()


if __name__ == "__main__":
    unittest.main()
