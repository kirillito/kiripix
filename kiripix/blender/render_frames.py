"""Run inside Blender: render a character's clips in every direction at the target pixel size (ticket 0104).

    blender -b -P render_frames.py -- <args.json> <result.json>

args:   {"rig_file": <the file to animate: the Model's `model.blend`, or the rigged file the Mixamo round trip brought back>,
         "root": [<bone names to try as the root, in order>], "model_height": <the normalised height, Blender units>,
         "clips": [{"name", "action", "file": <a clip-source file, or null for an action of `rig_file`>,
                    "frames": [<source frame numbers, ints or floats>], "root_motion": <bool>}],
         "directions": [{"name", "yaw": <degrees the Model turns about its up axis; 0 is facing the camera>}],
         "elevation": <degrees the camera looks down>, "frame": [<width>, <height>] in px, "px_per_unit": <px per Blender unit>,
         "pivot": [<x>, <y>] in px, where the ground point under the root lands, "device": "cpu" | "gpu",
         "toon": {"bands": 2 to 4, "shadow": 0 to 1, "light": {"angle": <deg round the view axis from screen top>, "tilt": <deg
                  toward the camera>}}, "output": <folder to write the frames into>}
result: {"device": <what rendered>, "depth_range": [<near>, <far>], "frames": {<clip>: {<direction>: [{"pivot": [x, y]}]}}}

Files, per clip, direction and frame (index from 0, three digits): `color/<clip>/<dir>/<index>.png` (RGBA, 8 bit),
`normal/...` (RGBA: the camera-space normal as (v + 1) / 2 * 255, X right, Y up, Z toward the camera),
`depth/...` (gray, 16 bit: 0 at `depth_range[0]`, 65535 at `[1]` and in the background; distance along the view axis,
in Blender units) and `mask/...` (gray, 8 bit, 0 or 255). Colour and normal carry the mask as their alpha, so it is 0 or 255.

Cycles renders it at one sample with a box filter 0.01 wide and no denoising, so every pixel is its centre's value and there
is no anti-aliasing. Every pass is a primary-ray value (Diffuse Color, Normal, Depth, Object Index), so the passes don't
depend on the device and don't have noise. The colour pass is the Diffuse Color toon-shaded by `shade` (ticket 0105): a light
fixed in camera space, stepped in `bands` levels in numpy, which works in Cycles on CPU and GPU alike.

The camera orbits the point under the root, in 3D the Model turning about its up axis there, so the pivot is the same pixel
in every direction. A clip whose root travels (`root_motion`) has the camera follow it, so the pivot is also the same pixel in
every frame; any other clip reports the pivot as the root puts it. Scale and the feet are normalised for a rigged file as
`normalise_model.py` does for a Model (a `model_root` Empty), and a clip source's action is applied to the rig by bone names.
"""

import json
import math
import re
import shutil
import struct
import sys
import zlib
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = "model_root"
DISTANCE = 10.0  # Blender units from the camera to the ground point under the root
DEPTH_MARGIN = 1.5  # of the Model's size around that point: how far a posed limb may reach beyond the rest pose


def progress(done: int, total: int, message: str) -> None:
    print(f"PROGRESS {done} {total} {message}", flush=True)


# files ---------------------------------------------------------------------------------------------------------------


def import_file(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".glb" or suffix == ".gltf":
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        raise ValueError(f"{path.name} is not a .glb, .fbx or .blend")


def open_rig(path: Path) -> None:
    if path.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        import_file(path)


def png(path: Path, array: np.ndarray, kind: str) -> None:
    """A PNG without PIL, which Blender's Python doesn't have: `rgba` (h, w, 4) uint8, `l8` (h, w) uint8, `l16` (h, w)."""
    height, width = array.shape[:2]
    if kind == "rgba":
        colour_type, depth, rows = 6, 8, array.astype(np.uint8).reshape(height, width * 4)
    elif kind == "l8":
        colour_type, depth, rows = 0, 8, array.astype(np.uint8)
    else:
        colour_type, depth = 0, 16
        rows = array.astype(">u2").view(np.uint8).reshape(height, width * 2)
    raw = np.zeros((height, rows.shape[1] + 1), dtype=np.uint8)
    raw[:, 1:] = rows  # filter type 0 on every row

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, depth, colour_type, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw.tobytes(), 6))
                     + chunk(b"IEND", b""))


def read_exr(path: Path) -> dict:
    """The channels of an uncompressed 32-bit OpenEXR, single or multi part, by name, as (height, width) float arrays,
    the top row first. Blender writes one part per render pass."""
    data = path.read_bytes()
    multipart = bool(data[5] & 0x10)
    position = 8
    parts = []
    while True:
        attributes = {}
        while data[position] != 0:
            end = data.index(b"\0", position)
            name = data[position:end].decode()
            position = end + 1
            end = data.index(b"\0", position)
            position = end + 1
            (size,) = struct.unpack_from("<i", data, position)
            position += 4
            attributes[name] = data[position:position + size]
            position += size
        position += 1
        parts.append(attributes)
        if not multipart or data[position] == 0:
            break
    if multipart:
        position += 1
    tables = []
    for attributes in parts:
        if "chunkCount" in attributes:
            (count,) = struct.unpack("<i", attributes["chunkCount"])
        else:
            _, y0, _, y1 = struct.unpack("<4i", attributes["dataWindow"])
            count = y1 - y0 + 1
        tables.append(struct.unpack_from(f"<{count}Q", data, position))
        position += 8 * count
    channels = {}
    for index, attributes in enumerate(parts):
        x0, y0, x1, y1 = struct.unpack("<4i", attributes["dataWindow"])
        width, height = x1 - x0 + 1, y1 - y0 + 1
        if attributes["compression"][0] != 0:
            raise ValueError("the EXR is compressed")
        names = []
        listing, where = attributes["channels"], 0
        while listing[where] != 0:
            end = listing.index(b"\0", where)
            name = listing[where:end].decode()
            where = end + 1
            (kind,) = struct.unpack_from("<i", listing, where)
            where += 16
            if kind != 2:
                raise ValueError("the EXR is not 32-bit float")
            names.append(name)
        for name in names:
            channels[name] = np.zeros((height, width), np.float32)
        for offset in tables[index]:
            at = offset + (4 if multipart else 0)
            row, _ = struct.unpack_from("<ii", data, at)
            at += 8
            for name in names:
                channels[name][row - y0] = np.frombuffer(data, np.float32, width, at)
                at += 4 * width
    return channels


def channel(channels: dict, *suffixes: str) -> np.ndarray:
    for suffix in suffixes:
        for name, values in channels.items():
            if name.endswith(suffix):
                return values
    raise KeyError(f"the render has no {' or '.join(suffixes)} pass")


# the scene -----------------------------------------------------------------------------------------------------------


def plain(name: str) -> str:
    return "".join(c for c in name.split(":")[-1].lower() if c.isalnum())


def find_root(armature, wanted: list) -> str:
    bones = {plain(b.name): b.name for b in armature.data.bones}
    for name in wanted:
        if plain(name) in bones:
            return bones[plain(name)]
    return armature.data.bones[0].name


def at_rest():
    """The armatures, with their pose position put back to what it was by `restore`."""
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    kept = [(a.data, a.data.pose_position) for a in armatures]
    for armature in armatures:
        armature.data.pose_position = "REST"
    bpy.context.view_layer.update()
    return kept


def restore(kept) -> None:
    for data, position in kept:
        data.pose_position = position
    bpy.context.view_layer.update()


def measure() -> tuple[Vector, Vector]:
    """The world-space corners of every mesh in the rest pose (as `normalise_model.py` measures)."""
    kept = at_rest()
    graph = bpy.context.evaluated_depsgraph_get()
    low, high = Vector((1e18,) * 3), Vector((-1e18,) * 3)
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(graph)
        for corner in evaluated.bound_box:
            world = evaluated.matrix_world @ Vector(corner)
            low = Vector(min(a, b) for a, b in zip(low, world))
            high = Vector(max(a, b) for a, b in zip(high, world))
    restore(kept)
    if low.x > high.x:
        raise ValueError("the file has no mesh")
    return low, high


def normalise(height: float) -> None:
    """A rigged file isn't at the Model's size: scale it to `height` with the feet at z = 0 and the middle at x = y = 0,
    under one Empty, as the `model` Stage does. A file the Stage saved already has that Empty."""
    if bpy.data.objects.get(ROOT) is not None:
        return
    low, high = measure()
    size = high.z - low.z
    if size <= 1e-6:
        raise ValueError("the Model has no height")
    scale = height / size
    root = bpy.data.objects.new(ROOT, None)
    bpy.context.scene.collection.objects.link(root)
    for obj in [o for o in bpy.data.objects if o.parent is None and o is not root]:
        obj.parent = root
        obj.matrix_parent_inverse = root.matrix_world.inverted()
    centre = (low + high) / 2
    root.scale = (scale, scale, scale)
    root.location = (-centre.x * scale, -centre.y * scale, -low.z * scale)
    bpy.context.view_layer.update()


def assign(armature, action) -> None:
    armature.animation_data_create()
    armature.animation_data.action = action
    slots = list(getattr(action, "slots", []))
    if slots:
        chosen = next((s for s in slots if s.target_id_type == "OBJECT"), slots[0])
        armature.animation_data.action_slot = chosen  # Blender 5: an action's channels sit in a slot


_SUFFIX = re.compile(r"\.\d{3}(?=\||$)")  # `Armature.001|Scene`: an imported name that was already taken
_loaded: dict = {}  # clip-source file -> {action name: action}


def actions_of(path: Path) -> dict:
    """The actions of a clip-source file, brought in without its objects, so they can be applied to the rig."""
    if str(path) in _loaded:
        return _loaded[str(path)]
    before_actions = set(bpy.data.actions)
    before_objects = set(bpy.data.objects)
    if path.suffix.lower() == ".blend":
        with bpy.data.libraries.load(str(path)) as (source, wanted):
            wanted.actions = list(source.actions)
    else:
        import_file(path)
        for obj in set(bpy.data.objects) - before_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    found = {}
    for action in set(bpy.data.actions) - before_actions:
        action.use_fake_user = True
        base = _SUFFIX.sub("", action.name)  # an action named as one already here got a `.001`
        found[action.name if base in found else base] = action
    _loaded[str(path)] = found
    return found


def action_for(clip: dict):
    wanted = clip["action"]
    if clip.get("file"):
        found = actions_of(Path(clip["file"]))
        if wanted not in found:
            raise ValueError(f"{Path(clip['file']).name} has no action {wanted}")
        return found[wanted]
    action = bpy.data.actions.get(wanted)
    if action is None:
        raise ValueError(f"the rig's file has no action {wanted}")
    return action


def set_up_scene(args: dict, armature, root_bone: str) -> dict:
    scene = bpy.context.scene
    width, height = args["frame"]
    scene.render.engine = "CYCLES"
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = width, height, 100
    scene.render.film_transparent = True
    scene.render.use_persistent_data = True
    scene.render.use_file_extension = False
    scene.render.image_settings.media_type = "MULTI_LAYER_IMAGE"
    scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "NONE"
    cycles = scene.cycles
    cycles.samples = 1
    cycles.use_adaptive_sampling = False
    cycles.use_denoising = False
    cycles.pixel_filter_type = "BOX"
    cycles.filter_width = 0.01  # the smallest Cycles takes: a pixel is its centre's value
    cycles.seed = 0
    cycles.use_animated_seed = False
    cycles.max_bounces = 0
    layer = bpy.context.view_layer
    layer.use_pass_z = True
    layer.use_pass_normal = True
    layer.use_pass_object_index = True
    layer.use_pass_diffuse_color = True

    for obj in bpy.data.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            obj.pass_index = 1  # the object mask: everything that is the character
    for material in bpy.data.materials:
        if material.node_tree is not None:
            for node in material.node_tree.nodes:
                if node.type == "TEX_IMAGE":
                    node.interpolation = "Closest"  # no texture filtering

    bpy.context.view_layer.update()
    low, high = measure()
    head = armature.matrix_world @ armature.data.bones[root_bone].head_local  # the rest pose's root
    ground = Vector((head.x, head.y, 0.0))
    corners = [Vector((x, y, z)) for x in (low.x, high.x) for y in (low.y, high.y) for z in (low.z, high.z)]
    radius = max((corner - ground).length for corner in corners)

    elevation = math.radians(float(args["elevation"]))
    turntable = bpy.data.objects.new("kiripix_turntable", None)  # at the pivot; turning it orbits the camera and light
    turntable.location = ground
    scene.collection.objects.link(turntable)
    data = bpy.data.cameras.new("kiripix_camera")
    data.type = "ORTHO"
    data.ortho_scale = max(width, height) / float(args["px_per_unit"])
    data.clip_start, data.clip_end = 0.1, 100.0
    camera = bpy.data.objects.new("kiripix_camera", data)
    scene.collection.objects.link(camera)
    camera.parent = turntable
    camera.location = (0.0, -DISTANCE * math.cos(elevation), DISTANCE * math.sin(elevation))
    camera.rotation_euler = (math.pi / 2 - elevation, 0.0, 0.0)
    scene.camera = camera
    bpy.context.view_layer.update()

    # the camera looks at the pivot; shift the view so that the pivot lands at the wanted pixel
    wanted_y = 1.0 - float(args["pivot"][1]) / height
    here = world_to_camera_view(scene, camera, ground)
    data.shift_y = (here.y - wanted_y) * height / max(width, height)
    data.shift_x = (here.x - float(args["pivot"][0]) / width) * width / max(width, height)
    bpy.context.view_layer.update()
    landed = world_to_camera_view(scene, camera, ground)
    if abs(landed.x * width - float(args["pivot"][0])) > 0.01 or abs((1.0 - landed.y) * height - float(args["pivot"][1])) > 0.01:
        raise ValueError("the pivot did not land where it was asked to")
    return {"ground": ground, "turntable": turntable, "camera": camera, "radius": radius}


def choose_device(want: str) -> str:
    cycles = bpy.context.scene.cycles
    if want == "gpu":
        preferences = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                preferences.compute_device_type = kind
                preferences.refresh_devices()
            except (TypeError, AttributeError):
                continue
            gpus = [d for d in preferences.devices if d.type == kind]
            if gpus:
                for device in preferences.devices:
                    device.use = device.type == kind
                cycles.device = "GPU"
                return f"gpu {kind} {gpus[0].name}"
    cycles.device = "CPU"
    return "cpu"


# the passes ----------------------------------------------------------------------------------------------------------


def srgb(linear: np.ndarray) -> np.ndarray:
    linear = np.clip(linear, 0.0, 1.0)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * np.power(linear, 1 / 2.4) - 0.055)


def to_u8(values: np.ndarray) -> np.ndarray:
    return np.floor(np.clip(values, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def light_vector(light: dict) -> np.ndarray:
    """The unit vector toward the key light in camera space (X right, Y up, Z toward the camera). `angle` goes round the view
    axis from the top of the screen (90 is the right, -45 the upper left); `tilt` is how far it leans toward the camera."""
    angle, tilt = math.radians(float(light["angle"])), math.radians(float(light["tilt"]))
    return np.array([math.sin(angle) * math.cos(tilt), math.cos(angle) * math.cos(tilt), math.sin(tilt)])


def shade(albedo: np.ndarray, normal: np.ndarray, mask: np.ndarray, toon: dict) -> np.ndarray:
    """The colour pass, (h, w, 3) linear: toon shading (ticket 0105). The key light is fixed in camera space, so it sits in the
    same place on screen for every direction, frame and character. Half-Lambert (n . l * 0.5 + 0.5) is cut into `bands` steps;
    the brightest keeps the Model's own colour and each step down darkens it by an equal share of `shadow` (0 to 1). Pure numpy
    on the primary-ray normal, so it works the same on CPU and GPU and has no noise (a Shader to RGB node is EEVEE-only)."""
    bands = int(toon["bands"])
    lit = np.clip(normal @ light_vector(toon["light"]) * 0.5 + 0.5, 0.0, 1.0)
    step = np.minimum(np.floor(lit * bands), bands - 1) / (bands - 1)  # 0 darkest band .. 1 brightest
    factor = 1.0 - float(toon["shadow"]) * (1.0 - step)
    return albedo * factor[..., None]


def write_frame(output: Path, clip: str, direction: str, index: int, exr: Path, camera, depth_range: tuple, toon: dict) -> None:
    channels = read_exr(exr)
    mask = channel(channels, "Object Index.X", "IndexOB.X") > 0.5
    albedo = np.stack([channel(channels, f"Diffuse Color.{c}", f"DiffCol.{c}") for c in "RGB"], axis=-1)
    world = np.stack([channel(channels, f"Normal.{c}") for c in "XYZ"], axis=-1)
    rotation = np.array(camera.matrix_world.to_3x3())
    view = world @ rotation  # (R^T n) for every row vector n: camera space
    length = np.linalg.norm(view, axis=-1, keepdims=True)
    view = view / np.where(length < 1e-9, 1.0, length)
    depth = channel(channels, "Depth.Z", "Z.Z")
    near, far = depth_range
    scaled = np.clip((depth - near) / (far - near), 0.0, 1.0)
    scaled = np.where(mask, scaled, 1.0)

    alpha = np.where(mask, 255, 0).astype(np.uint8)
    colour = np.zeros(mask.shape + (4,), dtype=np.uint8)
    colour[..., :3] = np.where(mask[..., None], to_u8(srgb(shade(albedo, view, mask, toon))), 0)
    colour[..., 3] = alpha
    normal = np.zeros(mask.shape + (4,), dtype=np.uint8)
    normal[..., :3] = np.where(mask[..., None], to_u8((view + 1.0) / 2.0), 0)
    normal[..., 3] = alpha
    name = f"{index:03d}.png"
    png(output / "color" / clip / direction / name, colour, "rgba")
    png(output / "normal" / clip / direction / name, normal, "rgba")
    png(output / "depth" / clip / direction / name, np.floor(scaled * 65535.0 + 0.5), "l16")
    png(output / "mask" / clip / direction / name, alpha, "l8")


def pose(armature, frame) -> None:
    scene = bpy.context.scene
    whole = int(math.floor(frame))
    scene.frame_set(whole, subframe=float(frame) - whole)
    bpy.context.view_layer.update()


def render(args: dict) -> dict:
    progress(0, 1, "opening the file")
    open_rig(Path(args["rig_file"]))
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not armatures:
        raise ValueError("the file has no armature")
    armature = armatures[0]
    armature.data.pose_position = "POSE"
    normalise(float(args["model_height"]))
    root_bone = find_root(armature, list(args.get("root", [])))

    output = Path(args["output"])
    scratch = output / ".scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    exr = scratch / "pass.exr"
    scene = bpy.context.scene
    device = choose_device(args["device"])
    setup = set_up_scene(args, armature, root_bone)
    scene.render.filepath = str(exr)
    ground, turntable, camera = setup["ground"], setup["turntable"], setup["camera"]
    depth_range = (DISTANCE - DEPTH_MARGIN * setup["radius"], DISTANCE + DEPTH_MARGIN * setup["radius"])

    directions = args["directions"]
    total = sum(len(c["frames"]) for c in args["clips"]) * len(directions)
    done = 0
    pivots: dict = {}
    for clip in args["clips"]:
        assign(armature, action_for(clip))
        pivots[clip["name"]] = {d["name"]: [] for d in directions}
        for index, frame in enumerate(clip["frames"]):
            pose(armature, frame)
            head = armature.matrix_world @ armature.pose.bones[root_bone].head
            under = Vector((head.x, head.y, 0.0))
            follow = clip.get("root_motion", False)
            turntable.location = under if follow else ground
            for direction in directions:
                progress(done, total, f"{clip['name']} {direction['name']} {index + 1}/{len(clip['frames'])}")
                turntable.rotation_euler.z = -math.radians(float(direction["yaw"]))
                bpy.context.view_layer.update()
                seen = world_to_camera_view(scene, camera, under)
                pivots[clip["name"]][direction["name"]].append(
                    {"pivot": [round(seen.x * args["frame"][0], 3), round((1.0 - seen.y) * args["frame"][1], 3)]})
                bpy.ops.render.render(write_still=True)
                write_frame(output, clip["name"], direction["name"], index, exr, camera, depth_range, args["toon"])
                done += 1
    shutil.rmtree(scratch, ignore_errors=True)
    progress(total, total, "done")
    return {"device": device, "depth_range": [round(depth_range[0], 4), round(depth_range[1], 4)], "frames": pivots}


def main() -> None:
    separator = sys.argv.index("--")
    args = json.loads(Path(sys.argv[separator + 1]).read_text(encoding="utf-8"))
    result_path = Path(sys.argv[separator + 2])
    try:
        result = render(args)
    except Exception as error:  # reported to Kiripix as the Stage's failure
        result = {"error": f"{type(error).__name__}: {error}"}
    result_path.write_text(json.dumps(result), encoding="utf-8")


main()
