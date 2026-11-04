from pathlib import Path
import math
import os
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtPrintSupport import QPrinter
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except ImportError:
    HAS_QT = False

from mechstudio.openscad import discover_openscad


@unittest.skipUnless(HAS_QT and discover_openscad(), "PySide6 and OpenSCAD are required")
class GuiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dynamic_feature_generation_viewports_and_pdf(self):
        from mechstudio.gui.drawing import DrawingRenderer, configure_letter_landscape
        from mechstudio.gui.main_window import MainWindow
        from mechstudio.settings import AppSettings

        with tempfile.TemporaryDirectory() as temporary:
            settings = AppSettings(Path(temporary))
            window = MainWindow(settings)
            module = window.registry.install(ROOT / "examples" / "modules" / "plain_bushing.scad")
            window._refresh_modules()
            window.parameter_panel.feature_combo.setCurrentIndex(
                window.parameter_panel.feature_combo.findData(module.module_id)
            )
            self.assertEqual(set(window.parameter_panel.editors), {"inner_diameter", "outer_diameter", "length"})

            window.parameter_panel.set_values(
                {"inner_diameter": "1/8", "outer_diameter": "1/2", "length": "1 1/2"}
            )
            window._parameter_values_changed(window.parameter_panel.values())
            def generate_and_wait(mode):
                window.generate(mode)
                self.assertIsNotNone(window.process)
                loop = QEventLoop()
                window.process.finished.connect(loop.quit)
                QTimer.singleShot(60_000, loop.quit)
                loop.exec()

            generate_and_wait("sae")

            self.assertIsNotNone(window.snapshot, window.generation_log)
            self.assertTrue(window.snapshot.current_for(window.document))
            self.assertTrue(window.export_action.isEnabled())
            self.assertTrue(all(panel.canvas.mesh is window.mesh for panel in window.viewer.panels))
            self.assertAlmostEqual(window.mesh.dimensions[0], 12.7, places=2)
            self.assertAlmostEqual(window.mesh.dimensions[2], 38.1, places=2)
            smallest_diameter = 2 * min(
                math.hypot(vertex[0], vertex[1])
                for triangle in window.mesh.triangles
                for vertex in triangle
            )
            self.assertAlmostEqual(smallest_diameter, 3.175, places=2)

            generate_and_wait("metric")
            self.assertAlmostEqual(window.mesh.dimensions[0], 0.5, places=3)
            self.assertAlmostEqual(window.mesh.dimensions[2], 1.5, places=3)

            pdf = Path(temporary) / "drawing.pdf"
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(pdf))
            configure_letter_landscape(printer)
            DrawingRenderer(window.mesh, window.document, None).paint(printer)
            self.assertTrue(pdf.is_file())
            self.assertGreater(pdf.stat().st_size, 1_000)
            window.document.modified = False
            window.close()


if __name__ == "__main__":
    unittest.main()
