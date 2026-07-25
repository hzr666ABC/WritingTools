import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from WritingToolApp import WritingToolApp


class GenerationRoutingTests(unittest.TestCase):
    def _app(self, *, current=True):
        return SimpleNamespace(
            _request_guard=SimpleNamespace(is_current=Mock(return_value=current)),
            config={"history_enabled": True},
            history_store=SimpleNamespace(add_entry=Mock()),
            current_response_window=None,
            replace_text=Mock(),
            source_window_handle=None,
            pending_option="",
            pending_original="",
        )

    def test_stale_result_is_discarded(self):
        app = self._app(current=False)

        WritingToolApp._handle_generation_result(
            app,
            {
                "request_id": 1,
                "result": "旧结果",
                "source_window_handle": 200,
            },
        )

        app.replace_text.assert_not_called()
        self.assertIsNone(app.source_window_handle)

    def test_direct_result_keeps_its_original_window_and_text(self):
        app = self._app()

        WritingToolApp._handle_generation_result(
            app,
            {
                "request_id": 2,
                "option": "Rewrite",
                "original": "原文",
                "result": "新结果",
                "source_window_handle": 0x1_0000_0200,
                "open_in_window": False,
            },
        )

        self.assertEqual(app.source_window_handle, 0x1_0000_0200)
        self.assertEqual(app.pending_option, "Rewrite")
        self.assertEqual(app.pending_original, "原文")
        app.replace_text.assert_called_once_with("新结果")

    def test_history_failure_does_not_hide_window_result(self):
        app = self._app()
        app.history_store.add_entry.side_effect = OSError("history locked")
        window = Mock()
        window.request_id = 3
        app.current_response_window = window

        WritingToolApp._handle_generation_result(
            app,
            {
                "request_id": 3,
                "option": "Summary",
                "original": "原文",
                "result": "总结",
                "open_in_window": True,
                "provider": "Demo",
                "model": "model-a",
            },
        )

        window.set_text.assert_called_once_with("总结")


if __name__ == "__main__":
    unittest.main()
