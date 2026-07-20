"""Versioned import/export format for shareable Writing Tools presets."""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone

from preset_icon_library import normalize_preset_icon


PACK_FORMAT = "writing-tools-preset-pack"
PACK_VERSION = 1
MAX_PACK_BYTES = 2_000_000
MAX_PRESETS = 200
MAX_NAME_CHARS = 80
MAX_LABEL_CHARS = 120
MAX_PREFIX_CHARS = 10_000
MAX_INSTRUCTION_CHARS = 50_000
MAX_HOTKEY_CHARS = 80
ALLOWED_FIELDS = {
    "label", "prefix", "instruction", "icon", "open_in_window",
    "uses_base_instruction", "hotkey",
}


def export_preset_pack(options: dict) -> dict:
    presets = {}
    for key, value in (options or {}).items():
        if not isinstance(value, dict):
            continue
        presets[str(key)] = {
            field: copy.deepcopy(value[field])
            for field in ALLOWED_FIELDS
            if field in value
        }
    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "presets": presets,
    }


def validate_preset_pack(pack: dict) -> dict:
    if not isinstance(pack, dict):
        raise ValueError("预设包必须是 JSON 对象")
    if pack.get("format") != PACK_FORMAT:
        raise ValueError("这不是 Writing Tools 预设包")
    if int(pack.get("version", 0)) != PACK_VERSION:
        raise ValueError("不支持的预设包版本")
    presets = pack.get("presets")
    if not isinstance(presets, dict) or not presets:
        raise ValueError("预设包中没有可导入的预设")
    if len(presets) > MAX_PRESETS:
        raise ValueError(f"预设包最多包含 {MAX_PRESETS} 个预设")
    output = {}
    for raw_key, raw_value in presets.items():
        key = str(raw_key).strip()
        if not key or not isinstance(raw_value, dict):
            continue
        if len(key) > MAX_NAME_CHARS or any(ord(char) < 32 for char in key):
            raise ValueError("预设名称过长或包含控制字符")
        instruction = str(raw_value.get("instruction", "")).strip()
        if not instruction:
            continue
        if len(instruction) > MAX_INSTRUCTION_CHARS:
            raise ValueError(f"“{key}”的提示词超过 {MAX_INSTRUCTION_CHARS} 字符")
        value = {field: copy.deepcopy(raw_value[field]) for field in ALLOWED_FIELDS if field in raw_value}
        value["instruction"] = instruction
        value["prefix"] = str(value.get("prefix", ""))
        if len(value["prefix"]) > MAX_PREFIX_CHARS:
            raise ValueError(f"“{key}”的前缀超过 {MAX_PREFIX_CHARS} 字符")
        if "label" in value:
            value["label"] = str(value["label"]).strip()[:MAX_LABEL_CHARS]
        value["icon"] = normalize_preset_icon(value.get("icon"))
        value["open_in_window"] = value.get("open_in_window", False) is True
        value["uses_base_instruction"] = value.get("uses_base_instruction", True) is not False
        if value.get("hotkey"):
            value["hotkey"] = str(value["hotkey"]).strip().lower()
            if len(value["hotkey"]) > MAX_HOTKEY_CHARS:
                raise ValueError(f"“{key}”的快捷键字段过长")
        output[key] = value
    if not output:
        raise ValueError("预设包中的内容无效")
    return output


def load_preset_pack(path: str) -> dict:
    """Read a bounded UTF-8 preset pack before validating its schema."""
    try:
        size = os.path.getsize(path)
    except OSError as error:
        raise ValueError(f"无法读取预设包：{error}") from error
    if size > MAX_PACK_BYTES:
        raise ValueError(f"预设包不能超过 {MAX_PACK_BYTES // 1_000_000} MB")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return validate_preset_pack(json.load(handle))
    except UnicodeDecodeError as error:
        raise ValueError("预设包不是有效的 UTF-8 文件") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"预设包 JSON 格式无效：第 {error.lineno} 行") from error


def merge_presets(existing: dict, imported: dict, global_shortcut: str = "") -> tuple[dict, list[str]]:
    """Merge safely, rename collisions, and clear conflicting imported hotkeys."""
    merged = copy.deepcopy(existing or {})
    notices = []
    used_hotkeys = {
        str(value.get("hotkey", "")).strip().lower()
        for value in merged.values()
        if isinstance(value, dict) and value.get("hotkey")
    }
    if global_shortcut:
        used_hotkeys.add(global_shortcut.strip().lower())
    for original_key, raw_value in imported.items():
        key = original_key
        suffix = 2
        while key in merged:
            key = f"{original_key}（导入 {suffix}）"
            suffix += 1
        value = copy.deepcopy(raw_value)
        hotkey = str(value.get("hotkey", "")).strip().lower()
        if hotkey and hotkey in used_hotkeys:
            value.pop("hotkey", None)
            notices.append(f"“{key}”的快捷键冲突，已自动清除。")
        elif hotkey:
            used_hotkeys.add(hotkey)
        merged[key] = value
    return merged, notices
