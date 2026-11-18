"""Run with Blender to verify materials are the sole texture source."""

import os
import sys
import tempfile
import zipfile

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from blender_fih_exporter import export_scene, register, unregister


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
crate = bpy.context.object
crate.name = "Crate"
copy = crate.copy()
copy.data = crate.data
copy.name = "Crate.001"
bpy.context.collection.objects.link(copy)

register()
try:
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "map.fihmap.zip")
        image = bpy.data.images.new("Picked", width=4, height=4, alpha=True)
        image.pixels[:] = [0.8, 0.2, 0.1, 1.0] * 16
        image.update()
        material = bpy.data.materials.new("Crate Image")
        material.use_nodes = True
        texture = material.node_tree.nodes.new("ShaderNodeTexImage")
        texture.image = image
        shader = material.node_tree.nodes.get("Principled BSDF")
        link = material.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
        crate.data.materials.append(material)

        # A legacy picker value must not override the Blender material.
        crate["fih_texture_file"] = os.path.join(folder, "missing.png")
        export_scene(bpy.context.scene, path, "Material Texture")
        with zipfile.ZipFile(path) as archive:
            assert "textures/Crate.png" in archive.namelist()

        material.node_tree.links.remove(link)
        export_scene(bpy.context.scene, path, "Untextured")
        with zipfile.ZipFile(path) as archive:
            assert "textures/Crate.png" not in archive.namelist()
        print("FIH_MATERIAL_TEXTURE_PASS")
finally:
    unregister()
