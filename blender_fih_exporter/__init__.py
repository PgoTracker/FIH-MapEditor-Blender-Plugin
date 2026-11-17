"""Export named Blender meshes as a Flipping Is Hard map package."""

bl_info = {
    "name": "Flipping Is Hard Map Exporter",
    "author": "FIH Map Editor contributors",
    "version": (0, 2, 13),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > FIH Map",
    "description": "Export scene meshes, matching textures and C# as .fihmap.zip",
    "category": "Import-Export",
}

import os
import tempfile
import math
import uuid

import bpy
import bmesh
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy.types import Menu, Operator, Panel
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from .package import ExportError, asset_name, write_package
from .markers import create_marker, refresh_marker_assets


# Blender is Z-up; the game's map is Y-up. Keeping both Blender X and Y
# positive in the corresponding horizontal game axes requires a reflection.
# Conjugating object transforms remains a proper rotation; reflected OBJ
# triangles need their winding reversed below.
AXIS = Matrix(((1.0, 0.0, 0.0, 0.0),
               (0.0, 0.0, 1.0, 0.0),
               (0.0, 1.0, 0.0, 0.0),
               (0.0, 0.0, 0.0, 1.0)))
AXIS_INV = AXIS.inverted()


def _vec(values):
    return [round(float(value), 6) for value in values]


def _converted_transform(obj):
    converted = AXIS @ obj.matrix_world @ AXIS_INV
    position, rotation, scale = converted.decompose()
    if min(scale) <= 0:
        raise ExportError(f"{obj.name}: apply mirror or negative scale before export")
    reconstructed = Matrix.LocRotScale(position, rotation, scale)
    if any(abs(converted[row][col] - reconstructed[row][col]) > 0.0001
           for row in range(4) for col in range(4)):
        raise ExportError(f"{obj.name}: transform contains shear; apply transforms before export")
    return converted, position, rotation, scale


def _yaw(rotation):
    # The marker arrow points along Blender local -Y. Use that exact direction
    # after axis conversion, including the reflected game Z axis.
    forward = rotation @ (AXIS.to_3x3() @ Vector((0.0, -1.0, 0.0)))
    return round(math.degrees(math.atan2(forward.x, forward.z)) % 360.0, 6)


def _marker_bounds(obj, depsgraph, scale):
    if obj.type != "MESH":
        return Vector((0.0, 0.0, 0.0)), Vector(4.0 * scale[axis] for axis in range(3))
    evaluated = obj.evaluated_get(depsgraph)
    corners = [AXIS @ Vector(corner) for corner in evaluated.bound_box]
    lows = Vector(min(corner[axis] for corner in corners) for axis in range(3))
    highs = Vector(max(corner[axis] for corner in corners) for axis in range(3))
    dimensions = highs - lows
    if min(dimensions) <= 0:
        raise ExportError(f"{obj.name}: marker mesh must have volume")
    return (lows + highs) / 2.0, Vector(dimensions[axis] * scale[axis] for axis in range(3))


def _marker_data(obj, kind, map_name, depsgraph):
    converted, position, rotation, scale = _converted_transform(obj)
    if kind == "Spawn":
        return {"Pos": _vec(position), "Yaw": _yaw(rotation)}
    if kind == "Goal":
        local_center, size = _marker_bounds(obj, depsgraph, scale)
        angles = _vec(math.degrees(angle) for angle in rotation.to_euler("YXZ"))
        return {"Center": _vec(converted @ local_center), "Size": _vec(size),
                "Rot": angles if any(abs(value) > 0.000001 for value in angles) else None}
    radius = float(obj.fih_checkpoint_radius)
    if radius <= 0:
        raise ExportError(f"{obj.name}: checkpoint radius must be positive")
    if obj.type == "MESH":
        _, dimensions = _marker_bounds(obj, depsgraph, scale)
        radius = max(dimensions) / 2.0
    else:
        radius *= max(scale)
    return {"Uid": uuid.uuid5(uuid.NAMESPACE_URL, f"fih:{map_name}:checkpoint:{obj.name}").hex,
            "Pos": _vec(position), "Yaw": _yaw(rotation), "Radius": round(radius, 6),
            "Size": None, "Rot": None}


def _boundary_components(bm):
    remaining = {edge for edge in bm.edges if edge.is_boundary}
    components = []
    while remaining:
        component = set()
        queue = [next(iter(remaining))]
        while queue:
            edge = queue.pop()
            if edge in component:
                continue
            component.add(edge)
            remaining.discard(edge)
            for vertex in edge.verts:
                queue.extend(other for other in vertex.link_edges
                             if other.is_boundary and other not in component)
        components.append(component)
    return components


def _repair_matching_open_strip(mesh):
    """Bridge only two translation-matched boundary loops in a temporary mesh."""
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        if not any(edge.is_boundary for edge in bm.edges):
            return 0, False
        # This also removes the zero-area faces seen in TEST.blend. Work only
        # on the evaluated export copy; the user's Blender mesh is untouched.
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.000001)
        components = _boundary_components(bm)
        edge_count = sum(map(len, components))
        if len(components) != 2 or len(components[0]) != len(components[1]) or len(components[0]) < 3:
            return edge_count, False
        loops = []
        for component in components:
            vertices = {vertex for edge in component for vertex in edge.verts}
            if len(vertices) != len(component) or any(
                sum(edge in component for edge in vertex.link_edges) != 2 for vertex in vertices
            ):
                return edge_count, False
            loops.append(list(vertices))
        if len(loops[0]) > 5000:
            return edge_count, False
        centers = [sum((v.co for v in loop), Vector((0.0, 0.0, 0.0))) / len(loop) for loop in loops]
        delta = centers[1] - centers[0]
        span = max((vertex.co - centers[0]).length for loop in loops for vertex in loop)
        tolerance = max(0.00001, span * 0.00001)
        if delta.length <= tolerance:
            return edge_count, False
        tree = KDTree(len(loops[1]))
        for index, vertex in enumerate(loops[1]):
            tree.insert(vertex.co, index)
        tree.balance()
        matched = set()
        for vertex in loops[0]:
            _, index, distance = tree.find(vertex.co + delta)
            if distance > tolerance or index in matched:
                return edge_count, False
            matched.add(index)
            other = loops[1][index]
            if any(edge.other_vert(vertex) == other for edge in vertex.link_edges):
                # These loops already have a surface between them, such as the
                # open ends of a tube. Bridging would duplicate that surface.
                return edge_count, False
        original_loop = set(loops[0])
        opposite_loop = set(loops[1])
        existing_surface = BVHTree.FromBMesh(bm)
        bridge = bmesh.ops.bridge_loops(bm, edges=list(components[0] | components[1]))
        if len(bridge["faces"]) != len(loops[0]) or any(edge.is_boundary for edge in bm.edges):
            return edge_count, False
        covered_faces = 0
        for face in bridge["faces"]:
            center = sum((vertex.co for vertex in face.verts), Vector((0.0, 0.0, 0.0))) / len(face.verts)
            nearest = existing_surface.find_nearest(center)
            if nearest is not None and nearest[3] <= tolerance:
                covered_faces += 1
            for edge in face.edges:
                a, b = edge.verts
                if a in original_loop and b in opposite_loop:
                    offset = b.co - a.co
                elif b in original_loop and a in opposite_loop:
                    offset = a.co - b.co
                else:
                    continue
                if (offset - delta).length > tolerance:
                    return edge_count, False
        if covered_faces >= len(bridge["faces"]) * 0.1:
            # An open tube can have the same pair of end loops but already
            # have a wall between them. Do not add coplanar faces over it.
            return edge_count, False
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        mesh.update()
        return 0, True
    finally:
        bm.free()


def _obj_bytes(obj, depsgraph, require_uv=False, repair_open=False, repairs=None):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        if not mesh.vertices or not mesh.polygons:
            raise ExportError(f"{obj.name}: mesh has no faces")
        repaired = False
        if repair_open:
            _, repaired = _repair_matching_open_strip(mesh)
        if repaired:
            print(f"FIH Map Exporter: bridged matching open loops in {obj.name} for this export")
            if repairs is not None:
                repairs.append(obj.name)
        mesh.calc_loop_triangles()
        triangles = [triangle for triangle in mesh.loop_triangles
                     if (mesh.vertices[mesh.loops[triangle.loops[1]].vertex_index].co
                         - mesh.vertices[mesh.loops[triangle.loops[0]].vertex_index].co).cross(
                         mesh.vertices[mesh.loops[triangle.loops[2]].vertex_index].co
                         - mesh.vertices[mesh.loops[triangle.loops[0]].vertex_index].co).length_squared > 1e-16]
        if not triangles:
            raise ExportError(f"{obj.name}: mesh contains no non-degenerate faces")
        if len(triangles) * 3 > 250000:
            raise ExportError(f"{obj.name}: mesh has more face corners than the editor's 250,000-vertex limit")
        uv = mesh.uv_layers.active
        if require_uv and uv is None:
            raise ExportError(f"{obj.name}: textured mesh needs a UV map")
        axis = AXIS.to_3x3()
        lines = ["# FIH Map Exporter; local mesh coordinates\n"]
        for vertex in mesh.vertices:
            v = axis @ vertex.co
            lines.append(f"v {v.x:.9g} {v.y:.9g} {v.z:.9g}\n")
        # A UV and normal for every face corner preserves seams and sharp edges.
        for triangle in triangles:
            for loop_index in triangle.loops:
                if uv:
                    tex = uv.data[loop_index].uv
                    lines.append(f"vt {tex.x:.9g} {tex.y:.9g}\n")
                normal = axis @ mesh.corner_normals[loop_index].vector
                lines.append(f"vn {normal.x:.9g} {normal.y:.9g} {normal.z:.9g}\n")
        corner = 1
        for triangle in triangles:
            tokens = []
            for loop_index in triangle.loops:
                vertex_index = mesh.loops[loop_index].vertex_index + 1
                tokens.append(f"{vertex_index}/{corner}/{corner}" if uv else f"{vertex_index}//{corner}")
                corner += 1
            lines.append("f " + " ".join((tokens[0], tokens[2], tokens[1])) + "\n")
        return "".join(lines).encode("ascii")
    finally:
        evaluated.to_mesh_clear()


def _texture_image(obj):
    images = set()
    untextured_material = False
    used_indices = {poly.material_index for poly in obj.data.polygons}
    for index in used_indices:
        material = obj.data.materials[index] if index < len(obj.data.materials) else None
        if material is None:
            untextured_material = True
            continue
        if not material.use_nodes:
            raise ExportError(f"{obj.name}: material {material.name} must use nodes")
        outputs = [node for node in material.node_tree.nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output]
        if not outputs:
            untextured_material = True
            continue
        surface = outputs[0].inputs.get("Surface")
        if not surface or not surface.is_linked:
            untextured_material = True
            continue
        shader = surface.links[0].from_node
        base = shader.inputs.get("Base Color")
        if not base or not base.is_linked:
            untextured_material = True
            continue
        source = base.links[0].from_node
        if source.type != "TEX_IMAGE" or source.image is None:
            raise ExportError(f"{obj.name}: Base Color must link directly to one Image Texture")
        images.add(source.image)
    if len(images) > 1:
        raise ExportError(f"{obj.name}: the map format supports one texture per asset; bake materials to one image")
    if images and untextured_material:
        raise ExportError(f"{obj.name}: textured and plain material faces need baking into one image")
    return next(iter(images)) if images else None


def _png_bytes(image, scene):
    if image.size[0] > 2048 or image.size[1] > 2048:
        raise ExportError(f"{image.name}: image exceeds 2048 x 2048")
    settings = scene.render.image_settings
    original = (settings.file_format, settings.color_mode, settings.color_depth)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        settings.file_format = "PNG"
        settings.color_mode = "RGBA"
        settings.color_depth = "8"
        image.save_render(path, scene=scene)
        with open(path, "rb") as stream:
            return stream.read()
    finally:
        settings.file_format, settings.color_mode, settings.color_depth = original
        os.unlink(path)


def _script_bytes(name, scripts_dir):
    text = bpy.data.texts.get(name + ".cs")
    path = os.path.join(bpy.path.abspath(scripts_dir), name + ".cs") if scripts_dir else None
    if text and path and os.path.isfile(path):
        raise ExportError(f"{name}: C# exists in Blender Text and scripts folder; keep one copy")
    if text:
        return text.as_string().encode("utf-8")
    if path and os.path.isfile(path):
        with open(path, "rb") as stream:
            return stream.read()
    return None


def export_scene(scene, filepath, map_name, selected_only=False, scripts_dir="", depsgraph=None,
                 repair_open=False, repairs=None):
    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    markers = {"Spawn": [], "Goal": [], "Checkpoint": []}
    meshes = []
    for obj in scene.objects:
        if selected_only and not obj.select_get():
            continue
        kind = obj.name.rsplit(".", 1)[0] if obj.name.rsplit(".", 1)[-1].isdigit() else obj.name
        kind = next((name for name in markers if name.casefold() == kind.casefold()), None)
        if kind is not None:
            if obj.type not in ("EMPTY", "MESH"):
                raise ExportError(f"{obj.name}: {kind} marker must be an Empty or Mesh")
            markers[kind].append(obj)
        elif obj.type == "MESH":
            meshes.append(obj)
    if len(markers["Spawn"]) > 1 or len(markers["Goal"]) > 1:
        raise ExportError("A map can contain only one Spawn and one Goal marker")
    meshes.sort(key=lambda obj: obj.name.lower())
    assets = {}
    objects = []
    for obj in meshes:
        name = asset_name(obj.name)
        image = _texture_image(obj)
        geometry = _obj_bytes(obj, depsgraph, require_uv=image is not None,
                              repair_open=repair_open, repairs=repairs)
        texture = _png_bytes(image, scene) if image else None
        key = name.lower()
        if key in assets:
            previous = assets[key]
            if previous[1]["obj"] != geometry or previous[1]["png"] != texture:
                raise ExportError(
                    f"{obj.name}: objects named {name} and {name}.001 must share the same local mesh "
                    "and texture. Give distinct meshes different names."
                )
            canonical = previous[0]
        else:
            canonical = name
            assets[key] = (name, {"obj": geometry, "png": texture, "cs": _script_bytes(name, scripts_dir)})
        _, position, rotation, scale = _converted_transform(obj)
        # Unity Quaternion.Euler(x,y,z) uses the YXZ rotation order.
        angles = rotation.to_euler("YXZ")
        objects.append({
            "Source": "package://" + canonical,
            "SourceName": canonical,
            "Pos": _vec(position),
            "Rot": _vec(math.degrees(angle) for angle in angles),
            "Scale": _vec(scale),
        })
    spawn = _marker_data(markers["Spawn"][0], "Spawn", map_name, depsgraph) if markers["Spawn"] else None
    goal = _marker_data(markers["Goal"][0], "Goal", map_name, depsgraph) if markers["Goal"] else None
    checkpoints = [_marker_data(obj, "Checkpoint", map_name, depsgraph)
                   for obj in sorted(markers["Checkpoint"], key=lambda item: item.name.lower())]
    return write_package(filepath, map_name, objects, {value[0]: value[1] for value in assets.values()},
                         base_mode="Blank" if scene.fih_blank_world else "Overlay", spawn=spawn,
                         goal=goal, checkpoints=checkpoints)


class FIH_OT_export(Operator):
    bl_idname = "fih.export_map_package"
    bl_label = "Export Map Package"
    bl_description = "Create a .fihmap.zip from named mesh objects in this scene"

    def execute(self, context):
        scene = context.scene
        try:
            path = bpy.path.abspath(scene.fih_output_path)
            if not path.lower().endswith(".fihmap.zip"):
                path += ".fihmap.zip"
            repairs = []
            export_scene(scene, path, scene.fih_map_name, scene.fih_selected_only, scene.fih_scripts_dir,
                         repair_open=scene.fih_repair_open, repairs=repairs)
        except (ExportError, OSError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Exported {path}; auto-repaired {len(repairs)} mesh(es)")
        return {"FINISHED"}


class FIH_OT_add_marker(Operator):
    bl_idname = "fih.add_map_marker"
    bl_label = "Add Map Marker"
    bl_description = "Add a textured marker that exports as map metadata"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(items=[
        ("Spawn", "Spawn", "Player start position and facing"),
        ("Goal", "Goal", "Goal trigger box"),
        ("Checkpoint", "Checkpoint", "Checkpoint position and facing"),
    ])

    def execute(self, context):
        try:
            marker = create_marker(context, self.kind)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Added {marker.name}; arrow points toward player forward")
        return {"FINISHED"}


class FIH_MT_add_markers(Menu):
    bl_idname = "FIH_MT_add_markers"
    bl_label = "FIH Map Markers"

    def draw(self, context):
        for kind, icon in (("Spawn", "PLAY"), ("Goal", "EVENT_G"), ("Checkpoint", "EVENT_C")):
            action = self.layout.operator(FIH_OT_add_marker.bl_idname, text=kind, icon=icon)
            action.kind = kind


def _draw_add_menu(self, context):
    self.layout.menu(FIH_MT_add_markers.bl_idname, icon="EMPTY_AXIS")


class FIH_PT_export(Panel):
    bl_label = "FIH Map"
    bl_idname = "FIH_PT_export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "FIH Map"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(scene, "fih_map_name")
        layout.prop(scene, "fih_output_path")
        layout.prop(scene, "fih_selected_only")
        layout.prop(scene, "fih_blank_world")
        layout.prop(scene, "fih_repair_open")
        layout.prop(scene, "fih_scripts_dir")
        layout.operator(FIH_OT_export.bl_idname, icon="EXPORT")


class FIH_PT_markers(Panel):
    bl_label = "Map Markers"
    bl_idname = "FIH_PT_markers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "FIH Map"

    def draw(self, context):
        layout = self.layout
        for kind, icon in (("Spawn", "PLAY"), ("Goal", "EVENT_G"), ("Checkpoint", "EVENT_C")):
            action = layout.operator(FIH_OT_add_marker.bl_idname, text=f"Add {kind}", icon=icon)
            action.kind = kind
        obj = context.active_object
        if obj and obj.get("fih_marker_kind"):
            layout.separator()
            layout.label(text=f"Selected: {obj.name}")
            if obj.name.casefold().startswith("checkpoint") and obj.type == "EMPTY":
                layout.prop(obj, "fih_checkpoint_radius")
            if obj.name.casefold().startswith(("spawn", "checkpoint")):
                layout.label(text="Arrow / local -Y = player forward")
        layout.label(text="View textures in Material Preview")


CLASSES = (FIH_OT_export, FIH_OT_add_marker, FIH_MT_add_markers, FIH_PT_export, FIH_PT_markers)


@persistent
def _refresh_markers_on_load(_):
    # Blender exposes _RestrictData while enabling extensions at startup.
    # The load_post handler runs after real scene data becomes available.
    if not hasattr(bpy.data, "materials"):
        return
    try:
        refresh_marker_assets()
    except Exception as exc:
        print(f"FIH Map Exporter: marker preview refresh failed: {exc}")


def register():
    bpy.types.Scene.fih_map_name = StringProperty(name="Map Name", default="Blender Map")
    bpy.types.Scene.fih_output_path = StringProperty(name="Package", subtype="FILE_PATH", default="//BlenderMap.fihmap.zip")
    bpy.types.Scene.fih_selected_only = BoolProperty(name="Selected Meshes Only", default=False)
    bpy.types.Scene.fih_blank_world = BoolProperty(
        name="Blank Game World", default=True,
        description="Hide the game's built-in level and show only this map's objects")
    bpy.types.Scene.fih_repair_open = BoolProperty(name="Repair Matching Gaps", default=False,
                                                  description="Bridge two matching open edge loops in the export copy")
    bpy.types.Object.fih_checkpoint_radius = FloatProperty(
        name="Checkpoint Radius", default=1.5, min=0.01,
        description="Radius for an Empty checkpoint; object scale also applies")
    bpy.types.Scene.fih_scripts_dir = StringProperty(name="C# Scripts Folder", subtype="DIR_PATH", default="")
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_add.append(_draw_add_menu)
    bpy.app.handlers.load_post.append(_refresh_markers_on_load)
    _refresh_markers_on_load(None)


def unregister():
    if _refresh_markers_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_refresh_markers_on_load)
    try:
        bpy.types.VIEW3D_MT_add.remove(_draw_add_menu)
    except ValueError:
        pass
    for key in ("fih_checkpoint_radius",):
        if hasattr(bpy.types.Object, key):
            delattr(bpy.types.Object, key)
    for key in ("fih_map_name", "fih_output_path", "fih_selected_only", "fih_repair_open",
                "fih_scripts_dir", "fih_blank_world"):
        if hasattr(bpy.types.Scene, key):
            delattr(bpy.types.Scene, key)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
