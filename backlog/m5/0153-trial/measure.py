import json, sys
from common import *
from kiripix.recipes.render import clip_bounds, fit_cell
args = base_args(400, [200.0, 300.0], measure=True, show=["body", "hair", "jacket", "legs", "coat", "pack"])
res = blender(args, SC / "measure.json")
bounds = {c["name"]: clip_bounds(res["frames"][c["name"]], c["root_motion"]) for c in args["clips"]}
side, pivot = fit_cell(52, list(bounds.values()))
# per clip, per object set
out = {"bounds": bounds, "cell": side, "pivot": pivot}
for name, shown in (("body", ["body"]), ("stack_jacket", ["body", "hair", "jacket", "legs", "pack"]), ("stack_coat", ["body", "hair", "legs", "coat", "pack"])):
    r = blender(base_args(400, [200.0, 300.0], measure=True, show=shown), SC / "measure.json")
    b = {c["name"]: clip_bounds(r["frames"][c["name"]], c["root_motion"]) for c in args["clips"]}
    out[name] = {"bounds": b, "fit": fit_cell(52, list(b.values()))}
(HERE / "measure_cell.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
