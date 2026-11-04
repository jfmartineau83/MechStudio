from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..models import FeatureModule, ParameterSpec, ParameterType


class ParameterEditor(QWidget):
    changed = Signal()

    def __init__(self, spec: ParameterSpec, parent: QWidget | None = None):
        super().__init__(parent)
        self.spec = spec
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.line: QLineEdit | None = None
        self.checkbox: QCheckBox | None = None
        self.combo: QComboBox | None = None
        self.slider: QSlider | None = None
        if spec.parameter_type == ParameterType.BOOLEAN:
            self.checkbox = QCheckBox()
            self.checkbox.setChecked(bool(spec.default))
            self.checkbox.toggled.connect(self.changed)
            layout.addWidget(self.checkbox)
        elif spec.parameter_type == ParameterType.ENUM and spec.options:
            self.combo = QComboBox()
            for option in spec.options:
                self.combo.addItem(option.label, str(option.value))
            selected = self.combo.findData(str(spec.default))
            self.combo.setCurrentIndex(max(0, selected))
            self.combo.currentIndexChanged.connect(self.changed)
            layout.addWidget(self.combo)
        else:
            self.line = QLineEdit(self._format_default(spec.default))
            self.line.setClearButtonEnabled(True)
            self.line.setPlaceholderText(spec.parameter_type.value)
            self.line.textChanged.connect(self._line_changed)
            layout.addWidget(self.line, 1)
            if (
                spec.parameter_type in {ParameterType.INTEGER, ParameterType.FLOAT, ParameterType.ANGLE, ParameterType.RATIO, ParameterType.PERCENTAGE}
                and spec.minimum is not None
                and spec.maximum is not None
                and spec.step
                and 0 < (spec.maximum - spec.minimum) / spec.step <= 1000
            ):
                self.slider = QSlider(Qt.Orientation.Horizontal)
                self.slider.setRange(0, round((spec.maximum - spec.minimum) / spec.step))
                self.slider.setValue(round((float(spec.default) - spec.minimum) / spec.step))
                self.slider.valueChanged.connect(self._slider_changed)
                layout.addWidget(self.slider, 1)
        self.setToolTip(spec.description)

    @staticmethod
    def _format_default(value: Any) -> str:
        if isinstance(value, list):
            return "[" + ", ".join(str(item) for item in value) + "]"
        return str(value)

    def _line_changed(self) -> None:
        if self.slider and self.line and self.spec.minimum is not None and self.spec.step:
            try:
                numeric = float(self.line.text())
                value = round((numeric - self.spec.minimum) / self.spec.step)
                self.slider.blockSignals(True)
                self.slider.setValue(value)
                self.slider.blockSignals(False)
            except ValueError:
                pass
        self.changed.emit()

    def _slider_changed(self, value: int) -> None:
        assert self.line and self.spec.minimum is not None and self.spec.step
        numeric = self.spec.minimum + value * self.spec.step
        text = str(int(numeric)) if self.spec.parameter_type == ParameterType.INTEGER else f"{numeric:g}"
        self.line.setText(text)

    def value(self) -> str:
        if self.checkbox:
            return "true" if self.checkbox.isChecked() else "false"
        if self.combo:
            return str(self.combo.currentData())
        return self.line.text() if self.line else ""

    def set_value(self, text: str) -> None:
        self.blockSignals(True)
        if self.checkbox:
            self.checkbox.setChecked(text.strip().lower() in {"true", "1", "yes", "on"})
        elif self.combo:
            index = self.combo.findData(text)
            if index >= 0:
                self.combo.setCurrentIndex(index)
        elif self.line:
            self.line.setText(text)
        self.blockSignals(False)

    def set_error(self, message: str | None) -> None:
        widget = self.line or self.combo or self.checkbox
        if not widget:
            return
        widget.setStyleSheet("border: 1px solid #d9534f" if message else "")
        widget.setToolTip(message or self.spec.description)


class ParameterPanel(QFrame):
    feature_selected = Signal(str)
    values_changed = Signal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.editors: dict[str, ParameterEditor] = {}
        self.specs: dict[str, ParameterSpec] = {}
        self._loading = False
        layout = QVBoxLayout(self)
        title = QLabel("Feature parameters")
        title.setStyleSheet("font-size: 16px; font-weight: 650")
        layout.addWidget(title)
        self.feature_combo = QComboBox()
        self.feature_combo.setPlaceholderText("Select an installed feature")
        self.feature_combo.currentIndexChanged.connect(self._feature_changed)
        layout.addWidget(self.feature_combo)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.contents = QWidget()
        self.form_stack = QVBoxLayout(self.contents)
        self.form_stack.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.contents)
        layout.addWidget(self.scroll, 1)
        self.message = QLabel("Import a feature module to begin.")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #7f8c99")
        layout.addWidget(self.message)

    def set_modules(self, modules: list[FeatureModule], selected_id: str | None = None) -> None:
        self.feature_combo.blockSignals(True)
        self.feature_combo.clear()
        self.feature_combo.addItem("Select feature…", "")
        for module in modules:
            self.feature_combo.addItem(f"{module.name}  v{module.version}", module.module_id)
        if selected_id:
            index = self.feature_combo.findData(selected_id)
            self.feature_combo.setCurrentIndex(max(0, index))
        self.feature_combo.blockSignals(False)

    def _feature_changed(self, _index: int) -> None:
        if not self._loading:
            self.feature_selected.emit(str(self.feature_combo.currentData() or ""))

    def clear_form(self) -> None:
        while self.form_stack.count():
            item = self.form_stack.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.editors.clear()
        self.specs.clear()

    def load_module(self, module: FeatureModule | None, values: dict[str, str] | None = None) -> None:
        self._loading = True
        self.clear_form()
        if not module:
            self.message.setText("Select an installed feature.")
            self._loading = False
            return
        values = values or {}
        groups: dict[str, QFormLayout] = {}
        for spec in module.parameters:
            if spec.group not in groups:
                box = QGroupBox(spec.group)
                box.setCheckable(True)
                box.setChecked(True)
                form = QFormLayout(box)
                form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
                groups[spec.group] = form
                self.form_stack.addWidget(box)
            editor = ParameterEditor(spec)
            editor.set_value(values.get(spec.name, ParameterEditor._format_default(spec.default)))
            editor.changed.connect(self._values_changed)
            groups[spec.group].addRow(spec.label + ":", editor)
            self.editors[spec.name] = editor
            self.specs[spec.name] = spec
        self.form_stack.addStretch()
        self.message.setText(module.description or "Parameters are defined by the installed OpenSCAD module.")
        self._loading = False
        self._update_visibility()

    def values(self) -> dict[str, str]:
        return {name: editor.value() for name, editor in self.editors.items()}

    def set_values(self, values: dict[str, str]) -> None:
        self._loading = True
        for name, value in values.items():
            if name in self.editors:
                self.editors[name].set_value(value)
        self._loading = False
        self._update_visibility()

    def show_errors(self, errors: dict[str, str]) -> None:
        for name, editor in self.editors.items():
            editor.set_error(errors.get(name))
        self.message.setText("Fix the highlighted parameter values." if errors else "Parameters are valid.")

    def _values_changed(self) -> None:
        if self._loading:
            return
        self._update_visibility()
        self.values_changed.emit(self.values())

    def _update_visibility(self) -> None:
        values = self.values()
        for name, spec in self.specs.items():
            visible = True
            if spec.visible_if and "=" in spec.visible_if:
                controller, expected = spec.visible_if.split("=", 1)
                visible = values.get(controller) == expected
            self.editors[name].setVisible(visible)
            label = self.editors[name].parentWidget().layout().labelForField(self.editors[name]) if hasattr(self.editors[name].parentWidget().layout(), "labelForField") else None
            if label:
                label.setVisible(visible)

