"""Run with Blender to verify per-object script and impact audio packaging."""

import os
import sys
import tempfile
import zipfile

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from blender_fih_exporter import export_scene, register


register()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
bpy.context.object.name = "Suzanne"

with tempfile.TemporaryDirectory() as folder:
    audio = b"RIFF----WAVEfmt "
    selected = os.path.join(folder, "oof_sound.wav")
    with open(selected, "wb") as stream:
        stream.write(audio)
    script = b"using FIHMapEditor; public class Suzanne : IPackagedGeometryBehavior { }"
    script_path = os.path.join(folder, "custom_behavior.cs")
    with open(script_path, "wb") as stream:
        stream.write(script)
    original = bpy.context.object
    original.fih_impact_sound_path = selected
    instance = original.copy()
    instance.data = original.data
    instance.name = "Suzanne.001"
    bpy.context.collection.objects.link(instance)
    instance.fih_impact_sound_path = ""
    instance.fih_script_path = script_path
    package = os.path.join(folder, "selected.fihmap.zip")
    export_scene(bpy.context.scene, package, "Selected Asset Files Test")
    with zipfile.ZipFile(package) as archive:
        assert archive.read("sounds/Suzanne.wav") == audio
        assert archive.read("scripts/Suzanne.cs") == script
        assert len([name for name in archive.namelist() if name.startswith("geometry/")]) == 1
    print("FIH_PER_OBJECT_FILES_EXPORT_PASS")
