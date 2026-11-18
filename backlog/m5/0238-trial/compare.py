"""Trial 0238 step 2, 3, 4 numbers: (a) against (c) on the outline and the stack, the body's colours when a thing is added, the atlas.
Writes compare.json."""
import json, sys
import numpy as np
from PIL import Image
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
proj = SC / "proj/assets/character"
R = SC / "render"
out = {}


def png(path):
    return np.array(Image.open(path).convert("RGBA"))


def place(small, side, offset):
    """a 78 cell frame inside a larger cell, its pivot on the larger cell's pivot"""
    big = np.zeros((side, side, 4), np.uint8)
    h, w = small.shape[:2]
    big[offset[1]:offset[1] + h, offset[0]:offset[0] + w] = small
    return big


def over(base, top):
    a = top[..., 3:4] > 0
    return np.where(a, top, base)


# 1. (c) stacked against (a): colour frames straight from Blender (before palette). A layer is pasted over the body, which is
#    in its own 78 cell; the layer's cell is the larger one for the stick.
def stack_diff(a_scen, c_scen, clip, side, offset):
    diff = total = frames = 0
    detail = []
    for d in EIGHT:
        n = len(list((R / a_scen / "color" / clip / d).glob("*.png")))
        for i in range(n):
            name = f"{i:03d}.png"
            a = png(R / a_scen / "color" / clip / d / name)
            body = place(png(R / "base" / "color" / clip / d / name), side, offset)
            layer = png(R / c_scen / "color" / clip / d / name)
            st = over(body, layer)
            diff += int((st != a).any(-1).sum())
            total += int((a[..., 3] > 0).sum())
            frames += 1
    return {"frames": frames, "visible_px": total, "differing_px": diff}


out["stack_vs_a"] = {
    "attack_stick_cell86": stack_diff("a_attack", "c_stick", "attack", 86, (4, 8)),
    **{f"{c}_phone_cell78": stack_diff("a_phone", "c_phone", c, 78, (0, 0)) for c in ("phone_in", "phone", "phone_out")}}

# 2. the thing's own pixels per clip, how many of them are hidden by the body (the holdout): thing in (a) vs thing in (c)
def thing_px(scen, clip):
    n = 0
    for d in EIGHT:
        for f in (R / scen / "mask" / clip / d).glob("*.png"):
            n += int((png(f)[..., 0] > 0).sum())
    return n
out["thing_mask_px"] = {"layer_stick_attack": thing_px("c_stick", "attack"), "layer_phone_phone": thing_px("c_phone", "phone")}
out["body_mask_px"] = {"attack": thing_px("base", "attack"), "phone": thing_px("base", "phone")}
out["a_mask_px"] = {"attack": thing_px("a_attack", "attack"), "phone": thing_px("a_phone", "phone")}

# 3. the outline: finished frames of (a) with inner lines (held_a1rows, the Asset's own setting) against silhouette only (held_a1off)
def finished(name, clip, d, i):
    return png(proj / name / "work/finish/color" / clip / d / f"{i:03d}.png")

lines = {"clips": {}}
for clip in ("phone", "attack"):
    inner = near_thing = whole = 0
    for d in EIGHT:
        n = len(list((proj / "held_a1rows/work/finish/color" / clip / d).glob("*.png")))
        for i in range(n):
            on, off = finished("held_a1rows", clip, d, i), finished("held_a1off", clip, d, i)
            changed = (on != off).any(-1)
            mat = np.array(Image.open(proj / "held_a1rows/work/render/material" / clip / d / f"{i:03d}.png"))
            thing = np.isin(mat, [13, 14, 15])
            near = np.zeros_like(thing)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    near |= np.roll(np.roll(thing, dy, 0), dx, 1)
            inner += int(changed.sum()); near_thing += int((changed & near).sum()); whole += int((on[..., 3] > 0).sum())
    lines["clips"][clip] = {"px_that_inner_lines_change": inner, "of_them_within_1px_of_the_thing": near_thing, "figure_px": whole}
out["inner_lines"] = lines

# 4. the body's colours when a thing is added: idle and walk have no thing, and are re-rendered at the new cell (86 against 78)
def drift(a_name):
    res = {}
    for clip in ("idle", "walk"):
        diff = 0; total = 0
        for d in EIGHT:
            n = len(list((proj / "held_base/work/finish/color" / clip / d).glob("*.png")))
            for i in range(n):
                base = place(finished("held_base", clip, d, i), 86, (4, 8))
                new = finished(a_name, clip, d, i)
                diff += int((base != new).any(-1).sum()); total += int((new[..., 3] > 0).sum())
        res[clip] = {"differing_px": diff, "visible_px": total}
    return res
out["body_colours_without_thing_in_frame"] = {"held_a1 (things fixed)": drift("held_a1"), "held_a1rows (a ramp row each)": drift("held_a1rows")}

# 5. atlas sizes of the real sheets
sheet = {}
for n in ("held_base", "held_a1", "held_a1rows", "held_rake"):
    j = json.loads((proj / n / "work/sheet/sheet.json").read_text())
    sheet[n] = {"cell": j["cell"], "columns": j["columns"], "atlas": j["atlas"]}
    for k in ("color", "normal", "depth"):
        sheet[n][k + "_png_bytes"] = (proj / n / "work/sheet/" / f"{k}.png").stat().st_size
out["sheets"] = sheet
(HERE / "compare.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
