from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import ParameterType
from ..module_registry import ModuleRegistry
from ..scad_parser import ParseIssue


class PreferencesDialog(QDialog):
    def __init__(self, current_executable: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(600, 130)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        self.path = QLineEdit(current_executable)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row_layout.addWidget(self.path, 1)
        row_layout.addWidget(browse)
        form.addRow("OpenSCAD executable:", row)
        layout.addLayout(form)
        note = QLabel("Leave blank to search PATH and the standard OpenSCAD installation folders.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select OpenSCAD", filter="OpenSCAD (openscad.exe);;Programs (*.exe)")
        if path:
            self.path.setText(path)


class TypeResolutionDialog(QDialog):
    def __init__(self, issues: list[ParseIssue], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Resolve parameter meanings")
        self.resize(720, 360)
        self.combos: dict[str, QComboBox] = {}
        layout = QVBoxLayout(self)
        explanation = QLabel(
            "These numeric values do not say whether they are dimensions, angles, counts, or unitless values. "
            "Choose their meanings before installing. The choices are cached with the installed module."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        table = QTableWidget(len(issues), 3)
        table.setHorizontalHeaderLabels(["Parameter", "Reason", "Meaning"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        choices = [
            ParameterType.LENGTH,
            ParameterType.FLOAT,
            ParameterType.INTEGER,
            ParameterType.ANGLE,
            ParameterType.RATIO,
            ParameterType.PERCENTAGE,
        ]
        for row, issue in enumerate(issues):
            table.setItem(row, 0, QTableWidgetItem(issue.parameter))
            table.setItem(row, 1, QTableWidgetItem(issue.message))
            combo = QComboBox()
            for choice in choices:
                combo.addItem(choice.value.title(), choice)
            table.setCellWidget(row, 2, combo)
            self.combos[issue.parameter] = combo
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def resolutions(self) -> dict[str, ParameterType]:
        return {name: combo.currentData() for name, combo in self.combos.items()}


class ModuleManagerDialog(QDialog):
    registry_changed = Signal()

    def __init__(self, registry: ModuleRegistry, parent: QWidget | None = None):
        super().__init__(parent)
        self.registry = registry
        self.setWindowTitle("Manage Installed Features")
        self.resize(820, 420)
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Enabled", "Feature", "Version", "Module ID", "Source"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)
        controls = QHBoxLayout()
        toggle = QPushButton("Enable / Disable")
        toggle.clicked.connect(self._toggle)
        remove = QPushButton("Remove Installed Copy…")
        remove.clicked.connect(self._remove)
        controls.addWidget(toggle)
        controls.addWidget(remove)
        controls.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        controls.addWidget(close)
        layout.addLayout(controls)
        self.refresh()

    def refresh(self) -> None:
        modules = self.registry.modules
        self.table.setRowCount(len(modules))
        for row, module in enumerate(modules):
            enabled = QTableWidgetItem("Yes" if module.enabled else "No")
            enabled.setData(Qt.ItemDataRole.UserRole, module.module_id)
            self.table.setItem(row, 0, enabled)
            self.table.setItem(row, 1, QTableWidgetItem(module.name))
            self.table.setItem(row, 2, QTableWidgetItem(module.version))
            self.table.setItem(row, 3, QTableWidgetItem(module.module_id))
            self.table.setItem(row, 4, QTableWidgetItem(module.original_source))
        self.table.resizeColumnsToContents()

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return str(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))

    def _toggle(self) -> None:
        module_id = self._selected_id()
        if not module_id:
            return
        module = self.registry.get(module_id)
        if module:
            self.registry.set_enabled(module_id, not module.enabled)
            self.refresh()
            self.registry_changed.emit()

    def _remove(self) -> None:
        module_id = self._selected_id()
        if not module_id:
            return
        module = self.registry.get(module_id)
        if not module:
            return
        result = QMessageBox.question(
            self,
            "Remove feature",
            f"Remove the installed copy of “{module.name}”?\n\nThe original imported file is not changed.",
        )
        if result == QMessageBox.StandardButton.Yes:
            self.registry.remove(module_id)
            self.refresh()
            self.registry_changed.emit()


class DiagnosticLogDialog(QDialog):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("OpenSCAD Diagnostic Log")
        self.resize(850, 520)
        layout = QVBoxLayout(self)
        from PySide6.QtWidgets import QPlainTextEdit

        editor = QPlainTextEdit(text)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class DrawingSetupDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Technical Drawing")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.scale = QComboBox()
        self.scale.addItem("Fit to page (NTS)", None)
        for denominator in (1, 2, 5, 10, 20, 50):
            self.scale.addItem(f"1:{denominator}", denominator)
        form.addRow("Drawing scale:", self.scale)
        layout.addLayout(form)
        note = QLabel("General bounding dimensions are derived from the current mesh. Specialized callouts require module metadata.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

