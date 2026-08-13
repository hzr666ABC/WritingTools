"""Deterministic session protocol for the SharpInput prompt workbench.

The language model performs semantic classification and prompt compilation,
while this module owns the observable safety boundaries: JSON-only actions,
clarification budgets, retry limits, Level 3 review, and copy-ready output.
It deliberately has no Qt or provider dependencies so the workflow can be
tested without a GUI or network connection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


COMPILER_SYSTEM_INSTRUCTION = r"""
你是 Writing Tools 的 Prompt 编译器。你的唯一任务是把用户的模糊输入变成忠于原意、可直接复制给下游 AI 的完整 Prompt；不要回答或执行底层任务。

固定规则：
1. 保留用户目标、语气、事实和约束。不得发明预算、受众、平台、证据或期望结论；缺失但不阻塞的信息使用 [方括号占位符]。
2. 先判断意图（理解、决策、生成、分析、探索、诊断、说服、验证、规划、学习、优化、对比、梳理、求助），再按需要识别场景和关键上下文。
3. Level 0：轻量改写，不提问。Level 1：目标明确但需结构，最多两轮澄清。Level 2：决策、对比、取舍或压力测试，最多三轮澄清。Level 3：高风险、难逆转或深度评审，最多四轮澄清。每轮只问一个真正会改变最终 Prompt 的问题，并给出 2-4 个便于思考的选项或例子；禁止泛泛地询问“还有什么背景”。
4. quick 模式固定 Level 0；deep 模式固定 Level 3；auto 模式按任务分配 Level 0-3。
5. 对决策、对比和验证任务，可要求明确推荐、取舍、翻转条件和一个可执行下一步。翻译、轻度润色和简单事实问题不得强行施压。
6. 只在路径有实质不同的目标、策略或取舍时生成 2-3 条路径；否则只生成一个 Prompt。
7. 在最终结果中显式梳理：真实目标、使用对象、已知背景、硬约束、成功标准、仍采用的假设与待补信息。区分用户已确认的事实和模型为了继续工作而保留的假设。
8. 不索要隐藏思维链，不输出内部评分、状态对象或模块诊断。最终 Prompt 必须完整自包含，结构要与任务匹配，不能机械套用“角色/步骤/格式”模板。
9. 返回严格 JSON，不要 Markdown 代码围栏、前言或后记。为了支持流式预览，final 时把 prompt 或 paths 放在 summary 等说明字段之前。

允许的响应结构只有两种：

需要澄清时：
{
  "action": "clarify",
  "level": 1,
  "route": "clarify_first",
  "questions": [{"text": "一个具体问题", "why": "为什么会改变结果"}]
}

可以完成时：
{
  "action": "final",
  "level": 1,
  "route": "quick_rewrite",
  "prompt": "一个完整、可直接复制的 Prompt；多路径时可为空",
  "paths": [{"label": "路径名称", "prompt": "完整 Prompt", "tradeoff": "具体取舍"}],
  "understanding": {
    "goal": "真正要达成的结果",
    "audience": "使用者、读者或影响对象",
    "context": ["已确认的关键背景"],
    "constraints": ["硬约束和明确边界"],
    "success_criteria": ["如何判断结果可用"],
    "assumptions": ["尚未确认但为了继续生成而保留的假设"],
    "open_items": ["仍应由用户补充或替换的信息"]
  },
  "summary": "一句话说明最重要的改进",
  "placeholders": ["只列真正影响结果的占位符"],
  "tradeoff": "Level 2/3 的一个具体取舍；不适用时为空"
}

当上文明确说问题额度耗尽、用户选择跳过或要求立即编译时，必须返回 final，并用占位符处理剩余缺口。
""".strip()


JUDGE_SYSTEM_INSTRUCTION = r"""
你是独立的 Prompt 质量复审器。只评审 Prompt 草稿，不回答底层任务，也不声称核实了外部事实。

检查：意图忠实、场景匹配、关键上下文、约束强度、压力是否适度、是否完整可复制、风险或翻转条件是否清楚。若证据无法核实，evidence_status 必须是 unverified 或 not_applicable。

只返回严格 JSON：
{
  "verdict": "pass | minor_fix | rewrite_required",
  "main_problem": "最重要的问题；没有则为空",
  "fix_instruction": "可执行的修订要求；没有则为空",
  "flip_condition": "能改变建议或风险判断的条件；不适用则为空",
  "risk_level": "low | conditional | high",
  "evidence_status": "verified | unverified | not_applicable"
}

intent drift、发明重要事实、隐藏关键缺口、强迫结论、直接回答底层任务或不可复制时必须 rewrite_required。局部问题使用 minor_fix。
""".strip()


VALID_ROUTES = {"quick_rewrite", "clarify_first", "pressure_prompt", "judge_mode"}
VALID_VERDICTS = {"pass", "minor_fix", "rewrite_required"}
VALID_RISK_LEVELS = {"low", "conditional", "high"}
VALID_EVIDENCE_STATUS = {"verified", "unverified", "not_applicable"}
VALID_MODES = {"auto", "quick", "deep"}
MAX_TARGET_INPUT_CHARS = 60_000
PREFERENCE_KEYS = {
    "preferred_language",
    "default_depth",
    "role",
    "domain",
    "tech_stack",
    "common_constraints",
    "pressure_strength",
}


class WorkflowProtocolError(ValueError):
    """Raised when a model response cannot satisfy the workbench protocol."""


@dataclass(frozen=True)
class WorkflowEvent:
    """A provider-independent action for the UI/controller."""

    kind: str
    level: int = 0
    questions: tuple[dict[str, str], ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    message: str = ""


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract one JSON object, accepting a fenced object as a safe fallback."""

    raw = str(text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    decoder = json.JSONDecoder()
    starts = [index for index, char in enumerate(raw) if char == "{"]
    for start in starts:
        try:
            value, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise WorkflowProtocolError("模型没有返回有效的 JSON 对象")


def _clean_text(value: Any, *, maximum: int = 200_000) -> str:
    return str(value or "").strip()[:maximum]


def _level(value: Any, mode: str) -> int:
    if mode == "quick":
        return 0
    if mode == "deep":
        return 3
    try:
        return max(0, min(3, int(value)))
    except (TypeError, ValueError):
        return 1


def _question_budget(level: int) -> int:
    if level == 3:
        return 4
    if level == 2:
        return 3
    if level == 1:
        return 2
    return 0


def _partial_json_string(raw: str, start: int) -> str:
    """Decode the available part of a JSON string without requiring closure."""

    result = []
    index = start
    escapes = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
    while index < len(raw):
        character = raw[index]
        if character == '"':
            break
        if character != "\\":
            result.append(character)
            index += 1
            continue
        if index + 1 >= len(raw):
            break
        escaped = raw[index + 1]
        if escaped == "u":
            digits = raw[index + 2 : index + 6]
            if len(digits) < 4 or not all(value in "0123456789abcdefABCDEF" for value in digits):
                break
            result.append(chr(int(digits, 16)))
            index += 6
            continue
        result.append(escapes.get(escaped, escaped))
        index += 2
    return "".join(result)


def stream_visible_text(response_preview: str) -> str:
    """Return only user-facing text from a partial compiler JSON stream."""

    raw = str(response_preview or "")
    values: dict[str, list[str]] = {"prompt": [], "text": [], "summary": []}
    pattern = re.compile(r'"(prompt|text|summary)"\s*:\s*"')
    for match in pattern.finditer(raw):
        value = _partial_json_string(raw, match.end())
        if value:
            values[match.group(1)].append(value)
    if values["prompt"]:
        return values["prompt"][-1]
    if values["text"]:
        return "\n\n".join(values["text"])
    if values["summary"]:
        return values["summary"][-1]
    return ""


def _normalized_preferences(preferences: dict | None) -> dict[str, str]:
    normalized = {}
    for key, value in (preferences or {}).items():
        if key not in PREFERENCE_KEYS:
            continue
        text = _clean_text(value, maximum=2_000)
        if text:
            normalized[key] = text
    return normalized


class SharpInputSession:
    """State machine for one in-memory Prompt Workbench conversation."""

    def __init__(
        self,
        target_input: str,
        *,
        mode: str = "auto",
        preferences: dict | None = None,
        scene: dict | None = None,
    ):
        if mode not in VALID_MODES:
            raise ValueError(f"Unsupported workbench mode: {mode}")
        self.target_input = str(target_input or "")
        self.mode = mode
        self.preferences = _normalized_preferences(preferences)
        scene = scene if isinstance(scene, dict) else {}
        self.scene = {
            "id": _clean_text(scene.get("id"), maximum=80) or "smart",
            "name": _clean_text(scene.get("name"), maximum=120) or "智能通用",
            "instruction": _clean_text(scene.get("instruction"), maximum=4_000),
        }
        self.level = 0 if mode == "quick" else 3 if mode == "deep" else 1
        self.route = "quick_rewrite"
        self.questions_asked = 0
        self.compiler_parse_failures = 0
        self.judge_parse_failures = 0
        self.judge_completed = False
        self.revision_requested = False
        self.pending_final: dict[str, Any] | None = None
        self.judge_result: dict[str, str] | None = None
        self.stage = "ready"
        self._history: list[dict[str, str]] = []
        self._judge_repair_requested = False

    def start(self) -> list[dict[str, str]]:
        """Initialize and return a defensive copy of provider messages."""

        if not self.target_input.strip():
            raise ValueError("Prompt 工作台输入不能为空")
        if len(self.target_input) > MAX_TARGET_INPUT_CHARS:
            raise ValueError(
                f"输入超过 {MAX_TARGET_INPUT_CHARS:,} 个字符，请缩短内容或改用支持更大上下文的模型"
            )
        if not self._history:
            request = {
                "task_mode": "prompt_optimization",
                "interaction_mode": self.mode,
                "target_input": self.target_input,
                "scene": self.scene,
                "confirmed_preferences": self.preferences,
                "instruction": "分析后按协议澄清或编译；不要回答底层任务。",
            }
            self._history.append(
                {
                    "role": "user",
                    "content": json.dumps(request, ensure_ascii=False),
                }
            )
        self.stage = "compiling"
        return self.compiler_messages()

    def compiler_messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": COMPILER_SYSTEM_INSTRUCTION},
            *[dict(message) for message in self._history],
        ]

    def answer(self, text: str, *, skipped: bool = False) -> list[dict[str, str]]:
        if self.stage != "waiting_for_user":
            raise RuntimeError("当前会话没有等待回答的问题")
        content = _clean_text(text)
        if skipped or not content:
            content = "用户选择跳过澄清。请立即使用明确占位符完成 Prompt，不要再提问。"
        self._history.append({"role": "user", "content": content})
        self.stage = "compiling"
        return self.compiler_messages()

    def request_revision(self, instruction: str) -> list[dict[str, str]]:
        """Continue refining a completed prompt inside the same session."""

        content = _clean_text(instruction)
        if not content:
            raise ValueError("修改要求不能为空")
        if not self.pending_final:
            raise RuntimeError("当前会话还没有可修改的 Prompt")
        self._history.append(
            {
                "role": "user",
                "content": (
                    "请根据以下修改要求调整刚才的最终 Prompt。不得再提澄清问题，"
                    "缺失内容使用占位符，并返回 action=final 的严格 JSON：\n" + content
                ),
            }
        )
        self.judge_completed = self.level != 3
        self.revision_requested = self.level == 3
        self.stage = "compiling"
        return self.compiler_messages()

    def consume_compiler_response(self, response_text: str) -> WorkflowEvent:
        """Validate one compiler response and return the next controller action."""

        raw = str(response_text or "")
        try:
            action = extract_json_object(raw)
        except (WorkflowProtocolError, TypeError, ValueError) as error:
            return self._compiler_protocol_failure(raw, error, append_response=True)

        # Record the model turn before a transition appends the next user
        # instruction. This keeps roles chronological when compilation is
        # forced after the clarification budget is exhausted.
        self._history.append({"role": "assistant", "content": raw[:200_000]})
        try:
            event = self._consume_compiler_action(action)
        except (WorkflowProtocolError, TypeError, ValueError) as error:
            return self._compiler_protocol_failure(raw, error, append_response=False)

        self.compiler_parse_failures = 0
        return event

    def _compiler_protocol_failure(
        self,
        raw: str,
        error: Exception,
        *,
        append_response: bool,
    ) -> WorkflowEvent:
        """Request one schema repair without duplicating an assistant turn."""

        if append_response:
            self._history.append({"role": "assistant", "content": raw[:20_000]})
        self.compiler_parse_failures += 1
        if self.compiler_parse_failures <= 1:
            self._history.append(
                {
                    "role": "user",
                    "content": (
                        "上一个响应不符合协议。只返回一个有效 JSON 对象；"
                        "不得添加代码围栏或说明。错误：" + _clean_text(error, maximum=400)
                    ),
                }
            )
            self.stage = "compiling"
            return WorkflowEvent("retry_compiler", level=self.level, message=str(error))
        self.stage = "error"
        return WorkflowEvent("error", level=self.level, message=str(error))

    def _consume_compiler_action(self, action: dict[str, Any]) -> WorkflowEvent:
        action_name = _clean_text(action.get("action"), maximum=40).casefold()
        if action_name not in {"clarify", "final"}:
            raise WorkflowProtocolError("action 必须是 clarify 或 final")

        level = _level(action.get("level"), self.mode)
        route = _clean_text(action.get("route"), maximum=40)
        if route not in VALID_ROUTES:
            route = "judge_mode" if level == 3 else "pressure_prompt" if level == 2 else "quick_rewrite"
        self.level = level
        self.route = route

        if action_name == "clarify":
            questions = []
            seen = set()
            for item in action.get("questions") or []:
                if isinstance(item, str):
                    text, why = _clean_text(item, maximum=2_000), ""
                elif isinstance(item, dict):
                    text = _clean_text(item.get("text"), maximum=2_000)
                    why = _clean_text(item.get("why"), maximum=500)
                else:
                    continue
                if text and text not in seen:
                    seen.add(text)
                    questions.append({"text": text, "why": why})

            remaining = max(0, _question_budget(level) - self.questions_asked)
            if not questions or remaining <= 0:
                self._history.append(
                    {
                        "role": "user",
                        "content": (
                            "澄清问题额度已耗尽。请立即返回 action=final，"
                            "用 [方括号占位符] 处理所有剩余缺口，不得再提问。"
                        ),
                    }
                )
                self.stage = "compiling"
                return WorkflowEvent("retry_compiler", level=level)

            # One focused question per turn creates a real conversation and
            # lets each answer inform the next question.
            selected = tuple(questions[: min(1, remaining)])
            self.questions_asked += len(selected)
            self.stage = "waiting_for_user"
            return WorkflowEvent("clarify", level=level, questions=selected)

        final = self._normalize_final(action)
        self.pending_final = final
        if level == 3 and not self.judge_completed and not self.revision_requested:
            self.stage = "judging"
            return WorkflowEvent("judge_required", level=level, payload=final)

        self.stage = "complete"
        return WorkflowEvent("final", level=level, payload=self.final_payload())

    @staticmethod
    def _normalize_final(action: dict[str, Any]) -> dict[str, Any]:
        prompt = _clean_text(action.get("prompt"))
        paths = []
        for item in action.get("paths") or []:
            if not isinstance(item, dict):
                continue
            path_prompt = _clean_text(item.get("prompt"))
            if not path_prompt:
                continue
            paths.append(
                {
                    "label": _clean_text(item.get("label"), maximum=120) or f"路径 {len(paths) + 1}",
                    "prompt": path_prompt,
                    "tradeoff": _clean_text(item.get("tradeoff"), maximum=1_000),
                }
            )
        paths = paths[:3]
        if not prompt and not paths:
            raise WorkflowProtocolError("final 响应缺少完整 Prompt")
        if prompt and paths:
            # One canonical prompt plus paths is redundant. Prefer the paths
            # only when the model actually produced multiple useful options.
            if len(paths) < 2:
                paths = []
        placeholders = []
        for value in action.get("placeholders") or []:
            text = _clean_text(value, maximum=300)
            if text and text not in placeholders:
                placeholders.append(text)
        understanding_source = action.get("understanding")
        understanding_source = understanding_source if isinstance(understanding_source, dict) else {}
        understanding = {}
        for key in ("goal", "audience"):
            value = _clean_text(understanding_source.get(key), maximum=2_000)
            if value:
                understanding[key] = value
        for key in (
            "context",
            "constraints",
            "success_criteria",
            "assumptions",
            "open_items",
        ):
            source = understanding_source.get(key) or []
            if isinstance(source, str):
                source = [source]
            items = []
            for value in source if isinstance(source, (list, tuple)) else []:
                text = _clean_text(value, maximum=1_000)
                if text and text not in items:
                    items.append(text)
            if items:
                understanding[key] = items[:12]
        return {
            "prompt": prompt,
            "paths": paths,
            "understanding": understanding,
            "summary": _clean_text(action.get("summary"), maximum=2_000),
            "placeholders": placeholders[:20],
            "tradeoff": _clean_text(action.get("tradeoff"), maximum=2_000),
        }

    def judge_messages(self) -> list[dict[str, str]]:
        if not self.pending_final:
            raise RuntimeError("没有可复审的 Prompt 草稿")
        payload = {
            "original_input": self.target_input,
            "known_preferences": self.preferences,
            "draft": self.pending_final,
        }
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_INSTRUCTION},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        if self._judge_repair_requested:
            messages.append(
                {
                    "role": "user",
                    "content": "上一次复审响应无效。请严格按指定 schema 只返回 JSON。",
                }
            )
        return messages

    def consume_judge_response(self, response_text: str) -> WorkflowEvent:
        raw = str(response_text or "")
        try:
            action = extract_json_object(raw)
            verdict = _clean_text(action.get("verdict"), maximum=40)
            if verdict not in VALID_VERDICTS:
                raise WorkflowProtocolError("Judge verdict 无效")
            risk_level = _clean_text(action.get("risk_level"), maximum=40)
            evidence_status = _clean_text(action.get("evidence_status"), maximum=40)
            if risk_level not in VALID_RISK_LEVELS:
                risk_level = "conditional"
            if evidence_status not in VALID_EVIDENCE_STATUS:
                evidence_status = "unverified"
            self.judge_result = {
                "verdict": verdict,
                "main_problem": _clean_text(action.get("main_problem"), maximum=2_000),
                "fix_instruction": _clean_text(action.get("fix_instruction"), maximum=2_000),
                "flip_condition": _clean_text(action.get("flip_condition"), maximum=2_000),
                "risk_level": risk_level,
                "evidence_status": evidence_status,
            }
        except (WorkflowProtocolError, TypeError, ValueError) as error:
            self.judge_parse_failures += 1
            if self.judge_parse_failures <= 1:
                self._judge_repair_requested = True
                self.stage = "judging"
                return WorkflowEvent("retry_judge", level=self.level, message=str(error))
            self.stage = "error"
            return WorkflowEvent("error", level=self.level, message=str(error))

        self.judge_parse_failures = 0
        self._judge_repair_requested = False
        if self.judge_result["verdict"] == "pass":
            self.judge_completed = True
            self.stage = "complete"
            return WorkflowEvent("final", level=self.level, payload=self.final_payload())

        instruction = self.judge_result["fix_instruction"] or self.judge_result["main_problem"]
        self._history.append(
            {
                "role": "user",
                "content": (
                    "质量复审要求修订一次。不得再提澄清问题，不得回答底层任务；"
                    "请返回 action=final 的严格 JSON。修订要求：" + instruction
                ),
            }
        )
        self.judge_completed = True
        self.revision_requested = True
        self.stage = "compiling"
        return WorkflowEvent("retry_compiler", level=self.level, payload={"judge": self.judge_result})

    def final_payload(self) -> dict[str, Any]:
        if not self.pending_final:
            raise RuntimeError("当前会话还没有最终 Prompt")
        payload = dict(self.pending_final)
        payload["level"] = self.level
        payload["route"] = self.route
        payload["judge"] = dict(self.judge_result or {})
        return payload

    def primary_prompt(self) -> str:
        if not self.pending_final:
            return ""
        if self.pending_final.get("prompt"):
            return str(self.pending_final["prompt"])
        paths = self.pending_final.get("paths") or []
        return str(paths[0].get("prompt", "")) if paths else ""


__all__ = [
    "COMPILER_SYSTEM_INSTRUCTION",
    "JUDGE_SYSTEM_INSTRUCTION",
    "MAX_TARGET_INPUT_CHARS",
    "PREFERENCE_KEYS",
    "SharpInputSession",
    "WorkflowEvent",
    "WorkflowProtocolError",
    "extract_json_object",
    "stream_visible_text",
]
