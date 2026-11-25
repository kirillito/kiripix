"""Trial 0383: how far a re-render with a projected texture is from the render it came from.

    uv run python roundtrip_measure.py <original views folder> <re-render folder> [--views front,back,left,right] [--out report.json]

Compares `<view>_color_exact.png` (1x, no anti-aliasing, alpha = silhouette) of the two folders pixel by pixel: the silhouettes
(they should be identical: same geometry), and inside both the colour error as the Euclidean distance in sRGB bytes (0 to 441) and
the largest channel difference. `inner` is the same with the silhouette shrunk by 3 px.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def erode(mask: np.ndarray, count: int) -> np.ndarray:
    out = mask.copy()
    for _ in range(count):
        p = np.pad(out, 1, constant_values=False)
        out = out & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return out


def measure(original: Path, other: Path, view: str) -> dict:
    a = np.array(Image.open(original / f"{view}_color_exact.png").convert("RGBA")).astype(np.int32)
    b = np.array(Image.open(other / f"{view}_color_exact.png").convert("RGBA")).astype(np.int32)
    ma, mb = a[..., 3] > 127, b[..., 3] > 127
    both = ma & mb
    out = {"silhouette_pixels": int(ma.sum()), "silhouette_pixels_differing": int((ma ^ mb).sum())}
    material = np.array(Image.open(original / f"{view}_material.png")).astype(np.int32)
    same = np.ones(material.shape, bool)  # no other material within 2 px (or the silhouette)
    pad = np.pad(material, 2, constant_values=-1)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            same &= pad[2 + dy:2 + dy + material.shape[0], 2 + dx:2 + dx + material.shape[1]] == material
    normal = np.array(Image.open(original / f"{view}_normal.png").convert("RGBA")).astype(np.float64) if (original / f"{view}_normal.png").exists() else None
    bands = [("all", both), ("inner_3px", erode(both, 3)), ("away_from_material_edges_2px", both & same)]
    if normal is not None:  # the camera-space normal's Z is the cosine to the camera: how squarely the view faces the surface
        cosine = normal[..., 2] / 255.0 * 2 - 1
        bands += [("facing_squarely_cos>=0.75", both & (cosine >= 0.75)), ("facing_obliquely_0.2<=cos<0.75", both & (cosine >= 0.2) & (cosine < 0.75)),
                  ("facing_grazing_cos<0.2", both & (cosine < 0.2))]
    for label, sel in bands:
        d = a[..., :3] - b[..., :3]
        dist = np.sqrt((d * d).sum(-1))[sel]
        chan = np.abs(d).max(-1)[sel]
        out[label] = {"pixels": int(sel.sum()), "mean_distance": round(float(dist.mean()), 3),
                      "worst_distance": round(float(dist.max()), 2), "p99.9_distance": round(float(np.percentile(dist, 99.9)), 2),
                      "worst_channel_difference": int(chan.max()), "mean_channel_difference": round(float(chan.mean()), 3),
                      "share_over_8_bytes": round(float((chan > 8).mean()), 5), "share_identical": round(float((chan == 0).mean()), 4)} if sel.any() else {"pixels": 0}
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("original")
    p.add_argument("other")
    p.add_argument("--views", default="front,back,left,right")
    p.add_argument("--out")
    args = p.parse_args()
    report = {v: measure(Path(args.original), Path(args.other), v) for v in args.views.split(",")}
    text = json.dumps(report, indent=1)
    if args.out:
        Path(args.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
