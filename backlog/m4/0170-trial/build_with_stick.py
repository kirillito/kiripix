"""Trial 0170: make a scratch Project `projS` from the built baseline `projC`, with mc02's render replaced by one where the attack
clip carries the stick and the cell is the fitted one (every clip re-rendered at that size). Then palette, finish and sheet are run
on it with Kiripix's own Stages (kiripix run --force palette). Usage: build_with_stick.py <scratch>"""
import json
import shutil
import sys
from pathlib import Path

from run_trial import *  # noqa: F401,F403

scratch = Path(sys.argv[1])
shutil.rmtree(scratch / "projS", ignore_errors=True)
shutil.copytree(scratch / "projC", scratch / "projS")
asset = scratch / "projS/assets/character/mc02"
measures = json.loads((Path(__file__).parent / "measures.json").read_text())
side, pivot = measures["cell_with_stick"], measures["pivot_with_stick"]
info = load(asset)
folder = scratch / "render_all_stick"
shutil.rmtree(folder, ignore_errors=True)
args = base_args(asset, info, [c["name"] for c in info["clips"]], side, pivot, folder, "cpu")
result = blender({**args, "weapon": WEAPON}, scratch / "result_all_stick.json")
render = info["render"]
render.update(frame={"width": side, "height": side}, pivot=pivot, depth_range=result["depth_range"], materials=result["materials"])
bounds = {"attack": measures["attack_bounds_with_stick"]}
for clip in render["clips"]:
    if clip["name"] in bounds:
        clip["bounds"] = bounds[clip["name"]]
    for direction, frames in clip["directions"].items():
        for frame, found in zip(frames, result["frames"][clip["name"]][direction]):
            frame["pivot"] = list(pivot) if clip["stationary"] else found["pivot"]
shutil.rmtree(asset / "work/render/color")
for p in ("color", "normal", "depth", "mask", "material"):
    shutil.rmtree(asset / "work/render" / p, ignore_errors=True)
    shutil.copytree(folder / p, asset / "work/render" / p)
(asset / "work/render/render.json").write_text(json.dumps(render, indent=2))
print("total s", result["timing"])
