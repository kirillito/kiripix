"""Trial 0170: render ms/frame of the attack clip (200 frames, CPU), without and with the stick, alternating, 4 runs each."""
import json, shutil, sys
from pathlib import Path
from run_trial import *  # noqa

scratch = Path(sys.argv[1]); asset = scratch / "projC/assets/character/mc02"; info = load(asset)
m = json.loads((Path(__file__).parent / "measures.json").read_text())
res = {"ctrl": [], "stick": []}
for n in range(4):
    for tag, weapon, frame, pv in (("ctrl", None, 78, [39.0, 68.0]), ("stick", WEAPON, m["cell_with_stick"], m["pivot_with_stick"])):
        folder = scratch / f"bench_{tag}"; shutil.rmtree(folder, ignore_errors=True)
        r = blender({**base_args(asset, info, ["attack"], frame, pv, folder, "cpu"), "weapon": weapon}, scratch / "bench.json")
        res[tag].append(round(r["timing"]["loop_s"] / 200 * 1000, 1))
res["mean_ms"] = {k: round(sum(v) / len(v), 1) for k, v in res.items() if isinstance(v, list)}
(Path(__file__).parent / "bench.json").write_text(json.dumps(res, indent=1)); print(res)
