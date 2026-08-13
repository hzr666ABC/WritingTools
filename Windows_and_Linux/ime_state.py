"""Best-effort capture and restoration of a source window's Windows IME state."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


def _focused_child(top_level_handle: int) -> int:
    user32 = ctypes.windll.user32
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
    user32.GetGUIThreadInfo.restype = wintypes.BOOL
    thread_id = user32.GetWindowThreadProcessId(wintypes.HWND(int(top_level_handle)), None)
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(info)
    if thread_id and user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
        return int(info.hwndFocus or top_level_handle)
    return int(top_level_handle)


def capture_ime_state(top_level_handle: int | None) -> dict | None:
    if os.name != "nt" or not top_level_handle:
        return None
    try:
        target = _focused_child(int(top_level_handle))
        imm32 = ctypes.windll.imm32
        imm32.ImmGetContext.argtypes = [wintypes.HWND]
        imm32.ImmGetContext.restype = wintypes.HANDLE
        imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
        imm32.ImmReleaseContext.restype = wintypes.BOOL
        imm32.ImmGetOpenStatus.argtypes = [wintypes.HANDLE]
        imm32.ImmGetOpenStatus.restype = wintypes.BOOL
        imm32.ImmGetConversionStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
        imm32.ImmGetConversionStatus.restype = wintypes.BOOL
        context = imm32.ImmGetContext(wintypes.HWND(target))
        if not context:
            return None
        try:
            conversion = wintypes.DWORD()
            sentence = wintypes.DWORD()
            open_status = bool(imm32.ImmGetOpenStatus(context))
            has_conversion = bool(imm32.ImmGetConversionStatus(context, ctypes.byref(conversion), ctypes.byref(sentence)))
            return {
                "window": target,
                "open": open_status,
                "conversion": int(conversion.value) if has_conversion else None,
                "sentence": int(sentence.value) if has_conversion else None,
            }
        finally:
            imm32.ImmReleaseContext(wintypes.HWND(target), context)
    except (AttributeError, OSError, ValueError):
        return None


def restore_ime_state(state: dict | None, top_level_handle: int | None = None) -> bool:
    if os.name != "nt" or not isinstance(state, dict):
        return False
    try:
        target = _focused_child(int(top_level_handle)) if top_level_handle else int(state.get("window") or 0)
        if not target:
            return False
        imm32 = ctypes.windll.imm32
        imm32.ImmGetContext.argtypes = [wintypes.HWND]
        imm32.ImmGetContext.restype = wintypes.HANDLE
        imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
        imm32.ImmReleaseContext.restype = wintypes.BOOL
        imm32.ImmSetOpenStatus.argtypes = [wintypes.HANDLE, wintypes.BOOL]
        imm32.ImmSetOpenStatus.restype = wintypes.BOOL
        imm32.ImmSetConversionStatus.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        imm32.ImmSetConversionStatus.restype = wintypes.BOOL
        context = imm32.ImmGetContext(wintypes.HWND(target))
        if not context:
            return False
        try:
            imm32.ImmSetOpenStatus(context, wintypes.BOOL(bool(state.get("open"))))
            if state.get("conversion") is not None and state.get("sentence") is not None:
                imm32.ImmSetConversionStatus(context, wintypes.DWORD(int(state["conversion"])), wintypes.DWORD(int(state["sentence"])))
            return True
        finally:
            imm32.ImmReleaseContext(wintypes.HWND(target), context)
    except (AttributeError, OSError, TypeError, ValueError):
        return False


__all__ = ["capture_ime_state", "restore_ime_state"]
