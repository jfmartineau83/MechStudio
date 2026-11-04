# Architecture

## Decisions

The core application has no knowledge of bushings, gears, or any other part.
The boundary is a `FeatureModule`, discovered from an OpenSCAD source and
described by `ParameterSpec` records. A module owns geometry and mechanical
validation. The application owns interaction, units, documents, execution,
display, and derived output.

The first milestone uses a small tokenizer/parser for the supported top-level
OpenSCAD Customizer subset. It does not attempt to parse arbitrary OpenSCAD
expressions and, importantly, does not infer parameters using regular
expressions alone. Unsupported computed defaults are reported during import.
The original source is never modified. Resolved metadata is cached in a
generated `.mps.json` record beside the installed copy.

Millimetres are the only geometry unit. `ParameterValue` preserves the entered
text, and `UnitConverter` converts only parameters explicitly classified as
`length`. The conversion occurs in the `-D` values passed to OpenSCAD, before
geometry exists.

STL is treated as a derived cache. A parameter or mode change increments the
document revision and makes the cache stale. Export and drawing commands only
use geometry tagged with the current revision.

## Package map

```text
src/mechstudio/
  app.py                 process entry point
  models.py              module, parameter, and document domain models
  numbers.py             safe exact decimal/fraction parser
  units.py               semantic unit conversion
  scad_parser.py         tokenizer and supported Customizer parser
  module_registry.py     import, safe package extraction, persistence
  openscad.py            command construction and executable discovery
  stl.py                 dependency-free binary/ASCII STL reader
  settings.py            local paths and application settings
  gui/
    main_window.py       menus, commands, state coordination
    parameter_panel.py   dynamic parameter editor
    viewport.py          real-triangle Qt renderer
    dialogs.py           module manager/import resolution/preferences/log
    drawing.py           reusable drawing and print/PDF pipeline
examples/modules/        independently installable OpenSCAD fixtures
tests/                   core unit and optional integration tests
```

## Extension points

- `Document.components` and `FeatureInstance.children` provide stable places
  for multiple parts and ordered feature trees.
- The geometry engine is behind command/job objects, so future composition can
  emit a generated orchestration `.scad` without changing the GUI.
- `drawing` consumes a mesh plus metadata, not a part type. Module-supplied
  drawing annotations can be added to cached metadata later.
- Module IDs and semantic versions are persisted independently from file names.
- `ParameterSpec.visible_if` provides declarative conditional controls.

## Trust model

Imports are copied into an application-owned directory. ZIP entries are
validated against path traversal and symlinks. OpenSCAD is invoked with an
argument vector and `shell=False`. Imports remain disabled until accepted, and
module removal never touches the original source.

