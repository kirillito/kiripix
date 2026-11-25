"""Trial 0383, part 1: project painted views of a character back onto its UV texture. Prototype (not Kiripix code); run inside Blender:

    blender -b -P project_views.py -- <args.json> <result.json>

args:   {"model": <a .blend; opened, never saved in place>, "views_dir": <the folder render_views.py wrote: `<view>.npz` and `camera.json`>,
         "painted": {"front": <a PNG>, ...} (any subset of front, back, left, right; each at the canvas size of the views, aligned to the
                    render: use measure_drift.py --write-aligned to bring a repaint that isn't),
         "out": <folder>, "uv_size": 2048, "unwrap": true (a fresh unwrap `uv_layer` by Smart UV Project) or false (use `uv_layer` as it is),
         "uv_layer": "kpx_paint", "erode": 2 (px the silhouette is shrunk by, so no background colour is picked up),
         "sharpness": 8 (a view's weight is cos^sharpness: the view facing most squarely wins, equal views blend at the seam),
         "cos_min": 0.2 (a texel no view sees at least this squarely is filled), "fill_voxel": 0.02 (Model units),
         "pad": 8 (texels the islands are grown by), "name": "texture" (file stem), "save_model": true}

Per texel: its place and normal on the Model (rest pose) are rasterised from the UV layer; each view is asked: is the texel inside the
shrunk silhouette, is its depth the depth pass's there (so not hidden), how squarely does it face the camera (cos)? The painted colour
(bilinear) is averaged with the weights cos^sharpness. Texels no view sees at cos >= cos_min are filled: from the nearest squarely seen
texels of the same material in 3D (voxel growing), so an armpit takes its arm's colour, not the chest's. Outside the islands the colour
is grown by `pad` texels.

Files in `out`: <name>.png (RGB, the texture), <name>_coverage.png (false colour: 0 unused, red filled, orange grazing, yellow oblique,
green squarely seen), <name>_winner.png (which view won: front red, back blue, left green, right yellow, blended texels white),
<name>_layout.png (the UV layout: island edges), `model_uv.blend` (a copy of the Model with the UV layer; the original is untouched),
<name>_stats.json (shares by surface area and by texel; per view).
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpycommon as bc  # noqa: E402

VIEW_COLOURS = {"front": (230, 40, 40), "back": (50, 80, 230), "left": (40, 190, 60), "right": (240, 220, 40)}


def unwrap(obj, name: str) -> None:
    me = obj.data
    if name in me.uv_layers:
        me.uv_layers.remove(me.uv_layers[name])
    layer = me.uv_layers.new(name=name)
    me.uv_layers.active = layer
    layer.active_render = True
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.004, area_weight=0.0, correct_aspect=True,
                             scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def erode(mask: np.ndarray, count: int) -> np.ndarray:
    out = mask.copy()
    for _ in range(count):
        p = np.pad(out, 1, constant_values=False)
        out = out & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return out


def bilinear(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """image (h, w, 3) float; x, y continuous with pixel centres at i + 0.5."""
    h, w = image.shape[:2]
    fx, fy = x - 0.5, y - 0.5
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    tx, ty = (fx - x0)[:, None], (fy - y0)[:, None]
    x0c, x1c = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
    y0c, y1c = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
    top = image[y0c, x0c] * (1 - tx) + image[y0c, x1c] * tx
    bottom = image[y1c, x0c] * (1 - tx) + image[y1c, x1c] * tx
    return top * (1 - ty) + bottom * ty


def texel_geometry(obj, uv_layer: str, size: int) -> dict:
    graph = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(graph)
    me = ev.to_mesh()
    tris = bc.triangles(me)
    uv = bc.uv_loops(me, uv_layer)
    tri, bary, count, _ = bc.rasterise(uv, tris["loops"], size)
    matrix = np.array(obj.matrix_world)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    world = co @ matrix[:3, :3].T + matrix[:3, 3]
    normals = np.empty(len(me.corner_normals) * 3, np.float32)
    me.corner_normals.foreach_get("vector", normals)
    normals = normals.reshape(-1, 3) @ np.linalg.inv(matrix[:3, :3])  # inverse transpose for the normal matrix
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    materials = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", materials)
    names = [s.material.name for s in obj.material_slots]
    covered = tri >= 0
    t = tri[covered]
    b = bary[covered]
    loops = tris["loops"][t]
    verts = tris["vertices"][t]
    position = np.einsum("nk,nkj->nj", b, world[verts]).astype(np.float64)
    normal = np.einsum("nk,nkj->nj", b, normals[loops]).astype(np.float64)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    material = materials[tris["polygon"][t]]
    # world area per texel: the triangle's area in 3D over its area in texels
    area3 = 0.5 * np.linalg.norm(np.cross(world[tris["vertices"][:, 1]] - world[tris["vertices"][:, 0]],
                                          world[tris["vertices"][:, 2]] - world[tris["vertices"][:, 0]]), axis=1)
    a, b2, c = (uv[tris["loops"][:, i]] * size for i in range(3))
    area_uv = 0.5 * np.abs((b2[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b2[:, 1] - a[:, 1]))
    per_tri = area3 / np.maximum(area_uv, 1e-9)
    ev.to_mesh_clear()
    return {"covered": covered, "position": position, "normal": normal, "material": material, "names": names,
            "texel_area": per_tri[t], "overlap_texels": int((count > 1).sum()), "uv": uv, "tris": tris}


def grow(colour: np.ndarray, known: np.ndarray, steps: int) -> np.ndarray:
    """Grow the known texels' colour outward by `steps` texels (mean of the known 8-neighbours)."""
    colour = colour.copy()
    known = known.copy()
    for _ in range(steps):
        pc = np.pad(colour * known[..., None], ((1, 1), (1, 1), (0, 0)))
        pk = np.pad(known.astype(np.float64), 1)
        total = np.zeros_like(colour)
        number = np.zeros(known.shape)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                total += pc[1 + dy:pc.shape[0] - 1 + dy, 1 + dx:pc.shape[1] - 1 + dx]
                number += pk[1 + dy:pk.shape[0] - 1 + dy, 1 + dx:pk.shape[1] - 1 + dx]
        new = (~known) & (number > 0)
        colour[new] = total[new] / number[new][:, None]
        known = known | new
    return colour


def voxel_fill(position, material, colour, source, target, voxel, max_radius=20):
    """For the `target` texels, the mean colour of the nearest `source` texels of the same material in 3D (a voxel grid per
    material, growing the box until it holds some). Returns (colour (n, 3), found (n,))."""
    out = np.zeros((target.sum(), 3))
    found = np.zeros(target.sum(), bool)
    target_index = np.flatnonzero(target)
    lo = position.min(0) - 1e-6
    dims = np.ceil((position.max(0) - lo) / voxel).astype(int) + 1
    cell = np.floor((position - lo) / voxel).astype(int)
    for m in np.unique(material[target]):
        src = source & (material == m)
        if not src.any():
            continue
        flat = np.ravel_multi_index(cell[src].T, dims)
        sums = np.zeros((dims.prod(), 3))
        counts = np.zeros(dims.prod())
        np.add.at(counts, flat, 1.0)
        for ch in range(3):
            sums[:, ch] = np.bincount(flat, colour[src][:, ch], minlength=dims.prod())
        sums, counts = sums.reshape(*dims, 3), counts.reshape(dims)
        wanted = target & (material == m)
        pick = np.flatnonzero(wanted[target_index])
        tcell = cell[target][pick]
        remaining = np.ones(len(pick), bool)
        for r in range(0, max_radius + 1):
            box_s = box_sum(sums, r)
            box_c = box_sum(counts[..., None], r)[..., 0]
            c = box_c[tcell[:, 0], tcell[:, 1], tcell[:, 2]]
            hit = remaining & (c > 0)
            if hit.any():
                s = box_s[tcell[hit, 0], tcell[hit, 1], tcell[hit, 2]]
                out[pick[hit]] = s / c[hit][:, None]
                found[pick[hit]] = True
                remaining &= ~hit
            if not remaining.any():
                break
    return out, found


def box_sum(a: np.ndarray, r: int) -> np.ndarray:
    if r == 0:
        return a
    out = a
    for axis in range(3):
        c = np.cumsum(out, axis=axis)
        pad = [(0, 0)] * out.ndim
        pad[axis] = (r + 1, r)
        c = np.pad(c, pad, mode="edge")
        # c[i + r + 1 + ... ] : window sum over [i - r, i + r]
        n = out.shape[axis]
        hi = np.take(c, np.arange(n) + 2 * r + 1, axis=axis)
        lo = np.take(c, np.arange(n), axis=axis)
        out = hi - lo
    return out


def main() -> None:
    args, result_path = bc.args_from_argv()
    out = Path(args["out"])
    out.mkdir(parents=True, exist_ok=True)
    size = int(args.get("uv_size", 2048))
    layer = args.get("uv_layer", "kpx_paint")
    name = args.get("name", "texture")
    sharp = float(args.get("sharpness", 8))
    cos_min = float(args.get("cos_min", 0.2))
    views_dir = Path(args["views_dir"])
    cameras = json.loads((views_dir / "camera.json").read_text())
    ppu = cameras["px_per_unit"]

    bpy.ops.wm.open_mainfile(filepath=str(args["model"]))
    bc.rest_pose()
    obj = bc.body_object()
    if args.get("unwrap", True):
        unwrap(obj, layer)
    geo = texel_geometry(obj, layer, size)
    covered = geo["covered"]
    position, normal, material, area = geo["position"], geo["normal"], geo["material"], geo["texel_area"]
    n = len(position)
    names = geo["names"]
    stats: dict = {"uv_layer": layer, "uv_size": size, "texels_used": int(n), "uv_space_used": round(n / size / size, 4),
                   "texels_covered_by_2_or_more_triangles": geo["overlap_texels"],
                   "surface_area_total_m2": float(area.sum()), "views": {}}

    painted = args["painted"]
    sums = np.zeros((n, 3))
    wsum = np.zeros(n)
    best = np.zeros(n)
    best_view = np.full(n, -1)
    second = np.zeros(n)
    view_names = list(painted)
    usable = {}
    for index, view in enumerate(view_names):
        cam = cameras["cameras"][view]
        data = np.load(views_dir / f"{view}.npz")
        height, width = data["mask"].shape
        image = bc.load_rgba(Path(painted[view]))
        if image.shape[:2] != (height, width):
            raise SystemExit(f"{painted[view]} is {image.shape[1]}x{image.shape[0]}, the view is {width}x{height}; align it first")
        rgb = image[..., :3].astype(np.float64)
        inner = erode(data["mask"], int(args.get("erode", 2)))
        right, up, forward = (np.array(cam[k]) for k in ("right", "up", "forward"))
        rel = position - np.array(cam["location"])
        px = width / 2 + (rel @ right) * ppu
        py = height / 2 - (rel @ up) * ppu
        depth = rel @ forward
        ix, iy = np.floor(px).astype(int), np.floor(py).astype(int)
        inside = (ix >= 0) & (ix < width) & (iy >= 0) & (iy < height)
        ixc, iyc = np.clip(ix, 0, width - 1), np.clip(iy, 0, height - 1)
        cos = -(normal @ forward)
        tan = np.sqrt(np.clip(1 - cos * cos, 0, 1)) / np.maximum(cos, 1e-3)
        tol = 0.003 + np.minimum(tan, 6.0) / ppu
        seen = inside & inner[iyc, ixc] & (np.abs(data["depth"][iyc, ixc] - depth) <= tol) & (cos > 0.02)
        weight = np.where(seen, np.power(np.maximum(cos, 0), sharp), 0.0)
        colour = np.zeros((n, 3))
        if seen.any():
            colour[seen] = bilinear(rgb, px[seen], py[seen])
        sums += colour * weight[:, None]
        wsum += weight
        usable[view] = np.where(seen, cos, 0.0)
        new_best = weight > best
        second = np.where(new_best, best, np.maximum(second, weight))
        best_view = np.where(new_best, index, best_view)
        best = np.where(new_best, weight, best)
    cos_all = np.stack([usable[v] for v in view_names], 0)
    max_cos = cos_all.max(0)
    texel = np.where(wsum[:, None] > 0, sums / np.maximum(wsum, 1e-300)[:, None], 0.0)
    good = max_cos >= cos_min
    tier = np.zeros(n, np.int8)  # 0 unseen, 1 grazing (seen below cos_min), 2 oblique, 3 squarely
    tier[max_cos > 0.02] = 1
    tier[max_cos >= cos_min] = 2
    tier[max_cos >= 0.5] = 3

    fill = ~good
    filled_colour = np.zeros((int(fill.sum()), 3))
    found = np.zeros(int(fill.sum()), bool)
    if fill.any() and good.any():
        filled_colour, found = voxel_fill(position, material, texel, good, fill, float(args.get("fill_voxel", 0.02)))
    leftover = 0
    if fill.any():
        idx = np.flatnonzero(fill)
        texel[idx[found]] = filled_colour[found]
        for i in idx[~found]:
            pass
        lost = idx[~found]
        leftover = int(len(lost))
        if leftover:
            for m in np.unique(material[lost]):
                pool = good & (material == m)
                mean = texel[pool].mean(0) if pool.any() else texel[good].mean(0) if good.any() else np.full(3, 128.0)
                texel[lost[material[lost] == m]] = mean

    # shares: by surface area, and by texel
    def share(mask) -> dict:
        return {"area_share": round(float(area[mask].sum() / area.sum()), 4), "texel_share": round(float(mask.mean()), 4)}

    stats["seen_squarely_cos>=0.5"] = share(tier == 3)
    stats["seen_obliquely_0.2<=cos<0.5"] = share(tier == 2)
    stats["filled_seen_only_grazing_0.02<cos<0.2"] = share(tier == 1)
    stats["filled_not_seen_at_all"] = share(tier == 0)
    stats["filled_total"] = share(fill)
    stats["filled_by_3d_neighbours_texels"] = int(found.sum())
    stats["filled_by_material_mean_texels"] = leftover
    for index, view in enumerate(view_names):
        c = cos_all[index]
        stats["views"][view] = {
            "usable (inside, not hidden, cos>=cos_min)": share(c >= cos_min),
            "squarely (cos>=0.5)": share(c >= 0.5),
            "wins (largest weight, among usable texels)": share(good & (best_view == index)),
            "blended with another at >=10% (the seam)": share(good & (best_view == index) & (second >= 0.1 * best)),
        }
    by_material = {}
    for m, mname in enumerate(names):
        sel = material == m
        if sel.any():
            by_material[mname] = {"area_share_of_model": round(float(area[sel].sum() / area.sum()), 4),
                                  "not_seen_squarely_area_share_within_material": round(float(area[sel & (tier < 3)].sum() / area[sel].sum()), 4),
                                  "filled_area_share_within_material": round(float(area[sel & fill].sum() / area[sel].sum()), 4)}
    stats["by_material"] = by_material

    # where the filled texels are on the body (world position of their area-weighted bounding boxes by height band)
    if fill.any():
        z = position[fill, 2]
        a = area[fill]
        bands = {"soles_and_feet (z<0.06)": z < 0.06, "legs (0.06-0.9)": (z >= 0.06) & (z < 0.9), "torso_and_arms (0.9-1.55)": (z >= 0.9) & (z < 1.55),
                 "head (>=1.55)": z >= 1.55}
        stats["filled_area_by_height"] = {k: round(float(a[v].sum() / a.sum()), 4) for k, v in bands.items()}
        stats["filled_area_arms_beyond_x0.3"] = round(float(a[np.abs(position[fill, 0]) > 0.3].sum() / a.sum()), 4)
        top = position[fill, 2] >= 1.8
        stats["filled_area_top_of_head (z>=1.8)"] = round(float(a[top].sum() / a.sum()), 4)

    # the images
    img = np.zeros((size, size, 3))
    img[covered] = np.clip(texel, 0, 255)
    padded = grow(img, covered, int(args.get("pad", 8)))
    bc.png(out / f"{name}.png", np.clip(np.rint(padded), 0, 255).astype(np.uint8), "rgb")
    cov = np.zeros((size, size, 3), np.uint8)
    palette = np.array([[220, 40, 40], [240, 150, 30], [235, 225, 60], [60, 190, 80]], np.uint8)
    cov[covered] = palette[tier]
    bc.png(out / f"{name}_coverage.png", cov, "rgb")
    win = np.zeros((size, size, 3), np.uint8)
    wc = np.array([VIEW_COLOURS.get(v, (200, 200, 200)) for v in view_names] + [(255, 255, 255)], np.uint8)
    pick = np.where(good & (second >= 0.1 * best), len(view_names), best_view)
    pick = np.where(good, pick, -1)
    wcol = np.where(pick[:, None] >= 0, wc[np.clip(pick, 0, len(wc) - 1)], np.array([90, 90, 90], np.uint8))
    win[covered] = wcol
    bc.png(out / f"{name}_winner.png", win, "rgb")
    layout = np.zeros((size, size), np.uint8)
    layout[covered] = 90
    bc.png(out / f"{name}_layout.png", layout, "l8")
    (out / f"{name}_stats.json").write_text(json.dumps(stats, indent=1))
    if args.get("save_model", True):
        bpy.ops.wm.save_as_mainfile(filepath=str(out / "model_uv.blend"), copy=True)
    result_path.write_text(json.dumps(stats, indent=1))


main()
