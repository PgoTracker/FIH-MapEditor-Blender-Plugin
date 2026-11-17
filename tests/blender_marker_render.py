"""Render marker faces for visual inspection. FIH_MARKER_RENDER_DIR is required."""

import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from blender_fih_exporter.markers import create_marker

folder = os.environ["FIH_MARKER_RENDER_DIR"]
os.makedirs(folder, exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

camera_data = bpy.data.cameras.new("Marker QA Camera")
camera_data.type = "ORTHO"
camera_data.ortho_scale = 6
camera = bpy.data.objects.new("Marker QA Camera", camera_data)
bpy.context.collection.objects.link(camera)
bpy.context.scene.camera = camera
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 4
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512
bpy.context.scene.render.resolution_percentage = 100
bpy.context.scene.render.image_settings.file_format = "PNG"

for kind, position, up in (
    ("Spawn", (0, 0, 8), "Y"),
    ("Goal", (0, -8, 0), "Z"),
    ("Checkpoint", (0, 0, 8), "Y"),
):
    for obj in list(bpy.context.scene.objects):
        if obj.get("fih_marker_kind"):
            bpy.data.objects.remove(obj, do_unlink=True)
    create_marker(bpy.context, kind)
    camera.location = position
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", up).to_euler()
    bpy.context.scene.render.filepath = os.path.join(folder, f"{kind.lower()}.png")
    bpy.ops.render.render(write_still=True)
    print("FIH_MARKER_RENDER", kind, bpy.context.scene.render.filepath)
