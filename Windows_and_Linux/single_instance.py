"""Windows single-instance coordination for the packaged desktop app."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0


class SingleInstanceGuard:
    """Own a named mutex and receive activation requests from later launches."""

    def __init__(self, instance_name="WritingToolsCN.Desktop.Instance"):
        self.already_running = False
        self._event_handle = None
        self._mutex_handle = None
        self._kernel32 = None

        if os.name != "nt":
            return

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateEventW.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        kernel32.CreateEventW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.SetEvent.argtypes = (wintypes.HANDLE,)
        kernel32.SetEvent.restype = wintypes.BOOL
        kernel32.ResetEvent.argtypes = (wintypes.HANDLE,)
        kernel32.ResetEvent.restype = wintypes.BOOL
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32

        event_name = f"Local\\{instance_name}.Activate"
        mutex_name = f"Local\\{instance_name}.Mutex"
        self._event_handle = kernel32.CreateEventW(None, True, False, event_name)
        if not self._event_handle:
            raise ctypes.WinError(ctypes.get_last_error())

        ctypes.set_last_error(0)
        self._mutex_handle = kernel32.CreateMutexW(None, False, mutex_name)
        if not self._mutex_handle:
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    def notify_existing(self):
        """Ask the running instance to bring its UI to the foreground."""

        if self._kernel32 and self._event_handle:
            self._kernel32.SetEvent(self._event_handle)

    def consume_activation_request(self):
        """Return True once for each coalesced activation request."""

        if not self._kernel32 or not self._event_handle:
            return False
        if self._kernel32.WaitForSingleObject(self._event_handle, 0) != WAIT_OBJECT_0:
            return False
        self._kernel32.ResetEvent(self._event_handle)
        return True

    def close(self):
        if not self._kernel32:
            return
        for handle_name in ("_mutex_handle", "_event_handle"):
            handle = getattr(self, handle_name)
            if handle:
                self._kernel32.CloseHandle(handle)
                setattr(self, handle_name, None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
