"""Trial 0238: the renders. Each scenario is one Blender process (CPU, so no GPU lock; the lock is for the GPU render), timed.
  base      the body alone, six clips, the Asset's own cell (78, pivot 39,67)
  a1        (a) attached, ONE cell for the character: phone in phone_in/phone/phone_out, stick in attack, every clip at 86
  a_attack  (a) attached, a cell per clip: attack with the stick at 86;  a_phone: the phone clips at 78
  c_stick   (c) the stick as a layer (body is a holdout) in attack, at the layer's cell 86;  c_phone: the phone layer at 78
  rake_a / rake_c   the same for a 1.5 m rake, cell 138
Usage: render_scenarios.py <name> ...   (default: all)"""
import json, shutil, sys
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *

CLIPS = ["idle", "walk", "attack", "phone_in", "phone", "phone_out"]
PHONE = ["phone_in", "phone", "phone_out"]
A = SC / "things/model_a.blend"
BODY = SC / "model.blend"
EXTRA = {"eyes": ["eyes"], "points": [{"name": "hand_r", "target": "mixamorig:RightHand"}, {"name": "hand_l", "target": "mixamorig:LeftHand"}]}
m = json.loads((HERE / "measures_cells.json").read_text())
SCEN = {
    "base":     dict(rig=BODY, clips=CLIPS, cell=(78, (39, 67))),
    "a1":       dict(rig=A, clips=CLIPS, cell=(86, (43, 75)), held={"attack": ["stick"], **{c: ["phone"] for c in PHONE}}),
    "a_attack": dict(rig=A, clips=["attack"], cell=(86, (43, 75)), held={"attack": ["stick"]}),
    "a_phone":  dict(rig=A, clips=PHONE, cell=(78, (39, 67)), held={c: ["phone"] for c in PHONE}),
    "c_stick":  dict(rig=BODY, clips=["attack"], cell=(86, (43, 75)), wearable=SC / "things/layer_stick.blend"),
    "c_phone":  dict(rig=BODY, clips=PHONE, cell=(78, (39, 67)), wearable=SC / "things/layer_phone.blend"),
    "rake_a":   dict(rig=A, clips=["attack"], cell=(138, (69, 113)), held={"attack": ["rake"]}),
    "rake_c":   dict(rig=BODY, clips=["attack"], cell=(138, (69, 113)), wearable=SC / "things/layer_rake.blend"),
}
names = sys.argv[1:] or list(SCEN)
timings = json.loads((HERE / "timings.json").read_text()) if (HERE / "timings.json").exists() else {}
for name in names:
    s = SCEN[name]
    out = SC / "render" / name
    shutil.rmtree(out, ignore_errors=True)
    side, pivot = s["cell"]
    extra = dict(EXTRA)
    if "held" in s:
        extra["held_per_clip"] = s["held"]
    if "wearable" in s:
        extra["wearable"] = {"file": str(s["wearable"])}
    args = base_args(s["rig"], s["clips"], side=side, pivot=pivot, output=out, **extra)
    res = blender("held_render.py", args, SC / f"result_{name}.json")
    frames = sum(len(c["frames"]) for c in args["clips"]) * 8
    timings[name] = {**res["timing"], "frames": frames, "ms_per_frame": round(res["timing"]["loop_s"] * 1000 / frames, 1), "cell": side}
    shutil.copy(SC / f"result_{name}.json", out / "result.json")
    print(name, timings[name], flush=True)
    (HERE / "timings.json").write_text(json.dumps(timings, indent=1))
