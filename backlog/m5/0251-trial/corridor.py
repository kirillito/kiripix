"""Ticket 0251, steps 3 and 4: slice the palette-mapped Sources into 16 px tiles, lay out a test corridor with turns,
count the seams that show, and draw the comparison with a painted ch01 dungeon room.

Inputs: `work/pal_*.png`, the `palette` Stage's output from the scratch Project (see README.md); the art Project's
`ch01_dungeon_r01` and a character, read-only. Output: `out/`.

The layout is hand-written (LAYOUT, below) as floor and wall; each tile's piece is picked from what is next to it, the
way an autotile rule would: a wall tile with floor 1-3 tiles below it is the top wall's face (row 3 - d of grid4's
9-slice), with floor 1-2 tiles above it the bottom wall, and so on; a tile that sees floor only on a diagonal is a room
corner (grid4 has those); a tile that sees floor both straight down or up and straight left or right is the inside of a
turn, a convex corner, which grid4 doesn't have.

Three kits:
- A: grid4 only. A convex corner falls back to the top or bottom wall's piece.
- B: grid4, with grid5's convex corners.
- C: B, with grid2's four floor tiles for the floor (plain 70 %, each other 10 %).
"""

import json
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from kiripix.ops.colour import srgb_to_oklab
from kiripix.ops.palette import parse_gpl

HERE = Path(__file__).parent
WORK = HERE / "work"
OUT = HERE / "out"
ART = Path("C:/Workspace/urban-mystery-club-art")
ROOM = ART / "assets/room/ch01_dungeon_r01/work/palette/palette.png"
CHAR = ART / "assets/character/mc03_female_clothes01/out/export"
TS = 16
SCREEN = (40, 22)  # tiles: 640 x 352

# Hand-written layout, one character per tile: '.' floor, anything else wall. A corridor 4 tiles (2 battle cells) wide
# runs right, turns down, turns right again, out at the right edge.
LAYOUT = [
    "########################################",
    "########################################",
    "########################################",
    "########################################",
    "..................######################",
    "..................######################",
    "..................######################",
    "..................######################",
    "##############....######################",
    "##############....######################",
    "##############....######################",
    "##############....######################",
    "##############..........................",
    "##############..........................",
    "##############..........................",
    "##############..........................",
    "########################################",
    "########################################",
    "########################################",
    "########################################",
    "########################################",
    "########################################",
]

TOP, BOT, SIDE = 3, 2, 2  # wall band thickness in tiles (grid4's 9-slice)


def tiles_of(path: Path) -> np.ndarray:
    a = np.asarray(Image.open(path).convert("RGB"))
    h, w = a.shape[0] // TS, a.shape[1] // TS
    return a[: h * TS, : w * TS].reshape(h, TS, w, TS, 3).swapaxes(1, 2)  # [row, col, y, x, c]


def is_floor(x: int, y: int) -> bool:
    return 0 <= y < SCREEN[1] and 0 <= x < SCREEN[0] and LAYOUT[y][x] == "."


def first_floor(x: int, y: int, dx: int, dy: int, reach: int) -> int | None:
    for d in range(1, reach + 1):
        if is_floor(x + dx * d, y + dy * d):
            return d
    return None


def role(x: int, y: int) -> tuple:
    """What a tile is: ('floor',), ('void',), ('band', v, h) or ('concave', v, h) or ('convex', v, h); v and h are
    (side, distance) or None."""
    if is_floor(x, y):
        return ("floor",)
    down, up = first_floor(x, y, 0, 1, TOP), first_floor(x, y, 0, -1, BOT)
    right, left = first_floor(x, y, 1, 0, SIDE), first_floor(x, y, -1, 0, SIDE)
    v = ("top", down) if down else ("bot", up) if up else None
    h = ("left", right) if right else ("right", left) if left else None
    if v and h:
        return ("convex", v, h)
    if v or h:
        return ("band", v, h)
    for vs, dy, reach in (("top", 1, TOP), ("bot", -1, BOT)):
        for hs, dx in (("left", 1), ("right", -1)):
            for dv in range(1, reach + 1):
                for dh in range(1, SIDE + 1):
                    if is_floor(x + dx * dh, y + dy * dv):
                        return ("concave", (vs, dv), (hs, dh))
    return ("void",)


def g4_row(v: tuple) -> int:
    return 3 - v[1] if v[0] == "top" else 17 + v[1]


def g4_col(h: tuple) -> int:
    return 2 - h[1] if h[0] == "left" else 17 + h[1]


def g5_convex(v: tuple, h: tuple) -> tuple[int, int]:
    """grid5's junction: vertical corridor floor in columns 9-10, horizontal corridor floor in rows 9-10."""
    col = 9 - h[1] if h[0] == "left" else 10 + h[1]
    row = 9 - v[1] if v[0] == "top" else 10 + v[1]
    return row, col


def run_to_wall(x: int, y: int, dx: int, dy: int) -> int | None:
    """Floor tiles from (x, y) to the wall in one direction, or None if the floor runs off the screen."""
    k = 0
    while True:
        x, y = x + dx, y + dy
        if not (0 <= x < SCREEN[0] and 0 <= y < SCREEN[1]):
            return None
        if not is_floor(x, y):
            return k
        k += 1


def floor_rc(x: int, y: int) -> tuple[int, int]:
    """grid4's floor tile for a floor tile, counted from the nearest wall as in the painted room (rows 3-17, columns
    2-17), so a wall's foot meets the floor it was painted beside. Far from any wall it repeats the floor."""
    up, down = run_to_wall(x, y, 0, -1), run_to_wall(x, y, 0, 1)
    left, right = run_to_wall(x, y, -1, 0), run_to_wall(x, y, 1, 0)
    if up is not None and up < 8 and (down is None or up <= down):
        row = 3 + up
    elif down is not None and down < 7:
        row = 17 - down
    else:
        row = 3 + y % 15
    if left is not None and left < 8 and (right is None or left <= right):
        col = 2 + left
    elif right is not None and right < 8:
        col = 17 - right
    else:
        col = 2 + x % 16
    return row, col


def pick(kit: str, x: int, y: int, rng: random.Random) -> tuple[str, int, int]:
    r = role(x, y)
    if r[0] == "floor":
        if kit == "C":
            return ("g2floor", 0, rng.choices([0, 1, 2, 3], [70, 10, 10, 10])[0])
        return ("g4", *floor_rc(x, y))
    if r[0] == "void":
        return ("void", 0, 0)
    v, h = r[1], r[2]
    if r[0] == "convex":
        if kit == "A":
            return ("g4", g4_row(v), floor_rc(x, y + (v[1] if v[0] == "top" else -v[1]))[1])
        return ("g5", *g5_convex(v, h))
    if r[0] == "concave":
        return ("g4", g4_row(v), g4_col(h))
    if v:
        return ("g4", g4_row(v), floor_rc(x, y + (v[1] if v[0] == "top" else -v[1]))[1])
    return ("g4", floor_rc(x + (h[1] if h[0] == "left" else -h[1]), y)[0], g4_col(h))


def build(kit: str, atlases: dict, void: np.ndarray) -> tuple[np.ndarray, list[list[tuple]]]:
    rng = random.Random(251)
    W, H = SCREEN
    img = np.zeros((H * TS, W * TS, 3), np.uint8)
    picks = [[pick(kit, x, y, rng) for x in range(W)] for y in range(H)]
    for y in range(H):
        for x in range(W):
            name, r, c = picks[y][x]
            img[y * TS : (y + 1) * TS, x * TS : (x + 1) * TS] = void if name == "void" else atlases[name][r, c]
    return img, picks


def palette_step() -> float:
    pal = parse_gpl((ART / "style/palette.gpl").read_text(encoding="utf-8"))
    lab = srgb_to_oklab(pal.rgb().reshape(-1, 1, 3)).reshape(-1, 3)
    d = np.linalg.norm(lab[:, None] - lab[None], axis=2)
    np.fill_diagonal(d, np.inf)
    return float(np.median(d.min(axis=1)))


def seams(img: np.ndarray, picks: list[list[tuple]], step: float) -> tuple[list[dict], int]:
    """A seam candidate is an edge between two tiles that weren't neighbours in their Source (same atlas, same offset).
    Its pixel pairs across the edge break when they are more than a palette step apart (OKLab); so do pairs one pixel
    inside each tile, the baseline. A seam shows when the edge breaks at least 4 more of its 16 pairs than the
    baseline's rate (0.25)."""
    lab = srgb_to_oklab(img)
    W, H = SCREEN
    found, candidates = [], 0
    for y in range(H):
        for x in range(W):
            for dx, dy in ((1, 0), (0, 1)):
                x2, y2 = x + dx, y + dy
                if x2 >= W or y2 >= H:
                    continue
                a, b = picks[y][x], picks[y2][x2]
                if a[0] == "void" or b[0] == "void":
                    continue
                if a[0] == b[0] and (b[1] - a[1], b[2] - a[2]) == (dy, dx):
                    continue
                candidates += 1
                if dx:
                    e = (x + 1) * TS
                    cols = lambda i: lab[y * TS : (y + 1) * TS, i]  # noqa: E731
                    edge = np.linalg.norm(cols(e - 1) - cols(e), axis=1)
                    inner = np.concatenate([np.linalg.norm(cols(e - 2) - cols(e - 1), axis=1),
                                            np.linalg.norm(cols(e) - cols(e + 1), axis=1)])
                else:
                    e = (y + 1) * TS
                    rows = lambda i: lab[i, x * TS : (x + 1) * TS]  # noqa: E731
                    edge = np.linalg.norm(rows(e - 1) - rows(e), axis=1)
                    inner = np.concatenate([np.linalg.norm(rows(e - 2) - rows(e - 1), axis=1),
                                            np.linalg.norm(rows(e) - rows(e + 1), axis=1)])
                f_edge, f_in = float((edge > step).mean()), float((inner > step).mean())
                if f_edge - f_in >= 0.25:
                    kinds = sorted({role(x, y)[0], role(x2, y2)[0]})
                    found.append({"x": x, "y": y, "dir": "right" if dx else "down", "edge": round(f_edge, 2),
                                  "inner": round(f_in, 2), "roles": kinds})
    return found, candidates


def character() -> tuple[Image.Image, tuple[int, int]]:
    """mc03_female_clothes01's idle, facing south, frame 0, and its pivot within the returned image."""
    meta = json.loads((CHAR / "character.json").read_text(encoding="utf-8"))
    clip = next(c for c in meta["clips"] if c["name"] == "idle")
    f = clip["directions"]["s"][0]
    r = f["rect"]
    im = Image.open(CHAR / "color.png").convert("RGBA").crop((r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"]))
    return im, (clip["pivot"]["x"] - f["offset"]["x"], clip["pivot"]["y"] - f["offset"]["y"])


def stage(base: Image.Image, feet: list[tuple[int, int]], label: str) -> Image.Image:
    """Characters at their feet, then the 32 px battle grid over it all."""
    im = base.convert("RGBA")
    ch, (px, py) = character()
    for fx, fy in feet:
        im.alpha_composite(ch, (fx - px, fy - py))
    grid = Image.new("RGBA", im.size)
    d = ImageDraw.Draw(grid)
    for gx in range(0, im.width, 32):
        d.line([(gx, 0), (gx, im.height)], fill=(255, 255, 255, 70))
    for gy in range(0, im.height, 32):
        d.line([(0, gy), (im.width, gy)], fill=(255, 255, 255, 70))
    im.alpha_composite(grid)
    ImageDraw.Draw(im).text((4, im.height - 12), label, fill=(255, 255, 0, 255))
    return im.convert("RGB")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    atlases = {n: tiles_of(WORK / f"pal_{n}.png") for n in ("g4", "g5", "g2floor")}
    void = atlases["g5"][0, 0]  # grid5's plain dark void
    step = palette_step()
    results = {"palette_step_oklab": round(step, 4)}
    feet = [(96, 116), (256, 180), (480, 244)]  # on the floor of each leg
    panels = []
    for kit in ("A", "B", "C"):
        img, picks = build(kit, atlases, void)
        found, candidates = seams(img, picks, step)
        Image.fromarray(img).save(OUT / f"corridor_{kit}.png")
        marked = Image.fromarray(img).resize((img.shape[1] * 3, img.shape[0] * 3), Image.Resampling.NEAREST)
        d = ImageDraw.Draw(marked)
        for s in found:
            if s["dir"] == "right":
                X = (s["x"] + 1) * TS * 3
                d.line([(X, s["y"] * TS * 3), (X, (s["y"] + 1) * TS * 3)], fill=(255, 0, 0), width=3)
            else:
                Y = (s["y"] + 1) * TS * 3
                d.line([(s["x"] * TS * 3, Y), ((s["x"] + 1) * TS * 3, Y)], fill=(255, 0, 0), width=3)
        marked.save(OUT / f"corridor_{kit}_seams_3x.png")
        by_role: dict[str, int] = {}
        for s in found:
            k = "+".join(s["roles"])
            by_role[k] = by_role.get(k, 0) + 1
        results[kit] = {"candidate_edges": candidates, "seams_showing": len(found), "by_roles": by_role,
                        "seams": found}
        panel = stage(Image.fromarray(img), feet, f"kit {kit}")
        panel.save(OUT / f"compare_{kit}_1x.png")
        panel.resize((panel.width * 3, panel.height * 3), Image.Resampling.NEAREST).save(OUT / f"compare_{kit}_3x.png")
        panels.append(panel)

    room = Image.open(ROOM).convert("RGB")
    crop = room.crop((0, room.height - 352, room.width, room.height))  # the room's lower 400 x 352
    rp = stage(crop, [(200, 300), (120, 250)], "ch01_dungeon_r01 (painted)")
    rp.save(OUT / "compare_room_1x.png")
    rp.resize((rp.width * 3, rp.height * 3), Image.Resampling.NEAREST).save(OUT / "compare_room_3x.png")

    sheet = Image.new("RGB", (640 + 8 + 400, 352 * 2 + 8), (40, 40, 40))
    sheet.paste(panels[0], (0, 0))
    sheet.paste(panels[1], (0, 360))
    sheet.paste(rp, (648, 0))
    sheet.save(OUT / "compare_1x.png")
    sheet.resize((sheet.width * 3, sheet.height * 3), Image.Resampling.NEAREST).save(OUT / "compare_3x.png")

    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "seams"})
                      for k, v in results.items()}, indent=1))


if __name__ == "__main__":
    main()
