"""Run inside Blender: render a character's clips in every direction at the target pixel size (ticket 0104).

    blender -b -P render_frames.py -- <args.json> <result.json>

args:   {"rig_file": <the file to animate: the Model's `model.blend`, or the rigged file the Mixamo round trip brought back>,
         "root": [<bone names to try as the root, in order>], "model_height": <the normalised height, Blender units>,
         "clips": [{"name", "action", "file": <a clip-source file, or null for an action of `rig_file`>,
                    "frames": [<source frame numbers, ints or floats>], "root_motion": <bool>}],
         a transition clip (ticket 0218) has no "action" or "file" but "transition": {"from": <end>, "to": <end>}, an end being
         {"action", "file", "frame": <the action's frame>, "root_motion": <bool>}, and its "frames" are the blend positions
         between 0 (the `from` pose) and 1 (the `to` pose);
         "directions": [{"name", "yaw": <degrees the Model turns about its up axis; 0 is facing the camera>}],
         "elevation": <degrees the camera looks down>, "frame": [<width>, <height>] in px, "px_per_unit": <px per Blender unit>,
         "pivot": [<x>, <y>] in px, where the ground point under the root lands, "device": "cpu" | "gpu",
         "toon": {"bands": 2 to 4, "shadow": 0 to 1, "band_edge": 0 to 1, "band_smooth": px, "light": {"angle": <deg round the view axis from screen top>, "tilt": <deg
                  toward the camera>}}, "eyes": [<names of the materials that are the eyes; optional>],
         "points": [{"name": <the point's name>, "target": <a bone of the armature or an Empty, by name>}; optional],
         "output": <folder to write the frames into>}
result: {"device": <what rendered>, "depth_range": [<near>, <far>], "materials": [{"index": <from 1>, "name"}],
         "frames": {<clip>: {<direction>: [{"pivot": [x, y]}]}}}

With `eyes`, each frame also has `"eyes"`: one entry per eye, the Model's right one first (ticket 0203), from the posed mesh and
not from the pixels: `{"x", "y"}`, the eye's centre in px (x right, y down), `"width"` and `"height"`, its extent on screen in
px, `"depth"`, its centre's distance along the view axis in Blender units (as the depth pass counts it), and `"normal"`, its
mean normal in camera space (X right, Y up, Z toward the camera). An eye is the faces of those materials on one side of the
Model's middle in the rest pose.

With `points` (ticket 0237), each frame also has `"points"`: `{<name>: {"x", "y", "depth", "hidden"}}`, the target's place in px
(x right, y down, sub-pixel), its depth as the eyes' (Blender units along the view axis) and `hidden`, true when the depth pass
has the body in front of it by more than `HIDDEN_MARGIN` of the Model's height. A bone's place is its head in the pose; an Empty's
is its own (a socket parented to a bone follows it). A target that is neither a bone nor an Empty ends the run before any frame, with
the result `{"points_unknown": [<targets>], "bones": [<the armature's bones>], "empties": [<the Empties>]}`.

With `"measure": true` in args nothing is rendered or written (ticket 0155): the result is where each frame lands, for sizing
the cell, `{"frames": {<clip>: {<direction>: [{"bounds": [left, top, right, bottom], "under": [x, y]}]}}}` in px from the
point the camera orbits (`measure_poses`).

Files, per clip, direction and frame (index from 0, three digits): `color/<clip>/<dir>/<index>.png` (RGBA, 8 bit),
`normal/...` (RGBA: the camera-space normal as (v + 1) / 2 * 255, X right, Y up, Z toward the camera),
`depth/...` (gray, 16 bit: 0 at `depth_range[0]`, 65535 at `[1]` and in the background; distance along the view axis,
in Blender units) and `mask/...` (gray, 8 bit, 0 or 255) and `material/...` (gray, 8 bit: the pixel's material, numbered from 1 in the order of
`materials`, the names of the materials the rendered meshes use sorted, 0 for the background; ticket 0148). Colour and normal carry the mask as their alpha, so it is 0 or 255.

Cycles renders it at one sample with a box filter 0.01 wide and no denoising, so every pixel is its centre's value and there
is no anti-aliasing. Every pass is a primary-ray value (Diffuse Color, Normal, Depth, Object Index, Material Index), so the passes don't
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
from mathutils import Matrix, Quaternion, Vector

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


def rendered_meshes() -> list:
    """The mesh objects that render: not hidden from renders, and in a collection that renders (`rendered_collections`).
    Measuring and rendering count the same ones (ticket 0162)."""
    shown = rendered_collections()
    return [o for o in bpy.data.objects
            if o.type == "MESH" and not o.hide_render and any(c in shown for c in o.users_collection)]


def measure() -> tuple[Vector, Vector]:
    """The world-space corners of every mesh that renders, in the rest pose (as `normalise_model.py` measures)."""
    kept = at_rest()
    graph = bpy.context.evaluated_depsgraph_get()
    low, high = Vector((1e18,) * 3), Vector((-1e18,) * 3)
    for obj in rendered_meshes():
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


MAX_MATERIALS = 255  # an 8 bit pass, 0 being the background


def number_materials() -> list:
    """The materials of the meshes that render, numbered from 1 by name (Material Index, a primary-ray value), as
    [{"index", "name"}]. A mesh with no material slot is index 0, as the background is."""
    used = {slot.material for obj in rendered_meshes() for slot in obj.material_slots if slot.material is not None}
    ordered = sorted(used, key=lambda m: m.name)
    if len(ordered) > MAX_MATERIALS:
        raise ValueError(f"the Model has {len(ordered)} materials; the material pass holds at most {MAX_MATERIALS}")
    for index, material in enumerate(ordered, start=1):
        material.pass_index = index
    return [{"index": index, "name": material.name} for index, material in enumerate(ordered, start=1)]


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
    layer.use_pass_material_index = True
    layer.use_pass_diffuse_color = True

    for obj in bpy.data.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            obj.pass_index = 1  # the object mask: everything that is the character
    for material in bpy.data.materials:
        if material.node_tree is not None:
            for node in material.node_tree.nodes:
                if node.type == "TEX_IMAGE":
                    node.interpolation = "Closest"  # no texture filtering

    materials = number_materials()
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
    return {"ground": ground, "turntable": turntable, "camera": camera, "radius": radius, "materials": materials}


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


def smooth_normal(normal: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    """The normals blurred by a Gaussian of `sigma` px inside the mask only (a normalised convolution, so the background does
    not leak in), scaled back to unit length. Outside the mask the normals are returned as they are."""
    radius = max(1, int(math.ceil(3.0 * sigma)))
    taps = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    taps /= taps.sum()

    def blur(values: np.ndarray) -> np.ndarray:
        for axis in (0, 1):
            pad = [(0, 0)] * values.ndim
            pad[axis] = (radius, radius)
            padded = np.pad(values, pad)
            size = values.shape[axis]
            values = sum(w * np.take(padded, np.arange(i, i + size), axis=axis) for i, w in enumerate(taps))
        return values

    weight = mask.astype(np.float64)
    total = blur(normal * weight[..., None]) / np.maximum(blur(weight), 1e-9)[..., None]
    length = np.linalg.norm(total, axis=-1, keepdims=True)
    total = total / np.where(length < 1e-9, 1.0, length)
    return np.where(mask[..., None], total, normal)


def shade(albedo: np.ndarray, normal: np.ndarray, mask: np.ndarray, toon: dict) -> np.ndarray:
    """The colour pass, (h, w, 3) linear: toon shading (ticket 0105). The key light is fixed in camera space, so it sits in the
    same place on screen for every direction, frame and character. Half-Lambert (n . l * 0.5 + 0.5) is shifted by
    `0.5 - band_edge`, clipped to 0..1 and cut into `bands` steps, so with 2 bands the cut is at `band_edge` (ticket 0213); the
    brightest keeps the Model's own colour and each step down darkens it by an equal share of `shadow` (0 to 1). With
    `band_smooth` above 0 the normals are blurred inside the mask first (only here: the normal pass is not). Pure numpy
    on the primary-ray normal, so it works the same on CPU and GPU and has no noise (a Shader to RGB node is EEVEE-only)."""
    bands = int(toon["bands"])
    edge, sigma = float(toon.get("band_edge", 0.5)), float(toon.get("band_smooth", 0.0))
    if sigma > 0:
        normal = smooth_normal(normal, mask, sigma)
    lit = normal @ light_vector(toon["light"]) * 0.5 + 0.5
    if edge != 0.5:
        lit = lit + (0.5 - edge)
    lit = np.clip(lit, 0.0, 1.0)
    step = np.minimum(np.floor(lit * bands), bands - 1) / (bands - 1)  # 0 darkest band .. 1 brightest
    factor = 1.0 - float(toon["shadow"]) * (1.0 - step)
    return albedo * factor[..., None]


def write_frame(output: Path, clip: str, direction: str, index: int, exr: Path, camera, depth_range: tuple, toon: dict):
    """Writes the passes of one frame; returns its depth (Blender units, as rendered) and mask, for `mark_hidden`."""
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
    numbered = np.rint(channel(channels, "Material Index.X", "IndexMA.X")).astype(np.int64)
    png(output / "material" / clip / direction / name, np.where(mask, np.clip(numbered, 0, 255), 0), "l8")
    return depth, mask


def pose(armature, frame) -> None:
    scene = bpy.context.scene
    whole = int(math.floor(frame))
    scene.frame_set(whole, subframe=float(frame) - whole)
    bpy.context.view_layer.update()


def reset_pose(armature) -> None:
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)


def in_place(armature, root_bone: str, ground: Vector, basis: dict) -> None:
    """Take the travel out of a captured pose (`basis`, each bone's matrix_basis): the root bone's translation is moved so that
    the point under it is the ground point again. What is left is the pose, as a clip with no root motion shows it."""
    bone = armature.pose.bones[root_bone]
    head = armature.matrix_world @ bone.head
    delta = armature.matrix_world.to_3x3().inverted() @ Vector((ground.x - head.x, ground.y - head.y, 0.0))
    rest = bone.bone.matrix_local.to_3x3()
    if bone.parent is not None:
        rest = bone.parent.matrix.to_3x3() @ bone.parent.bone.matrix_local.to_3x3().inverted() @ rest
    moved = basis[root_bone].copy()
    moved.translation = moved.translation + rest.inverted() @ delta
    basis[root_bone] = moved


def capture_end(armature, end: dict, root_bone: str, ground: Vector) -> dict:
    """The local pose of every bone (matrix_basis, as the NLA blends it) at one end of a transition."""
    reset_pose(armature)
    assign(armature, action_for(end))
    pose(armature, end["frame"])
    basis = {bone.name: bone.matrix_basis.copy() for bone in armature.pose.bones}
    if end.get("root_motion"):
        in_place(armature, root_bone, ground, basis)
    return basis


def begin_clip(armature, clip: dict, root_bone: str, ground: Vector):
    """Ready the rig for a clip: its action assigned, or for a transition both ends' poses captured. The result is what
    `pose_clip` needs."""
    if "transition" not in clip:
        assign(armature, action_for(clip))
        return None
    ends = [capture_end(armature, clip["transition"][side], root_bone, ground) for side in ("from", "to")]
    armature.animation_data.action = None  # the blend is set by hand, which a frame change must not undo
    return ends


def blend_pose(armature, ends: list, weight: float) -> None:
    """Every bone at `weight` between the two end poses, in its local space as the NLA does: location and scale linear,
    rotation a quaternion slerp along the short way round."""
    for bone in armature.pose.bones:
        loc_a, rot_a, scale_a = ends[0][bone.name].decompose()
        loc_b, rot_b, scale_b = ends[1][bone.name].decompose()
        if rot_a.dot(rot_b) < 0.0:
            rot_b = Quaternion((-rot_b.w, -rot_b.x, -rot_b.y, -rot_b.z))
        bone.matrix_basis = Matrix.LocRotScale(
            loc_a.lerp(loc_b, weight), rot_a.slerp(rot_b, weight), scale_a.lerp(scale_b, weight))
    bpy.context.view_layer.update()


def pose_clip(armature, clip: dict, state, frame) -> None:
    if state is None:
        pose(armature, frame)
    else:
        blend_pose(armature, state, float(frame))


def end_clip(armature, state) -> None:
    if state is not None:
        reset_pose(armature)  # what the next clip's action doesn't animate is at rest, not left in the blend


def open_posable(args: dict):
    """The rig's file opened and normalised: its armature, in the pose position, and its root bone's name."""
    progress(0, 1, "opening the file")
    open_rig(Path(args["rig_file"]))
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not armatures:
        raise ValueError("the file has no armature")
    armature = armatures[0]
    armature.data.pose_position = "POSE"
    normalise(float(args["model_height"]))
    return armature, find_root(armature, list(args.get("root", [])))


def rendered_collections() -> set:
    """The collections whose objects render: not excluded from the view layer and not hidden from renders, with their
    parents. The glTF importer puts objects it doesn't want, such as a bone shape's `Icosphere`, in an excluded one."""
    found: set = set()

    def walk(layer) -> None:
        if layer.exclude or layer.collection.hide_render:
            return
        found.add(layer.collection)
        for child in layer.children:
            walk(child)

    walk(bpy.context.view_layer.layer_collection)
    return found


def posed_points() -> np.ndarray:
    """Every vertex of every mesh that renders, in the current pose, in world space: an (n, 3) array."""
    graph = bpy.context.evaluated_depsgraph_get()
    found = []
    for obj in rendered_meshes():
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", co)
        finally:
            evaluated.to_mesh_clear()
        matrix = np.array(evaluated.matrix_world, dtype=np.float64)
        found.append(co.reshape(-1, 3).astype(np.float64) @ matrix[:3, :3].T + matrix[:3, 3])
    if not found:
        raise ValueError("the file has no mesh")
    return np.concatenate(found)


def eye_groups(names: list, ground: Vector) -> list:
    """The eyes: per side of the Model's middle (x below the ground point's first), the vertices of the faces whose material
    is one of `names`, as [(object, vertex indexes)]. A side with no such face has no entry. Read in the rest shape, which a
    mesh's own data is."""
    sides: list = [[], []]
    for obj in rendered_meshes():
        slots = {i for i, slot in enumerate(obj.material_slots) if slot.material is not None and slot.material.name in names}
        if not slots:
            continue
        found: list = [set(), set()]
        for polygon in obj.data.polygons:
            if polygon.material_index in slots:
                centre = obj.matrix_world @ polygon.center
                found[0 if centre.x < ground.x else 1].update(polygon.vertices)
        for side in (0, 1):
            if found[side]:
                sides[side].append((obj, np.array(sorted(found[side]), dtype=np.int64)))
    return [side for side in sides if side]


def posed_eyes(groups: list) -> list:
    """Each eye in the current pose, in world space: (its vertices (n, 3), its mean unit normal)."""
    graph = bpy.context.evaluated_depsgraph_get()
    eyes = []
    for group in groups:
        points, normals = [], []
        for obj, indexes in group:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            try:
                if len(mesh.vertices) != len(obj.data.vertices):
                    raise ValueError(f"{obj.name} has a modifier that changes its vertices, so its eyes can't be followed")
                co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
                mesh.vertices.foreach_get("co", co)
                normal = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
                mesh.vertex_normals.foreach_get("vector", normal)
            finally:
                evaluated.to_mesh_clear()
            matrix = np.array(evaluated.matrix_world, dtype=np.float64)
            points.append(co.reshape(-1, 3).astype(np.float64)[indexes] @ matrix[:3, :3].T + matrix[:3, 3])
            normals.append(normal.reshape(-1, 3).astype(np.float64)[indexes] @ np.linalg.inv(matrix[:3, :3]))
        mean = np.concatenate(normals).mean(axis=0)
        length = float(np.linalg.norm(mean))
        eyes.append((np.concatenate(points), mean / length if length > 1e-9 else np.array([0.0, 0.0, 0.0])))
    return eyes


def seen_eyes(eyes: list, camera, args: dict) -> list:
    """Where each posed eye lands in the frame: its centre and extent in px, its depth, and its normal in camera space."""
    scene = bpy.context.scene
    width, height = args["frame"]
    scale = float(args["px_per_unit"])
    axes = np.array(camera.matrix_world.to_3x3(), dtype=np.float64)
    eye_point = np.array(camera.matrix_world.translation, dtype=np.float64)
    found = []
    for points, normal in eyes:
        middle = points.mean(axis=0)
        centre = world_to_camera_view(scene, camera, Vector(middle))
        across, up = points @ axes[:, 0] * scale, points @ axes[:, 1] * scale
        found.append({"x": round(centre.x * width, 3), "y": round((1.0 - centre.y) * height, 3),
                      "width": round(float(across.max() - across.min()), 3),
                      "height": round(float(up.max() - up.min()), 3),
                      "depth": round(float((eye_point - middle) @ axes[:, 2]), 4),
                      "normal": [round(float(normal @ axes[:, i]), 4) for i in range(3)]})
    return found


HIDDEN_MARGIN = 0.08  # of the Model's height: a bone lies inside the body, so only a body this much nearer hides a point


def points_unknown(args: dict, armature) -> dict | None:
    """The result that reports the targets of `points` that are neither a bone of the armature nor an Empty, or None."""
    specs = list(args.get("points") or [])
    bones = [b.name for b in armature.pose.bones]
    empties = sorted(o.name for o in bpy.data.objects if o.type == "EMPTY")
    missing = [s["target"] for s in specs if s["target"] not in bones and s["target"] not in empties]
    if not missing:
        return None
    return {"points_unknown": missing, "bones": bones, "empties": empties}


def posed_places(args: dict, armature) -> list:
    """Each point's place in the current pose, in world space: [(name, Vector)]. A bone gives its head; an Empty its own place."""
    graph = bpy.context.evaluated_depsgraph_get()
    found = []
    for spec in args.get("points") or []:
        bone = armature.pose.bones.get(spec["target"])
        if bone is not None:
            found.append((spec["name"], armature.matrix_world @ bone.head))
        else:
            found.append((spec["name"], bpy.data.objects[spec["target"]].evaluated_get(graph).matrix_world.translation.copy()))
    return found


def seen_points(places: list, camera, args: dict) -> dict:
    """Where each posed point lands in the frame: `{name: {"x", "y", "depth"}}` in px and Blender units."""
    scene = bpy.context.scene
    width, height = args["frame"]
    axes = np.array(camera.matrix_world.to_3x3(), dtype=np.float64)
    eye_point = np.array(camera.matrix_world.translation, dtype=np.float64)
    found = {}
    for name, place in places:
        seen = world_to_camera_view(scene, camera, place)
        found[name] = {"x": round(seen.x * width, 3), "y": round((1.0 - seen.y) * height, 3),
                       "depth": round(float((eye_point - np.array(place)) @ axes[:, 2]), 4)}
    return found


def mark_hidden(found: dict, depth, mask, margin: float) -> None:
    """Adds `hidden` to each point: the pixel it falls on is the body, nearer than the point by more than `margin`."""
    rows, columns = mask.shape
    for point in found.values():
        column, row = math.floor(point["x"]), math.floor(point["y"])
        inside = 0 <= column < columns and 0 <= row < rows and bool(mask[row, column])
        point["hidden"] = bool(inside and float(depth[row, column]) < point["depth"] - margin)


def measure_poses(args: dict) -> dict:
    """Where every frame of every clip lands on screen, without rendering (ticket 0155), so that `render` can size one cell
    that holds every pose. Per clip, direction and frame: `bounds`, the mesh's extent [left, top, right, bottom] in px from
    the point the camera orbits (x right, y down), and `under`, the point under the root from that point, in px: the pivot
    `render` reports is the cell's pivot plus `under`. The camera is the render's own, so these are the frames' pixels."""
    armature, root_bone = open_posable(args)
    unknown = points_unknown(args, armature)
    if unknown:
        return unknown
    setup = set_up_scene(args, armature, root_bone)
    ground, turntable, camera = setup["ground"], setup["turntable"], setup["camera"]
    scale = float(args["px_per_unit"])
    directions = args["directions"]
    total = sum(len(c["frames"]) for c in args["clips"]) * len(directions)
    done = 0
    found: dict = {}
    for clip in args["clips"]:
        state = begin_clip(armature, clip, root_bone, ground)
        found[clip["name"]] = {d["name"]: [] for d in directions}
        for frame in clip["frames"]:
            pose_clip(armature, clip, state, frame)
            points = posed_points()
            head = armature.matrix_world @ armature.pose.bones[root_bone].head
            under = Vector((head.x, head.y, 0.0))
            centre = under if clip.get("root_motion", False) else ground
            turntable.location = centre
            offsets = points - np.array(centre)
            for direction in directions:
                progress(done, total, f"measuring {clip['name']} {direction['name']}")
                turntable.rotation_euler.z = -math.radians(float(direction["yaw"]))
                bpy.context.view_layer.update()
                axes = np.array(camera.matrix_world.to_3x3(), dtype=np.float64)
                xs, ys = offsets @ axes[:, 0] * scale, -(offsets @ axes[:, 1]) * scale
                root = np.array(under - centre)
                found[clip["name"]][direction["name"]].append({
                    "bounds": [round(float(xs.min()), 3), round(float(ys.min()), 3),
                               round(float(xs.max()), 3), round(float(ys.max()), 3)],
                    "under": [round(float(root @ axes[:, 0] * scale), 3), round(float(-(root @ axes[:, 1]) * scale), 3)]})
                done += 1
        end_clip(armature, state)
    progress(total, total, "done")
    return {"frames": found}


def render(args: dict) -> dict:
    if args.get("measure"):
        return measure_poses(args)
    armature, root_bone = open_posable(args)
    unknown = points_unknown(args, armature)
    if unknown:
        return unknown

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
    groups = eye_groups(list(args.get("eyes") or []), ground)
    for clip in args["clips"]:
        state = begin_clip(armature, clip, root_bone, ground)
        pivots[clip["name"]] = {d["name"]: [] for d in directions}
        for index, frame in enumerate(clip["frames"]):
            pose_clip(armature, clip, state, frame)
            eyes = posed_eyes(groups)
            places = posed_places(args, armature)
            head = armature.matrix_world @ armature.pose.bones[root_bone].head
            under = Vector((head.x, head.y, 0.0))
            follow = clip.get("root_motion", False)
            turntable.location = under if follow else ground
            for direction in directions:
                progress(done, total, f"{clip['name']} {direction['name']} {index + 1}/{len(clip['frames'])}")
                turntable.rotation_euler.z = -math.radians(float(direction["yaw"]))
                bpy.context.view_layer.update()
                seen = world_to_camera_view(scene, camera, under)
                placed: dict = {"pivot": [round(seen.x * args["frame"][0], 3), round((1.0 - seen.y) * args["frame"][1], 3)]}
                if groups:
                    placed["eyes"] = seen_eyes(eyes, camera, args)
                if places:
                    placed["points"] = seen_points(places, camera, args)
                pivots[clip["name"]][direction["name"]].append(placed)
                bpy.ops.render.render(write_still=True)
                depth, mask = write_frame(output, clip["name"], direction["name"], index, exr, camera, depth_range, args["toon"])
                if places:
                    mark_hidden(placed["points"], depth, mask, HIDDEN_MARGIN * float(args["model_height"]))
                done += 1
        end_clip(armature, state)
    shutil.rmtree(scratch, ignore_errors=True)
    progress(total, total, "done")
    return {"device": device, "depth_range": [round(depth_range[0], 4), round(depth_range[1], 4)],
            "materials": setup["materials"], "frames": pivots}


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
