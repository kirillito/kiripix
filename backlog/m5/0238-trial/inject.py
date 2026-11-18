"""Trial 0238: make a scratch Asset `held_<name>` from the built `held_base`, with the render of the named scenarios put where
`render` writes it (as 0170 did), then run palette, finish and sheet on it with Kiripix's own Stages.
Usage: inject.py <name> <cell side> <pivot x> <pivot y> <clip>=<scenario> ... [--parts <palette parts>] [--no-run]
The scenario's frames are in scratch/render/<scenario>; its result.json has each frame's pivot, eyes and points."""
import json, shutil, subprocess, sys
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *

args = sys.argv[1:]
name, side, px, py = args[0], int(args[1]), float(args[2]), float(args[3])
rest = args[4:]
parts = None
if "--parts" in rest:
    i = rest.index("--parts"); parts = rest[i + 1]; del rest[i:i + 2]
sets = []
while "--set" in rest:
    i = rest.index("--set"); sets.append(rest[i + 1]); del rest[i:i + 2]  # --set finish.inner_lines=off
run = "--no-run" not in rest
mapping = dict(a.split("=") for a in rest if "=" in a)
proj = SC / "proj"
src, dst = proj / "assets/character/held_base", proj / f"assets/character/held_{name}"
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("palette", "finish", "sheet", "out", "history.jsonl"))
work = dst / "work/render"
doc = json.loads((work / "render.json").read_text())
doc["frame"] = {"width": side, "height": side}
doc["pivot"] = [px, py]
held = {}
results = {s: json.loads((SC / f"render/{s}/result.json").read_text()) for s in set(mapping.values())}
doc["clips"] = [c for c in doc["clips"] if c["name"] in mapping]  # a trial asset with fewer clips than `clips.json`
for clip in doc["clips"]:
    scen = mapping[clip["name"]]
    res = results[scen]
    for p in ("color", "normal", "depth", "mask", "material"):
        shutil.rmtree(work / p / clip["name"], ignore_errors=True)
        shutil.copytree(SC / f"render/{scen}/{p}/{clip['name']}", work / p / clip["name"])
    for d, frames in clip["directions"].items():
        for f, found in zip(frames, res["frames"][clip["name"]][d]):
            f["pivot"] = [px, py] if clip["stationary"] else found["pivot"]  # as `render` sets it (0154)
            for key in ("eyes", "points"):
                if key in found:
                    f[key] = found[key]
    for h in res.get("held_materials", []):
        held[h["name"]] = h["index"]
    clip["bounds"] = None
for clip in doc["clips"]:
    clip.pop("bounds"), clip.pop("measure_key", None)
    # bounds are the render's own record of the fit; the sheet does not need them
doc["materials"] = doc["materials"] + [{"index": i, "name": n} for n, i in sorted(held.items(), key=lambda kv: kv[1])]
doc["depth_range"] = next(iter(results.values()))["depth_range"]
(work / "render.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
for p in ("color", "normal", "depth", "mask", "material"):
    for folder in (work / p).iterdir():
        if folder.name not in mapping:
            shutil.rmtree(folder)
print("held materials", held)
if run:
    def kpx(*a):
        r = subprocess.run(["uv", "run", "--project", str(REPO), "kiripix", *a, "--json"], cwd=proj, capture_output=True, text=True)
        return json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else r.stdout + r.stderr
    if parts:
        d = kpx("set", f"character.held_{name}", "palette", f"parts={parts}")
        print("set parts", d.get("ok"), d.get("findings") if isinstance(d, dict) else d)
    for item in sets:
        stage, kv = item.split(".", 1)
        d = kpx("set", f"character.held_{name}", stage, kv)
        print("set", item, d.get("ok") if isinstance(d, dict) else d)
    d = kpx("run", f"character.held_{name}", "--force", "--from", "palette", "--cpu")
    if isinstance(d, dict):
        print("run", d["ok"], [(r["stage"], r["outcome"]) for r in d["data"].get("results", [])], [f["code"] for f in d["findings"]])
    else:
        print(d[-2000:])
