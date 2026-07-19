"""Prompt composition and option metadata helpers.

The UI lets users describe the goal of a custom preset.  That goal should not
have to repeat the safety and output-shape rules that every inline writing
action needs, so custom presets are composed from a stable base instruction
plus the user's objective.
"""

from __future__ import annotations

from copy import deepcopy


BASE_CUSTOM_PRESET_INSTRUCTION = """You are a precise writing and coding assistant.
Apply the preset objective to the user's selected text.
Output ONLY the final transformed text or code, without explanations, labels, prefaces, or quotation marks.
Preserve the input language unless the preset objective explicitly requests a translation.
Preserve the original meaning, factual details, structure, and formatting unless the preset objective explicitly asks to change them.
Do not answer or respond conversationally to the selected text.
If the selected text is incompatible with the preset objective, output exactly \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\"."""


BUILTIN_OPTION_LABELS_ZH_CN = {
    "Proofread": "校对",
    "Rewrite": "改写",
    "Friendly": "更友好",
    "Professional": "更专业",
    "Concise": "更简洁",
    "Summary": "总结",
    "Key Points": "关键要点",
    "Table": "表格",
    "Custom": "自定义修改",
}


def uses_base_instruction(option: dict) -> bool:
    """Return whether an option should receive the shared custom base prompt.

    New custom presets store the explicit flag.  The icon fallback upgrades
    presets created by older WritingTools versions without rewriting the file.
    """

    if "uses_base_instruction" in option:
        return bool(option["uses_base_instruction"])
    return option.get("icon") == "icons/custom"


def compose_system_instruction(option: dict) -> str:
    """Build the final system instruction for an option."""

    objective = str(option.get("instruction", "")).strip()
    if not uses_base_instruction(option):
        return objective
    if not objective:
        return BASE_CUSTOM_PRESET_INSTRUCTION
    return (
        f"{BASE_CUSTOM_PRESET_INSTRUCTION}\n\n"
        "Preset objective supplied by the user:\n"
        f"{objective}"
    )


def option_display_name(option_key: str, option: dict) -> str:
    """Return the localized display label while keeping stable internal keys."""

    return str(
        option.get("label")
        or BUILTIN_OPTION_LABELS_ZH_CN.get(option_key)
        or option_key
    )


def normalize_options(options: dict | None) -> dict:
    """Return a normalized copy that remains compatible with legacy files."""

    normalized = deepcopy(options or {})
    for key, option in normalized.items():
        if not isinstance(option, dict):
            continue
        if key in BUILTIN_OPTION_LABELS_ZH_CN:
            option.setdefault("label", BUILTIN_OPTION_LABELS_ZH_CN[key])
        if option.get("icon") == "icons/custom":
            option.setdefault("uses_base_instruction", True)
    return normalized
