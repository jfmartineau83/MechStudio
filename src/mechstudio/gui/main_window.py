from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import QByteArray, QProcess, QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QToolBar,
)

from ..models import (
    FeatureInstance,
    FeatureModule,
    GenerationSnapshot,
    ParameterValue,
    ProjectDocument,
)
from ..module_registry import ModuleImportError, ModuleRegistry
from ..openscad import OpenScadNotFoundError, build_generation_command, discover_openscad
from ..settings import AppSettings
from ..stl import Mesh, StlError, load_stl
from ..units import ParameterValidationError, convert_parameters
from .dialogs import (
    DiagnosticLogDialog,
    DrawingSetupDialog,
    ModuleManagerDialog,
    PreferencesDialog,
    TypeResolutionDialog,
)
from .drawing import DrawingRenderer, configure_letter_landscape
from .parameter_panel import ParameterPanel
from .viewport import ViewerGrid


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings | None = None):
        super().__init__()
        self.settings_store = settings or AppSettings()
        self.settings_store.ensure_directories()
        self.qt_settings = QSettings("MechanicalPartsStudio", "MechStudio")
        self.registry = ModuleRegistry(self.settings_store.modules_dir)
        registry_errors = self.registry.reload()
        self.document = ProjectDocument()
        self.snapshot: GenerationSnapshot | None = None
        self.mesh: Mesh | None = None
        self.process: QProcess | None = None
        self.generation_cancelled = False
        self.generation_log = ""
        self._generation_revision = 0
        self._generation_mode = "metric"
        self._generation_parameters: dict[str, object] = {}
        self._generation_output: Path | None = None

        self.setWindowTitle("Mechanical Parts Studio")
        self.resize(1450, 900)
        self.setMinimumSize(960, 640)
        self.parameter_panel = ParameterPanel()
        self.viewer = ViewerGrid()
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.addWidget(self.parameter_panel)
        self.workspace_splitter.addWidget(self.viewer)
        self.workspace_splitter.setStretchFactor(0, 0)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setSizes([340, 1100])
        self.setCentralWidget(self.workspace_splitter)
        self.parameter_panel.feature_selected.connect(self._feature_selected)
        self.parameter_panel.values_changed.connect(self._parameter_values_changed)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()
        self._restore_window_state()
        self._refresh_modules()
        self._refresh_recent_menu()
        self._update_title()
        if registry_errors:
            self.warning_label.setText(f"{len(registry_errors)} module(s) could not be loaded")
            self.generation_log = "Module registry warnings:\n" + "\n".join(registry_errors)

    def _icon(self, standard: QStyle.StandardPixmap) -> QIcon:
        return self.style().standardIcon(standard)

    def _create_actions(self) -> None:
        self.new_action = QAction(self._icon(QStyle.StandardPixmap.SP_FileIcon), "New", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.triggered.connect(self.new_project)
        self.open_action = QAction(self._icon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_project)
        self.save_action = QAction(self._icon(QStyle.StandardPixmap.SP_DialogSaveButton), "Save", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_project)
        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(lambda: self.save_project(save_as=True))

        self.metric_action = QAction(self._icon(QStyle.StandardPixmap.SP_MediaPlay), "Generate Metric", self)
        self.metric_action.setShortcut("F5")
        self.metric_action.triggered.connect(lambda: self.generate("metric"))
        self.sae_action = QAction(self._icon(QStyle.StandardPixmap.SP_MediaPlay), "Generate SAE", self)
        self.sae_action.setShortcut("Shift+F5")
        self.sae_action.triggered.connect(lambda: self.generate("sae"))
        self.cancel_action = QAction(self._icon(QStyle.StandardPixmap.SP_BrowserStop), "Cancel Generation", self)
        self.cancel_action.setEnabled(False)
        self.cancel_action.triggered.connect(self.cancel_generation)
        self.export_action = QAction(self._icon(QStyle.StandardPixmap.SP_DriveFDIcon), "Export STL", self)
        self.export_action.setShortcut("Ctrl+E")
        self.export_action.setEnabled(False)
        self.export_action.triggered.connect(self.export_stl)
        self.print_action = QAction(self._icon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Print", self)
        self.print_action.setShortcut("Ctrl+P")
        self.print_action.setEnabled(False)
        self.print_action.triggered.connect(self.print_preview)
        self.pdf_action = QAction("Save Drawing as PDF…", self)
        self.pdf_action.setEnabled(False)
        self.pdf_action.triggered.connect(self.save_drawing_pdf)

        self.import_action = QAction("Import New Feature…", self)
        self.import_action.triggered.connect(self.import_feature)
        self.manage_action = QAction("Manage Installed Features…", self)
        self.manage_action.triggered.connect(self.manage_modules)
        self.reload_action = QAction("Reload Features", self)
        self.reload_action.triggered.connect(self.reload_modules)
        self.modules_folder_action = QAction("Open Modules Folder", self)
        self.modules_folder_action.triggered.connect(self.open_modules_folder)
        self.preferences_action = QAction("Preferences…", self)
        self.preferences_action.triggered.connect(self.preferences)
        self.fit_action = QAction("Fit All Views", self)
        self.fit_action.setShortcut("F")
        self.fit_action.triggered.connect(self.viewer.fit_all)
        self.reset_views_action = QAction("Reset All Cameras", self)
        self.reset_views_action.triggered.connect(self.viewer.reset_all)
        self.log_action = QAction("Diagnostic Log…", self)
        self.log_action.triggered.connect(lambda: DiagnosticLogDialog(self.generation_log, self).exec())
        self.save_preset_action = QAction("Save Named Preset…", self)
        self.save_preset_action.triggered.connect(self.save_preset)
        self.load_preset_action = QAction("Load Preset…", self)
        self.load_preset_action.triggered.connect(self.load_preset)
        self.about_action = QAction("About Mechanical Parts Studio", self)
        self.about_action.triggered.connect(self.about)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action])
        self.recent_menu = file_menu.addMenu("Recent Projects")
        file_menu.addSeparator()
        file_menu.addActions([self.export_action, self.pdf_action, self.print_action])
        file_menu.addSeparator()
        quit_action = QAction("Exit", self)
        quit_action.setShortcut("Alt+F4")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.preferences_action)
        design_menu = self.menuBar().addMenu("&Design")
        design_menu.addActions([self.metric_action, self.sae_action, self.cancel_action])
        design_menu.addSeparator()
        design_menu.addActions([self.save_preset_action, self.load_preset_action])
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addActions([self.fit_action, self.reset_views_action, self.log_action])
        modules_menu = self.menuBar().addMenu("&Modules")
        modules_menu.addActions([self.import_action, self.manage_action, self.reload_action, self.modules_folder_action])
        window_menu = self.menuBar().addMenu("&Window")
        restore_action = QAction("Restore Viewports", self)
        restore_action.triggered.connect(self._restore_viewports)
        window_menu.addAction(restore_action)
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main toolbar")
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(True)
        icon_extent = max(28, QApplication.style().pixelMetric(QStyle.PixelMetric.PM_LargeIconSize))
        toolbar.setIconSize(QSize(icon_extent, icon_extent))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)
        toolbar.addActions([self.new_action, self.open_action, self.save_action])
        toolbar.addSeparator()
        toolbar.addActions([self.metric_action, self.sae_action, self.export_action, self.print_action])

    def _create_status_bar(self) -> None:
        status = self.statusBar()
        self.module_label = QLabel("Feature: none")
        self.generation_label = QLabel("Ready")
        self.mode_label = QLabel("Units: Metric")
        self.bounds_label = QLabel("Bounds: —")
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #c97a40")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(120)
        self.progress.hide()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_generation)
        self.cancel_button.hide()
        for widget in (self.module_label, self.generation_label, self.mode_label, self.bounds_label, self.warning_label):
            status.addPermanentWidget(widget)
        status.addPermanentWidget(self.progress)
        status.addPermanentWidget(self.cancel_button)

    def _restore_window_state(self) -> None:
        geometry = self.qt_settings.value("window/geometry", QByteArray())
        state = self.qt_settings.value("window/state", QByteArray())
        workspace = self.qt_settings.value("layout/workspace", QByteArray())
        horizontal = self.qt_settings.value("layout/view-horizontal", QByteArray())
        vertical = self.qt_settings.value("layout/view-vertical", QByteArray())
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        if workspace:
            self.workspace_splitter.restoreState(workspace)
        self.viewer.restore_layout(bytes(horizontal) if horizontal else None, bytes(vertical) if vertical else None)

    def _save_window_state(self) -> None:
        self.qt_settings.setValue("window/geometry", self.saveGeometry())
        self.qt_settings.setValue("window/state", self.saveState())
        self.qt_settings.setValue("layout/workspace", self.workspace_splitter.saveState())
        horizontal, vertical = self.viewer.save_layout()
        self.qt_settings.setValue("layout/view-horizontal", QByteArray(horizontal))
        self.qt_settings.setValue("layout/view-vertical", QByteArray(vertical))

    def _restore_viewports(self) -> None:
        if self.viewer.expanded:
            self.viewer.toggle_expand(self.viewer.expanded)
        self.viewer.reset_all()

    def _refresh_modules(self) -> None:
        selected = self.document.active_feature.module_id if self.document.active_feature else None
        self.parameter_panel.set_modules(self.registry.enabled_modules, selected)
        module = self.registry.get(selected) if selected else None
        values = {name: value.text for name, value in self.document.active_feature.parameters.items()} if self.document.active_feature else {}
        self.parameter_panel.load_module(module if module and module.enabled else None, values)
        self.module_label.setText(f"Feature: {module.name}" if module else "Feature: none")

    def reload_modules(self) -> None:
        errors = self.registry.reload()
        self._refresh_modules()
        if errors:
            QMessageBox.warning(self, "Module reload", "Some modules could not be loaded:\n\n" + "\n".join(errors))
        else:
            self.statusBar().showMessage("Feature library reloaded", 3000)

    def _feature_selected(self, module_id: str) -> None:
        if not module_id:
            return
        module = self.registry.get(module_id)
        if not module:
            return
        parameters = {
            spec.name: ParameterValue(self._default_text(spec.default))
            for spec in module.parameters
        }
        instance = FeatureInstance(str(uuid.uuid4()), module.module_id, module.version, module.name, parameters)
        self.document.components = [instance]
        self.document.active_component = 0
        if self.document.name == "Untitled":
            self.document.name = module.name
        self.document.touch()
        self.parameter_panel.load_module(module, {name: value.text for name, value in parameters.items()})
        self.module_label.setText(f"Feature: {module.name}")
        self.invalidate_geometry("Feature changed — regenerate")
        self._update_title()

    @staticmethod
    def _default_text(value: object) -> str:
        if isinstance(value, list):
            return "[" + ", ".join(str(item) for item in value) + "]"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _parameter_values_changed(self, values: dict[str, str]) -> None:
        feature = self.document.active_feature
        if not feature:
            return
        feature.parameters = {name: ParameterValue(value) for name, value in values.items()}
        self.document.touch()
        self.invalidate_geometry("Parameters changed — regenerate")
        self._update_title()

    def invalidate_geometry(self, message: str) -> None:
        self.export_action.setEnabled(False)
        self.print_action.setEnabled(False)
        self.pdf_action.setEnabled(False)
        self.warning_label.setText(message)

    def new_project(self) -> None:
        if not self._confirm_discard_changes():
            return
        self.document = ProjectDocument()
        self.snapshot = None
        self.mesh = None
        self.viewer.set_mesh(None)
        self.bounds_label.setText("Bounds: —")
        self.warning_label.clear()
        self._refresh_modules()
        self._update_title()

    def _confirm_discard_changes(self) -> bool:
        if not self.document.modified:
            return True
        result = QMessageBox.warning(
            self,
            "Unsaved changes",
            "Save changes to the current project?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Save:
            return self.save_project()
        return result == QMessageBox.StandardButton.Discard

    def open_project(self, path: Path | None = None) -> None:
        if not self._confirm_discard_changes():
            return
        if path is None:
            selected, _ = QFileDialog.getOpenFileName(self, "Open project", filter="Mechanical Parts Studio (*.mpsproj);;JSON (*.json)")
            if not selected:
                return
            path = Path(selected)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            document = ProjectDocument.from_dict(data, path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Open project", str(exc))
            return
        self.document = document
        self.snapshot = None
        self.mesh = None
        self.viewer.set_mesh(None)
        self.settings_store.add_recent(path)
        self._refresh_recent_menu()
        self._refresh_modules()
        feature = document.active_feature
        module = self.registry.get(feature.module_id) if feature else None
        if feature and not module:
            self.warning_label.setText(f"Missing module: {feature.module_id}")
            QMessageBox.warning(self, "Missing feature", f"This project needs module “{feature.module_id}”. Import or enable it before generating.")
        elif feature and module and feature.module_version != module.version:
            self.warning_label.setText(f"Project uses v{feature.module_version}; installed v{module.version}")
        else:
            self.warning_label.setText("Project opened — generate geometry")
        self.mode_label.setText(f"Units: {'SAE (inches)' if document.generation_mode == 'sae' else 'Metric (mm)'}")
        self._update_title()

    def save_project(self, save_as: bool = False) -> bool:
        path = self.document.path
        if save_as or path is None:
            default = f"{self.document.name or 'Untitled'}.mpsproj"
            selected, _ = QFileDialog.getSaveFileName(self, "Save project", default, "Mechanical Parts Studio (*.mpsproj)")
            if not selected:
                return False
            path = Path(selected)
            if path.suffix.lower() != ".mpsproj":
                path = path.with_suffix(".mpsproj")
        try:
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(json.dumps(self.document.to_dict(), indent=2), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            QMessageBox.critical(self, "Save project", str(exc))
            return False
        self.document.path = path
        self.document.modified = False
        self.settings_store.add_recent(path)
        self._refresh_recent_menu()
        self._update_title()
        self.statusBar().showMessage(f"Saved {path.name}", 3000)
        return True

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = self.settings_store.get("recent_projects", [])
        if not recent:
            empty = self.recent_menu.addAction("No recent projects")
            empty.setEnabled(False)
            return
        for item in recent:
            path = Path(item)
            action = self.recent_menu.addAction(path.name)
            action.setToolTip(str(path))
            action.triggered.connect(lambda _checked=False, selected=path: self.open_project(selected))

    def generate(self, mode: str) -> None:
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Generation running", "Cancel the current generation before starting another.")
            return
        feature = self.document.active_feature
        if not feature:
            QMessageBox.information(self, "Generate", "Select or import a feature first.")
            return
        module = self.registry.get(feature.module_id)
        if not module or not module.enabled:
            QMessageBox.warning(self, "Generate", "The project's feature module is missing or disabled.")
            return
        values = self.parameter_panel.values()
        feature.parameters = {name: ParameterValue(value) for name, value in values.items()}
        if self.document.generation_mode != mode:
            self.document.generation_mode = mode
            self.document.touch()
            self._update_title()
        try:
            converted = convert_parameters(module.parameters, values, mode)
            self.parameter_panel.show_errors({})
            executable = discover_openscad(self.settings_store.get("openscad_executable", "") or None)
            output = self.settings_store.cache_dir / f"generation-{uuid.uuid4().hex}.stl"
            command = build_generation_command(executable, module.source_path, output, converted)
        except ParameterValidationError as exc:
            self.parameter_panel.show_errors(exc.errors)
            QMessageBox.warning(self, "Invalid parameters", "Correct the highlighted values before generating.")
            return
        except (OpenScadNotFoundError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Cannot generate", str(exc))
            return

        self.generation_log = f"Program: {command.executable}\nArguments: {' '.join(command.arguments)}\n\n"
        self._generation_revision = self.document.revision
        self._generation_mode = mode
        self._generation_parameters = converted
        self._generation_output = output
        self.generation_cancelled = False
        self.process = QProcess(self)
        self.process.setProgram(str(command.executable))
        self.process.setArguments(command.arguments)
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.readyReadStandardError.connect(self._read_process_error)
        self.process.finished.connect(self._generation_finished)
        self.process.errorOccurred.connect(self._generation_process_error)
        self.process.start()
        self.progress.show()
        self.cancel_button.show()
        self.cancel_action.setEnabled(True)
        self.metric_action.setEnabled(False)
        self.sae_action.setEnabled(False)
        self.generation_label.setText("Generating…")
        self.mode_label.setText(f"Units: {'SAE (inches)' if mode == 'sae' else 'Metric (mm)'}")
        self.warning_label.clear()

    def _read_process_output(self) -> None:
        if self.process:
            self.generation_log += bytes(self.process.readAllStandardOutput()).decode(errors="replace")

    def _read_process_error(self) -> None:
        if self.process:
            self.generation_log += bytes(self.process.readAllStandardError()).decode(errors="replace")

    def _generation_process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            detail = self.process.errorString() if self.process else "Unknown process error"
            self.generation_log += f"\nOpenSCAD failed to start: {detail}\n"
            self.progress.hide()
            self.cancel_button.hide()
            self.cancel_action.setEnabled(False)
            self.metric_action.setEnabled(True)
            self.sae_action.setEnabled(True)
            self.generation_label.setText("Failed to start")
            self.warning_label.setText("OpenSCAD failed to start — see Diagnostic Log")

    def cancel_generation(self) -> None:
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            return
        self.generation_cancelled = True
        self.process.terminate()
        QTimer.singleShot(1500, self._kill_generation_if_running)
        self.generation_label.setText("Cancelling…")

    def _kill_generation_if_running(self) -> None:
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def _generation_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._read_process_output()
        self._read_process_error()
        self.progress.hide()
        self.cancel_button.hide()
        self.cancel_action.setEnabled(False)
        self.metric_action.setEnabled(True)
        self.sae_action.setEnabled(True)
        output = self._generation_output
        if self.generation_cancelled:
            self.generation_label.setText("Cancelled")
            self.warning_label.setText("Generation cancelled; previous valid geometry was not replaced")
            return
        if exit_code != 0 or not output or not output.is_file():
            self.generation_label.setText("Failed")
            self.warning_label.setText("OpenSCAD generation failed — see Diagnostic Log")
            QMessageBox.critical(self, "OpenSCAD generation failed", "No valid geometry was produced. Open View → Diagnostic Log for details.")
            return
        try:
            mesh = load_stl(output)
        except (OSError, StlError) as exc:
            self.generation_label.setText("Invalid mesh")
            self.warning_label.setText(str(exc))
            QMessageBox.critical(self, "Invalid STL", str(exc))
            return
        self.mesh = mesh
        self.viewer.set_mesh(mesh)
        self.snapshot = GenerationSnapshot(
            self._generation_revision,
            self._generation_mode,
            output,
            self._generation_parameters,
            mesh.bounds,
        )
        x, y, z = mesh.dimensions
        self.bounds_label.setText(f"Bounds: {x:.3f} × {y:.3f} × {z:.3f} mm")
        self.generation_label.setText("Generated")
        current = self.snapshot.current_for(self.document)
        self.export_action.setEnabled(current)
        self.print_action.setEnabled(current)
        self.pdf_action.setEnabled(current)
        self.warning_label.setText("" if current else "Geometry completed but parameters changed; regenerate before export")

    def _require_current_geometry(self) -> bool:
        if not self.snapshot or not self.mesh or not self.snapshot.current_for(self.document) or not self.snapshot.stl_path.is_file():
            QMessageBox.warning(self, "Geometry is out of date", "Generate the current parameters before exporting or drawing.")
            return False
        return True

    def export_stl(self) -> None:
        if not self._require_current_geometry():
            return
        default_name = self._safe_filename(self.document.name) + ".stl"
        selected, _ = QFileDialog.getSaveFileName(self, "Export STL", default_name, "STL mesh (*.stl)")
        if not selected:
            return
        path = Path(selected)
        if path.suffix.lower() != ".stl":
            path = path.with_suffix(".stl")
        try:
            shutil.copy2(self.snapshot.stl_path, path)
        except OSError as exc:
            QMessageBox.critical(self, "Export STL", str(exc))
            return
        self.statusBar().showMessage(f"Exported {path.name} in millimetres", 5000)

    @staticmethod
    def _safe_filename(value: str) -> str:
        invalid = '<>:"/\\|?*'
        result = "".join("-" if character in invalid else character for character in value).strip(" .")
        return result or "part"

    def _drawing_setup(self) -> int | None | bool:
        if not self._require_current_geometry():
            return False
        dialog = DrawingSetupDialog(self)
        if not dialog.exec():
            return False
        return dialog.scale.currentData()

    def print_preview(self) -> None:
        denominator = self._drawing_setup()
        if denominator is False:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        configure_letter_landscape(printer)
        renderer = DrawingRenderer(self.mesh, self.document, denominator)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Technical Drawing Print Preview")
        preview.paintRequested.connect(renderer.paint)
        preview.exec()

    def save_drawing_pdf(self) -> None:
        denominator = self._drawing_setup()
        if denominator is False:
            return
        selected, _ = QFileDialog.getSaveFileName(self, "Save technical drawing", self._safe_filename(self.document.name) + ".pdf", "PDF (*.pdf)")
        if not selected:
            return
        path = Path(selected)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(path))
        configure_letter_landscape(printer)
        DrawingRenderer(self.mesh, self.document, denominator).paint(printer)
        if path.is_file() and path.stat().st_size:
            self.statusBar().showMessage(f"Saved {path.name}", 5000)
        else:
            QMessageBox.critical(self, "Save PDF", "The PDF could not be written.")

    def import_feature(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Import feature", filter="OpenSCAD features (*.scad *.zip);;OpenSCAD (*.scad);;Packages (*.zip)")
        if not selected:
            return
        source = Path(selected)
        try:
            inspection = self.registry.inspect(source)
            main_relative = inspection.scad_files[0]
            if len(inspection.scad_files) > 1:
                main_relative, accepted = QInputDialog.getItem(
                    self,
                    "Choose feature source",
                    "Main OpenSCAD source:",
                    inspection.scad_files,
                    0,
                    False,
                )
                if not accepted:
                    return
            preview = self.registry.preview(source, main_relative)
            resolutions = {}
            if preview.issues:
                dialog = TypeResolutionDialog(preview.issues, self)
                if not dialog.exec():
                    return
                resolutions = dialog.resolutions()
            generator = preview.metadata.get("generator")
            if not generator and preview.candidates:
                options = ["Render source directly", *[f"Call module: {item.name}" for item in preview.candidates]]
                selected_generator, accepted = QInputDialog.getItem(
                    self,
                    "Choose generator",
                    "The file defines callable modules. Choose the complete-part generator, or render its top-level geometry:",
                    options,
                    0,
                    False,
                )
                if not accepted:
                    return
                if selected_generator != options[0]:
                    generator = selected_generator.removeprefix("Call module: ")
            module_id = preview.metadata.get("id")
            replace = False
            if module_id and self.registry.get(module_id):
                answer = QMessageBox.question(self, "Replace installed feature", f"Module “{module_id}” is already installed. Replace its installed copy?")
                if answer != QMessageBox.StandardButton.Yes:
                    return
                replace = True
            module = self.registry.install(
                source,
                main_relative=main_relative,
                type_resolutions=resolutions,
                generator=generator,
                replace=replace,
            )
        except (ModuleImportError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Import feature", str(exc))
            return
        self._refresh_modules()
        index = self.parameter_panel.feature_combo.findData(module.module_id)
        self.parameter_panel.feature_combo.setCurrentIndex(index)
        self.statusBar().showMessage(f"Installed {module.name}", 5000)

    def manage_modules(self) -> None:
        dialog = ModuleManagerDialog(self.registry, self)
        dialog.registry_changed.connect(self._refresh_modules)
        dialog.exec()
        self._refresh_modules()

    def open_modules_folder(self) -> None:
        self.settings_store.modules_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.settings_store.modules_dir)))

    def preferences(self) -> None:
        configured = self.settings_store.get("openscad_executable", "")
        dialog = PreferencesDialog(configured, self)
        if dialog.exec():
            value = dialog.path.text().strip()
            if value and not Path(value).is_file():
                QMessageBox.warning(self, "Preferences", "The selected OpenSCAD executable does not exist.")
                return
            self.settings_store.set("openscad_executable", value)

    def save_preset(self) -> None:
        feature = self.document.active_feature
        module = self.registry.get(feature.module_id) if feature else None
        if not module:
            QMessageBox.information(self, "Save preset", "Select a feature first.")
            return
        name, accepted = QInputDialog.getText(self, "Save preset", "Preset name:")
        if not accepted or not name.strip():
            return
        try:
            self.registry.save_preset(self.settings_store.presets_dir, module, name.strip(), self.parameter_panel.values())
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Save preset", str(exc))
            return
        self.statusBar().showMessage(f"Saved preset “{name.strip()}”", 3000)

    def load_preset(self) -> None:
        feature = self.document.active_feature
        module = self.registry.get(feature.module_id) if feature else None
        if not module:
            QMessageBox.information(self, "Load preset", "Select a feature first.")
            return
        presets = self.registry.list_presets(self.settings_store.presets_dir, module.module_id)
        if not presets:
            QMessageBox.information(self, "Load preset", "No presets are saved for this feature.")
            return
        names = [item[0] for item in presets]
        selected, accepted = QInputDialog.getItem(self, "Load preset", "Preset:", names, 0, False)
        if not accepted:
            return
        path = presets[names.index(selected)][1]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            values = {str(name): str(value) for name, value in data["values"].items()}
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Load preset", str(exc))
            return
        self.parameter_panel.set_values(values)
        self._parameter_values_changed(self.parameter_panel.values())

    def about(self) -> None:
        executable = discover_openscad(self.settings_store.get("openscad_executable", "") or None)
        QMessageBox.about(
            self,
            "About Mechanical Parts Studio",
            "<b>Mechanical Parts Studio 0.1.0</b><br><br>Offline, module-driven parametric mechanical design.<br>"
            f"OpenSCAD: {executable or 'not found'}<br><br>Geometry is always generated and exported in millimetres.",
        )

    def _update_title(self) -> None:
        marker = "*" if self.document.modified else ""
        self.setWindowTitle(f"{self.document.name}{marker} — Mechanical Parts Studio")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._confirm_discard_changes():
            event.ignore()
            return
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.cancel_generation()
        self._save_window_state()
        event.accept()

