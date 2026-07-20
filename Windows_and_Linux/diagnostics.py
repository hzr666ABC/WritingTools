"""Redacted local compatibility checks for Writing Tools."""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from dataclasses import asdict, dataclass

import pyperclip

from provider_studio import probe_provider
from secure_storage import redacted_config, redact_text


@dataclass
class DiagnosticItem:
    name: str
    ok: bool
    detail: str
    category: str = "本机"


def _json_check(path: str, label: str) -> DiagnosticItem:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("根节点不是对象")
        return DiagnosticItem(label, True, f"UTF-8 JSON 正常，共 {len(value)} 项")
    except Exception as error:
        return DiagnosticItem(label, False, str(error))


def run_local_diagnostics(config_path: str, options_path: str) -> list[DiagnosticItem]:
    install_dir = os.path.dirname(config_path)
    items = [
        _json_check(config_path, "配置文件"),
        _json_check(options_path, "预设文件"),
        DiagnosticItem(
            "安装目录写入",
            os.access(install_dir, os.W_OK),
            install_dir if os.access(install_dir, os.W_OK) else "当前账户无法写入安装目录",
        ),
        DiagnosticItem(
            "Python/系统架构",
            True,
            f"Python {platform.python_version()} · {platform.system()} {platform.release()} · {platform.machine()}",
        ),
    ]
    return items


def run_clipboard_roundtrip() -> DiagnosticItem:
    marker = f"writing-tools-diagnostic-{time.time_ns()}"
    try:
        original = pyperclip.paste()
        pyperclip.copy(marker)
        actual = pyperclip.paste()
        pyperclip.copy(original)
        ok = actual == marker
        return DiagnosticItem(
            "剪贴板读写与恢复",
            ok,
            "写入、读取和恢复均正常" if ok else "剪贴板返回内容与测试值不一致",
            "文本捕获",
        )
    except Exception as error:
        return DiagnosticItem("剪贴板读写与恢复", False, str(error), "文本捕获")


def run_provider_diagnostic(provider_name: str, values: dict) -> tuple[DiagnosticItem, object]:
    result = probe_provider(provider_name, values)
    detail = result.message
    if result.ok:
        detail += f" 延迟 {result.latency_ms} ms。"
    return DiagnosticItem("当前 AI 服务", result.ok, detail, "AI 服务"), result


def build_report(items: list[DiagnosticItem], config: dict) -> dict:
    """Build a support report that is safe to copy or export."""
    return {
        "format": "writing-tools-diagnostic-report",
        "version": 1,
        "generated_by": "Writing Tools 中文定制版",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "checks": [
            {**asdict(item), "detail": redact_text(item.detail)}
            for item in items
        ],
        "config": redacted_config(config),
    }
