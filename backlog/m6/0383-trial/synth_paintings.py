"""Trial 0383: a synthetic "painting" of each view, to test projection: a checker in a colour per view (front red, back blue, left
green, right yellow), the view's name in big letters, and the original colour kept faintly. Stays inside the silhouette; the rest is
the background, as a repaint would be.

    uv run python synth_paintings.py <views folder> <out folder> [--views front,back,left,right]

Writes `<out>/<view>_painted.png` (RGB, canvas size; what project_views.py takes) and, for roundtrip_measure.py, the same inside the
silhouette as `<view>_color_exact.png` (RGBA) with the views' `<view>_material.png` and `<view>_normal.png` copied beside it.
"""
import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HUES = {"front": (225, 50, 50), "back": (50, 80, 225), "left": (40, 180, 60), "right": (235, 210, 40)}
CELL = 32


def font(size: int):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def paint(view: str, exact: np.ndarray) -> np.ndarray:
    h, w = exact.shape[:2]
    mask = exact[..., 3] > 127
    yy, xx = np.mgrid[0:h, 0:w]
    cell = ((yy // CELL) + (xx // CELL)) % 2 == 0
    hue = np.array(HUES[view])
    paint = np.where(cell[..., None], hue, np.array([245, 245, 245]))
    painted = (0.8 * paint + 0.2 * exact[..., :3]).astype(np.uint8)
    image = Image.fromarray(painted)
    draw = ImageDraw.Draw(image)
    ys, xs = np.where(mask)
    cx, cy = int(xs.mean()), int(ys.min() + (ys.max() - ys.min()) * 0.42)
    draw.text((cx, cy), view.upper(), fill=(0, 0, 0), font=font(80), anchor="mm", stroke_width=4, stroke_fill=(255, 255, 255))
    return np.array(image)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("views_dir")
    p.add_argument("out")
    p.add_argument("--views", default="front,back,left,right")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    background = np.array([160, 160, 160], np.uint8)
    for view in a.views.split(","):
        exact = np.array(Image.open(Path(a.views_dir) / f"{view}_color_exact.png").convert("RGBA"))
        painted = paint(view, exact)
        mask = exact[..., 3] > 127
        full = np.where(mask[..., None], painted, background)
        Image.fromarray(full.astype(np.uint8)).save(out / f"{view}_painted.png")
        Image.fromarray(np.dstack([np.where(mask[..., None], painted, 0), mask.astype(np.uint8) * 255]).astype(np.uint8), "RGBA").save(out / f"{view}_color_exact.png")
        for extra in ("material", "normal"):
            shutil.copy(Path(a.views_dir) / f"{view}_{extra}.png", out / f"{view}_{extra}.png")


if __name__ == "__main__":
    main()
