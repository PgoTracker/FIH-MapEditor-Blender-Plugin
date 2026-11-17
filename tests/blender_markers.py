"""Run with Blender in background to check visual marker creation and export."""

import json
import os
import sys
import tempfile
import zipfile

import bpy


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from blender_fih_exporter import register, unregister, export_scene


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
register()
try:
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, -3))
    bpy.context.object.name = "Platform"
    for kind in ("Spawn", "Goal", "Checkpoint", "Checkpoint"):
        assert bpy.ops.fih.add_map_marker(kind=kind) == {"FINISHED"}
        marker = bpy.context.object
        assert marker.type == "MESH"
        assert marker.get("fih_marker_kind") == kind
        assert marker.data.uv_layers.active is not None
        material = marker.data.materials[0]
        image_nodes = [node for node in material.node_tree.nodes if node.type == "TEX_IMAGE"]
        assert len(image_nodes) == 1
        image = image_nodes[0].image
        assert image and image.packed_file is None
        assert image.source == "FILE"
        assert os.path.isfile(bpy.path.abspath(image.filepath))
        assert tuple(image.size) == (256, 256)
        assert any(value > 0.9 for value in image.pixels[:4096])
        top_uv = marker.data.uv_layers.active
        assert tuple(top_uv.data[marker.data.polygons[0].loop_indices[0]].uv) == (0, 0)
    assert [obj.name for obj in bpy.context.scene.objects if obj.get("fih_marker_kind")] == [
        "Spawn", "Goal", "Checkpoint", "Checkpoint.001"]
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "markers.fihmap.zip")
        export_scene(bpy.context.scene, path, "Marker Test")
        with zipfile.ZipFile(path) as archive:
            data = json.loads(archive.read("map.fihmap.json"))
            assert archive.namelist() == ["map.fihmap.json", "geometry/Platform.obj"]
            assert len(data["Objects"]) == 1
            assert data["Spawn"] == {"Pos": [0, 0, 0], "Yaw": 0}, data
            assert data["Goal"] == {"Center": [0, 0, 0], "Size": [4, 4, 4], "Rot": None}, data
            assert [checkpoint["Radius"] for checkpoint in data["Checkpoints"]] == [1.5, 1.5]
        if os.environ.get("FIH_MARKER_BLEND"):
            bpy.ops.wm.save_as_mainfile(filepath=os.environ["FIH_MARKER_BLEND"])
    print("FIH_MARKERS_PASS")
finally:
    unregister()
