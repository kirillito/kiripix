"""Trial 0238: the extents of every clip, as render_frames's own measure pass gives them, and the cell Kiripix's fit_cell makes of
them: the body alone, (a) the things attached (phone in phone, phone_in, phone_out; stick or rake in attack), and (c) each thing
alone as a Wearable (the body hidden). Writes measures_cells.json."""
import json, sys
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
from kiripix.recipes.render import clip_bounds, fit_cell

CLIPS = ["idle", "walk", "attack", "phone_in", "phone", "phone_out"]
PHONE = ["phone_in", "phone", "phone_out"]
FOLLOW = {c["name"]: bool(c["root_motion"]) for c in clip_table()}
FRAMES = {c["name"]: len(c["frames"]) for c in clip_table()}


def measure(rig, names, per_clip=None, wearable=None):
    args = base_args(rig, names, measure=True)
    if per_clip:
        args["held_per_clip"] = per_clip
    if wearable:
        args["wearable"] = {"file": str(wearable)}
    r = blender("held_render.py", args, SC / "measure_result.json")
    out = {}
    for name in names:
        out[name] = clip_bounds(r["frames"][name], FOLLOW[name])
    return out


def cells(bounds):
    per = {n: fit_cell(52, [b]) for n, b in bounds.items()}
    one = fit_cell(52, list(bounds.values()))
    return {"per_clip": {n: [s, p] for n, (s, p) in per.items()}, "one": [one[0], one[1]], "bounds": bounds}


res = {}
res["body"] = cells(measure(SC / "model.blend", CLIPS))
A = SC / "things/model_a.blend"
for weapon in ("stick", "rake"):
    per_clip = {"attack": [weapon], **{c: ["phone"] for c in PHONE}}
    res[f"a_{weapon}"] = cells(measure(A, CLIPS, per_clip))
for thing, clips in (("phone", PHONE), ("stick", ["attack"]), ("rake", ["attack"])):
    res[f"c_{thing}"] = cells(measure(SC / "model.blend", clips, wearable=SC / f"things/layer_{thing}.blend"))
(HERE / "measures_cells.json").write_text(json.dumps(res, indent=1))
for k, v in res.items():
    print(k, "one", v["one"], {n: c[0] for n, c in v["per_clip"].items()})
