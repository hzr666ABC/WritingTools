import json
import unittest

from sharpinput_workflow import (
    MAX_TARGET_INPUT_CHARS,
    SharpInputSession,
    extract_json_object,
    stream_visible_text,
)


def response(**values):
    return json.dumps(values, ensure_ascii=False)


class SharpInputWorkflowTests(unittest.TestCase):
    def test_oversized_input_is_rejected_before_provider_dispatch(self):
        session = SharpInputSession("需" * (MAX_TARGET_INPUT_CHARS + 1))

        with self.assertRaisesRegex(ValueError, "超过"):
            session.start()

    def test_extracts_fenced_json_without_accepting_prose_as_state(self):
        parsed = extract_json_object('```json\n{"action":"final","prompt":"完整"}\n```')
        self.assertEqual(parsed["action"], "final")

    def test_quick_mode_never_allows_a_clarification(self):
        session = SharpInputSession("帮我把这个问题说清楚", mode="quick")
        session.start()
        event = session.consume_compiler_response(
            response(
                action="clarify",
                level=3,
                route="clarify_first",
                questions=[{"text": "你要什么？", "why": "影响输出"}],
            )
        )
        self.assertEqual(event.kind, "retry_compiler")
        self.assertEqual(session.level, 0)
        self.assertEqual(session.questions_asked, 0)
        self.assertIn("额度已耗尽", session.compiler_messages()[-1]["content"])

    def test_level_two_asks_one_focused_question_per_turn_up_to_three(self):
        session = SharpInputSession("这两个方案怎么选")
        session.start()
        event = session.consume_compiler_response(
            response(
                action="clarify",
                level=2,
                route="clarify_first",
                questions=[
                    {"text": "最不能妥协的约束是什么？", "why": "会改变推荐"},
                    {"text": "你喜欢哪一个？", "why": "次要偏好"},
                ],
            )
        )
        self.assertEqual(event.kind, "clarify")
        self.assertEqual(len(event.questions), 1)
        self.assertEqual(session.questions_asked, 1)

        session.answer("预算不能超过 500 元")
        second = session.consume_compiler_response(
            response(
                action="clarify",
                level=2,
                route="clarify_first",
                questions=[{"text": "更看重速度还是质量？", "why": "影响推荐"}],
            )
        )
        self.assertEqual(second.kind, "clarify")
        self.assertEqual(session.questions_asked, 2)
        session.answer("质量")
        third = session.consume_compiler_response(
            response(
                action="clarify",
                level=2,
                route="clarify_first",
                questions=[{"text": "决定必须在什么时候完成？", "why": "影响方案"}],
            )
        )
        self.assertEqual(third.kind, "clarify")
        self.assertEqual(session.questions_asked, 3)
        session.answer("今天")
        exhausted = session.consume_compiler_response(
            response(
                action="clarify",
                level=2,
                route="clarify_first",
                questions=[{"text": "还有背景吗？", "why": "补充"}],
            )
        )
        self.assertEqual(exhausted.kind, "retry_compiler")
        self.assertIn("占位符", session.compiler_messages()[-1]["content"])

    def test_partial_json_stream_exposes_only_user_facing_text(self):
        raw = '{"action":"final","prompt":"请分析目标并给出\\n三个步骤'
        self.assertEqual(stream_visible_text(raw), "请分析目标并给出\n三个步骤")
        question = '{"action":"clarify","questions":[{"text":"主要给谁使用？","why":"影响表达"}]}'
        self.assertEqual(stream_visible_text(question), "主要给谁使用？")

    def test_skipping_a_question_forces_placeholder_compilation(self):
        session = SharpInputSession("帮我做产品方案")
        session.start()
        event = session.consume_compiler_response(
            response(
                action="clarify",
                level=1,
                route="clarify_first",
                questions=[{"text": "目标用户是谁？", "why": "影响方案"}],
            )
        )
        self.assertEqual(event.kind, "clarify")
        messages = session.answer("", skipped=True)
        self.assertIn("立即", messages[-1]["content"])
        self.assertIn("占位符", messages[-1]["content"])

    def test_level_two_final_is_copy_ready(self):
        session = SharpInputSession("比较 A 和 B")
        session.start()
        event = session.consume_compiler_response(
            response(
                action="final",
                level=2,
                route="pressure_prompt",
                prompt="请比较 A 和 B，并给出明确推荐、取舍和翻转条件。",
                paths=[],
                summary="加入判断标准",
                placeholders=["[预算]"],
                tradeoff="更明确但更长",
            )
        )
        self.assertEqual(event.kind, "final")
        self.assertEqual(session.primary_prompt(), "请比较 A 和 B，并给出明确推荐、取舍和翻转条件。")
        self.assertEqual(event.payload["level"], 2)

    def test_final_normalizes_requirement_understanding(self):
        session = SharpInputSession("帮我梳理功能")
        session.start()
        event = session.consume_compiler_response(
            response(
                action="final",
                level=1,
                route="quick_rewrite",
                prompt="请设计该功能。",
                understanding={
                    "goal": "完成可验收的功能设计",
                    "audience": "桌面用户",
                    "constraints": ["保留原快捷键", "保留原快捷键"],
                    "open_items": "[目标平台]",
                },
            )
        )
        self.assertEqual(event.payload["understanding"]["goal"], "完成可验收的功能设计")
        self.assertEqual(event.payload["understanding"]["constraints"], ["保留原快捷键"])
        self.assertEqual(event.payload["understanding"]["open_items"], ["[目标平台]"])

    def test_level_three_runs_judge_before_final(self):
        session = SharpInputSession("严格评审一个高投入方案", mode="deep")
        session.start()
        draft = session.consume_compiler_response(
            response(
                action="final",
                level=1,
                route="quick_rewrite",
                prompt="请严格评审这个方案：[方案]。",
                paths=[],
                summary="",
                placeholders=["[方案]"],
                tradeoff="",
            )
        )
        self.assertEqual(draft.kind, "judge_required")
        self.assertEqual(session.level, 3)
        judged = session.consume_judge_response(
            response(
                verdict="pass",
                main_problem="",
                fix_instruction="",
                flip_condition="出现新证据",
                risk_level="conditional",
                evidence_status="unverified",
            )
        )
        self.assertEqual(judged.kind, "final")
        self.assertEqual(judged.payload["judge"]["verdict"], "pass")

    def test_judge_requests_exactly_one_revision_without_a_second_judge_loop(self):
        session = SharpInputSession("评审方案", mode="deep")
        session.start()
        first = session.consume_compiler_response(
            response(action="final", level=3, route="judge_mode", prompt="评审它", paths=[])
        )
        self.assertEqual(first.kind, "judge_required")
        revision = session.consume_judge_response(
            response(
                verdict="minor_fix",
                main_problem="缺少翻转条件",
                fix_instruction="加入能推翻建议的信号",
                flip_condition="",
                risk_level="conditional",
                evidence_status="not_applicable",
            )
        )
        self.assertEqual(revision.kind, "retry_compiler")
        revised = session.consume_compiler_response(
            response(
                action="final",
                level=3,
                route="judge_mode",
                prompt="请评审它，并给出能推翻建议的信号。",
                paths=[],
            )
        )
        self.assertEqual(revised.kind, "final")
        self.assertEqual(revised.payload["judge"]["verdict"], "minor_fix")

    def test_invalid_compiler_json_gets_one_repair_then_errors(self):
        session = SharpInputSession("一个输入")
        session.start()
        first = session.consume_compiler_response("not json")
        second = session.consume_compiler_response("still not json")
        self.assertEqual(first.kind, "retry_compiler")
        self.assertEqual(second.kind, "error")

    def test_only_whitelisted_preferences_enter_provider_context(self):
        session = SharpInputSession(
            "帮我优化",
            preferences={"role": "产品经理", "raw_history": "不能发送", "domain": "SaaS"},
        )
        messages = session.start()
        content = messages[-1]["content"]
        self.assertIn("产品经理", content)
        self.assertNotIn("不能发送", content)


if __name__ == "__main__":
    unittest.main()
