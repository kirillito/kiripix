"""Trial 0238: the sheets (x4) and GIFs of the finished frames (palette and finish are Kiripix's own Stages, run in the scratch
Project): held_base (no things, cell 78), held_a1rows (things attached, cell 86, a ramp row each), held_rake (cell 138).
Rows of a sheet are the 8 directions s sw w nw n ne e se. Left block without the thing, right block with it, both in the same
cell, the body's cell placed in the larger one by the pivots."""
import sys
from PIL import Image, ImageDraw
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
proj = SC / "proj/assets/character"
OUT = HERE / "sheets"
BG = (58, 62, 72, 255)


def frame(asset, clip, d, i, side, piv, base_piv=(39, 67), base_side=78):
    im = Image.open(proj / asset / "work/finish/color" / clip / d / f"{i:03d}.png").convert("RGBA")
    if im.width != side:
        placed = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        placed.paste(im, (int(piv[0] - base_piv[0]), int(piv[1] - base_piv[1])))
        im = placed
    return im


def tile(im, scale):
    t = Image.new("RGBA", im.size, BG)
    t.alpha_composite(im)
    return t.resize((im.width * scale, im.height * scale), Image.NEAREST)


def sheet(name, clip, picks, side, piv, with_asset, without_asset="held_base", scale=4, both=True):
    w = side * scale
    blocks = [without_asset, with_asset] if both else [with_asset]
    gap = 16
    img = Image.new("RGBA", (60 + len(blocks) * len(picks) * w + (len(blocks) - 1) * gap, 8 * w), (20, 20, 24, 255))
    dr = ImageDraw.Draw(img)
    for r, d in enumerate(EIGHT):
        dr.text((6, r * w + w // 2), d, fill=(255, 255, 255, 255))
        for b, asset in enumerate(blocks):
            for c, i in enumerate(picks):
                img.alpha_composite(tile(frame(asset, clip, d, i, side, piv), scale), (60 + b * (len(picks) * w + gap) + c * w, r * w))
    img.convert("RGB").save(OUT / name)
    print(name, img.size)


def gif(name, clip, n, fps, side, piv, asset, scale):
    frames = []
    for i in range(n):
        img = Image.new("RGBA", (4 * side * scale, 2 * side * scale), BG)
        for k, d in enumerate(EIGHT):
            img.alpha_composite(tile(frame(asset, clip, d, i, side, piv), scale), ((k % 4) * side * scale, (k // 4) * side * scale))
        frames.append(img.convert("RGB"))
    frames[0].save(OUT / name, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0)
    print(name, frames[0].size, n)


sheet("phone_8dir_without_left_with_right_x4.png", "phone", [0, 6, 12, 18, 24], 86, (43, 75), "held_a1rows")
sheet("stick_attack_8dir_without_left_with_right_x4.png", "attack", [0, 4, 8, 12, 15, 18], 86, (43, 75), "held_a1rows")
sheet("rake_attack_8dir_with_x4.png", "attack", [0, 4, 8, 12, 15, 18], 138, (69, 113), "held_rake", both=False)
gif("phone_phone_8dir_x3.gif", "phone", 27, 8, 86, (43, 75), "held_a1rows", 3)
gif("stick_attack_8dir_x3.gif", "attack", 19, 12, 86, (43, 75), "held_a1rows", 3)
gif("rake_attack_8dir_x2.gif", "attack", 19, 12, 138, (69, 113), "held_rake", 2)
