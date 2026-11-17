"""Trial 0170 driver (plain Python, not Kiripix code). Builds render_frames args for mc02 from a built scratch Project, runs
weapon_render.py in Blender, and fits the cell with Kiripix's own fit_cell. Usage: run_trial.py <project> <step> ..."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from kiripix.recipes.render import YAW, fit_cell, clip_bounds  # noqa: E402  (read-only import of the cell fit)

BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
HERE = Path(__file__).resolve().parent
EIGHT = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
WEAPON = {"clips": ["attack"], "bone": "RightHand", "length": 1.18, "radius": 0.04, "material": "weapon",
          "colour": [0.55, 0.32, 0.12], "grip": 0.25, "along": "x"}


def load(asset: Path) -> dict:
    clips = json.loads((asset / "work/clips/clips.json").read_text())["clips"]
    rig = json.loads((asset / "work/rig/rig.json").read_text())
    model = json.loads((asset / "work/model/model.json").read_text())
    render = json.loads((asset / "work/render/render.json").read_text())
    return {"clips": clips, "rig": rig, "model": model, "render": render}


def base_args(asset: Path, info: dict, only: list[str], frame: int, pivot: list[float], output: Path, device: str) -> dict:
    render = info["render"]
    files = {p.name.split(".")[0]: str(p) for p in (asset / "src/clips").glob("*.fbx")}
    return {
        "rig_file": str(asset / "src/rigged" / info["rig"]["file"]), "root": ["root", info["rig"]["mapping"]["hips"]],
        "model_height": float(info["model"]["height"]),
        "clips": [{"name": c["name"], "action": c["action"], "file": files[c["source"]], "frames": c["frames"],
                   "root_motion": bool(c["root_motion"])} for c in info["clips"] if c["name"] in only],
        "directions": [{"name": d, "yaw": YAW[d]} for d in EIGHT], "elevation": render["elevation"], "frame": [frame, frame],
        "px_per_unit": render["px_per_unit"], "pivot": pivot, "toon": render["toon"], "device": device, "output": str(output)}


def blender(args: dict, result: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / "args.json"
        a.write_text(json.dumps(args))
        subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                        str(HERE / "weapon_render.py"), "--", str(a), str(result)], check=True,
                       stdout=subprocess.DEVNULL)
    out = json.loads(result.read_text())
    if "error" in out:
        raise SystemExit(out["error"])
    return out
