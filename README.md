# FIH Blender Map Exporter

Blender add-on for creating `.fihmap.zip` packages for [FIH Map Editor](https://github.com/PgoTracker/FIH_MapEditor). This is a separate project; it does not change the editor or game.

## Install

In Blender 4.2 or newer, open **Edit → Preferences → Get Extensions → menu → Install from Disk** and select [`fih_map_exporter-0.2.18.zip`](dist/fih_map_exporter-0.2.18.zip). Enable the add-on if prompted. In the 3D Viewport, press **N** and open the **FIH Map** tab.

## Build a map

1. Give every mesh object an asset name, such as `Spinner`. Blender duplicates named `Spinner.001`, `Spinner.002`, etc. become additional placements of the same asset. Their local meshes and texture must match. Give genuinely different meshes different names.
2. UV unwrap any mesh that needs a texture. In its Blender material, connect one **Image Texture** directly to **Principled BSDF → Base Color**. The exporter converts the image to `textures/<asset name>.png` in the package, shared by numbered instances. To export an object without a texture, unlink the image from Base Color or use a plain material. The map format supports one texture per asset; bake multiple materials to one atlas first.
3. Select a mesh and set its optional **C# Script** and **Impact Sound** files in the FIH Map panel. The exporter packages them using the asset name: selecting `behavior.cs` and `oof_sound.wav` on Suzanne produces `scripts/Suzanne.cs` and `sounds/Suzanne.wav`. Numbered instances share one script and sound; set either picker on one instance, or use the same file on each. A Blender Text block named `Suzanne.cs` is used when no script file is selected. The C# class must be named `Suzanne` and implement `IPackagedGeometryBehavior` as described in the editor repository's `PACKAGED_GEOMETRY.md`. A matching script enables the custom sound with `context.EnablePackagedImpactSound()`.
4. Set **Map Name** and **Package** in the FIH Map panel, then click **Export Map Package**. The package contains one OBJ, optional PNG and optional C# file per unique asset, plus a map JSON with one placement per mesh object.
5. Copy the `.fihmap.zip` to `BepInEx/plugins/FIHMapEditor/Maps/`, refresh Local Maps, and load it. Enable map C# separately in the game's Local Maps screen if you trust the script.

Older scenes that used the global C# Scripts Folder or Impact Sounds Folder need the files selected on their mesh objects before re-exporting.

**Selected Meshes Only** lets you export part of a scene. The exporter includes evaluated modifiers and object position, rotation and scale. Coordinates map from Blender `(X, Y, Z)` to game `(X, Z, Y)`, keeping objects on the same side when viewed from the same end. The exporter reverses OBJ face winding to keep outward surfaces visible after this axis conversion. Apply object-level mirror or sheared transforms before export.

**Blank Game World** is checked by default. It writes `"BaseMode": "Blank"`, which hides the game's existing level while the map is active. Uncheck it to write `"BaseMode": "Overlay"` and keep the existing level visible.

## Spawn, goal, and checkpoints

Use the **Map Markers** panel in the FIH Map tab, or **Add → FIH Map Markers**, to add a Spawn, Goal, or Checkpoint at the 3D cursor. These are textured mesh guides: blue Spawn, green Goal, and orange Checkpoint. Their labels identify the type, and the large arrow points along local **-Y**. Use Material Preview or Rendered view to see the textures; object names and colors also appear in Solid view. The three PNG textures are bundled inside the installed add-on and referenced by the `.blend`, not packed into it. Keep the add-on installed when editing that `.blend` on another computer. Markers are not exported as playable map geometry. Opening an older `.blend` with this version relinks the add-on's marker materials and fixes their UVs automatically.

You can also create your own Blender Empties or meshes named `Spawn`, `Goal`, and `Checkpoint`. Additional checkpoints can be named `Checkpoint.001`, `Checkpoint.002`, and so on. A map can have one Spawn, one Goal, and any number of checkpoints. Names are case-insensitive. **Selected Meshes Only** also filters markers by selection.

- **Spawn:** its origin becomes `Spawn.Pos`. Rotate it around Blender Z to set `Spawn.Yaw`. Local **-Y** points in the player's forward direction; an unrotated marker has yaw 0.
- **Goal:** its center and dimensions become `Goal.Center` and `Goal.Size`. A mesh marker uses its evaluated bounding box, including modifiers and object scale. An Empty starts as a 4 × 4 × 4 goal box; its object scale changes that size. Rotation becomes `Goal.Rot`, or `null` when unrotated.
- **Checkpoint:** its origin becomes `Pos`, and its Z rotation sets respawn `Yaw`. The provided orange marker is 3 units across, giving radius 1.5; scale it to change the radius. An Empty starts with radius 1.5; set **Checkpoint Radius** on the active Empty marker or scale it to change it. A mesh marker uses half its largest evaluated dimension as radius. Each checkpoint gets a stable `Uid` based on map name and marker name. Checkpoints export as spherical triggers (`Size` and `Rot` are `null`).

All marker positions and rotations use the same Blender Z-up to game Y-up conversion as custom geometry. Markers are only exported into the map package; the Blender scene is unchanged.

Older `.blend` files may still store a **Turn Around in Game** value from previous versions. The exporter ignores it; all mesh placements now use the same axis conversion.

Open meshes export without an opt-in or topology check that blocks the package. **Repair Matching Gaps** is optional and off by default. If enabled, the exporter bridges exactly two matching open edge loops with no existing surface between them in a temporary copy before writing the OBJ. The Blender file stays unchanged, and `Cube`/`Cube.001` still become two placements of one asset. If the loops do not match, their open geometry exports as-is. The repair is geometric; inspect UVs on newly bridged faces if the mesh uses a texture.

If a mesh looks incomplete in game, inspect its open edges in Blender: select the mesh, enter Edit Mode, deselect all, then use **Select → Select All by Trait → Non-Manifold**. Simplification can remove surfaces and leave edge loops with different vertex counts; the optional repair cannot safely reconstruct those surfaces.

Asset names must start with a letter or `_` and contain only letters, digits and `_` (at most 80 characters). PNGs are limited to 2048 × 2048 and 8 MB; OBJ files to 8 MB; scripts to 256 KB; packages to 64 MB expanded and compressed.

The exporter creates a new map containing the Blender scene meshes and named markers. It does not import existing FIH maps, game terrain, or level edits. You can place and edit the exported objects in the editor and save the map there.

## Development

Run `python -m unittest discover -s tests -p test_package.py` for package checks. Run `blender --background --factory-startup --python tests/blender_integration.py` for a Blender export check. `tests/ReaderCheck.csproj` can validate a generated package with the editor's core parser by setting the `FIH_EDITOR_CORE` environment variable to the path of `FIHMapEditor.Core.csproj` before `dotnet run --project tests/ReaderCheck.csproj -- <package>`.

Build the installable extension with `blender --command extension build --source-dir blender_fih_exporter --output-dir dist`. Blender's [extension build documentation](https://docs.blender.org/manual/en/5.3/advanced/command_line/extension_arguments.html) describes this command.
