"""Portrait set trial (ticket 0241): cutout, register, fit, set colours, outline, shimmer.

Reads kiripix.ops only. Every function takes and returns numpy arrays; `main()` runs a folder of images.
Run:  uv run python backlog/m5/0241-trial/portrait_set.py <folder> <out> [--n 32] [--dither 0]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from kiripix.ops import (Alignment, Grid, add_outline, chroma_key, dilate, downscale, key_fringe, map_set, register,
                         remove_small_pieces, set_colours, srgb_to_oklab, warp_nearest)

CANVAS = (160, 224)
OUTLINE = (53, 38, 37)  # the characters' outline colour: palette index 195 of the Project palette
EXTS = {".png", ".jpg", ".jpeg"}
# Rough face box in the neutral's source px (x0, y0, x1, y1): the head, the hair and the neck, with margin for the
# turned heads. Drawn by eye for Sanjay at 896 x 1200; the real Kind has the Owner draw it.
FACE_BOX = (190, 70, 700, 600)


def load(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def background(rgb: np.ndarray) -> tuple[int, int, int]:
    """The flat colour: the median of the top 30 rows and the side 30 columns above the figure's feet."""
    h = rgb.shape[0]
    border = np.concatenate([rgb[:30].reshape(-1, 3), rgb[: h * 2 // 3, :30].reshape(-1, 3),
                             rgb[: h * 2 // 3, -30:].reshape(-1, 3)])
    r, g, b = (int(v) for v in np.median(border, axis=0))
    return r, g, b


def cutout(rgb: np.ndarray, tolerance: float = 0.06, halo_reach: int = 10, halo: bool = True, islands: int = 1500):
    """Chroma key tolerant of JPEG noise: pixels within `tolerance` (OKLab) of the background snap to it exactly, then
    `chroma_key` clears them. A bright, unsaturated rim the image model draws round the figure (a sticker halo) is
    cleared where it connects to the background within `halo_reach` px."""
    key = background(rgb)
    lab = srgb_to_oklab(rgb)
    dist = np.sqrt(((lab - srgb_to_oklab(np.array(key, dtype=np.uint8))) ** 2).sum(-1))
    rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
    rgba[dist <= tolerance, :3] = key
    keyed = chroma_key(rgba, key)
    info = {"key": key}
    if halo:
        gone = keyed[..., 3] == 0
        start = int(gone.sum())
        # JPEG spill: green-tinted pixels touching the background within 3 px
        spill = (rgb[..., 1].astype(int) - np.maximum(rgb[..., 0], rgb[..., 2]).astype(int)) > 25
        for _ in range(3):
            gone = gone | (spill & dilate(gone, 1))
        light = (lab[..., 0] > 0.8) & (np.hypot(lab[..., 1], lab[..., 2]) < 0.09)
        for _ in range(halo_reach):
            grown = gone | (light & dilate(gone, 1))
            if (grown == gone).all():
                break
            gone = grown
        keyed[gone] = 0
        info["halo_px"] = int(gone.sum()) - start
    # opaque islands under `islands` px (halo crumbs the rim removal left) go too
    alone = keyed[..., 3] == 255
    kept = remove_small_pieces(alone, islands)
    info["island_px"] = int((alone & ~kept).sum())
    keyed[alone & ~kept] = 0
    info["fringe_left"] = int(key_fringe(keyed, key, 0.15).sum())
    return keyed, info


def on_grey(rgba: np.ndarray, grey: int = 128) -> np.ndarray:
    out = rgba.copy()
    out[rgba[..., 3] == 0] = (grey, grey, grey, 255)
    out[..., 3] = 255
    return out


def box_mask(shape, box) -> np.ndarray:
    m = np.zeros(shape, bool)
    m[box[1]:box[3] + 1, box[0]:box[2] + 1] = True
    return m


def register_set(cuts: dict, reference: str, box):
    """Each emotion's Alignment to the reference, over the whole figure (box None) or outside `box`."""
    ref = on_grey(cuts[reference])
    exclude = box_mask(ref.shape[:2], box) if box else None
    return {name: register(ref, on_grey(c), exclude) for name, c in cuts.items() if name != reference}


def fit_grid(shape, canvas=CANVAS, cx: int | None = None) -> Grid:
    """One Grid for the set: the largest uniform scale that fills the canvas height, anchored bottom centre.
    `cx` is the source column to centre the crop on (default: the image centre)."""
    h, w = shape
    probe = Grid.cover(w, h, canvas[0], canvas[1])
    used_w = int(probe.edges_x()[-1])
    left = w - used_w
    off_x = left // 2 if cx is None else min(max(cx - used_w // 2, 0), left)
    off_y = h - int(probe.edges_y()[-1])  # bottom anchor
    return Grid.cover(w, h, canvas[0], canvas[1], off_x, off_y)


def mapped(images: list, n: int, dither: int, keep=(OUTLINE,), alone: bool = False):
    alphas = [i[..., 3] for i in images]
    if alone:
        out = []
        for i in images:
            pal = set_colours([i], [i[..., 3]], n, keep)
            out.append(map_set([i], pal, dither)[0])
        return out, None
    pal = set_colours(images, alphas, n, keep)
    return map_set(images, pal, dither), pal


def outline(img: np.ndarray, placement: str = "outside") -> np.ndarray:
    return add_outline(img, OUTLINE, placement)


def lock_outside_face(images: dict, reference: str, face: np.ndarray) -> dict:
    ref = images[reference]
    out = {}
    for k, v in images.items():
        o = v.copy()
        o[~face] = ref[~face]
        out[k] = o
    return out


def shimmer(images: dict, reference: str, face: np.ndarray) -> dict:
    ref = images[reference]
    return {k: int(((v != ref).any(-1) & ~face).sum()) for k, v in images.items() if k != reference}


def face_target(box, grid: Grid) -> np.ndarray:
    """The face box in target px (every target pixel the box touches)."""
    ex, ey = grid.edges_x(), grid.edges_y()
    x0 = int(np.searchsorted(ex, box[0], side="right") - 1)
    x1 = int(np.searchsorted(ex, box[2], side="right") - 1)
    y0 = int(np.searchsorted(ey, box[1], side="right") - 1)
    y1 = int(np.searchsorted(ey, box[3], side="right") - 1)
    m = np.zeros((grid.height, grid.width), bool)
    m[max(y0, 0):y1 + 1, max(x0, 0):x1 + 1] = True
    return m


def build(folder: Path, out: Path, n: int = 32, dither: int = 0, reference: str = "neutral", use_face: bool = True,
          lock: bool = False):
    """The whole fallback: a folder of images named <emotion>.png/.jpg; writes <emotion>.png at 160 x 224."""
    files = {p.stem: p for p in sorted(folder.iterdir()) if p.suffix.lower() in EXTS}
    if reference not in files:
        raise SystemExit(f"{folder} has no {reference} image")
    cuts = {k: cutout(load(p))[0] for k, p in files.items()}
    shape = cuts[reference].shape[:2]
    box = FACE_BOX if use_face else None
    aligns = register_set(cuts, reference, box)
    aligned = {reference: cuts[reference], **{k: warp_nearest(cuts[k], a) for k, a in aligns.items()}}
    ys, xs = np.nonzero(aligned[reference][..., 3])
    grid = fit_grid(shape, cx=int((xs.min() + xs.max()) // 2))
    fitted = {k: downscale(v, grid) for k, v in aligned.items()}
    names = list(fitted)
    imgs, _pal = mapped([fitted[k] for k in names], n, dither)
    final = {k: outline(i) for k, i in zip(names, imgs)}
    if lock:
        final = lock_outside_face(final, reference, face_target(FACE_BOX, grid))
    out.mkdir(parents=True, exist_ok=True)
    for k, v in final.items():
        Image.fromarray(v).save(out / f"{k}.png")
    (out / "portrait.json").write_text(json.dumps({
        "canvas": list(CANVAS), "anchor": "bottom_centre", "fallback": reference, "n": n, "dither": dither,
        "emotions": {k: f"{k}.png" for k in names}, "grid": grid.to_json(),
        "alignment": {k: vars(a) for k, a in aligns.items()}}, indent=2, default=float))
    return final


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--n", type=int, default=32)
    ap.add_argument("--dither", type=int, default=0, choices=[0, 2, 4, 8])
    ap.add_argument("--no-face", action="store_true")
    ap.add_argument("--lock", action="store_true", help="copy the neutral's pixels outside the face box")
    a = ap.parse_args()
    build(a.folder, a.out, a.n, a.dither, use_face=not a.no_face, lock=a.lock)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
