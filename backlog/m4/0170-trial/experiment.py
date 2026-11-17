"""Trial 0170: measure the cell with the stick, then render attack with and without it (CPU, timed). Usage: experiment.py <scratch>"""
import json
import shutil
import sys
from pathlib import Path

from run_trial import *  # noqa: F401,F403

scratch = Path(sys.argv[1])
asset = scratch / "projC/assets/character/mc02"
info = load(asset)
render = info["render"]
height, bounds = render["height"], {c["name"]: c["bounds"] for c in render["clips"]}
out: dict = {"baseline_cell": render["frame"]["width"], "baseline_pivot": render["pivot"], "baseline_bounds": bounds}
args = base_args(asset, info, ["attack"], render["frame"]["width"], render["pivot"], scratch / "unused", "cpu")
measured = blender({**args, "measure": True, "weapon": WEAPON}, scratch / "measure_stick.json")["frames"]
stick_bounds = clip_bounds(measured["attack"], True)
out["attack_bounds_with_stick"] = stick_bounds
side, pivot = fit_cell(height, [stick_bounds, bounds["idle"], bounds["walk"]])
out["cell_with_stick"], out["pivot_with_stick"] = side, pivot
side_a, pivot_a = fit_cell(height, [stick_bounds])
out["cell_attack_only_with_stick"] = side_a
for tag, weapon, frame, pv in (("ctrl", None, render["frame"]["width"], render["pivot"]), ("stick", WEAPON, side, pivot)):
    folder = scratch / f"render_{tag}"
    shutil.rmtree(folder, ignore_errors=True)
    a = base_args(asset, info, ["attack"], frame, pv, folder, "cpu")
    result = blender({**a, "weapon": weapon}, scratch / f"result_{tag}.json")
    out[f"timing_{tag}"] = result["timing"]
    out[f"materials_{tag}"] = result["materials"]
    out[f"depth_range_{tag}"] = result["depth_range"]
    (scratch / f"result_{tag}.json").write_text(json.dumps(result))
(Path(__file__).parent / "measures.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
