"""Turning one placement for the game preserves the asset and its center."""

import json
import os
import sys
import tempfile
import zipfile

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from blender_fih_exporter import export_scene, register, unregister


def read(path):
    with zipfile.ZipFile(path) as archive:
        return (json.loads(archive.read("map.fihmap.json")),
                archive.read("geometry/Text.obj"))


register()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
text = bpy.context.object
text.name = "Text"
for vertex in text.data.vertices:
    vertex.co.x += 2
    vertex.co.y += 0.1
    vertex.co.z += 1
other = text.copy()
other.data = text.data
other.name = "Text.001"
other.location.x = 10
bpy.context.collection.objects.link(other)

with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, "facing.fihmap.zip")
    export_scene(bpy.context.scene, path, "Before")
    before, geometry_before = read(path)
    text.fih_turn_for_game = True
    export_scene(bpy.context.scene, path, "After")
    after, geometry_after = read(path)
    assert geometry_before == geometry_after
    first, second = after["Objects"]
    assert first["Pos"] == [4.0, 0.0, -0.2], first
    assert abs(abs(first["Rot"][1]) - 180) < 0.001, first
    assert second == before["Objects"][1]
    assert text.matrix_world.translation[:] == (0.0, 0.0, 0.0)
    print("FIH_FACING_PASS")
unregister()
