import logging
import os
import sys

from PySide6 import QtCore

from single_instance import SingleInstanceGuard
from WritingToolApp import WritingToolApp

# Keep production logs minimal. Developers can opt into DEBUG explicitly.
_log_level_name = os.environ.get("WRITINGTOOLS_LOG_LEVEL", "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(level=_log_level, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    """
    The main entry point of the application.
    """
    with SingleInstanceGuard() as instance_guard:
        if instance_guard.already_running:
            instance_guard.notify_existing()
            return 0

        app = WritingToolApp(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        activation_timer = QtCore.QTimer(app)
        activation_timer.setInterval(180)
        activation_timer.timeout.connect(
            lambda: (
                app.activate_from_second_instance()
                if instance_guard.consume_activation_request()
                else None
            )
        )
        activation_timer.start()
        return app.exec()


if __name__ == '__main__':
    sys.exit(main())
