"""0332 trial: reads results.json and images/, writes table.md, sheet_figures.png and sheet_rooms.png beside it."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
R = json.loads((HERE / "results.json").read_text())

NUM = {k: i + 1 for i, k in enumerate(R)}
LABEL = {
    "body_male": "mc03_male body (idle s, finish)", "body_female": "mc03_female body (idle s, finish)",
    "wearable_male_clothes01": "mc03_male_clothes01 Wearable", "sprite_raccoon": "raccoon sprite (idle s)",
    "room_laneway": "laneway (Layers composited; no full Plate)", "room_dungeon_r01": "ch01 dungeon r01 Plate",
    "room_dungeon_r02": "ch01 dungeon r02 Plate", "room_dungeon_r03": "ch01 dungeon r03 Plate",
    "prop_bin_r02": "bin Layer, r02 (stand-in Prop)", "prop_bin_r03": "bin Layer, r03 (stand-in Prop)",
    "mm_sprite_2x": "MISMATCH raccoon at 2x pixels", "mm_body_no_outline": "MISMATCH mc03_male, outline off",
    "mm_sprite_saturated": "MISMATCH raccoon, chroma x1.8, unmapped", "mm_sprite_vivid": "MISMATCH raccoon, chroma x4, unmapped",
    "mm_sprite_mirrored": "MISMATCH raccoon mirrored", "mm_body_mirrored": "MISMATCH mc03_male mirrored",
    "mm_room_mirrored_r02": "MISMATCH r02 mirrored", "mm_room_mirrored_laneway": "MISMATCH laneway mirrored",
}


def rows():
    cols = [("off-pal px", lambda v: v["palette"]["off_palette_px"], "{:.2f}"),
            ("pal used", lambda v: v["palette"]["used_share"], "{:.3f}"),
            ("pal TV", lambda v: v["palette"]["tv_vs_refs"], "{:.2f}"),
            ("L span", lambda v: v["range"]["Lspan"], "{:.2f}"),
            ("C95", lambda v: v["range"]["C95"], "{:.3f}"),
            ("outline dens", lambda v: v["outline"]["density"], "{:.2f}"),
            ("run med", lambda v: v["scale"]["run_median"], "{:.0f}"),
            ("run gcd", lambda v: v["scale"]["run_gcd"], "{:d}"),
            ("even bnd", lambda v: v["scale"]["even_boundary_share"], "{:.2f}"),
            ("lit left", lambda v: v["light_grad"]["lit_left"], "{:+.2f}"),
            ("lit top", lambda v: v["light_grad"]["lit_top"], "{:+.2f}"),
            ("L-R thirds", lambda v: v["light_thirds"]["left_minus_right"], "{:+.3f}"),
            ("nx coef", lambda v: v["light_norm"]["nx_coef"] if "light_norm" in v else None, "{:+.3f}"),
            ("time s", lambda v: sum(v["time_s"].values()), "{:.2f}")]
    return cols


def table():
    cols = rows()
    out = ["| # | Asset | Stage | " + " | ".join(c[0] for c in cols) + " |", "|" + "---|" * (len(cols) + 3)]
    for k, v in R.items():
        stage = {"figure": "finish (sheet frame)", "room": "palette plate / layers (export)", "prop": "export layer"}[v["group"]]
        cells = []
        for _, f, fmt in cols:
            x = f(v)
            cells.append("-" if x is None else fmt.format(int(x) if fmt == "{:d}" else x))
        out.append(f"| {NUM[k]} | {LABEL[k]} | {stage} | " + " | ".join(cells) + " |")
    (HERE / "table.md").write_text("\n".join(out) + "\n")


def spread():
    """Matched min and max per measure per group, and each mismatch's margin outside its group's matched range."""
    lines = []
    meas = {"off_palette_px": lambda v: v["palette"]["off_palette_px"], "C95": lambda v: v["range"]["C95"],
            "Lspan": lambda v: v["range"]["Lspan"], "outline density": lambda v: v["outline"]["density"],
            "even boundary share": lambda v: v["scale"]["even_boundary_share"], "run median": lambda v: v["scale"]["run_median"],
            "pal used": lambda v: v["palette"]["used_share"], "pal TV": lambda v: v["palette"]["tv_vs_refs"],
            "lit_left": lambda v: v["light_grad"]["lit_left"], "L-R thirds": lambda v: v["light_thirds"]["left_minus_right"]}
    for g in ("figure", "room", "prop"):
        lines.append(f"## matched {g}")
        for m, f in meas.items():
            xs = [f(v) for v in R.values() if v["matched"] and v["group"] == g]
            lines.append(f"{m}: min {min(xs):.3f} max {max(xs):.3f}")
    lines.append("## all matched")
    for m, f in meas.items():
        xs = [f(v) for v in R.values() if v["matched"]]
        lines.append(f"{m}: min {min(xs):.3f} max {max(xs):.3f}")
    (HERE / "spread.txt").write_text("\n".join(lines) + "\n")


def font(size):
    for n in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return ImageFont.load_default()


def tile(k, scale_to, f):
    im = Image.open(HERE / "images" / f"{k}.png").convert("RGBA")
    w, h = im.size
    if max(w, h) <= scale_to:
        s = max(1, scale_to // max(w, h))
        im = im.resize((w * s, h * s), Image.NEAREST); note = f"shown x{s}"
    else:
        s = -(-max(w, h) // scale_to)
        im = im.resize((w // s, h // s), Image.NEAREST); note = f"shown 1/{s}"
    v = R[k]
    lines = [f"#{NUM[k]}  {LABEL[k]}", f"{w}x{h} px, {note}  (nearest)",
             f"off-palette {v['palette']['off_palette_px']:.0%}   C95 {v['range']['C95']:.3f}",
             f"outline {v['outline']['density']:.2f}   even-bnd {v['scale']['even_boundary_share']:.2f}  gcd {v['scale']['run_gcd']}",
             f"lit-left {v['light_grad']['lit_left']:+.2f}   lit-top {v['light_grad']['lit_top']:+.2f}"]
    tw = max(im.width, 560)
    t = Image.new("RGB", (tw, scale_to + 8 + 26 * len(lines)), (210, 210, 210))
    bg = Image.new("RGBA", im.size, (120, 124, 130, 255))
    bg.alpha_composite(im)
    t.paste(bg.convert("RGB"), ((tw - im.width) // 2, scale_to - im.height))
    d = ImageDraw.Draw(t)
    for i, ln in enumerate(lines):
        d.text((6, scale_to + 6 + 26 * i), ln, fill=(0, 0, 0) if "MISMATCH" not in ln else (170, 0, 0), font=f)
    return t


def sheet(keys, name, scale_to, per_row):
    f = font(20)
    tiles = [tile(k, scale_to, f) for k in keys]
    rows_ = [tiles[i:i + per_row] for i in range(0, len(tiles), per_row)]
    W = max(sum(t.width + 12 for t in r) for r in rows_)
    H = sum(max(t.height for t in r) + 12 for r in rows_)
    S = Image.new("RGB", (W, H), (255, 255, 255))
    y = 0
    for r in rows_:
        x = 0
        for t in r:
            S.paste(t, (x, y)); x += t.width + 12
        y += max(t.height for t in r) + 12
    S.save(HERE / name)


if __name__ == "__main__":
    table()
    spread()
    figs = [k for k, v in R.items() if v["group"] in ("figure", "prop")]
    sheet(figs, "sheet_figures.png", 300, 4)
    sheet([k for k, v in R.items() if v["group"] == "room"], "sheet_rooms.png", 400, 3)
