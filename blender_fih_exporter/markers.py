"""Blender-only visual markers for map spawn, goal, and checkpoints."""

import os

import bpy


COLORS = {
    "Spawn": (0.08, 0.54, 0.95),
    "Goal": (0.16, 0.77, 0.31),
    "Checkpoint": (1.0, 0.57, 0.09),
}

def _marker_image(kind):
    path = os.path.join(os.path.dirname(__file__), "assets", kind.lower() + ".png")
    image = bpy.data.images.load(path, check_existing=True)
    image.name = f"FIH {kind} Marker Texture (Add-on)"
    return image


def _set_marker_uv(mesh):
    uv = mesh.uv_layers.active or mesh.uv_layers.new(name="Marker Label")
    # Face 0 is the top; face 1 is the underside. Keep text readable from the
    # outside of each face, including when the marker is viewed from below.
    normal = ((0, 0), (1, 0), (1, 1), (0, 1))
    underside = ((1, 1), (0, 1), (0, 0), (1, 0))
    for face_index, polygon in enumerate(mesh.polygons):
        coordinates = underside if face_index == 1 else normal
        for index, coordinate in zip(polygon.loop_indices, coordinates):
            uv.data[index].uv = coordinate


def refresh_marker_assets():
    """Upgrade markers in an existing .blend to the add-on PNGs and fixed UVs."""
    old_images = []
    for kind in COLORS:
        material = bpy.data.materials.get(f"FIH {kind} Marker Material")
        if material is None or not material.use_nodes:
            continue
        image = _marker_image(kind)
        for node in material.node_tree.nodes:
            if node.type != "TEX_IMAGE":
                continue
            if node.image and node.image != image and node.image.name == f"FIH {kind} Marker Texture":
                old_images.append(node.image)
            node.image = image
    seen_meshes = set()
    for obj in bpy.data.objects:
        kind = obj.get("fih_marker_kind")
        if kind not in COLORS or obj.type != "MESH":
            continue
        mesh = obj.data
        if mesh.as_pointer() in seen_meshes or len(mesh.polygons) != 6 or not mesh.name.startswith(f"FIH {kind} Marker Shape"):
            continue
        seen_meshes.add(mesh.as_pointer())
        _set_marker_uv(mesh)
    for image in old_images:
        if image.users == 0 and image.packed_file is not None:
            bpy.data.images.remove(image)


def _marker_material(kind):
    name = f"FIH {kind} Marker Material"
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*COLORS[kind], 1.0)
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = _marker_image(kind)
    material.node_tree.links.new(texture.outputs["Color"], emission.inputs["Color"])
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def _marker_mesh(kind):
    # The box dimensions are also the exporter's goal size / checkpoint diameter.
    half_xy = 2.0 if kind == "Goal" else 1.5 if kind == "Checkpoint" else 1.0
    half_z = 2.0 if kind == "Goal" else 0.1
    x, y, z = half_xy, half_xy, half_z
    sides = (
        ((-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)),
        ((-x, y, -z), (x, y, -z), (x, -y, -z), (-x, -y, -z)),
        ((-x, -y, -z), (x, -y, -z), (x, -y, z), (-x, -y, z)),
        ((x, y, -z), (-x, y, -z), (-x, y, z), (x, y, z)),
        ((x, -y, -z), (x, y, -z), (x, y, z), (x, -y, z)),
        ((-x, y, -z), (-x, -y, -z), (-x, -y, z), (-x, y, z)),
    )
    vertices = [point for side in sides for point in side]
    faces = [tuple(range(i * 4, i * 4 + 4)) for i in range(len(sides))]
    mesh = bpy.data.meshes.new(f"FIH {kind} Marker Shape")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    _set_marker_uv(mesh)
    mesh.materials.append(_marker_material(kind))
    return mesh


def create_marker(context, kind):
    if kind in ("Spawn", "Goal") and any(
        (obj.name.rsplit(".", 1)[0] if obj.name.rsplit(".", 1)[-1].isdigit() else obj.name).casefold()
        == kind.casefold() for obj in context.scene.objects
    ):
        raise ValueError(f"This scene already has a {kind} marker")
    obj = bpy.data.objects.new(kind, _marker_mesh(kind))
    context.collection.objects.link(obj)
    obj.location = context.scene.cursor.location
    obj.color = (*COLORS[kind], 1.0)
    obj.show_name = True
    obj["fih_marker_kind"] = kind
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj
