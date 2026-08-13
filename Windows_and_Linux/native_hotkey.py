"""Native Windows registration for the application's core shortcuts.

RegisterHotKey consumes the chord before it reaches the focused application or
IME. This matters especially for Ctrl+Space because many Chinese input methods
otherwise toggle language state at the same time Writing Tools opens.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
from ctypes import wintypes


class WindowsCtrlSpaceHotkey:
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012
    PM_NOREMOVE = 0x0000
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    MOD_NOREPEAT = 0x4000
    VK_SPACE = 0x20
    HOTKEY_ID = 0x5754

    def __init__(
        self,
        callback,
        *,
        modifiers=None,
        virtual_key=None,
        hotkey_id=None,
        label="Ctrl+Space",
        user32=None,
        kernel32=None,
    ):
        self.callback = callback
        self.modifiers = (
            self.MOD_CONTROL | self.MOD_NOREPEAT
            if modifiers is None
            else int(modifiers)
        )
        self.virtual_key = self.VK_SPACE if virtual_key is None else int(virtual_key)
        self.hotkey_id = self.HOTKEY_ID if hotkey_id is None else int(hotkey_id)
        self.label = str(label or "快捷键")
        self.user32 = user32 or (ctypes.windll.user32 if os.name == "nt" else None)
        self.kernel32 = kernel32 or (ctypes.windll.kernel32 if os.name == "nt" else None)
        self.thread = None
        self.thread_id = 0
        self.registered = False
        self.error = ""
        self._ready = threading.Event()

    @staticmethod
    def _signature(function, argtypes, restype):
        try:
            function.argtypes = argtypes
            function.restype = restype
        except (AttributeError, TypeError):
            pass

    def start(self, timeout=2.0) -> bool:
        if self.user32 is None or self.kernel32 is None:
            self.error = "当前系统不支持 Windows 原生快捷键"
            return False
        if self.thread and self.thread.is_alive():
            return self.registered
        self._ready.clear()
        self.thread = threading.Thread(
            target=self._run,
            name="WritingToolsCtrlSpaceHotkey",
            daemon=True,
        )
        self.thread.start()
        self._ready.wait(max(0.1, float(timeout)))
        return self.registered

    def _run(self):
        self._signature(self.kernel32.GetCurrentThreadId, [], wintypes.DWORD)
        self._signature(
            self.user32.RegisterHotKey,
            [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT],
            wintypes.BOOL,
        )
        self._signature(
            self.user32.UnregisterHotKey,
            [wintypes.HWND, ctypes.c_int],
            wintypes.BOOL,
        )
        self._signature(
            self.user32.GetMessageW,
            [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT],
            ctypes.c_int,
        )
        self.thread_id = int(self.kernel32.GetCurrentThreadId())
        message = wintypes.MSG()
        try:
            self.registered = bool(
                self.user32.RegisterHotKey(
                    None,
                    self.hotkey_id,
                    self.modifiers,
                    self.virtual_key,
                )
            )
            if not self.registered:
                self.error = f"{self.label} 已被其他程序注册"
                return
            self._ready.set()
            while True:
                result = int(self.user32.GetMessageW(ctypes.byref(message), None, 0, 0))
                if result <= 0:
                    break
                if message.message == self.WM_HOTKEY and int(message.wParam) == self.hotkey_id:
                    try:
                        self.callback()
                    except Exception:
                        # A hotkey hook must remain alive even if its consumer is closing.
                        logging.exception("Native Ctrl+Space callback failed")
        finally:
            if self.registered:
                self.user32.UnregisterHotKey(None, self.hotkey_id)
            self.registered = False
            self._ready.set()

    def stop(self, timeout=2.0):
        if not self.thread or not self.thread.is_alive() or not self.thread_id:
            return
        self._signature(
            self.user32.PostThreadMessageW,
            [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
            wintypes.BOOL,
        )
        self.user32.PostThreadMessageW(self.thread_id, self.WM_QUIT, 0, 0)
        self.thread.join(max(0.1, float(timeout)))


__all__ = ["WindowsCtrlSpaceHotkey"]
