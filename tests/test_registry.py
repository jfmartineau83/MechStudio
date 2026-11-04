from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mechstudio.module_registry import ModuleImportError, ModuleRegistry


class RegistryTests(unittest.TestCase):
    def test_install_reload_disable_and_second_module_without_core_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = ModuleRegistry(Path(temporary) / "modules")
            first = registry.install(ROOT / "examples" / "modules" / "plain_bushing.scad")
            second = registry.install(ROOT / "examples" / "modules" / "spur_gear.scad")
            self.assertNotEqual(first.module_id, second.module_id)
            self.assertEqual(len(registry.enabled_modules), 2)

            restarted = ModuleRegistry(Path(temporary) / "modules")
            self.assertFalse(restarted.reload())
            self.assertEqual(len(restarted.enabled_modules), 2)
            restarted.set_enabled(first.module_id, False)
            self.assertEqual([item.module_id for item in restarted.enabled_modules], [second.module_id])
            restarted.remove(first.module_id)
            self.assertIsNone(restarted.get(first.module_id))

    def test_invalid_module_and_unsafe_package_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = ModuleRegistry(root / "modules")
            invalid = root / "invalid.scad"
            invalid.write_text("cube(1);\n", encoding="utf-8")
            with self.assertRaises(ModuleImportError):
                registry.install(invalid)

            package = root / "unsafe.zip"
            with zipfile.ZipFile(package, "w") as bundle:
                bundle.writestr("../escape.scad", "value = 1;")
            with self.assertRaises(ModuleImportError):
                registry.preview(package)


if __name__ == "__main__":
    unittest.main()

