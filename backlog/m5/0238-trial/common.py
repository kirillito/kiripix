"""Trial 0238 helpers (plain Python, not Kiripix code): paths, the mc03_male_clothes01 clips as render_frames args, a Blender call."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
ASSET = Path("C:/Workspace/urban-mystery-club-art/assets/character/mc03_male_clothes01")  # read only
SC = Path("C:/Users/Kirill/AppData/Local/Temp/claude/e7ccd5c4395c2f79/d37c99bd-e08f-4e58-95e9-b481c39f9155/scratchpad")
EIGHT = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
HAND = "mixamorig:RightHand"


def clip_table() -> list:
    return json.loads((ASSET / "work/clips/clips.json").read_text())["clips"]


def clips(names):
    """render_frames clips for the named clips of the Asset (a transition is not used)."""
    files = {p.name.split(".")[0]: str(p) for p in (ASSET / "src/clips").glob("*.fbx")}
    out = {c["name"]: {"name": c["name"], "action": c["action"], "file": files[c["source"]], "frames": c["frames"],
                       "root_motion": bool(c["root_motion"])} for c in clip_table() if "transition" not in c}
    return [out[n] for n in names]


def base_args(rig_file, names, side=78, pivot=(39.0, 67.0), output=None, device="cpu", frames=None, directions=EIGHT, **extra):
    from kiripix.recipes.render import YAW
    render = json.loads((ASSET / "work/render/render.json").read_text())
    use = clips(names)
    if frames:
        for c in use:
            c["frames"] = c["frames"][: frames]
    args = {"rig_file": str(rig_file), "root": ["root", "mixamorig:Hips"], "model_height": 2.0, "clips": use,
            "directions": [{"name": d, "yaw": YAW[d]} for d in directions], "elevation": render["elevation"],
            "frame": [side, side], "px_per_unit": render["px_per_unit"], "pivot": list(pivot), "toon": render["toon"],
            "device": device}
    if output:
        args["output"] = str(output)
    args.update(extra)
    return args


def blender(script, args, result, extra_args=()):
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / "args.json"
        a.write_text(json.dumps(args))
        done = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                               str(HERE / script), "--", str(a), str(result), *extra_args], capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(done.stdout[-3000:] + done.stderr[-2000:])
    out = json.loads(Path(result).read_text())
    if "error" in out:
        raise SystemExit(out["error"])
    return out
