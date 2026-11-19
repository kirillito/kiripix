"""0307 trial, lever A: per clip, one GIF (1x and 3x) with the fps variants side by side, each column labelled with its fps and its frame count,
rows the directions s, e, n. Finished frames (real palette and finish). Variants are the Assets `<body>` (the current fps) and `<body>_f<N>`
(min(fps, N), rendered again by the real Stages). All columns play the clip's length in time (the current clip's frames / fps); a looping clip
loops, a one-shot holds its last frame for half a second. Time ticks are 20 ms. Usage: make_gifs.py <body> ..."""
import json, sys
import numpy as np
from PIL import Image, ImageDraw
from common import *
from lib import *

OUT = HERE / "gifs"
OUT.mkdir(exist_ok=True)
BG = (58, 62, 72)
ROWS = ["s", "e", "n"]
CAPS = [8, 6, 4]
TICK = 20


def frames_of(name, clip, d):
    adir = PROJ / "assets/character" / name
    return [Image.open(adir / f"work/finish/color/{clip}/{d}/{i:03d}.png").convert("RGBA")
            for i in range(len(list((adir / f"work/finish/color/{clip}/{d}").glob("*.png"))))]


def main():
    for body in sys.argv[1:]:
        base = json.loads((PROJ / "assets/character" / body / "work/sheet/sheet.json").read_text())
        for c in base["clips"]:
            clip, fps, loop = c["name"], c["fps"], c["loop"]
            if "_to_" in clip:
                continue  # a transition: two frames
            still = len({frame_key(*[np.array(Image.open(PROJ / 'assets/character' / body / f'work/finish/{p}/{clip}/s/{i:03d}.png').convert('RGBA')) for p in ('color', 'normal')]) for i in range(len(c["directions"]["s"]))}) <= 2
            variants = [(body, fps)]
            if not still:
                for cap in CAPS:
                    if cap < fps and (PROJ / "assets/character" / f"{body}_f{cap}/work/sheet/sheet.json").exists():
                        variants.append((f"{body}_f{cap}", cap))
            cols = []
            for name, f in variants:
                per_dir = {d: frames_of(name, clip, d) for d in ROWS}
                cols.append((name, f, per_dir))
            n0 = len(cols[0][2]["s"])
            T = n0 / fps
            total = T + (0 if loop else 0.5)
            ticks = int(round(total * 1000 / TICK))
            for scale in (1, 3):
                w = cols[0][2]["s"][0].width * scale
                h = cols[0][2]["s"][0].height * scale
                lab = 16 if scale == 1 else 30
                gif = []
                for t in range(ticks):
                    sec = t * TICK / 1000
                    img = Image.new("RGB", (w * len(cols), lab + h * len(ROWS)), BG)
                    dr = ImageDraw.Draw(img)
                    for k, (name, f, per_dir) in enumerate(cols):
                        n = len(per_dir["s"])
                        idx = int(sec / T * n) % n if loop else min(int(sec / T * n), n - 1)
                        dr.text((k * w + 3, 2), f"{f} fps, {n} frames" + (" (current)" if k == 0 else ""), fill=(255, 255, 255))
                        for r, d in enumerate(ROWS):
                            im = per_dir[d][idx]
                            tile = Image.new("RGBA", im.size, BG + (255,))
                            tile.alpha_composite(im)
                            img.paste(tile.convert("RGB").resize((w, h), Image.NEAREST), (k * w, lab + r * h))
                    gif.append(img)
                p = OUT / f"{body}_{clip}_x{scale}.gif"
                gif[0].save(p, save_all=True, append_images=gif[1:], duration=TICK, loop=0, optimize=False, disposal=1)
                print(p.name, img.size, ticks, [(f, len(pd['s'])) for _, f, pd in cols], p.stat().st_size // 1024, "KB", flush=True)


main()
