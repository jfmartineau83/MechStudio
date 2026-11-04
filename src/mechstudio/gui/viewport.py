from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSplitter, QVBoxLayout, QWidget

from ..stl import Mesh, Triangle, Vec3


@dataclass(slots=True)
class ProjectedTriangle:
    points: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    depth: float
    shade: float


def _rotate(vertex: Vec3, yaw: float, pitch: float) -> Vec3:
    x, y, z = vertex
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    rx, ry = cy * x - sy * y, sy * x + cy * y
    return rx, cp * ry - sp * z, sp * ry + cp * z


def project_triangle(triangle: Triangle, view: str, yaw: float, pitch: float) -> ProjectedTriangle:
    transformed: list[Vec3] = []
    for vertex in triangle:
        if view == "top":
            transformed.append((vertex[0], -vertex[1], vertex[2]))
        elif view == "front":
            transformed.append((vertex[0], -vertex[2], -vertex[1]))
        else:
            transformed.append(_rotate(vertex, yaw, pitch))
    a, b, c = transformed
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nz = ux * vy - uy * vx
    length = math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + nz**2)
    shade = 0.45 if not length else 0.28 + 0.67 * abs(nz / length)
    return ProjectedTriangle(
        ((a[0], a[1]), (b[0], b[1]), (c[0], c[1])),
        (a[2] + b[2] + c[2]) / 3,
        shade,
    )


class MeshCanvas(QWidget):
    def __init__(self, view: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.view = view
        self.mesh: Mesh | None = None
        self.zoom = 1.0
        self.pan = QPointF()
        self.yaw = math.radians(-35)
        self.pitch = math.radians(28)
        self.last_position = QPoint()
        self.drag_mode = ""
        self.setMinimumSize(180, 130)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_mesh(self, mesh: Mesh | None) -> None:
        self.mesh = mesh
        self.fit_view()

    def fit_view(self) -> None:
        self.zoom = 1.0
        self.pan = QPointF()
        self.update()

    def reset_camera(self) -> None:
        self.yaw = math.radians(-35)
        self.pitch = math.radians(28)
        self.fit_view()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#131820"))
        self._draw_grid(painter)
        if not self.mesh:
            painter.setPen(QColor("#8491a5"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Generate geometry to populate this view")
            return

        projected = [project_triangle(item, self.view, self.yaw, self.pitch) for item in self.mesh.triangles]
        xs = [point[0] for item in projected for point in item.points]
        ys = [point[1] for item in projected for point in item.points]
        width = max(max(xs) - min(xs), 1e-9)
        height = max(max(ys) - min(ys), 1e-9)
        scale = min((self.width() - 32) / width, (self.height() - 32) / height) * self.zoom
        center_x = (min(xs) + max(xs)) / 2
        center_y = (min(ys) + max(ys)) / 2
        screen_center = QPointF(self.width() / 2, self.height() / 2) + self.pan

        projected.sort(key=lambda item: item.depth)
        edge_pen = QPen(QColor(25, 43, 58, 165), 0.8)
        for item in projected:
            polygon = QPolygonF(
                [
                    QPointF(
                        screen_center.x() + (x - center_x) * scale,
                        screen_center.y() + (y - center_y) * scale,
                    )
                    for x, y in item.points
                ]
            )
            base = QColor("#55b6d9")
            color = QColor.fromRgbF(
                base.redF() * item.shade,
                base.greenF() * item.shade,
                base.blueF() * item.shade,
                1.0,
            )
            painter.setBrush(color)
            painter.setPen(edge_pen)
            painter.drawPolygon(polygon)

        painter.setPen(QColor("#d7e4ee"))
        dimensions = self.mesh.dimensions
        painter.drawText(10, self.height() - 10, f"{dimensions[0]:.3f} × {dimensions[1]:.3f} × {dimensions[2]:.3f} mm")

    def _draw_grid(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor(43, 52, 64), 1))
        spacing = 24
        offset_x = int(self.pan.x()) % spacing
        offset_y = int(self.pan.y()) % spacing
        for x in range(offset_x, self.width(), spacing):
            painter.drawLine(x, 0, x, self.height())
        for y in range(offset_y, self.height(), spacing):
            painter.drawLine(0, y, self.width(), y)
        painter.setPen(QPen(QColor(65, 77, 91), 1))
        painter.drawLine(0, self.height() // 2 + int(self.pan.y()), self.width(), self.height() // 2 + int(self.pan.y()))
        painter.drawLine(self.width() // 2 + int(self.pan.x()), 0, self.width() // 2 + int(self.pan.x()), self.height())

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom = min(100.0, max(0.02, self.zoom * factor))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.last_position = event.position().toPoint()
        if event.button() == Qt.MouseButton.LeftButton and self.view == "ortho":
            self.drag_mode = "rotate"
        elif event.button() in {Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton}:
            self.drag_mode = "pan"
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self.drag_mode:
            return
        current = event.position().toPoint()
        delta = current - self.last_position
        self.last_position = current
        if self.drag_mode == "rotate":
            self.yaw += delta.x() * 0.01
            self.pitch = max(-math.pi / 2, min(math.pi / 2, self.pitch + delta.y() * 0.01))
        else:
            self.pan += QPointF(delta)
        self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:  # noqa: N802
        self.drag_mode = ""
        self.unsetCursor()


class ViewportPanel(QFrame):
    expand_requested = Signal(object)

    def __init__(self, title: str, view: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 4, 4)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600")
        header_layout.addWidget(label)
        header_layout.addStretch()
        fit = QPushButton("Fit")
        fit.setToolTip("Fit model to this view")
        fit.clicked.connect(lambda: self.canvas.fit_view())
        reset = QPushButton("Reset")
        reset.setToolTip("Reset this camera")
        reset.clicked.connect(lambda: self.canvas.reset_camera())
        self.expand = QPushButton("Expand")
        self.expand.setToolTip("Expand or restore this viewport")
        self.expand.clicked.connect(lambda: self.expand_requested.emit(self))
        for button in (fit, reset, self.expand):
            button.setFlat(True)
            header_layout.addWidget(button)
        layout.addWidget(header)
        self.canvas = MeshCanvas(view)
        layout.addWidget(self.canvas, 1)


class ViewerGrid(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.top_panel = ViewportPanel("Top — XY", "top")
        self.front_panel = ViewportPanel("Front — XZ", "front")
        self.ortho_panel = ViewportPanel("Ortho", "ortho")
        self.horizontal = QSplitter(Qt.Orientation.Horizontal)
        self.horizontal.addWidget(self.top_panel)
        self.horizontal.addWidget(self.front_panel)
        self.vertical = QSplitter(Qt.Orientation.Vertical)
        self.vertical.addWidget(self.horizontal)
        self.vertical.addWidget(self.ortho_panel)
        self.vertical.setStretchFactor(0, 1)
        self.vertical.setStretchFactor(1, 2)
        layout.addWidget(self.vertical)
        self.expanded: ViewportPanel | None = None
        self._saved_horizontal: list[int] = []
        self._saved_vertical: list[int] = []
        for panel in self.panels:
            panel.expand_requested.connect(self.toggle_expand)

    @property
    def panels(self) -> tuple[ViewportPanel, ViewportPanel, ViewportPanel]:
        return self.top_panel, self.front_panel, self.ortho_panel

    def set_mesh(self, mesh: Mesh | None) -> None:
        for panel in self.panels:
            panel.canvas.set_mesh(mesh)

    def fit_all(self) -> None:
        for panel in self.panels:
            panel.canvas.fit_view()

    def reset_all(self) -> None:
        for panel in self.panels:
            panel.canvas.reset_camera()

    def toggle_expand(self, panel: ViewportPanel) -> None:
        if self.expanded:
            for item in self.panels:
                item.show()
                item.expand.setText("Expand")
            if self._saved_horizontal:
                self.horizontal.setSizes(self._saved_horizontal)
            if self._saved_vertical:
                self.vertical.setSizes(self._saved_vertical)
            self.expanded = None
            return
        self._saved_horizontal = self.horizontal.sizes()
        self._saved_vertical = self.vertical.sizes()
        for item in self.panels:
            if item is not panel:
                item.hide()
        panel.expand.setText("Restore")
        self.expanded = panel

    def save_layout(self) -> tuple[bytes, bytes]:
        return bytes(self.horizontal.saveState()), bytes(self.vertical.saveState())

    def restore_layout(self, horizontal: bytes | None, vertical: bytes | None) -> None:
        if horizontal:
            self.horizontal.restoreState(horizontal)
        if vertical:
            self.vertical.restoreState(vertical)

