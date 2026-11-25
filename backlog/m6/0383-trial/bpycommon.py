"""Trial 0383 helpers for the bpy scripts (run inside Blender, which has numpy but no PIL). Prototype, not Kiripix code.

PNG writing and the uncompressed-EXR reader are the ones of `kiripix/blender/render_frames.py`, copied so this folder stands alone.
"""
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import bpy
import numpy as np

# The views. Yaw: degrees the camera goes round the Model; 0 is in front of the face (the Model faces -Y), and 90 is at the
# Model's left (+X). `pitch` degrees looks down. The first four are the ones that are painted and projected; the others are
# only for looking at a result.
VIEWS = {
    "front": (0.0, 0.0), "left": (90.0, 0.0), "back": (180.0, 0.0), "right": (270.0, 0.0),
    "q45": (45.0, 0.0), "q135": (135.0, 0.0), "q225": (225.0, 0.0), "q315": (315.0, 0.0), "top": (0.0, 89.9),
}
PAINTED_VIEWS = ["front", "back", "left", "right"]
BODY = "mc_f_base_a"


def png(path: Path, array: np.ndarray, kind: str) -> None:
    """kind: rgba (h, w, 4) uint8, rgb (h, w, 3) uint8, l8 (h, w) uint8, l16 (h, w), rgb16 (h, w, 3) uint16."""
    height, width = array.shape[:2]
    if kind == "rgba":
        colour_type, depth, rows = 6, 8, array.astype(np.uint8).reshape(height, width * 4)
    elif kind == "rgb":
        colour_type, depth, rows = 2, 8, array.astype(np.uint8).reshape(height, width * 3)
    elif kind == "l8":
        colour_type, depth, rows = 0, 8, array.astype(np.uint8)
    elif kind == "rgb16":
        colour_type, depth = 2, 16
        rows = array.astype(">u2").view(np.uint8).reshape(height, width * 6)
    else:
        colour_type, depth = 0, 16
        rows = array.astype(">u2").view(np.uint8).reshape(height, width * 2)
    raw = np.zeros((height, rows.shape[1] + 1), dtype=np.uint8)
    raw[:, 1:] = rows

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, depth, colour_type, 0, 0, 0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw.tobytes(), 6))
                     + chunk(b"IEND", b""))


def read_exr(path: Path) -> dict:
    data = Path(path).read_bytes()
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
    raise KeyError(f"no channel ending {suffixes}; have {sorted(channels)}")


def srgb_encode(linear: np.ndarray) -> np.ndarray:
    """Linear 0..1 to sRGB bytes, as the Standard view transform does (clip, then the sRGB curve)."""
    c = np.clip(linear, 0.0, 1.0).astype(np.float64)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    return np.clip(np.rint(s * 255.0), 0, 255).astype(np.uint8)


def srgb_decode(byte: np.ndarray) -> np.ndarray:
    c = byte.astype(np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4))


def load_rgba(path: Path) -> np.ndarray:
    """An 8-bit PNG as (h, w, 4) uint8, the top row first, through Blender's loader (Non-Color, straight alpha, so the bytes
    are the file's)."""
    image = bpy.data.images.load(str(path), check_existing=False)
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    width, height = image.size
    flat = np.empty(width * height * 4, np.float32)
    image.pixels.foreach_get(flat)
    bpy.data.images.remove(image)
    return np.rint(flat.reshape(height, width, 4)[::-1] * 255.0).astype(np.uint8)


def set_uv_active(me, name: str) -> None:
    for index, layer in enumerate(me.uv_layers):
        if layer.name == name:
            me.uv_layers.active_index = index
            layer.active_render = True
            return
    raise KeyError(f"the mesh has no UV layer {name}; it has {[u.name for u in me.uv_layers]}")


def uv_loops(me, name: str) -> np.ndarray:
    layer = me.uv_layers[name]
    flat = np.empty(len(me.loops) * 2, np.float32)
    try:
        layer.data.foreach_get("vector", flat)
    except (RuntimeError, AttributeError, TypeError):
        layer.data.foreach_get("uv", flat)
    return flat.reshape(-1, 2)


def triangles(me) -> dict:
    """The loop triangles: loops (T, 3), vertices (T, 3), polygon (T,)."""
    me.calc_loop_triangles()
    count = len(me.loop_triangles)
    loops = np.empty(count * 3, np.int32)
    verts = np.empty(count * 3, np.int32)
    poly = np.empty(count, np.int32)
    me.loop_triangles.foreach_get("loops", loops)
    me.loop_triangles.foreach_get("vertices", verts)
    me.loop_triangles.foreach_get("polygon_index", poly)
    return {"loops": loops.reshape(-1, 3), "vertices": verts.reshape(-1, 3), "polygon": poly}


def rasterise(uv: np.ndarray, tri_loops: np.ndarray, size: int):
    """Texel centres inside each UV triangle. Returns (tri (size, size) int32, -1 where none; bary (size, size, 3) float32;
    count (size, size) uint8: how many triangles cover the texel; sign (size, size) uint8: bit 0 a counter-clockwise (v up)
    triangle covers it, bit 1 a clockwise one). Row 0 is v = 1 (the top), as an image is."""
    tri = np.full((size, size), -1, np.int32)
    bary = np.zeros((size, size, 3), np.float32)
    count = np.zeros((size, size), np.uint8)
    sign = np.zeros((size, size), np.uint8)
    a_all = uv[tri_loops[:, 0]] * size
    b_all = uv[tri_loops[:, 1]] * size
    c_all = uv[tri_loops[:, 2]] * size
    for t in range(len(tri_loops)):
        a, b, c = a_all[t], b_all[t], c_all[t]
        # image coordinates: x = u * size, y = (1 - v) * size
        ax, ay, bx, by, cx, cy = a[0], size - a[1], b[0], size - b[1], c[0], size - c[1]
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        x0 = max(int(math.floor(min(ax, bx, cx) - 0.5)), 0)
        x1 = min(int(math.ceil(max(ax, bx, cx) - 0.5)), size - 1)
        y0 = max(int(math.floor(min(ay, by, cy) - 0.5)), 0)
        y1 = min(int(math.ceil(max(ay, by, cy) - 0.5)), size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = np.arange(y0, y1 + 1) + 0.5
        px, py = np.meshgrid(xs, ys)
        w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
        w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
        w2 = 1.0 - w0 - w1
        eps = -1e-6
        inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if not inside.any():
            continue
        window = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        tri[window][inside] = t
        bary[window][inside] = np.stack([w0, w1, w2], -1)[inside]
        count[window][inside] += 1
        # image y runs down, so a counter-clockwise triangle in (u, v) has a negative det here
        sign[window][inside] |= 1 if det < 0 else 2
    return tri, bary, count, sign


def analyse_uv(me, name: str, size: int = 1024) -> dict:
    uv = uv_loops(me, name)
    tris = triangles(me)
    tri, _, count, sign = rasterise(uv, tris["loops"], size)
    covered = count > 0
    a, b, c = (uv[tris["loops"][:, i]] for i in range(3))
    area = 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    return {
        "layer": name,
        "u_range": [round(float(uv[:, 0].min()), 3), round(float(uv[:, 0].max()), 3)],
        "v_range": [round(float(uv[:, 1].min()), 3), round(float(uv[:, 1].max()), 3)],
        "uv_space_used": round(float(covered.mean()), 4),
        "texels_covered_by_2_or_more_triangles": round(float((count > 1).sum() / max(covered.sum(), 1)), 4),
        "texels_covered_by_both_winding_senses": round(float((sign == 3).sum() / max(covered.sum(), 1)), 4),
        "triangles_counter_clockwise": int((area > 0).sum()),
        "triangles_clockwise": int((area < 0).sum()),
        "triangles_without_area": int((area == 0).sum()),
    }


def body_object():
    obj = bpy.data.objects.get(BODY)
    if obj is None:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        obj = max(meshes, key=lambda o: len(o.data.vertices))
    return obj


def rest_pose() -> None:
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            obj.data.pose_position = "REST"
            if obj.animation_data:
                obj.animation_data.action = None
    bpy.context.view_layer.update()


def args_from_argv():
    argv = sys.argv[sys.argv.index("--") + 1:]
    return json.loads(Path(argv[0]).read_text()), Path(argv[1])
