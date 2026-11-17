"""Run with: blender --background --python tests/blender_integration.py"""

import json
import math
import os
import shutil
import sys
import tempfile
import zipfile

import bpy


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from blender_fih_exporter import export_scene, register, unregister
from blender_fih_exporter.package import ExportError


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(location=(2, 3, 4))
cube = bpy.context.object
cube.name = "Spinner"
image = bpy.data.images.new("TestTexture", width=4, height=4, alpha=True)
image.pixels[:] = [0.1, 0.5, 0.9, 1.0] * 16
image.update()
material = bpy.data.materials.new("TestMaterial")
material.use_nodes = True
nodes = material.node_tree.nodes
texture = nodes.new("ShaderNodeTexImage")
texture.image = image
shader = nodes.get("Principled BSDF")
material.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
cube.data.materials.append(material)
copy = cube.copy()
copy.data = cube.data
bpy.context.collection.objects.link(copy)
copy.name = "Spinner.001"
copy.location = (6, 7, 8)
bpy.ops.object.empty_add(type="ARROWS", location=(1, 2, 3))
spawn = bpy.context.object
spawn.name = "Spawn"
spawn.rotation_euler.z = math.pi / 2
bpy.ops.mesh.primitive_cube_add(size=2, location=(4, 5, 6))
goal = bpy.context.object
goal.name = "Goal"
goal.scale = (1, 2, 3)
goal.rotation_euler.z = math.pi / 2
bpy.ops.object.empty_add(type="SPHERE", location=(3, 4, 5))
checkpoint = bpy.context.object
checkpoint.name = "Checkpoint"
checkpoint.scale = (2, 2, 2)
bpy.ops.object.empty_add(type="SPHERE", location=(7, 8, 9))
second_checkpoint = bpy.context.object
second_checkpoint.name = "Checkpoint.001"
bpy.data.texts.new("Spinner.cs").write("using FIHMapEditor; public class Spinner : IPackagedGeometryBehavior { public void OnSpawn(PackagedGeometryContext c) {} public void Update(PackagedGeometryContext c, float dt) {} public void OnDespawn(PackagedGeometryContext c) {} }")

register()
try:
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "test.fihmap.zip")
        export_scene(bpy.context.scene, path, "Blender Test")
        with zipfile.ZipFile(path) as archive:
            assert set(archive.namelist()) == {"map.fihmap.json", "geometry/Spinner.obj", "textures/Spinner.png", "scripts/Spinner.cs"}
            data = json.loads(archive.read("map.fihmap.json"))
            assert len(data["Objects"]) == 2
            assert data["Objects"][0]["Pos"] == [2, 4, 3], data
            assert data["Objects"][1]["Pos"] == [6, 8, 7], data
            assert data["BaseMode"] == "Blank", data
            assert data["Spawn"] == {"Pos": [1, 3, 2], "Yaw": 90}, data
            assert data["Goal"]["Center"] == [4, 6, 5], data
            assert data["Goal"]["Size"] == [2, 6, 4], data
            assert all(abs(a - b) < 0.001 for a, b in zip(data["Goal"]["Rot"], [0, -90, 0])), data
            assert len(data["Checkpoints"]) == 2, data
            assert data["Checkpoints"][0]["Pos"] == [3, 5, 4], data
            assert data["Checkpoints"][0]["Radius"] == 3, data
            assert data["Checkpoints"][0]["Yaw"] == 180, data
            assert data["Checkpoints"][1]["Pos"] == [7, 9, 8], data
            assert data["Checkpoints"][1]["Radius"] == 1.5, data
            assert data["Checkpoints"][1]["Uid"] != data["Checkpoints"][0]["Uid"]
            uid = data["Checkpoints"][0]["Uid"]
            obj_lines = archive.read("geometry/Spinner.obj").decode("ascii").splitlines()
            assert any(line.startswith("vt ") for line in obj_lines)
            vertices = [tuple(map(float, line.split()[1:])) for line in obj_lines if line.startswith("v ")]
            normals = [tuple(map(float, line.split()[1:])) for line in obj_lines if line.startswith("vn ")]
            corners = next(line.split()[1:] for line in obj_lines if line.startswith("f "))
            indices = [tuple(int(value) for value in corner.split("/")) for corner in corners]
            a, b, c = [vertices[index[0] - 1] for index in indices]
            ab = [b[i] - a[i] for i in range(3)]
            ac = [c[i] - a[i] for i in range(3)]
            face_normal = (ab[1] * ac[2] - ab[2] * ac[1],
                           ab[2] * ac[0] - ab[0] * ac[2],
                           ab[0] * ac[1] - ab[1] * ac[0])
            normal = normals[indices[0][2] - 1]
            assert sum(face_normal[i] * normal[i] for i in range(3)) > 0
            assert archive.read("textures/Spinner.png")[:8] == b"\x89PNG\r\n\x1a\n"
            print("FIH_INTEGRATION_PASS", archive.namelist())
        if os.environ.get("FIH_TEST_PACKAGE"):
            shutil.copy2(path, os.environ["FIH_TEST_PACKAGE"])
        bpy.context.scene.fih_blank_world = False
        export_scene(bpy.context.scene, path, "Blender Test")
        with zipfile.ZipFile(path) as archive:
            data = json.loads(archive.read("map.fihmap.json"))
            assert data["BaseMode"] == "Overlay", data
            assert data["Checkpoints"][0]["Uid"] == uid, data
        copy.data = copy.data.copy()
        copy.data.vertices[0].co.x += 0.25
        try:
            export_scene(bpy.context.scene, path, "Should Fail")
        except ExportError as exc:
            assert "must share the same local mesh" in str(exc)
        else:
            raise AssertionError("Different meshes with a shared asset name must be rejected")
finally:
    unregister()
