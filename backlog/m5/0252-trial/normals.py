"""Trial 0252 step 2b: depth -> Grid transform -> Sobel normals -> quantise, per Plate and per Layer (cut by alpha).

usage: python normals.py <room_dir> <out_dir> [height_px] [deadzone] [levels]
Reads <out_dir>/depth.npy (source px) and the room's work/fit/grid.json, out/export/plate.png, layer.*.png.
Writes <out_dir>/normals/{plate,layer.X}.{naive,masked}.png (RGBA normal maps, Godot convention: +Y up, alpha = cut),
plus a depth preview and stats.json.  Prototype only; numpy + Pillow.
"""
import json, sys
from fractions import Fraction
from pathlib import Path
import numpy as np
from PIL import Image


def grid_resample(depth, grid):
    """The room's Grid transform for a downscale fit: source px -> target px (box filter, offset 0)."""
    assert grid["mode"] == "downscale" and grid["offset_x"] == 0 and grid["offset_y"] == 0, grid
    return np.asarray(Image.fromarray(depth, "F").resize((grid["width"], grid["height"]), Image.BOX))


def box(a, r):
    """Mean over a (2r+1)^2 window, edge-replicated (cumsum)."""
    p = np.pad(a, r, mode="edge"); c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    k = 2 * r + 1
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def masked_fill(val, mask):
    """Fill val where mask is False from nearby True pixels (normalised convolution, growing radius)."""
    out = np.where(mask, val, 0.0).astype(np.float32); known = mask.astype(np.float32)
    have = mask.copy()
    for r in (1, 2, 4, 8, 16, 32, 64, 128, 400):
        if have.all():
            break
        num = box(out * known, r) ; den = box(known, r)
        ok = (den > 1e-4) & ~have
        out[ok] = num[ok] / den[ok]; known[ok] = 1.0; have |= ok
    return out


def sobel(h):
    p = np.pad(h, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:] - p[:-2, :-2] - 2 * p[1:-1, :-2] - p[2:, :-2]) / 8.0
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:] - p[:-2, :-2] - 2 * p[:-2, 1:-1] - p[:-2, 2:]) / 8.0
    return gx, gy   # gy: image y down


def quantise(g, dz, levels):
    """g: tilt component in [-1, 1]. Deadzone to flat, then `levels` steps per side (levels=2: 0, +-0.5, +-1 of max tilt)."""
    a = np.abs(g); s = np.sign(g)
    mx = 0.75                                    # max tilt component kept (~49 degrees)
    t = np.clip((a - dz) / (mx - dz), 0, 1)
    q = np.ceil(t * levels - 1e-6) / levels      # 0 stays 0
    q = np.where(a <= dz, 0.0, np.maximum(q, 1.0 / levels))
    return s * q * mx


def to_normal(h, dz, levels):
    gx, gy = sobel(h)
    nx, ny = -gx, +gy                            # height up toward viewer; Godot's Y is up, image Y is down
    nxq, nyq = quantise(nx, dz, levels), quantise(ny, dz, levels)
    nz = np.sqrt(np.clip(1 - nxq ** 2 - nyq ** 2, 0, 1))
    return nxq, nyq, nz


def encode(nx, ny, nz, alpha):
    rgb = np.stack([nx, ny, nz], -1) * 0.5 + 0.5
    a = alpha[..., None]
    img = np.concatenate([np.round(rgb * 255).astype(np.uint8), a], -1)
    return Image.fromarray(img, "RGBA")


def main(room, out, H=60.0, dz=0.10, levels=3):
    room, out = Path(room), Path(out)
    grid = json.loads((room / "work/fit/grid.json").read_text())
    depth = np.load(out / "depth.npy")
    d = grid_resample(depth, grid)
    lo, hi = np.percentile(d, [1, 99]); d = np.clip((d - lo) / (hi - lo), 0, 1) * H   # height in target px
    ex = room / "out/export"
    plate = np.asarray(Image.open(ex / "plate.png").convert("RGBA"))[..., 3]
    layers = {p.stem.split(".", 1)[1]: np.asarray(Image.open(p).convert("RGBA"))[..., 3] for p in sorted(ex.glob("layer.*.png"))}
    nd = out / "normals"; nd.mkdir(exist_ok=True)
    walk = np.asarray(Image.open(room / "work/place/walkable.png").convert("L")) > 127
    stats = dict(H=H, deadzone=dz, levels=levels, size=[grid["width"], grid["height"]])
    cuts = {"plate": plate, **{f"layer.{k}": v for k, v in layers.items()}}
    for name, alpha in cuts.items():
        inside = alpha > 0
        for mode in ("naive", "masked"):
            # naive: Sobel of the whole room's depth, cut by alpha afterwards.
            # masked: depth outside this cut is refilled from inside it first, so no step at the cut's edge.
            h = d if mode == "naive" else masked_fill(d, inside)
            nx, ny, nz = to_normal(h, dz, levels)
            encode(nx, ny, nz, alpha).save(nd / f"{name}.{mode}.png")
            flat = (nx == 0) & (ny == 0)
            # rim: pixels of the cut within 2 px of its edge
            er = inside.copy()
            for _ in range(2):
                p = np.pad(er, 1, constant_values=False)
                er = er & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
            rim = inside & ~er
            s = dict(pixels=int(inside.sum()), flat_all=round(float(flat[inside].mean()), 3) if inside.any() else None)
            if rim.any():
                s["flat_rim2px"] = round(float(flat[rim].mean()), 3)
                s["strong_tilt_rim2px"] = round(float((np.hypot(nx, ny)[rim] > 0.6).mean()), 3)   # tilted >= 2 levels of 3
            if name == "plate":
                m = walk & inside
                s["flat_on_walkable"] = round(float(flat[m].mean()), 3)
            stats[f"{name}.{mode}"] = s
    Image.fromarray((np.clip(d / H, 0, 1) * 255).astype(np.uint8)).save(out / "depth_target.png")
    (out / "stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], *(float(x) for x in a[3:5]), *(int(x) for x in a[5:6]))
