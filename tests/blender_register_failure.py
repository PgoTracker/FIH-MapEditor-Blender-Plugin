"""A marker preview error must not hide the exporter or break map export."""

import os
import sys
import tempfile
import zipfile

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import blender_fih_exporter as addon


def fail_preview():
    raise RuntimeError("simulated marker image failure")


addon.refresh_marker_assets = fail_preview
addon.register()
try:
    scene = bpy.context.scene
    for name in ("fih_map_name", "fih_output_path", "fih_selected_only", "fih_blank_world",
                 "fih_repair_open"):
        assert hasattr(scene, name), name
    assert not hasattr(scene, "fih_scripts_dir")
    assert not hasattr(scene, "fih_impact_sounds_dir")
    bpy.ops.mesh.primitive_cube_add()
    bpy.context.object.name = "Platform"
    assert hasattr(bpy.context.object, "fih_script_path")
    assert hasattr(bpy.context.object, "fih_impact_sound_path")
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "works.fihmap.zip")
        scene.fih_output_path = path
        assert bpy.ops.fih.export_map_package() == {"FINISHED"}
        with zipfile.ZipFile(path) as archive:
            assert "map.fihmap.json" in archive.namelist()
    print("FIH_REGISTER_FAILURE_PASS")
finally:
    addon.unregister()
