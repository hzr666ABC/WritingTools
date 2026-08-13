import unittest
from unittest.mock import ANY, patch

from ui.AutostartManager import AutostartManager


class _Key:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class AutostartManagerTests(unittest.TestCase):
    def setUp(self):
        AutostartManager.last_error = ""

    @patch.object(AutostartManager, "get_startup_path", return_value=r"C:\Apps\Writing Tools.exe")
    def test_startup_command_quotes_paths_with_spaces(self, _path):
        self.assertEqual(
            AutostartManager.get_startup_command(),
            '"C:\\Apps\\Writing Tools.exe"',
        )

    @patch("ui.AutostartManager.winreg")
    @patch.object(
        AutostartManager,
        "get_startup_command",
        return_value='"C:\\Apps\\Writing Tools.exe"',
    )
    def test_enable_writes_current_user_run_value_and_removes_legacy_names(
        self, _command, registry
    ):
        registry.HKEY_CURRENT_USER = object()
        registry.KEY_QUERY_VALUE = 1
        registry.KEY_SET_VALUE = 2
        registry.REG_SZ = 1
        registry.CreateKeyEx.return_value = _Key()

        self.assertTrue(AutostartManager.set_autostart(True))

        registry.SetValueEx.assert_called_once_with(
            ANY,
            AutostartManager.VALUE_NAME,
            0,
            registry.REG_SZ,
            '"C:\\Apps\\Writing Tools.exe"',
        )
        self.assertEqual(
            registry.DeleteValue.call_count,
            len(AutostartManager.LEGACY_VALUE_NAMES),
        )

    @patch("ui.AutostartManager.winreg")
    @patch.object(
        AutostartManager,
        "get_startup_command",
        return_value='"C:\\Apps\\Writing Tools.exe"',
    )
    def test_disable_removes_current_and_legacy_values(self, _command, registry):
        registry.HKEY_CURRENT_USER = object()
        registry.KEY_QUERY_VALUE = 1
        registry.KEY_SET_VALUE = 2
        registry.CreateKeyEx.return_value = _Key()

        self.assertTrue(AutostartManager.set_autostart(False))
        self.assertEqual(
            registry.DeleteValue.call_count,
            1 + len(AutostartManager.LEGACY_VALUE_NAMES),
        )

    @patch("ui.AutostartManager.winreg")
    @patch.object(
        AutostartManager,
        "get_startup_command",
        return_value='"C:\\Apps\\Writing Tools.exe"',
    )
    @patch.object(
        AutostartManager,
        "get_startup_path",
        return_value=r"C:\Apps\Writing Tools.exe",
    )
    def test_check_accepts_exact_quoted_command(self, _path, _command, registry):
        registry.HKEY_CURRENT_USER = object()
        registry.KEY_QUERY_VALUE = 1
        registry.REG_SZ = 1
        registry.REG_EXPAND_SZ = 2
        registry.OpenKey.return_value = _Key()
        registry.QueryValueEx.side_effect = [
            ('"C:\\Apps\\Writing Tools.exe"', registry.REG_SZ)
        ]

        self.assertTrue(AutostartManager.check_autostart())

    @patch.object(AutostartManager, "get_startup_command", return_value=None)
    def test_unsupported_runtime_returns_clear_error(self, _command):
        self.assertFalse(AutostartManager.set_autostart(True))
        self.assertIn("Windows", AutostartManager.last_error)


if __name__ == "__main__":
    unittest.main()
