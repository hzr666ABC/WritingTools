import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from WritingToolApp import WritingToolApp
from sharpinput_workflow import WorkflowEvent


class PromptRoutingTests(unittest.TestCase):
    def test_stale_prompt_response_is_discarded(self):
        session = SimpleNamespace(consume_compiler_response=Mock())
        window = SimpleNamespace(_closed=False, request_id=4, session=session)
        app = SimpleNamespace(
            _prompt_request_guard=SimpleNamespace(is_current=Mock(return_value=False)),
            prompt_workbench_window=window,
        )

        WritingToolApp._handle_prompt_response(
            app,
            {
                "request_id": 4,
                "window": window,
                "kind": "compiler",
                "response": '{"action":"final"}',
                "error": "",
            },
        )

        session.consume_compiler_response.assert_not_called()

    def test_level_three_compiler_result_is_routed_to_judge(self):
        session = SimpleNamespace(
            consume_compiler_response=Mock(
                return_value=WorkflowEvent("judge_required", level=3)
            ),
            judge_messages=Mock(return_value=[{"role": "user", "content": "draft"}]),
        )
        status_label = SimpleNamespace(setText=Mock())
        window = SimpleNamespace(
            _closed=False,
            request_id=7,
            session=session,
            status_label=status_label,
        )
        app = SimpleNamespace(
            _prompt_request_guard=SimpleNamespace(is_current=Mock(return_value=True)),
            prompt_workbench_window=window,
            current_prompt_provider=object(),
            dispatch_prompt_request=Mock(),
        )

        WritingToolApp._handle_prompt_response(
            app,
            {
                "request_id": 7,
                "window": window,
                "kind": "compiler",
                "response": "valid compiler response",
                "error": "",
            },
        )

        app.dispatch_prompt_request.assert_called_once_with(
            window,
            "judge",
            [{"role": "user", "content": "draft"}],
        )

    def test_cancelling_prompt_request_does_not_invalidate_writing_request(self):
        prompt_provider = SimpleNamespace(cancel=Mock())
        prompt_guard = SimpleNamespace(begin=Mock(return_value=12))
        writing_guard = SimpleNamespace(begin=Mock())
        window = SimpleNamespace(request_id=11)
        app = SimpleNamespace(
            current_prompt_provider=prompt_provider,
            _prompt_request_guard=prompt_guard,
            _request_guard=writing_guard,
        )

        WritingToolApp.cancel_prompt_request(app, window)

        prompt_provider.cancel.assert_called_once_with()
        prompt_guard.begin.assert_called_once_with()
        writing_guard.begin.assert_not_called()
        self.assertEqual(window.request_id, 0)


if __name__ == "__main__":
    unittest.main()
