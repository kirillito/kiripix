"""Trial 0170: (1) how much of the stick the body hides, per direction; (2) how material numbering moves with the stick's name.
Usage: depth_and_numbering.py <scratch>"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from run_trial import *  # noqa: F401,F403

scratch = Path(sys.argv[1])
asset = scratch / "projC/assets/character/mc02"
info = load(asset)
m = json.loads((Path(__file__).parent / "measures.json").read_text())
side, pivot = m["cell_with_stick"], m["pivot_with_stick"]
out: dict = {}
# (1) the stick alone vs the full render, same cell
alone = scratch / "render_stick_alone"
shutil.rmtree(alone, ignore_errors=True)
args = base_args(asset, info, ["attack"], side, pivot, alone, "cpu")
blender({**args, "weapon": {**WEAPON, "only": True}}, scratch / "result_alone.json")
full = scratch / "render_stick"
rows = {}
for d in EIGHT:
    total = seen = front = behind_depth = 0
    for i in range(25):
        a = np.array(Image.open(alone / f"mask/attack/{d}/{i:03d}.png")) > 0
        f_mat = np.array(Image.open(full / f"material/attack/{d}/{i:03d}.png"))
        shown = f_mat == 10
        total += int(a.sum())
        seen += int((a & shown).sum())
    rows[d] = {"stick_px_if_unhidden": total, "stick_px_visible": seen, "hidden_pct": round(100 * (1 - seen / max(total, 1)), 1)}
out["hidden_by_direction"] = rows
# (2) numbering by name: a stick called `rake`, and `weapon` numbered after the Model's
for tag, spec in (("rake", {"material": "rake"}), ("weapon_last", {"number_last": True}), ("aardvark", {"material": "aardvark"})):
    folder = scratch / f"num_{tag}"
    a = base_args(asset, info, ["attack"], side, pivot, folder, "cpu")
    a["clips"][0]["frames"] = a["clips"][0]["frames"][:1]
    a["directions"] = a["directions"][:1]
    r = blender({**a, "weapon": {**WEAPON, **spec}}, scratch / f"num_{tag}.json")
    out[f"materials_{tag}"] = " ".join(f"{x['index']}:{x['name']}" for x in r["materials"])
(Path(__file__).parent / "depth_and_numbering.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
