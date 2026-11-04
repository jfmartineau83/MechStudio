# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import PySide6

# SPECPATH is the directory containing this spec (packaging/).
root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "src" / "mechstudio" / "app.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "examples" / "modules"), "examples/modules")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# The Codex build host adds document/PDF helper directories to PATH. They are
# not application dependencies, but PyInstaller's binary scanner can otherwise
# capture their private ICU, OpenSSL, and Universal CRT DLLs. Those copies can
# shadow the Windows/Python runtime libraries expected by Qt. Never publish a
# binary discovered from that host-only runtime cache.
a.binaries = [
    entry for entry in a.binaries
    if "codex-runtimes" not in str(entry[1]).casefold()
]

# Python 3.14 currently ships MSVC runtime 14.42, while PySide6 6.12 is linked
# against 14.44. PyInstaller normally puts Python's copy at the application
# root, where the Windows loader finds it before PySide6's matching copy. That
# produces WinError 127 ("specified procedure could not be found") while
# importing QtCore. Replace the two root runtime entries with PySide6's copies;
# keep the package-local entries as collected by the standard hook.
pyside_dir = Path(PySide6.__file__).parent
required_msvc_runtimes = {"VCRUNTIME140.dll", "VCRUNTIME140_1.dll"}
for index, (destination, source, typecode) in enumerate(a.binaries):
    if destination in required_msvc_runtimes:
        matching_runtime = pyside_dir / destination
        if not matching_runtime.is_file():
            raise FileNotFoundError(f"PySide6 runtime is missing: {matching_runtime}")
        a.binaries[index] = (destination, str(matching_runtime), typecode)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MechStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="MechStudio",
)
