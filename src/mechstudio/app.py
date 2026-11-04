from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from mechstudio.gui.main_window import MainWindow


STYLE = """
QMainWindow { background: #eef1f4; }
QToolBar { spacing: 5px; padding: 5px; border-bottom: 1px solid #aab2bc; background: #f8f9fb; }
QToolButton { min-width: 74px; padding: 5px; }
QGroupBox { font-weight: 600; margin-top: 12px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
QLineEdit, QComboBox { min-height: 25px; }
QStatusBar { border-top: 1px solid #aab2bc; }
"""


def main() -> int:
    QCoreApplication.setOrganizationName("MechanicalPartsStudio")
    QCoreApplication.setApplicationName("MechStudio")
    QCoreApplication.setApplicationVersion("0.1.0")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

