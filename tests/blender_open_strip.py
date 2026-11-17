"""Reopen the known repaired Blender mesh and verify automatic repair."""

import json
import os
import shutil
import sys
import tempfile
import zipfile

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from blender_fih_exporter import export_scene


def triangles(path):
    with zipfile.ZipFile(path) as archive:
        lines = archive.read("geometry/Cube.obj").decode("ascii").splitlines()
    verts = [tuple(round(float(v), 5) for v in line.split()[1:])
             for line in lines if line.startswith("v ")]
    oriented = set()
    for line in lines:
        if not line.startswith("f "):
            continue
        points = tuple(verts[int(token.split("/")[0]) - 1] for token in line.split()[1:])
        oriented.add(min(points, points[1:] + points[:1], points[2:] + points[:2]))
    return oriented


objects = sorted((obj for obj in bpy.context.scene.objects if obj.type == "MESH"), key=lambda obj: obj.name)
assert [obj.name for obj in objects] == ["Cube", "Cube.001"]
assert objects[0].data == objects[1].data

with tempfile.TemporaryDirectory() as folder:
    baseline = os.path.join(folder, "baseline.fihmap.zip")
    output = os.path.join(folder, "auto.fihmap.zip")
    export_scene(bpy.context.scene, baseline, "Baseline")

    broken = objects[0].data.copy()
    bm = bmesh.new()
    bm.from_mesh(broken)
    # These are the 204 faces we previously bridged between the matching U-shaped rims.
    strip = [face for face in bm.faces
             if abs(min(v.co.x for v in face.verts) + 9.626001) < 0.0001
             and abs(max(v.co.x for v in face.verts) + 7.626001) < 0.0001]
    assert len(strip) == 204
    bmesh.ops.delete(bm, geom=strip, context="FACES")
    assert sum(edge.is_boundary for edge in bm.edges) == 408
    bm.to_mesh(broken)
    bm.free()
    broken.update()
    for obj in objects:
        obj.data = broken

    export_scene(bpy.context.scene, output, "Open Mesh", repair_open=False)
    assert len(triangles(output)) < len(triangles(baseline))
    export_scene(bpy.context.scene, output, "Auto Repaired", repair_open=True)
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {"map.fihmap.json", "geometry/Cube.obj"}
        assert len(json.loads(archive.read("map.fihmap.json"))["Objects"]) == 2
    assert triangles(output) == triangles(baseline), "Automatic bridge must match the known good mesh"
    if os.environ.get("FIH_TEST_PACKAGE"):
        shutil.copy2(output, os.environ["FIH_TEST_PACKAGE"])
    print("FIH_AUTO_REPAIR_PASS", len(triangles(output)), "matching oriented triangles")
