"""Open planes and tubes export without an opt-in or an unwanted bridge."""

import os
import sys
import tempfile
import zipfile

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from blender_fih_exporter import export_scene, register, unregister


def geometry(path, name):
    with zipfile.ZipFile(path) as archive:
        return archive.read("geometry/" + name + ".obj")


register()
assert not hasattr(bpy.types.Object, "fih_allow_open")
assert not bpy.context.scene.fih_repair_open
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add()
bpy.context.object.name = "OpenPlane"
with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, "open.fihmap.zip")
    export_scene(bpy.context.scene, path, "Open Plane")
    assert b"f " in geometry(path, "OpenPlane")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, depth=2, end_fill_type="NOTHING")
    bpy.context.object.name = "OpenTube"
    mesh = bpy.context.object.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    long_edges = [edge for edge in bm.edges if abs(edge.verts[0].co.z - edge.verts[1].co.z) > 1]
    bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    export_scene(bpy.context.scene, path, "Open Tube", repair_open=False)
    baseline = geometry(path, "OpenTube")
    export_scene(bpy.context.scene, path, "Open Tube With Repair Enabled", repair_open=True)
    assert geometry(path, "OpenTube") == baseline, "Open tube wall must not be duplicated"
    print("FIH_OPEN_EXPORT_PASS")
unregister()
