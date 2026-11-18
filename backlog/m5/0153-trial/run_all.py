"""Trial 0153: render every scenario, one Blender process at a time; the timings go to timings.json."""
import json, shutil, sys
from common import *
ALL_J = ["body", "legs", "jacket", "hair", "pack"]
ALL_C = ["body", "legs", "coat", "hair", "pack"]
SCEN = {"body": (["body"], []), "full_jacket": (ALL_J, []), "full_coat": (ALL_C, [])}
for layer in ["hair", "legs", "jacket", "coat", "pack"]:
    SCEN["layer_" + layer] = (["body", layer], ["body"])
only = sys.argv[1:] or list(SCEN)
out_root = SC / "render"
timings = json.loads((HERE / "timings.json").read_text()) if (HERE / "timings.json").exists() else {}
for name in only:
    show, hold = SCEN[name]
    out = out_root / name
    shutil.rmtree(out, ignore_errors=True)
    args = base_args(78, [39.0, 66.0], out, show=show, holdout=hold)
    res = blender(args, SC / f"result_{name}.json")
    timings[name] = res["timing"]
    timings[name]["frames"] = sum(len(c["frames"]) for c in args["clips"]) * 8
    (HERE / "timings.json").write_text(json.dumps(timings, indent=1))
    (SC / f"result_{name}.json").replace(out / "result.json")
    print(name, res["timing"], flush=True)
