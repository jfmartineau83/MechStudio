from __future__ import annotations

from datetime import date
import math
from typing import Iterable

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen, QPolygonF
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPageLayout, QPageSize

from ..models import ProjectDocument
from ..stl import Mesh, Triangle
from .viewport import project_triangle


def configure_letter_landscape(printer: QPrinter) -> None:
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape)
    printer.setPageMargins(QMarginsF(8, 8, 8, 8), QPageLayout.Unit.Millimeter)


class DrawingRenderer:
    def __init__(self, mesh: Mesh, document: ProjectDocument, scale_denominator: int | None):
        self.mesh = mesh
        self.document = document
        self.scale_denominator = scale_denominator

    def paint(self, printer: QPrinter) -> None:
        painter = QPainter(printer)
        try:
            page = QRectF(printer.pageLayout().paintRectPixels(printer.resolution()))
            self._paint_page(painter, page, printer.resolution())
        finally:
            painter.end()

    def _paint_page(self, painter: QPainter, page: QRectF, dpi: int) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(page, Qt.GlobalColor.white)
        line = max(1.0, dpi / 600)
        painter.setPen(QPen(Qt.GlobalColor.black, line))
        painter.drawRect(page.adjusted(line, line, -line, -line))

        title_height = page.height() * 0.18
        drawing_area = page.adjusted(page.width() * 0.025, page.height() * 0.03, -page.width() * 0.025, -title_height - page.height() * 0.03)
        gap = drawing_area.width() * 0.025
        left_width = drawing_area.width() * 0.34
        top_box = QRectF(drawing_area.left(), drawing_area.top(), left_width, (drawing_area.height() - gap) / 2)
        front_box = QRectF(drawing_area.left(), top_box.bottom() + gap, left_width, top_box.height())
        ortho_box = QRectF(top_box.right() + gap, drawing_area.top(), drawing_area.width() - left_width - gap, drawing_area.height())
        for label, view, box in (("TOP (XY)", "top", top_box), ("FRONT (XZ)", "front", front_box), ("ISOMETRIC", "ortho", ortho_box)):
            self._draw_view(painter, box, label, view, dpi)
        self._draw_title_block(painter, QRectF(page.left(), page.bottom() - title_height, page.width(), title_height), dpi)

    def _draw_view(self, painter: QPainter, box: QRectF, label: str, view: str, dpi: int) -> None:
        painter.save()
        painter.setPen(QPen(Qt.GlobalColor.black, max(1.0, dpi / 900)))
        painter.drawRect(box)
        font = QFont("Arial", max(7, round(dpi / 110)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(box.adjusted(8, 5, -5, -5), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, label)

        yaw, pitch = math.radians(-35), math.radians(28)
        triangles = [project_triangle(item, view, yaw, pitch) for item in self.mesh.triangles]
        xs = [point[0] for item in triangles for point in item.points]
        ys = [point[1] for item in triangles for point in item.points]
        model_width = max(max(xs) - min(xs), 1e-9)
        model_height = max(max(ys) - min(ys), 1e-9)
        content = box.adjusted(box.width() * 0.09, box.height() * 0.14, -box.width() * 0.09, -box.height() * 0.14)
        if self.scale_denominator:
            scale = dpi / 25.4 / self.scale_denominator
        else:
            scale = min(content.width() / model_width, content.height() / model_height)
        center_x, center_y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        center = content.center()
        painter.setClipRect(box.adjusted(2, 2, -2, -2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(Qt.GlobalColor.black, max(0.8, dpi / 1200)))
        for triangle in triangles:
            polygon = QPolygonF(
                [QPointF(center.x() + (x - center_x) * scale, center.y() + (y - center_y) * scale) for x, y in triangle.points]
            )
            painter.drawPolygon(polygon)
        painter.setClipping(False)

        x, y, z = self.mesh.dimensions
        if view == "top":
            dimension = f"{x:.3f} × {y:.3f} mm"
        elif view == "front":
            dimension = f"{x:.3f} × {z:.3f} mm"
        else:
            dimension = f"BOUNDING: {x:.3f} × {y:.3f} × {z:.3f} mm"
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(box.adjusted(8, 5, -8, -8), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, dimension)
        painter.restore()

    def _draw_title_block(self, painter: QPainter, block: QRectF, dpi: int) -> None:
        painter.save()
        painter.setPen(QPen(Qt.GlobalColor.black, max(1.0, dpi / 700)))
        painter.drawRect(block)
        company_width = block.width() * 0.34
        details_width = block.width() * 0.42
        x1, x2 = block.left() + company_width, block.left() + company_width + details_width
        painter.drawLine(x1, block.top(), x1, block.bottom())
        painter.drawLine(x2, block.top(), x2, block.bottom())
        mid = block.center().y()
        painter.drawLine(x1, mid, block.right(), mid)
        title_font = QFont("Arial", max(9, round(dpi / 80)))
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QRectF(block.left() + 12, block.top(), company_width - 24, block.height()), Qt.AlignmentFlag.AlignCenter, "MECHANICAL PARTS STUDIO")
        body_font = QFont("Arial", max(7, round(dpi / 115)))
        painter.setFont(body_font)
        scale = f"1:{self.scale_denominator}" if self.scale_denominator else "NTS"
        middle_top = QRectF(x1 + 10, block.top() + 5, details_width - 20, block.height() / 2 - 10)
        middle_bottom = QRectF(x1 + 10, mid + 5, details_width - 20, block.height() / 2 - 10)
        painter.drawText(middle_top, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"TITLE: {self.document.name}\nDRAWING NO: {self.document.drawing_number or '—'}")
        painter.drawText(middle_bottom, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"DESCRIPTION: {self.document.description or '—'}")
        right_top = QRectF(x2 + 10, block.top() + 5, block.right() - x2 - 20, block.height() / 2 - 10)
        right_bottom = QRectF(x2 + 10, mid + 5, block.right() - x2 - 20, block.height() / 2 - 10)
        painter.drawText(right_top, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"REV: {self.document.revision_label}\nDATE: {date.today().isoformat()}")
        painter.drawText(right_bottom, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"UNITS: mm\nSCALE: {scale}")
        painter.restore()

