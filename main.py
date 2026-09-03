import os
import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from version import VERSION


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Chess Pionier")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("Chess Pionier")

    w = MainWindow()
    w.show()

    # The window performs its own best-effort cleanup in closeEvent.
    # After Qt has returned from the event loop, terminate the Python process
    # directly. This avoids native SDL/Qt finalizer crashes seen on Raspberry Pi.
    exit_code = app.exec()
    os._exit(int(exit_code))


if __name__ == "__main__":
    main()
