# Importing modules

Open **Modules → Import New Feature** and choose either a `.scad` file or a ZIP
package. A package must contain at least one `.scad` file; all relative
dependencies are installed together.

The importer performs these steps:

1. validates and copies the source/package into an application-owned staging
   directory;
2. tokenizes top-level assignments and reads Customizer/MPS comments;
3. asks for unresolved parameter types instead of guessing dimensions;
4. identifies callable `module()` definitions when a generator was not
   specified and allows the user to select one;
5. writes resolved `.mps.json` metadata and atomically installs the folder;
6. refreshes the feature dropdown immediately.

Installed modules live under `%LOCALAPPDATA%\MechanicalPartsStudio\modules` by
default. **Modules → Open Modules Folder** opens that location. The manager can
enable, disable, or remove installed copies; no source rebuild is involved.

ZIP entries with absolute paths, `..` traversal, or symlinks are rejected.
Only import local code you trust: OpenSCAD modules are programs and may use
features such as file inclusion.

