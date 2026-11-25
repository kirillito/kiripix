"""Trial 0354: the images for GPT Image's pose transfer, and its sheet cut back into directions.

    uv run python backlog/m6/0354-trial/pose_inputs.py pose  FRAME.png OUT.png [--size 1024]
    uv run python backlog/m6/0354-trial/pose_inputs.py grid  RENDER_DIR CLIP INDEX OUT.png [--size 1536]
    uv run python backlog/m6/0354-trial/pose_inputs.py split SHEET.png OUT_DIR

`pose`: one render frame (a mannequin at `top34_8`) enlarged by a whole number (nearest, no smoothing) and centred on a flat
backdrop, for image 1 of a pose-transfer call. `grid`: the 8 directions of one frame of a clip on a 3x3 template, the centre
empty, laid out as the screen sees them (north-west top left, south bottom middle), for the one-call sheet. `split`: a 3x3
sheet back into `s.png` ... `se.png`, each cell as it is (no downscale: Kiripix's `fit` does that on import).

The backdrop is BACKDROP, a flat green the prior art keyed well; the actors (grey and black fur, a worker's clothes) have
none of it. Change it with --backdrop if an actor is green.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor

BACKDROP = "#00b140"
GRID = (("nw", "n", "ne"), ("w", None, "e"), ("sw", "s", "se"))


def enlarged(frame: Image.Image, cell: int) -> Image.Image:
    """The frame scaled by the largest whole number that fits the cell, nearest-neighbour."""
    factor = max(1, cell // max(frame.size))
    return frame.resize((frame.width * factor, frame.height * factor), Image.Resampling.NEAREST)


def on_backdrop(frame: Image.Image, size: int, backdrop: str) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), backdrop)
    big = enlarged(frame.convert("RGBA"), size)
    canvas.alpha_composite(big, ((size - big.width) // 2, (size - big.height) // 2))
    return canvas.convert("RGB")


def cmd_pose(args: argparse.Namespace) -> None:
    on_backdrop(Image.open(args.frame), args.size, args.backdrop).save(args.out)
    print(args.out)


LONG = {"s": "south", "sw": "south-west", "w": "west", "nw": "north-west", "n": "north", "ne": "north-east", "e": "east",
        "se": "south-east"}


def direction_frame(folder: Path, clip: str, index: int, name: str) -> Image.Image:
    """One direction's frame: from a render (render.json there) or from a folder of PNGs named by direction, such as a
    PixelLab export's rotations/ (south.png, south-east.png ...; clip and index are then ignored)."""
    if (folder / "render.json").exists():
        render = json.loads((folder / "render.json").read_text(encoding="utf-8"))
        found = next(c for c in render["clips"] if c["name"] == clip)
        return Image.open(folder / found["directions"][name][index]["files"]["color"])
    for stem in (LONG[name], name):
        if (folder / f"{stem}.png").exists():
            return Image.open(folder / f"{stem}.png")
    raise SystemExit(f"{folder}: no render.json, and no {LONG[name]}.png or {name}.png")


def cmd_grid(args: argparse.Namespace) -> None:
    cell = args.size // 3
    sheet = Image.new("RGB", (cell * 3, cell * 3), args.backdrop)
    for row, names in enumerate(GRID):
        for column, name in enumerate(names):
            if name is None:
                continue
            frame = direction_frame(args.render_dir, args.clip, args.index, name)
            sheet.paste(on_backdrop(frame, cell, args.backdrop), (column * cell, row * cell))
    sheet.save(args.out)
    print(f"{args.out}: {sheet.width}x{sheet.height}, cells {cell} px")


def cmd_back(args: argparse.Namespace) -> None:
    """A pose-transfer result back onto the render frame's grid: the inverse of `pose` (the same whole-number factor and
    centring), each block averaged, the backdrop keyed out. Crude, for PixelLab's first_frame only: the keypoints are
    fractions of the render frame, so the actor must sit where the mannequin did. Scoring uses Kiripix's own `fit`."""
    frame = Image.open(args.frame)
    result = Image.open(args.result).convert("RGB").resize((args.size, args.size), Image.Resampling.LANCZOS)
    factor = max(1, args.size // max(frame.size))
    width, height = frame.width * factor, frame.height * factor
    left, top = (args.size - width) // 2, (args.size - height) // 2
    small = result.crop((left, top, left + width, top + height)).resize(frame.size, Image.Resampling.BOX).convert("RGBA")
    key = np.array(ImageColor.getrgb(args.backdrop)[:3], dtype=np.float64)
    pixels = np.array(small)
    near = np.linalg.norm(pixels[..., :3].astype(np.float64) - key, axis=-1) < args.tolerance
    pixels[near] = 0
    small = Image.fromarray(pixels, "RGBA")
    small.save(args.out)
    print(f"{args.out}: {small.width}x{small.height}, from {args.result} at 1/{factor}")


def cmd_split(args: argparse.Namespace) -> None:
    sheet = Image.open(args.sheet).convert("RGB")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    width, height = sheet.width // 3, sheet.height // 3
    for row, names in enumerate(GRID):
        for column, name in enumerate(names):
            if name:
                sheet.crop((column * width, row * height, (column + 1) * width, (row + 1) * height)).save(
                    args.out_dir / f"{name}.png")
    print(f"{args.out_dir}: 8 cells of {width}x{height}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pose")
    p.add_argument("frame", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--size", type=int, default=1024)
    p.set_defaults(run=cmd_pose)
    p = sub.add_parser("grid")
    p.add_argument("render_dir", type=Path,
                   help="a character's work/render/, or a folder of PNGs named by direction (rotations/)")
    p.add_argument("clip")
    p.add_argument("index", type=int)
    p.add_argument("out", type=Path)
    p.add_argument("--size", type=int, default=1536)
    p.set_defaults(run=cmd_grid)
    p = sub.add_parser("back", help="a pose-transfer result back to the render frame's size and place")
    p.add_argument("result", type=Path)
    p.add_argument("frame", type=Path, help="the render frame `pose` enlarged")
    p.add_argument("out", type=Path)
    p.add_argument("--size", type=int, default=1024, help="the size `pose` made")
    p.add_argument("--tolerance", type=float, default=90.0, help="RGB distance keyed out as backdrop")
    p.set_defaults(run=cmd_back)
    p = sub.add_parser("split")
    p.add_argument("sheet", type=Path)
    p.add_argument("out_dir", type=Path)
    p.set_defaults(run=cmd_split)
    for name in ("pose", "grid", "back"):
        sub.choices[name].add_argument("--backdrop", default=BACKDROP)
    args = parser.parse_args()
    for name in ("out", "out_dir"):
        if isinstance(getattr(args, name, None), Path):
            (args.out_dir if name == "out_dir" else args.out.parent).mkdir(parents=True, exist_ok=True)
    args.run(args)


if __name__ == "__main__":
    main()
