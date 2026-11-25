"""Trial 0383, part 1: render the body of a character unlit from four flat orthographic views, for GPT Image to paint and for
`project_views.py` to project back. Prototype (not Kiripix code); run inside Blender, headless:

    blender -b -P render_views.py -- <args.json> <result.json>

args:   {"model": <a .blend; opened, never saved>, "out": <folder>, "views": ["front", "back", "left", "right", ...],
         "canvas": [1024, 1536] (width, height, px), "height_px": 1024 (the Model's height on the canvas), "background": [r, g, b],
         "supersample": 3, "prefix": "" (filename prefix), "uv": <a UV layer, for the UV pass and a texture>,
         "texture": <a PNG on that UV layer, replacing the Diffuse Color of every material but the eyes> or "const:r,g,b",
         "eyes": "eyes" (the eyes' material, left as it is), "analyse": true (the mesh report in the result),
         "selftest": true (checks the colour path, see below)}

Unlit: no light, no world light; every material's Surface is an Emission of the colour the material has as its Diffuse Color
(its base colour times the vertex colours, or the texture's), strength 1, and the view transform is Standard, so a pixel is
the sRGB byte of that colour. Cycles at 1 sample with the box filter 0.01 wide: every pass is its pixel centre's value, no
anti-aliasing and no filtering (the texture is read with Closest). The colour PNG for GPT Image is rendered at `supersample` times
the size and averaged down, so its edge is anti-aliased and its inside is exact; the passes are the 1x render.

Per view `<prefix><view>_...`: color.png (RGB, anti-aliased, on the background), color_exact.png (RGBA, 1x, no AA, alpha is the
mask), mask.png (0 or 255), uv.png (RGB 16-bit: u, v, 0; 0 outside the silhouette), depth.png (16-bit: 0 at depth_range[0], 65535
at [1] and outside; distance along the view axis in Blender units), normal.png (RGBA: camera-space (v + 1) / 2 * 255, X right, Y
up, Z toward the camera), material.png (8-bit: slot index + 1, 0 outside), `<prefix><view>.npz` (float depth, uv, normal, material,
mask and the exact colour bytes, for projection). `<prefix>camera.json` holds the cameras: a point P in the world is at
rel = P - location; px = width / 2 + (rel . right) * px_per_unit; py = height / 2 - (rel . up) * px_per_unit (continuous, pixel i spans
[i, i + 1)); depth = rel . forward.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpycommon as bc  # noqa: E402

DISTANCE = 12.0


def convert_to_emission(eyes: str, texture: dict | None) -> None:
    """Every material's Surface becomes an Emission of its base colour (or the texture)."""
    for material in bpy.data.materials:
        tree = material.node_tree
        if tree is None:
            continue
        output = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL")
        principled = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        emission = tree.nodes.new("ShaderNodeEmission")
        emission.inputs["Strength"].default_value = 1.0
        base = principled.inputs["Base Color"]
        if texture is not None and material.name != eyes:
            coords = tree.nodes.new("ShaderNodeUVMap")
            coords.uv_map = texture["uv"]
            image_node = tree.nodes.new("ShaderNodeTexImage")
            image_node.image = texture["image"]
            image_node.interpolation = "Closest"
            image_node.extension = "EXTEND"
            tree.links.new(coords.outputs["UV"], image_node.inputs["Vector"])
            tree.links.new(image_node.outputs["Color"], emission.inputs["Color"])
        elif base.links:
            tree.links.new(base.links[0].from_socket, emission.inputs["Color"])
        else:
            emission.inputs["Color"].default_value = base.default_value
        for link in list(output.inputs["Surface"].links):
            tree.links.remove(link)
        tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])


def make_texture(spec: str, uv: str) -> dict:
    if spec.startswith("const:"):
        r, g, b = (int(v) for v in spec[6:].split(","))
        image = bpy.data.images.new("kpx_const", 8, 8, alpha=False)
        image.pixels = [r / 255.0, g / 255.0, b / 255.0, 1.0] * 64  # float pixels are linear for an sRGB image
        image.colorspace_settings.name = "Non-Color"
        # Non-Color holds the values as given; the bytes are what matters for the sampling, so go through a file
        path = Path(bpy.app.tempdir) / "const.png"
        bc.png(path, np.tile(np.array([r, g, b, 255], np.uint8), (8, 8, 1)), "rgba")
        bpy.data.images.remove(image)
        spec = str(path)
    image = bpy.data.images.load(spec, check_existing=False)
    image.colorspace_settings.name = "sRGB"
    image.alpha_mode = "CHANNEL_PACKED"
    return {"image": image, "uv": uv}


def set_up_scene(width: int, height: int):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.use_persistent_data = False
    scene.render.use_file_extension = False
    scene.render.image_settings.media_type = "MULTI_LAYER_IMAGE"
    scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "NONE"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.display_settings.display_device = "sRGB"
    scene.sequencer_colorspace_settings.name = "sRGB"
    cycles = scene.cycles
    cycles.samples = 1
    cycles.use_adaptive_sampling = False
    cycles.use_denoising = False
    cycles.pixel_filter_type = "BOX"
    cycles.filter_width = 0.01
    cycles.seed = 0
    cycles.use_animated_seed = False
    cycles.max_bounces = 0
    scene.world = bpy.data.worlds.new("kpx_black") if scene.world is None else scene.world
    scene.world.use_nodes = False
    scene.world.color = (0, 0, 0)
    data = bpy.data.cameras.new("kpx_camera")
    data.type = "ORTHO"
    data.clip_start, data.clip_end = 0.1, 100.0
    data.sensor_fit = "AUTO"
    camera = bpy.data.objects.new("kpx_camera", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return scene, camera


def place_camera(camera, centre: Vector, yaw: float, pitch: float, ppu: float, size: tuple):
    y, p = math.radians(yaw), math.radians(pitch)
    offset = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p))) * DISTANCE
    camera.location = centre + offset
    camera.rotation_euler = (-offset).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = max(size) / ppu
    bpy.context.view_layer.update()
    m = camera.matrix_world
    return {
        "yaw": yaw, "pitch": pitch,
        "location": [round(v, 6) for v in m.translation],
        "right": [round(v, 9) for v in m.col[0][:3]], "up": [round(v, 9) for v in m.col[1][:3]],
        "forward": [round(-v, 9) for v in m.col[2][:3]],
        "ortho_scale": camera.data.ortho_scale,
    }


def render_to(scene, path: Path, size: tuple, passes: bool) -> dict:
    scene.render.resolution_x, scene.render.resolution_y = size
    layer = bpy.context.view_layer
    layer.use_pass_z = layer.use_pass_normal = layer.use_pass_uv = passes
    layer.use_pass_object_index = layer.use_pass_material_index = passes
    layer.use_pass_diffuse_color = False
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return bc.read_exr(path)


def view_arrays(channels: dict) -> dict:
    alpha = bc.channel(channels, ".Combined.A")
    colour = np.stack([bc.channel(channels, f".Combined.{c}") for c in "RGB"], -1)
    out = {"alpha": alpha, "colour": colour}
    if "ViewLayer.Depth.Z" in channels or any(".Depth" in k for k in channels):
        out["depth"] = bc.channel(channels, ".Depth.Z")
        out["normal"] = np.stack([bc.channel(channels, f".Normal.{c}") for c in "XYZ"], -1)
        out["uv"] = np.stack([bc.channel(channels, f".UV.{c}") for c in "UV"], -1)
        out["material"] = bc.channel(channels, ".Material Index.X")
        out["object"] = bc.channel(channels, ".Object Index.X")
    return out


def analysis(obj, eyes: str) -> dict:
    me = obj.data
    report = {"mesh": obj.name, "vertices": len(me.vertices), "faces": len(me.polygons),
              "uv_layers": [], "active_render_uv": next((u.name for u in me.uv_layers if u.active_render), None),
              "colour_attributes": [a.name for a in me.color_attributes], "modifiers": [m.type for m in obj.modifiers],
              "materials": []}
    indices = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", indices)
    for slot, material in enumerate(m.material for m in obj.material_slots):
        tree = material.node_tree
        textures = [n.image.name for n in tree.nodes if n.type == "TEX_IMAGE" and n.image]
        principled = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
        report["materials"].append({
            "slot": slot, "name": material.name, "faces": int((indices == slot).sum()),
            "image_textures": textures, "flat_base_colour_linear": [round(v, 4) for v in material.diffuse_color[:3]],
            "base_colour_linked": bool(principled.inputs["Base Color"].links),
            "multiplied_by_vertex_colour": any(n.type == "VERTEX_COLOR" for n in tree.nodes)})
    report["images_in_file"] = [i.name for i in bpy.data.images if i.name != "Render Result"]
    for layer in me.uv_layers:
        report["uv_layers"].append(bc.analyse_uv(me, layer.name))
    return report


def main() -> None:
    args, result_path = bc.args_from_argv()
    out = Path(args["out"])
    out.mkdir(parents=True, exist_ok=True)
    width, height = args.get("canvas", [1024, 1536])
    background = np.array(args.get("background", [160, 160, 160]), np.float64)
    ss = int(args.get("supersample", 3))
    prefix = args.get("prefix", "")
    views = args.get("views", bc.PAINTED_VIEWS)
    eyes = args.get("eyes", "eyes")

    bpy.ops.wm.open_mainfile(filepath=str(args["model"]))  # never saved
    bc.rest_pose()
    obj = bc.body_object()
    for other in bpy.data.objects:
        other.hide_render = other is not obj
    result: dict = {"model": str(args["model"]), "canvas": [width, height]}
    if args.get("analyse"):
        result["analysis"] = analysis(obj, eyes)
        left_bone = next((b for b in bpy.data.objects["Armature"].data.bones if b.name.endswith("LeftArm")), None)
        if left_bone is not None:
            result["left_arm_bone_head_x"] = round(left_bone.head_local[0], 3)

    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    world = np.array([(obj.matrix_world @ v.co)[:] for v in mesh.vertices])
    low, high = world.min(0), world.max(0)
    evaluated.to_mesh_clear()
    model_height = float(high[2] - low[2])
    ppu = float(args.get("height_px", 1024)) / model_height
    centre = Vector(((low[0] + high[0]) / 2, (low[1] + high[1]) / 2, (low[2] + high[2]) / 2))
    result["model_bounds"] = {"min": [round(float(v), 5) for v in low], "max": [round(float(v), 5) for v in high]}

    texture = None
    if args.get("texture"):
        texture = make_texture(args["texture"], args["uv"])
    if args.get("uv"):
        bc.set_uv_active(obj.data, args["uv"])
    for slot, material in enumerate(m.material for m in obj.material_slots):
        material.pass_index = slot + 1
    obj.pass_index = 1

    scene, camera = set_up_scene(width, height)
    scene.render.use_persistent_data = False
    cameras = {}
    depth_range = [0.0, 0.0]

    if args.get("selftest"):
        result["selftest"] = selftest(scene, camera, obj, centre, ppu, (width, height), out, eyes)

    convert_to_emission(eyes, texture)
    bpy.context.view_layer.update()
    near, far = DISTANCE - 1.5, DISTANCE + 1.5
    depth_range = [near, far]
    for name in views:
        yaw, pitch = bc.VIEWS[name]
        cam = place_camera(camera, centre, yaw, pitch, ppu, (width, height))
        cam.update({"size": [width, height], "px_per_unit": ppu, "model_height": model_height})
        cameras[name] = cam
        exact = view_arrays(render_to(scene, out / "_pass.exr", (width, height), True))
        mask = exact["alpha"] > 0.5
        rgb = bc.srgb_encode(exact["colour"])
        rgb[~mask] = 0
        np.savez_compressed(out / f"{prefix}{name}.npz", depth=exact["depth"].astype(np.float32), uv=exact["uv"].astype(np.float32),
                            normal=exact["normal"].astype(np.float32), material=exact["material"].astype(np.uint8),
                            mask=mask, colour=rgb)
        bc.png(out / f"{prefix}{name}_color_exact.png", np.dstack([rgb, mask.astype(np.uint8) * 255]), "rgba")
        bc.png(out / f"{prefix}{name}_mask.png", mask.astype(np.uint8) * 255, "l8")
        uv16 = np.rint(np.clip(exact["uv"], 0, 1) * 65535).astype(np.uint16)
        uv16 = np.dstack([uv16, np.zeros(mask.shape, np.uint16)])
        uv16[~mask] = 0
        bc.png(out / f"{prefix}{name}_uv.png", uv16, "rgb16")
        depth = np.where(mask, (exact["depth"] - near) / (far - near), 1.0)
        bc.png(out / f"{prefix}{name}_depth.png", np.rint(np.clip(depth, 0, 1) * 65535).astype(np.uint16), "l16")
        normal = np.rint((np.clip(exact["normal"], -1, 1) + 1) / 2 * 255).astype(np.uint8)
        # Cycles' Normal pass is in world space; turn it into camera space (X right, Y up, Z toward the camera)
        right, up, forward = (np.array(cam[k]) for k in ("right", "up", "forward"))
        w = exact["normal"]
        cs = np.stack([w @ right, w @ up, -(w @ forward)], -1)
        normal = np.rint((np.clip(cs, -1, 1) + 1) / 2 * 255).astype(np.uint8)
        normal[~mask] = 128
        bc.png(out / f"{prefix}{name}_normal.png", np.dstack([normal, mask.astype(np.uint8) * 255]), "rgba")
        bc.png(out / f"{prefix}{name}_material.png", np.where(mask, exact["material"], 0).astype(np.uint8), "l8")
        # the anti-aliased colour: ss x ss exact samples per pixel, averaged in sRGB, over the background
        big = view_arrays(render_to(scene, out / "_big.exr", (width * ss, height * ss), False))
        sub_mask = big["alpha"] > 0.5
        sub = bc.srgb_encode(big["colour"]).astype(np.float64)
        sub[~sub_mask] = 0
        count = sub_mask.reshape(height, ss, width, ss).sum((1, 3)).astype(np.float64)
        summed = sub.reshape(height, ss, width, ss, 3).sum((1, 3))
        average = np.where(count[..., None] > 0, summed / np.maximum(count[..., None], 1), 0)
        cover = count / (ss * ss)
        final = average * cover[..., None] + background * (1 - cover[..., None])
        bc.png(out / f"{prefix}{name}_color.png", np.clip(np.rint(final), 0, 255).astype(np.uint8), "rgb")
        result.setdefault("views", {})[name] = {
            "mask_pixels": int(mask.sum()),
            "bbox": [int(v) for v in (np.where(mask.any(0))[0][[0, -1]].tolist() + np.where(mask.any(1))[0][[0, -1]].tolist())],
            "depth_min_max": [round(float(exact["depth"][mask].min()), 4), round(float(exact["depth"][mask].max()), 4)],
            "distinct_colours": int(len(np.unique(rgb[mask].reshape(-1, 3), axis=0))),
        }
    (out / "_pass.exr").unlink(missing_ok=True)
    (out / "_big.exr").unlink(missing_ok=True)
    (out / f"{prefix}camera.json").write_text(json.dumps({
        "canvas": [width, height], "px_per_unit": ppu, "depth_range": depth_range, "background": background.tolist(),
        "projection": "rel = P - location; px = width / 2 + (rel . right) * px_per_unit; py = height / 2 - (rel . up) * px_per_unit;"
                      " depth = rel . forward; pixel i spans [i, i + 1)",
        "cameras": cameras}, indent=1))
    result["depth_range"] = depth_range
    result_path.write_text(json.dumps(result, indent=1))


def selftest(scene, camera, obj, centre, ppu, size, out, eyes) -> dict:
    """Is the unlit colour the colour the Model has, byte for byte? (1) Emission against the Diffuse Color pass of the
    untouched materials; (2) my sRGB bytes against the bytes Blender's own Standard view transform writes to a PNG."""
    width, height = size
    place_camera(camera, centre, 0.0, 0.0, ppu, size)
    scene.render.resolution_x, scene.render.resolution_y = size
    layer = bpy.context.view_layer
    layer.use_pass_diffuse_color = True
    layer.use_pass_material_index = True
    scene.render.dither_intensity = 0.0  # Blender dithers its 8-bit files by default
    scene.render.filepath = str(out / "_self.exr")
    bpy.ops.render.render(write_still=True)
    ch = bc.read_exr(out / "_self.exr")
    diff = np.stack([bc.channel(ch, f".Diffuse Color.{c}") for c in "RGB"], -1)
    mask = bc.channel(ch, ".Combined.A") > 0.5
    layer.use_pass_diffuse_color = False
    convert_to_emission(eyes, None)
    scene.render.filepath = str(out / "_self2.exr")
    bpy.ops.render.render(write_still=True)
    ch2 = bc.read_exr(out / "_self2.exr")
    emission = np.stack([bc.channel(ch2, f".Combined.{c}") for c in "RGB"], -1)
    delta = np.abs(diff - emission).max(-1)
    materials_id = bc.channel(ch, ".Material Index.X")
    by_material = {int(i): {"max": round(float(delta[mask & (materials_id == i)].max()), 5),
                            "mean": round(float(delta[mask & (materials_id == i)].mean()), 6)}
                   for i in np.unique(materials_id[mask])}
    diff_error = float(delta[mask].max())
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(out / "_self.png")
    bpy.ops.render.render(write_still=True)
    blender_bytes = bc.load_rgba(out / "_self.png")
    mine = bc.srgb_encode(emission)
    byte_error = np.abs(blender_bytes[..., :3].astype(int)[mask] - mine.astype(int)[mask])
    scene.render.image_settings.media_type = "MULTI_LAYER_IMAGE"
    scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "NONE"
    for name in ("_self.exr", "_self2.exr", "_self.png"):
        (out / name).unlink(missing_ok=True)
    # the materials are now Emission already; convert_to_emission will run again in main and finds no Principled link to read
    return {"emission_vs_diffuse_color_pass_max_abs_linear": diff_error, "by_material_slot_plus_1": by_material,
            "own_srgb_vs_blender_png_max_abs_byte": int(byte_error.max()),
            "own_srgb_vs_blender_png_differing_pixels": int((byte_error.max(1) > 0).sum()),
            "pixels_compared": int(mask.sum())}


main()
