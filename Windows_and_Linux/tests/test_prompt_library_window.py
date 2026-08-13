import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets
from PySide6.QtTest import QTest

from prompt_library import PromptLibraryStore
from ui.PromptLibraryWindow import PromptLibraryWindow


class PromptLibraryWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_search_version_copy_and_load_clicks(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PromptLibraryStore(os.path.join(directory, "library.json"))
            entry = store.save(title="产品方案", prompt="版本一", tags=["产品"])
            store.save(entry_id=entry["id"], title="产品方案", prompt="版本二", tags=["产品"])
            workbench = SimpleNamespace(
                _closed=False,
                loaded="",
                load_library_prompt=lambda value: setattr(workbench, "loaded", value),
                showNormal=lambda: None,
                raise_=lambda: None,
                activateWindow=lambda: None,
            )
            app = SimpleNamespace(
                prompt_library_store=store,
                prompt_library_window=None,
                prompt_workbench_window=workbench,
                open_prompt_with_text=lambda value: workbench.load_library_prompt(value),
            )
            window = PromptLibraryWindow(app)
            app.prompt_library_window = window
            window.show()
            self.qt_app.processEvents()

            window.search.setText("产品")
            self.qt_app.processEvents()
            self.assertEqual(window.list_widget.count(), 1)
            self.assertEqual(window.version_combo.count(), 2)
            self.assertEqual(window.current_prompt(), "版本二")

            QTest.mouseClick(window.copy_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(QtWidgets.QApplication.clipboard().text(), "版本二")
            QTest.mouseClick(window.use_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(workbench.loaded, "版本二")
            window.close()

    def test_use_opens_workbench_when_it_does_not_exist_yet(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PromptLibraryStore(os.path.join(directory, "library.json"))
            store.save(title="收藏", prompt="首次载入", tags=[])
            opened = []
            app = SimpleNamespace(
                prompt_library_store=store,
                prompt_library_window=None,
                prompt_workbench_window=None,
                open_prompt_with_text=opened.append,
            )
            window = PromptLibraryWindow(app)
            window.show()
            self.qt_app.processEvents()

            QTest.mouseClick(window.use_button, QtCore.Qt.MouseButton.LeftButton)
            self.assertEqual(opened, ["首次载入"])
            window.close()


if __name__ == "__main__":
    unittest.main()
