# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

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
