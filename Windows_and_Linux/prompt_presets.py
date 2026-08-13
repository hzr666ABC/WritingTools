"""Built-in and encrypted custom scene presets for Prompt Workbench."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import uuid
from dataclasses import dataclass, asdict

from secure_storage import protect_secret, unprotect_secret


@dataclass(frozen=True)
class PromptPreset:
    preset_id: str
    name: str
    description: str
    instruction: str
    template: str = ""
    builtin: bool = True


BUILTIN_PRESETS = (
    PromptPreset(
        "smart",
        "智能梳理",
        "从模糊想法中识别真实目标，再选择合适结构",
        """先区分用户是在探索问题、做决定、生成内容、解决故障还是验证方案。
按“真正想达成的结果→谁会使用结果→已有事实→硬约束→成功标准→仍不确定之处”的顺序诊断。
澄清时优先询问会改变方向的信息，并给出便于选择的具体选项；不要让用户自己猜该补什么。
最终 Prompt 的结构必须随任务变化，同时明确已确认内容、必要假设和待替换占位符。""",
    ),
    PromptPreset(
        "writing",
        "写作创作",
        "文章、故事、脚本、文案与风格改写",
        """先识别写作目的（告知、说服、叙事、转化或表达）以及读者读完后的期望反应。
依次检查受众认知、核心信息、素材来源、体裁、叙事视角、语气、结构、篇幅、发布渠道和禁用表达。
不要只堆风格形容词；把抽象风格转成句长、节奏、用词、信息密度和示例等可执行标准。
最终 Prompt 应包含内容边界、结构要求、质量检查和避免事项。""",
    ),
    PromptPreset(
        "research",
        "学习研究",
        "学习路线、知识解释、论文与资料调研",
        """先判断用户需要理解概念、建立知识体系、解决具体问题，还是形成可引用的研究结论。
检查现有知识水平、研究问题、范围边界、时间跨度、地区、资料类型、来源可信度、引用格式和交付深度。
主动区分事实、主流观点、争议和未知；要求标明不确定性，禁止虚构来源。
最终 Prompt 应给出研究步骤、证据标准、反例检查、结果结构和可继续追问的知识缺口。""",
    ),
    PromptPreset(
        "coding",
        "代码开发",
        "实现、排错、重构、代码审查与技术设计",
        """先识别任务是实现、诊断、优化、迁移还是审查，并确认允许修改的范围。
检查技术栈和版本、操作系统、依赖、现有行为、预期行为、输入输出、复现步骤、日志、性能目标和兼容边界。
对于故障先要求证据和最小复现；对于实现明确非目标、安全风险、错误处理和回滚方式。
最终 Prompt 应要求最小必要改动、关键取舍、自动化测试、人工验收步骤以及不能确定时如何报告。""",
    ),
    PromptPreset(
        "product",
        "产品需求",
        "把想法整理成可落地、可验收的产品方案",
        """先找出要解决的用户问题，而不是直接接受用户提出的功能形态。
检查目标用户、触发场景、现有替代方案、用户任务、核心价值、范围、非目标、依赖、权限、数据、异常路径和可访问性。
区分必须有、应该有和以后再做；识别最小可验证版本与可能造成需求膨胀的部分。
最终 Prompt 应包含用户流程、状态与边界、失败处理、衡量指标、验收标准和仍待产品决策的问题。""",
    ),
    PromptPreset(
        "decision",
        "方案决策",
        "选型、购买、优先级与多方案比较",
        """先澄清这项决定服务于什么结果、决策期限、不可妥协条件以及谁承担后果。
检查候选项是否完整，建立有权重的比较维度，并区分一次性成本、长期成本、可逆性、机会成本和最坏情况。
主动寻找能推翻初始偏好的证据，不用平均罗列优缺点逃避结论。
最终 Prompt 应要求明确推荐、理由、关键取舍、风险缓解、翻转条件和下一步低成本验证。""",
    ),
    PromptPreset(
        "communication",
        "沟通表达",
        "邮件、通知、汇报、反馈、谈判与困难对话",
        """先确认沟通对象、双方关系、对方已知信息、用户真正想让对方理解或采取的行动。
检查渠道、时机、语气、权力差异、敏感点、不能承诺的内容、证据和篇幅限制。
把“礼貌、专业、强硬”等抽象要求转成措辞边界，并预判最可能的误解或防御反应。
最终 Prompt 应包含核心信息顺序、明确行动请求、必要背景、风险措辞和可选的柔和/直接版本。""",
    ),
    PromptPreset(
        "visual",
        "图片视频",
        "图像、摄影、分镜、短视频与视觉设计",
        """先确认视觉内容的用途、观看平台、目标受众以及最重要的视觉焦点。
检查主体、动作、环境、时代、构图、景别、镜头、光线、色彩、材质、风格特征、画幅、时长、节奏和文字内容。
区分必须准确呈现的元素与允许自由发挥的部分，并记录负面约束、品牌限制和连续性要求。
最终 Prompt 应按主体→场景→构图镜头→光色材质→技术参数→负面约束组织；视频还需包含镜头序列和运动。""",
    ),
    PromptPreset(
        "review",
        "严格评审",
        "发现漏洞、隐藏假设、失败模式与改进优先级",
        """先明确评审对象、目标、所处阶段、允许推翻的范围以及错误判断的代价。
逐项检查论据与证据、隐藏假设、边界条件、利益相关者、反例、失败模式、不可逆风险和被忽略的替代方案。
区分致命问题、重要问题和润色建议；不为了显得严格而挑无关细节，也不接受未经证实的断言。
最终 Prompt 应要求按严重性排序，说明影响与证据，给出可验证的修正动作、停止条件和会改变结论的信号。""",
    ),
)


_VARIABLE_RE = re.compile(r"\[([^\[\]\r\n]{1,40})\]")


def preset_variables(preset: PromptPreset) -> tuple[str, ...]:
    seen = []
    for name in _VARIABLE_RE.findall(preset.template or ""):
        clean = name.strip()
        if clean and clean not in seen:
            seen.append(clean)
    return tuple(seen[:12])


def render_preset_input(preset: PromptPreset, user_input: str, values: dict | None = None) -> str:
    values = {str(k): str(v).strip() for k, v in (values or {}).items()}
    template = str(preset.template or "").strip()
    if template:
        for variable in preset_variables(preset):
            replacement = values.get(variable) or f"[{variable}]"
            template = template.replace(f"[{variable}]", replacement)
    sections = [str(user_input or "").strip()]
    if template:
        sections.append("场景模板：\n" + template)
    return "\n\n".join(section for section in sections if section)


class PromptPresetStore:
    FORMAT_VERSION = 1
    MAX_FILE_BYTES = 1_000_000
    MAX_PRESETS = 50

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_item(item: dict) -> PromptPreset | None:
        if not isinstance(item, dict):
            return None
        preset_id = str(item.get("preset_id") or "").strip()[:80]
        name = str(item.get("name") or "").strip()[:80]
        instruction = str(item.get("instruction") or "").strip()[:4_000]
        if not preset_id or not name or not instruction:
            return None
        return PromptPreset(
            preset_id=preset_id,
            name=name,
            description=str(item.get("description") or "").strip()[:240],
            instruction=instruction,
            template=str(item.get("template") or "").strip()[:8_000],
            builtin=False,
        )

    def _read(self) -> list[PromptPreset]:
        if not os.path.isfile(self.path):
            return []
        try:
            if os.path.getsize(self.path) > self.MAX_FILE_BYTES:
                return []
            with open(self.path, "r", encoding="utf-8") as handle:
                envelope = json.load(handle)
            payload = json.loads(unprotect_secret(envelope.get("payload", "")))
        except (OSError, UnicodeError, ValueError, TypeError):
            return []
        if not isinstance(payload, dict) or payload.get("schema_version") != self.FORMAT_VERSION:
            return []
        result = []
        for item in payload.get("presets") or []:
            normalized = self._normalize_item(item)
            if normalized:
                result.append(normalized)
        return result[: self.MAX_PRESETS]

    def list_custom(self) -> list[PromptPreset]:
        with self._lock:
            return self._read()

    def list_all(self) -> list[PromptPreset]:
        return [*BUILTIN_PRESETS, *self.list_custom()]

    def save(self, *, name: str, instruction: str, description: str = "", template: str = "", preset_id: str = "") -> PromptPreset:
        candidate = self._normalize_item(
            {
                "preset_id": preset_id or "custom-" + uuid.uuid4().hex,
                "name": name,
                "description": description,
                "instruction": instruction,
                "template": template,
            }
        )
        if candidate is None:
            raise ValueError("预设名称和场景规则不能为空")
        with self._lock:
            items = self._read()
            items = [item for item in items if item.preset_id != candidate.preset_id]
            items.append(candidate)
            self._write(items[-self.MAX_PRESETS :])
        return candidate

    def delete(self, preset_id: str) -> bool:
        with self._lock:
            items = self._read()
            kept = [item for item in items if item.preset_id != preset_id]
            if len(kept) == len(items):
                return False
            self._write(kept)
            return True

    def _write(self, items: list[PromptPreset]):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        payload = json.dumps(
            {"schema_version": self.FORMAT_VERSION, "presets": [asdict(item) for item in items]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        envelope = {"version": self.FORMAT_VERSION, "payload": protect_secret(payload)}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=directory, prefix=".prompt-presets-", suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                json.dump(envelope, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass


__all__ = ["BUILTIN_PRESETS", "PromptPreset", "PromptPresetStore", "preset_variables", "render_preset_input"]
