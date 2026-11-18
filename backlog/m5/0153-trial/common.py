"""Trial 0153 helpers (plain Python)."""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "C:/Homespace/kiripix")
BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
HERE = Path(__file__).resolve().parent
SC = Path("C:/Users/KIRILL~1.BRE/AppData/Local/Temp/claude/2a77692328d6afa9/5996f737-0349-4a66-8947-8351433c27d3/scratchpad")
ASSET = Path("C:/Homespace/urban-mystery-club-art/assets/character/mc03_male_clothes01")
EIGHT = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
FRAMES = {"idle": 1, "walk": 8, "attack": 19}  # idle is a still, 24 identical frames; one is enough


def clips():
    table = json.loads((ASSET / "work/clips/clips.json").read_text())["clips"]
    files = {p.name.split(".")[0]: str(p) for p in (ASSET / "src/clips").glob("*.fbx")}
    out = []
    for c in table:
        if c["name"] in FRAMES:
            out.append({"name": c["name"], "action": c["action"], "file": files[c["source"]],
                        "frames": c["frames"][: FRAMES[c["name"]]], "root_motion": bool(c["root_motion"])})
    return sorted(out, key=lambda c: list(FRAMES).index(c["name"]))


def base_args(frame, pivot, output=None, **extra):
    from kiripix.recipes.render import YAW
    render = json.loads((ASSET / "work/render/render.json").read_text())
    args = {"rig_file": str(SC / "rig.blend"), "root": ["root", "mixamorig:Hips"], "model_height": 2.0, "clips": clips(),
            "directions": [{"name": d, "yaw": YAW[d]} for d in EIGHT], "elevation": render["elevation"],
            "frame": [frame, frame], "px_per_unit": render["px_per_unit"], "pivot": pivot, "toon": render["toon"],
            "device": "cpu"}
    if output:
        args["output"] = str(output)
    args.update(extra)
    return args


def blender(args, result):
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / "args.json"
        a.write_text(json.dumps(args))
        subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                        str(HERE / "render_layers.py"), "--", str(a), str(result)], check=True, stdout=subprocess.DEVNULL)
    out = json.loads(Path(result).read_text())
    if "error" in out:
        raise SystemExit(out["error"])
    return out
