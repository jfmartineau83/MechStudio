# Mechanical Parts Studio

Mechanical Parts Studio is a Windows-first, offline desktop application for
parametric mechanical parts. The application knows how to edit parameters,
convert dimensions, run OpenSCAD, display real STL geometry, save editable
projects, and produce engineering drawings. Individual parts remain ordinary,
portable OpenSCAD files; the core contains no part-specific behavior.

This repository is the first working milestone. It includes:

- a PySide6 desktop UI with the requested menus and large-button toolbar;
- dynamic parameter panels generated from OpenSCAD Customizer annotations;
- safe decimal and fractional input with Metric/SAE interpretation;
- asynchronous, cancellable OpenSCAD generation and diagnostic output;
- three real-mesh Top, Front, and Ortho views with pan, zoom, fit, reset,
  expansion, and persisted splitter layout;
- editable `.mpsproj` project files, presets, recent files, and stale-output
  protection;
- STL export in canonical millimetres;
- Letter-landscape technical drawing preview, printing, and PDF export;
- module import/management with persisted metadata and safe ZIP extraction;
- two independently authored sample modules (plain bushing and spur gear);
- unit and optional OpenSCAD integration tests; and
- PyInstaller packaging configuration.

## Quick start on Windows

1. Install 64-bit Python 3.11 or later and
   [OpenSCAD](https://openscad.org/downloads.html). Add `openscad.exe` to
   `PATH`, or select it in **Edit → Preferences**.
2. In PowerShell from this directory:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e .[dev]
   mechstudio
   ```

3. Choose **Modules → Import New Feature** and select
   `examples/modules/plain_bushing.scad` or `spur_gear.scad`.
4. Enter values and choose **Generate Metric** or **Generate SAE**.

The selected unit mode changes only how dimensional text is interpreted. It
never rewrites the user's text. OpenSCAD and every exported STL always receive
millimetres.

To run the standard-library suite without optional dependencies:

```powershell
python -m unittest discover -s tests -v
```

The real OpenSCAD test is skipped when `openscad.exe` is unavailable.

## Packaging

After installing the development extras and OpenSCAD:

```powershell
pyinstaller packaging/MechStudio.spec --noconfirm
.\dist\MechStudio\MechStudio.exe --smoke-test
```

The build is written to `dist/MechStudio`. OpenSCAD is intentionally not
redistributed; users may configure an installed copy in Preferences. The smoke
test creates the real Qt main window in an isolated data directory and exits
automatically; a zero exit code confirms the packaged native DLL chain loads.

See [architecture.md](docs/architecture.md),
[module-authoring.md](docs/module-authoring.md), and
[module-import.md](docs/module-import.md) for the extension contract. The latest
automated and packaging evidence is recorded in
[test-results.md](docs/test-results.md).

## Milestone boundaries

The document schema already stores a list of components/features, but this
milestone edits and generates one active root feature at a time. Assemblies,
feature booleans, specialized dimension callouts, and geometric constraints
are extension points rather than partially implemented UI. The built-in mesh
renderer intentionally favors portability over advanced CAD shading.

