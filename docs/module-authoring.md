# OpenSCAD module authoring

A feature is a normal `.scad` file that OpenSCAD can render directly. Use
top-level literal assignments for configurable values. Standard Customizer
sections and constraints are supported.

```scad
// @mps id=org.example.part version=1.0.0 name="Example part"

/* [Dimensions] */
// @mps-param type=length label="Outer diameter" description="Finished diameter"
outer_diameter = 12; // [0.1:0.1:500]

/* [Options] */
// @mps-param type=enum label="Style"
style = "plain"; // [plain:Plain, ribbed:Ribbed]

// @mps-param type=boolean label="Add hole" visible_if="style=ribbed"
add_hole = true;

/* [Hidden] */
$fn = 96;
```

## Supported defaults

Numbers, booleans, quoted strings, and numeric vectors are supported as
top-level defaults. Exposed computed expressions are rejected with a clear
import issue instead of being guessed.

## Parameter annotations

`@mps-param` extends Customizer without changing OpenSCAD semantics. Keys are
space-separated `key=value` pairs; quote values containing spaces.

- `type`: `length`, `angle`, `integer`, `float`, `ratio`, `percentage`,
  `boolean`, `enum`, `text`, or `vector`.
- `label` and `description`: user-facing text.
- `visible_if`: `parameter=value` for conditional display.
- `drawing`: reserved for future specialized callouts.

Every numeric parameter must be explicitly typed unless its intent is
unambiguous (`boolean`, string enum, or vector). This prevents counts and angles
from being accidentally converted as dimensions.

Customizer suffixes are interpreted as:

- `[minimum:step:maximum]` numeric range;
- `[value:Label, value2:Other label]` enumeration; or
- `[10, 20, 30]` simple enumeration.

Sections named `Hidden` are not exposed. Use OpenSCAD `assert()` calls for
mechanical relationships; their messages appear in the application log.

## Module metadata

The file annotation supports `id`, `version`, `name`, `description`, and
`generator`. IDs should be reverse-DNS names and remain stable. `generator`
is optional; when present it names a callable module for which the importer
creates a non-destructive wrapper. A direct-rendering file needs no wrapper.

