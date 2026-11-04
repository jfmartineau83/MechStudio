# Verification results

Last verified: 2026-11-04 on Windows 11, Python 3.14.3, PySide6 6.12.0,
and OpenSCAD 2021.01.

## Automated suite

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --cov=mechstudio
```

Result: **18 tests passed plus 7 parameterized invalid-input cases**. Overall
line coverage was 63%; the domain parser, document model, and number parser
were 80%, 95%, and 91% covered respectively. GUI branches that open native
file, print, or confirmation dialogs account for most uncovered lines.

The suite verifies:

- decimal, proper-fraction, mixed-fraction, malformed, division-by-zero, and
  code-like input handling;
- conversion of only `length` parameters in SAE mode;
- Customizer/MPS discovery for the bushing and the independently authored
  gear, including length, angle, integer, ratio, boolean, and enum types;
- explicit reporting of ambiguous numeric parameters;
- preservation of original input notation in project round trips;
- generation revision tracking;
- module installation, process-restart reload, enable/disable, removal, and a
  second module without a core change, plus unsafe-package rejection;
- ASCII STL parsing, bounds, and empty-mesh rejection;
- real OpenSCAD CLI generation; and
- a Qt integration path that dynamically creates bushing controls, generates
  `ID=1/8`, `OD=1/2`, `Length=1 1/2` in SAE mode, loads the mesh into all three
  viewports, verifies 12.7 mm OD and 38.1 mm length, enables export only for the
  current document revision, and writes a nonempty drawing PDF.

## Packaging

Command:

```powershell
.\.venv\Scripts\pyinstaller.exe packaging\MechStudio.spec --noconfirm
```

Result: **successful**. The onedir build is under `dist/MechStudio`, occupies
approximately 158 MB, and its executable passed a launch/responsiveness smoke
test. PyInstaller reported only expected cross-platform optional imports
(`pwd`, `grp`, `fcntl`, and related POSIX modules).

## Manual checks still recommended before a public release

- exercise the system printer dialog against a physical printer;
- open an exported STL in the locally installed Bambu Studio and inspect its
  unit display (the mesh bounds are already asserted in millimetres);
- test several third-party module packages with nested dependencies; and
- code-sign the Windows executable and add an installer/updater if distribution
  beyond a portable folder is desired.

