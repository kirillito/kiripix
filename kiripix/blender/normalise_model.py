"""Run inside Blender: import a Model (.glb, .fbx or .blend), put it upright at a known size, and save it.

    blender -b -P normalise_model.py -- <args.json> <result.json>

args:   {"input": <file>, "output": <model.blend to write>, "height": <the Model's height afterwards, in Blender units>,
         "upload": <optional: an .fbx to write for Mixamo's auto-rigger when the Model has no armature>,
         "facing": <optional: the way the Model faces in the file, "-y" (default), "+y", "-x" or "+x">,
         "still": <optional: a .png to write, a 256 px preview of the normalised Model from direction `s`>}
result: {"still": <true when the still was written>, "height", "up", "facing", "bounds": {"min", "max"}, "vertices", "armature", "bones", "actions": [{"name", "start", "end"}],
         "upload": <true when the upload file was written>,
         "ignored": [{"name", "vertices"}: a mesh deleted from the Model, because it isn't skinned to the armature]}

In a rigged Model only the meshes skinned to an armature (an Armature modifier, or a parent that is an armature) are
measured and counted. A glTF export writes a bone's custom shape out as a mesh; measuring it would make the Model too tall. (The glTF importer
makes its own bone shape meshes: they are neither measured nor reported.)
A Model with no armature, or with no skinned mesh at all, is measured from every mesh.

`vertices` counts the distinct points of the meshes, whatever their size and place, so that the `rig` Stage can tell a
rigged file made from this Model from one made from another (importers split a vertex at each hard edge, so the raw
count differs by file format).

Importers give +Z up (glTF and FBX are converted on import; a .blend is Z up). The normalised Model hangs under one Empty,
`model_root`, that carries the scale and moves the feet to z = 0 and the middle to x = y = 0. The scale stays on the Empty
and isn't applied to a rig: applying it would leave an animation's location keys in the old units. Rig-free meshes under
the Empty get their transforms applied.

`facing` turns the Model about +Z, on the same Empty, so that it faces -Y afterwards (toward the `render` camera at
direction `s`). The turn comes before the measuring, so the bounds are the turned Model's. The upload for Mixamo has the
turn applied to its meshes, so a file Mixamo rigs from it faces -Y already and `render` turns nothing for a rigged file.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = "model_root"
STILL_SIZE = 256  # px, square
STILL_ELEVATION = 30.0  # degrees the camera looks down: the default camera preset's
STILL_PIVOT_Y = 232  # px from the top: the feet, the same row for every Model (like `render`'s 0.1 of the height above the bottom)
STILL_MARGIN = 8  # px kept free around the Model
DISTANCE = 10.0  # Blender units from the camera to the ground point, as in `render_frames.py`
TURN = {"-y": 0.0, "+y": math.pi, "-x": math.pi / 2, "+x": -math.pi / 2}  # about +Z, to make the Model face -Y


def progress(done: int, total: int, message: str) -> None:
    print(f"PROGRESS {done} {total} {message}", flush=True)


def import_model(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if suffix == ".glb" or suffix == ".gltf":
            bpy.ops.import_scene.gltf(filepath=str(path))
        elif suffix == ".fbx":
            bpy.ops.import_scene.fbx(filepath=str(path))
        else:
            raise ValueError(f"{path.name} is not a .glb, .fbx or .blend")


def is_skinned(obj: "bpy.types.Object") -> bool:
    return any(m.type == "ARMATURE" and m.object is not None for m in obj.modifiers) or         (obj.parent is not None and obj.parent.type == "ARMATURE")


def meshes() -> tuple[list, list]:
    """(measured, ignored): the meshes that make up the character, and the ones left out."""
    shapes = {b.custom_shape for o in bpy.data.objects if o.type == "ARMATURE" for b in o.pose.bones if b.custom_shape}
    every = [o for o in bpy.data.objects if o.type == "MESH" and o not in shapes]  # the glTF importer makes bone shapes itself
    if not any(o.type == "ARMATURE" for o in bpy.data.objects):
        return every, []
    skinned = [o for o in every if is_skinned(o)]
    if not skinned:
        return every, []
    return skinned, [o for o in every if not is_skinned(o)]


def measure() -> tuple[Vector, Vector]:
    """The world-space corners of every mesh, in the rest pose, so the height doesn't depend on the action showing."""
    rests = [(a.data, a.data.pose_position) for a in bpy.data.objects if a.type == "ARMATURE"]
    for armature, _ in rests:
        armature.pose_position = "REST"
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    low, high = Vector((1e18,) * 3), Vector((-1e18,) * 3)
    for obj in meshes()[0]:
        evaluated = obj.evaluated_get(graph)
        for corner in evaluated.bound_box:
            world = evaluated.matrix_world @ Vector(corner)
            low = Vector(min(a, b) for a, b in zip(low, world))
            high = Vector(max(a, b) for a, b in zip(high, world))
    for armature, pose in rests:
        armature.pose_position = pose
    if low.x > high.x:
        raise ValueError("the file has no mesh")
    return low, high


def distinct_points(low: Vector, high: Vector) -> int:
    """How many distinct points the meshes have in the rest pose, after moving them to the bounds' corner and dividing by
    their longest side."""
    longest = max(high - low) or 1.0
    rests = [(a.data, a.data.pose_position) for a in bpy.data.objects if a.type == "ARMATURE"]
    for armature, _ in rests:
        armature.pose_position = "REST"
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    points = set()
    for obj in meshes()[0]:
        evaluated = obj.evaluated_get(graph)
        matrix = evaluated.matrix_world
        for vertex in evaluated.data.vertices:
            world = matrix @ vertex.co
            points.add(tuple(round((world[i] - low[i]) / longest, 3) for i in range(3)))
    for armature, pose in rests:
        armature.pose_position = pose
    return len(points)


def write_upload(path: Path) -> None:
    """Export the meshes alone, upright, with their scale applied and no parent, as the .fbx that Mixamo takes. Last: it
    changes the open scene, which is saved already."""
    for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=False, object_types={"MESH"}, path_mode="COPY",
                             embed_textures=True)


def write_still(path: Path, low: Vector, high: Vector) -> None:
    """A 256 px preview of the Model as it is saved: rest pose, from the `s` direction, flat albedo, no anti-aliasing, no outline.
    Workbench does it (flat light, the material's own colour or texture): no samples, no device, the same pixels every run.
    Last but for the upload: it adds a camera to the open scene, which is saved already.

    The camera is the one `render` has for direction `s` and a 30 degree elevation (the default preset's), COPIED from
    `render_frames.py`: orthographic, DISTANCE units back from the ground point under the Model's middle, looking at it. It is
    fixed here, not the Asset's `camera` parameter, so that a camera change doesn't make `model` stale. The scale is not
    `render`'s: it is fitted so that any Model is whole in the picture, and the feet (the pivot) are on the same row, STILL_PIVOT_Y."""
    for armature in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        armature.data.pose_position = "REST"
        if armature.animation_data:
            armature.animation_data.action = None  # the rest pose, whatever action the file had showing
    shown = set(meshes()[0])
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj not in shown:
            obj.hide_render = True  # a bone's custom shape
    bpy.context.view_layer.update()
    size, elevation = STILL_SIZE, math.radians(STILL_ELEVATION)
    sin, cos = math.sin(elevation), math.cos(elevation)
    # the Model's corners on screen, in Blender units from the pivot: x right, y up (the camera looks down at `elevation`)
    corners = [(x, z * cos + y * sin) for x in (low.x, high.x) for y in (low.y, high.y) for z in (low.z, high.z)]
    room = STILL_MARGIN
    fit = [(size / 2 - room) / max(abs(c[0]) for c in corners) if any(c[0] for c in corners) else 1e9,
           (STILL_PIVOT_Y - room) / max(c[1] for c in corners),
           (size - STILL_PIVOT_Y - room) / max(-min(c[1] for c in corners), 1e-6)]
    px_per_unit = max(min(fit), 1.0)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.use_file_extension = False
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.display.render_aa = "OFF"
    shading = scene.display.shading
    shading.light = "FLAT"
    shading.color_type = "TEXTURE"
    shading.show_object_outline = False
    shading.show_cavity = False
    shading.show_shadows = False
    shading.show_specular_highlight = False

    data = bpy.data.cameras.new("kiripix_still_camera")
    data.type = "ORTHO"
    data.ortho_scale = size / px_per_unit
    data.clip_start, data.clip_end = 0.1, 100.0
    camera = bpy.data.objects.new("kiripix_still_camera", data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, -DISTANCE * cos, DISTANCE * sin)
    camera.rotation_euler = (math.pi / 2 - elevation, 0.0, 0.0)
    scene.camera = camera
    bpy.context.view_layer.update()
    ground = Vector((0.0, 0.0, 0.0))
    here = world_to_camera_view(scene, camera, ground)  # shift the view so that the ground point lands at the pivot's pixel
    data.shift_x = (here.x - 0.5)
    data.shift_y = (here.y - (1.0 - STILL_PIVOT_Y / size))
    bpy.context.view_layer.update()
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    separator = sys.argv.index("--")
    args = json.loads(Path(sys.argv[separator + 1]).read_text(encoding="utf-8"))
    result_path = Path(sys.argv[separator + 2])
    try:
        result = normalise(args)
    except Exception as error:  # reported to Kiripix as the Stage's failure
        result = {"error": f"{type(error).__name__}: {error}"}
    result_path.write_text(json.dumps(result), encoding="utf-8")


def normalise(args: dict) -> dict:
    progress(0, 3, "importing")
    import_model(Path(args["input"]))
    for obj in list(bpy.data.objects):
        if obj.name == ROOT:
            bpy.data.objects.remove(obj)  # a file saved by this script before: start again from its contents
    facing = str(args.get("facing", "-y"))
    if facing not in TURN:
        raise ValueError(f"facing {facing} is not one of {', '.join(TURN)}")
    dropped = meshes()[1]
    ignored = [{"name": o.name, "vertices": len(o.data.vertices)} for o in dropped]
    for obj in dropped:  # not part of the character: delete it, so `render` never draws it
        data = obj.data
        bpy.data.objects.remove(obj)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    progress(1, 3, "normalising")
    root = bpy.data.objects.new(ROOT, None)
    bpy.context.scene.collection.objects.link(root)
    for obj in [o for o in bpy.data.objects if o.parent is None and o is not root]:
        obj.parent = root
        obj.matrix_parent_inverse = root.matrix_world.inverted()  # the Empty is still at the origin, unturned
    root.rotation_euler = (0.0, 0.0, TURN[facing])
    bpy.context.view_layer.update()
    low, high = measure()  # the turned Model's, before the scale and the move
    height = high.z - low.z
    if height <= 1e-6:
        raise ValueError("the Model has no height")
    scale = float(args["height"]) / height
    centre = (low + high) / 2
    root.scale = (scale, scale, scale)
    root.location = (-centre.x * scale, -centre.y * scale, -low.z * scale)
    bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.type == "MESH" and not any(m.type == "ARMATURE" for m in obj.modifiers) and obj.data.shape_keys is None:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            try:
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            except RuntimeError:
                pass  # shared mesh data can't be applied; the Empty's scale still holds

    low, high = measure()
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    bones = [bone.name for armature in armatures for bone in armature.data.bones]
    actions = [{"name": a.name, "start": int(a.frame_range[0]), "end": int(a.frame_range[1])} for a in bpy.data.actions]

    vertices = distinct_points(low, high)

    progress(2, 3, "saving")
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(args["output"]), compress=True)
    uploaded = bool(args.get("upload")) and not armatures
    still = False
    if args.get("still"):
        write_still(Path(args["still"]), low, high)
        still = True
    if uploaded:
        write_upload(Path(args["upload"]))
    progress(3, 3, "done")
    return {
        "height": round(high.z - low.z, 6),
        "up": "+Z",
        "facing": facing,
        "bounds": {"min": [round(v, 6) for v in low], "max": [round(v, 6) for v in high]},
        "vertices": vertices,
        "upload": uploaded,
        "still": still,
        "armature": armatures[0].name if armatures else None,
        "bones": bones,
        "actions": actions,
        "ignored": ignored,
    }


main()
