"""Trial 0170: the sheet (x4) and the GIF of the attack's 8 directions, without and with the stick, from the finished frames of the
scratch Projects projC (without; cell 78) and projS (with; cell 92). The baseline cell is placed in the 92 cell by the pivots, so
both line up. Usage: make_sheet.py <scratch> <out folder>"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

scratch, out = Path(sys.argv[1]), Path(sys.argv[2])
EIGHT = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
BG = (58, 62, 72, 255)
CELL, DX, DY = 92, 7, 14  # the with-stick cell, and where the 78 cell's origin lands in it (92/2 - 78/2, 82 - 68)


def frame(project: str, direction: str, index: int) -> Image.Image:
    path = scratch / project / "assets/character/mc02/work/finish/color/attack" / direction / f"{index:03d}.png"
    im = Image.open(path).convert("RGBA")
    if project == "projC":
        placed = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        placed.paste(im, (DX, DY))
        im = placed
    return im


def tile(project: str, direction: str, index: int, scale: int) -> Image.Image:
    base = Image.new("RGBA", (CELL, CELL), BG)
    base.alpha_composite(frame(project, direction, index))
    return base.resize((CELL * scale, CELL * scale), Image.NEAREST)


# the sheet: one row per direction, 6 frames without the stick, then the same 6 with it
picks, scale, gap = [0, 4, 8, 12, 16, 20], 4, 16
w = CELL * scale
sheet = Image.new("RGBA", (2 * len(picks) * w + gap + 60, 8 * w), (20, 20, 24, 255))
draw = ImageDraw.Draw(sheet)
for r, d in enumerate(EIGHT):
    draw.text((6, r * w + w // 2), d, fill=(255, 255, 255, 255))
    for side, project in enumerate(("projC", "projS")):
        for c, i in enumerate(picks):
            sheet.alpha_composite(tile(project, d, i, scale), (60 + side * (len(picks) * w + gap) + c * w, r * w))
sheet.convert("RGB").save(out / "attack_8dir_without_left_with_right_x4.png")

# the GIF: the 8 directions side by side, without (top row) and with (bottom row), 25 frames at 12 fps
s = 2
gif = []
for i in range(25):
    img = Image.new("RGBA", (8 * CELL * s, 2 * CELL * s), BG)
    for k, d in enumerate(EIGHT):
        for row, project in enumerate(("projC", "projS")):
            img.alpha_composite(tile(project, d, i, s), (k * CELL * s, row * CELL * s))
    gif.append(img.convert("RGB"))
gif[0].save(out / "attack_8dir_without_top_with_bottom_x2.gif", save_all=True, append_images=gif[1:], duration=83, loop=0)
print("ok")
