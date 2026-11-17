# FIH Blender Map Exporter

Blender add-on for creating `.fihmap.zip` packages for [FIH Map Editor](https://github.com/PgoTracker/FIH_MapEditor). This is a separate project; it does not change the editor or game.

## Install

In Blender 4.2 or newer, open **Edit → Preferences → Get Extensions → menu → Install from Disk** and select [`fih_map_exporter-0.2.8.zip`](dist/fih_map_exporter-0.2.8.zip). Enable the add-on if prompted. In the 3D Viewport, press **N** and open the **FIH Map** tab.

## Build a map

1. Give every mesh object an asset name, such as `Spinner`. Blender duplicates named `Spinner.001`, `Spinner.002`, etc. become additional placements of the same asset. Their local meshes and texture must match. Give genuinely different meshes different names.
2. Set one image texture as the **Principled BSDF → Base Color** input and UV unwrap the mesh. The exporter converts the image to a compatible RGBA PNG. The current map format supports one texture per asset; bake multiple materials to one atlas first. Untextured meshes are allowed.
3. Optionally create a Blender Text block named `Spinner.cs`, or place `Spinner.cs` in the **C# Scripts Folder**. The C# class should also be named `Spinner` and implement `IPackagedGeometryBehavior` as described in the editor repository's `PACKAGED_GEOMETRY.md`.
4. Set **Map Name** and **Package** in the FIH Map panel, then click **Export Map Package**. The package contains one OBJ, optional PNG and optional C# file per unique asset, plus a map JSON with one placement per mesh object.
5. Copy the `.fihmap.zip` to `BepInEx/plugins/FIHMapEditor/Maps/`, refresh Local Maps, and load it. Enable map C# separately in the game's Local Maps screen if you trust the script.

**Selected Meshes Only** lets you export part of a scene. The exporter includes evaluated modifiers and object position, rotation and scale. Blender's Z-up coordinates are converted to the game's Y-up coordinates. Apply mirror or sheared transforms before export.

**Blank Game World** is checked by default. It writes `"BaseMode": "Blank"`, which hides the game's existing level while the map is active. Uncheck it to write `"BaseMode": "Overlay"` and keep the existing level visible.

## Spawn, goal, and checkpoints

Add Blender **Empties** or mesh objects named `Spawn`, `Goal`, and `Checkpoint`. Additional checkpoints can be named `Checkpoint.001`, `Checkpoint.002`, and so on. These are map markers, so their meshes are not included as visible custom geometry. A map can have one Spawn, one Goal, and any number of checkpoints. Names are case-insensitive. **Selected Meshes Only** also filters markers by selection.

- **Spawn:** its origin becomes `Spawn.Pos`. Rotate it around Blender Z to set `Spawn.Yaw`. Local **-Y** points in the player's forward direction; an unrotated marker has yaw 0.
- **Goal:** its center and dimensions become `Goal.Center` and `Goal.Size`. A mesh marker uses its evaluated bounding box, including modifiers and object scale. An Empty starts as a 4 × 4 × 4 goal box; its object scale changes that size. Rotation becomes `Goal.Rot`, or `null` when unrotated.
- **Checkpoint:** its origin becomes `Pos`, and its Z rotation sets respawn `Yaw`. An Empty starts with radius 1.5; set **Checkpoint Radius** on the active marker or scale the Empty to change it. A mesh marker uses half its largest evaluated dimension as radius. Each checkpoint gets a stable `Uid` based on map name and marker name. Checkpoints export as spherical triggers (`Size` and `Rot` are `null`).

All marker positions and rotations use the same Blender Z-up to game Y-up conversion as custom geometry. Markers are only exported into the map package; the Blender scene is unchanged.

The axis conversion rotates the whole Blender scene consistently; it cannot infer which side of a mesh the player will approach. For text or another mesh that should face the opposite side in game, select the object and enable **Turn Around in Game**. The exporter turns that placement 180° around Blender's vertical axis about its evaluated mesh center. The Blender object and exported OBJ asset geometry stay unchanged. Each instance can use this setting independently.

Open meshes export without an opt-in or topology check that blocks the package. **Repair Matching Gaps** is optional and off by default. If enabled, the exporter bridges exactly two matching open edge loops with no existing surface between them in a temporary copy before writing the OBJ. The Blender file stays unchanged, and `Cube`/`Cube.001` still become two placements of one asset. If the loops do not match, their open geometry exports as-is. The repair is geometric; inspect UVs on newly bridged faces if the mesh uses a texture.

If a mesh looks incomplete in game, inspect its open edges in Blender: select the mesh, enter Edit Mode, deselect all, then use **Select → Select All by Trait → Non-Manifold**. Simplification can remove surfaces and leave edge loops with different vertex counts; the optional repair cannot safely reconstruct those surfaces.

Asset names must start with a letter or `_` and contain only letters, digits and `_` (at most 80 characters). PNGs are limited to 2048 × 2048 and 8 MB; OBJ files to 8 MB; scripts to 256 KB; packages to 64 MB expanded and compressed.

The exporter creates a new map containing the Blender scene meshes and named markers. It does not import existing FIH maps, game terrain, or level edits. You can place and edit the exported objects in the editor and save the map there.

## Development

Run `python -m unittest discover -s tests -p test_package.py` for package checks. Run `blender --background --factory-startup --python tests/blender_integration.py` for a Blender export check. `tests/ReaderCheck.csproj` can validate a generated package with the editor's core parser by setting the `FIH_EDITOR_CORE` environment variable to the path of `FIHMapEditor.Core.csproj` before `dotnet run --project tests/ReaderCheck.csproj -- <package>`.

Build the installable extension with `blender --command extension build --source-dir blender_fih_exporter --output-dir dist`. Blender's [extension build documentation](https://docs.blender.org/manual/en/5.3/advanced/command_line/extension_arguments.html) describes this command.
