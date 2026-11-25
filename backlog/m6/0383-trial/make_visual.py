"""Trial 0383: the round-trip sheet. Rows: the unpainted views, their re-render from the projected texture, the difference (x8), the
synthetic painting, its re-render, and the textured Model from other angles.

    uv run python make_visual.py <views> <rt_id> <synth> <rt_syn> <out.png>
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

CROP = (40, 240, 984, 1296)
SCALE = 0.38


def panel(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB").crop(CROP)
    return im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)


def difference(a: Path, b: Path) -> Image.Image:
    x = np.array(Image.open(a).convert("RGBA")).astype(int)
    y = np.array(Image.open(b).convert("RGBA")).astype(int)
    d = np.clip(np.abs(x[..., :3] - y[..., :3]).max(-1) * 8, 0, 255).astype(np.uint8)
    d[(x[..., 3] == 0) & (y[..., 3] == 0)] = 0
    im = Image.fromarray(np.dstack([d, d, d])).crop(CROP)
    return im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)


def main() -> None:
    views, rt_id, synth, rt_syn, out = (Path(a) for a in sys.argv[1:6])
    names = ["front", "back", "left", "right"]
    rows = [
        ("1. the unpainted views (what the render gives)", [panel(views / f"{v}_color.png") for v in names]),
        ("2. re-rendered from the texture projected from row 1", [panel(rt_id / f"{v}_color.png") for v in names]),
        ("3. |row 1 - row 2| x 8 (1x, no anti-aliasing)", [difference(views / f"{v}_color_exact.png", rt_id / f"{v}_color_exact.png") for v in names]),
        ("4. synthetic paintings: checker per view, the view's name", [panel(synth / f"{v}_painted.png") for v in names]),
        ("5. re-rendered from the texture projected from row 4", [panel(rt_syn / f"{v}_color.png") for v in names]),
        ("6. the same texture from other angles: 45, 135, 225 deg, from above", [panel(rt_syn / f"{v}_color.png") for v in ("q45", "q135", "q225", "top")]),
    ]
    w, h = rows[0][1][0].size
    font = ImageFont.load_default(18)
    sheet = Image.new("RGB", (w * 4, (h + 28) * len(rows)), (30, 30, 30))
    draw = ImageDraw.Draw(sheet)
    for r, (caption, panels) in enumerate(rows):
        y = r * (h + 28)
        draw.text((6, y + 4), caption, fill=(255, 255, 255), font=font)
        for c, p in enumerate(panels):
            sheet.paste(p, (c * w, y + 28))
    sheet.save(out)


if __name__ == "__main__":
    main()
