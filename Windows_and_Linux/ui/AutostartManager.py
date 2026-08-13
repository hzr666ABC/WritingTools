"""Per-user Windows startup registration for the packaged application."""

from __future__ import annotations

import logging
import os
import sys

try:
    import winreg
except ImportError:  # pragma: no cover - exercised on non-Windows platforms
    winreg = None


class AutostartManager:
    """Manage the current user's Windows ``Run`` entry without elevation."""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    VALUE_NAME = "Writing Tools 中文增强版"
    LEGACY_VALUE_NAMES = ("WritingTools", "WritingToolsCN", "Writing Tools")
    last_error = ""

    @staticmethod
    def is_compiled():
        """Return whether the process is a frozen desktop build."""

        return bool(getattr(sys, "frozen", False))

    @classmethod
    def get_startup_path(cls):
        """Return the absolute packaged executable path, or ``None``."""

        if winreg is None or not sys.platform.startswith("win32"):
            return None
        if not cls.is_compiled():
            return None
        path = os.path.abspath(sys.executable)
        if '"' in path or not path.lower().endswith(".exe"):
            return None
        return path

    @classmethod
    def get_startup_command(cls):
        """Return a safely quoted command suitable for a Windows Run value."""

        path = cls.get_startup_path()
        return f'"{path}"' if path else None

    @classmethod
    def _delete_value(cls, key, name):
        try:
            winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass

    @classmethod
    def set_autostart(cls, enable: bool) -> bool:
        """Enable or disable startup for the current Windows user."""

        cls.last_error = ""
        command = cls.get_startup_command()
        if not command:
            cls.last_error = "开机启动仅支持正式打包的 Windows 版本。"
            return False

        try:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                cls.RUN_KEY,
                0,
                winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
            ) as key:
                if enable:
                    winreg.SetValueEx(
                        key,
                        cls.VALUE_NAME,
                        0,
                        winreg.REG_SZ,
                        command,
                    )
                else:
                    cls._delete_value(key, cls.VALUE_NAME)

                # Remove names used by older builds so Windows never launches
                # two copies after an upgrade.
                for legacy_name in cls.LEGACY_VALUE_NAMES:
                    cls._delete_value(key, legacy_name)
            return True
        except OSError as error:
            cls.last_error = f"无法修改当前用户的启动项：{error}"
            logging.error("Failed to modify autostart registry: %s", error)
            return False

    @classmethod
    def check_autostart(cls) -> bool:
        """Return whether a valid startup entry targets this exact EXE."""

        cls.last_error = ""
        command = cls.get_startup_command()
        path = cls.get_startup_path()
        if not command or not path:
            return False

        accepted_values = {command.casefold(), path.casefold()}
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                cls.RUN_KEY,
                0,
                winreg.KEY_QUERY_VALUE,
            ) as key:
                names = (cls.VALUE_NAME, *cls.LEGACY_VALUE_NAMES)
                for name in names:
                    try:
                        value, value_type = winreg.QueryValueEx(key, name)
                    except FileNotFoundError:
                        continue
                    if (
                        value_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ)
                        and str(value).strip().casefold() in accepted_values
                    ):
                        return True
        except FileNotFoundError:
            return False
        except OSError as error:
            cls.last_error = f"无法读取当前用户的启动项：{error}"
            logging.error("Failed to inspect autostart registry: %s", error)
        return False


__all__ = ["AutostartManager"]
