"""Diff rendering and source-window activation for safe text application."""

from __future__ import annotations

import ctypes
import difflib
import html
import os
import re


def capture_foreground_window() -> int | None:
    if os.name != "nt":
        return None
    handle = int(ctypes.windll.user32.GetForegroundWindow())
    return handle or None


def activate_window(handle: int | None) -> bool:
    if os.name != "nt" or not handle:
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow(int(handle), 9)  # SW_RESTORE
    return bool(user32.SetForegroundWindow(int(handle)))


def _tokens(text: str) -> list[str]:
    return re.findall(r"\s+|[\u3400-\u9fff]|[A-Za-z0-9_]+|[^\s]", text or "")


def build_diff_html(original: str, result: str, dark: bool = False) -> str:
    """Return a readable word/character-level inline diff."""
    old_tokens = _tokens(original)
    new_tokens = _tokens(result)
    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens)
    parts = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old = html.escape("".join(old_tokens[i1:i2]))
        new = html.escape("".join(new_tokens[j1:j2]))
        if tag == "equal":
            parts.append(new)
        elif tag == "delete":
            parts.append(f'<span class="deleted">{old}</span>')
        elif tag == "insert":
            parts.append(f'<span class="inserted">{new}</span>')
        else:
            parts.append(f'<span class="deleted">{old}</span><span class="inserted">{new}</span>')
    foreground = "#eef1ff" if dark else "#202638"
    background = "#242833" if dark else "#ffffff"
    return (
        "<html><head><style>"
        f"body{{font-family:'Microsoft YaHei UI','Segoe UI';font-size:14px;line-height:1.7;color:{foreground};background:{background};white-space:pre-wrap;}}"
        ".deleted{background:#ffd9df;color:#9f2538;text-decoration:line-through;border-radius:3px;padding:1px 2px;}"
        ".inserted{background:#d8f6e4;color:#16663a;border-radius:3px;padding:1px 2px;}"
        "</style></head><body>" + "".join(parts) + "</body></html>"
    )
