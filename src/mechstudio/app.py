from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

from mechstudio.gui.main_window import MainWindow
from mechstudio.settings import AppSettings


STYLE = """
QMainWindow { background: #eef1f4; }
QToolBar { spacing: 5px; padding: 5px; border-bottom: 1px solid #aab2bc; background: #f8f9fb; }
QToolButton { min-width: 74px; padding: 5px; }
QGroupBox { font-weight: 600; margin-top: 12px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
QLineEdit, QComboBox { min-height: 25px; }
QStatusBar { border-top: 1px solid #aab2bc; }
"""


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv if argv is None else argv)
    smoke_test = "--smoke-test" in arguments
    qt_arguments = [argument for argument in arguments if argument != "--smoke-test"]
    QCoreApplication.setOrganizationName("MechanicalPartsStudio")
    QCoreApplication.setApplicationName("MechStudio")
    QCoreApplication.setApplicationVersion("0.1.0")
    app = QApplication(qt_arguments)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    smoke_directory = tempfile.TemporaryDirectory(prefix="mechstudio-smoke-") if smoke_test else None
    settings = AppSettings(Path(smoke_directory.name)) if smoke_directory else None
    window = MainWindow(settings)
    window.show()
    if smoke_test:
        QTimer.singleShot(750, app.quit)
    result = app.exec()
    if smoke_directory:
        smoke_directory.cleanup()
    return result


if __name__ == "__main__":
    raise SystemExit(main())

