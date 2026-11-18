"""Trial 0238 (not Kiripix code): blender -b --factory-startup -P held_render.py -- <args.json> <result.json>
kiripix/blender/render_frames.py unchanged, plus, for option (a), what an `attach` would do:
    "held_per_clip": {<clip>: [<object names that show in that clip>]}   (the objects are in `rig_file`, hidden from renders)
The scene is set up with the body alone (camera, depth range, body material numbers), then the held things' materials are numbered
after the body's (0170: an attachment's materials come after the Model's) and the things show only in their clips. Option (c) is
the real `wearable` argument, with no wrapper code. The result carries "timing" (seconds) and "held_materials"."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rf  # noqa: E402
import bpy  # noqa: E402

ns = rf.load()
timing: dict = {}
ARGS: dict = {}
held_numbers: list = []
_set_up, _begin, _end = ns["set_up_scene"], ns["begin_clip"], ns["end_clip"]


def set_up_scene(args, armature, root_bone):
    setup = _set_up(args, armature, root_bone)
    per_clip = args.get("held_per_clip") or {}
    names = sorted({n for v in per_clip.values() for n in v})
    used = {s.material for n in names for s in bpy.data.objects[n].material_slots if s.material is not None}
    first = len(setup["materials"]) + 1
    for i, m in enumerate(sorted(used, key=lambda m: m.name), start=first):
        m.pass_index = i
        held_numbers.append({"index": i, "name": m.name})
    return setup


def begin_clip(armature, clip, root_bone, ground):
    timing.setdefault("loop_start", time.perf_counter())
    per_clip = ARGS.get("held_per_clip") or {}
    every = {n for v in per_clip.values() for n in v}
    for n in every:
        bpy.data.objects[n].hide_render = n not in per_clip.get(clip["name"], [])
    bpy.context.view_layer.update()
    return _begin(armature, clip, root_bone, ground)


def end_clip(armature, state):
    _end(armature, state)
    timing["loop_end"] = time.perf_counter()


ns.update(set_up_scene=set_up_scene, begin_clip=begin_clip, end_clip=end_clip)
sep = sys.argv.index("--")
ARGS.update(json.loads(Path(sys.argv[sep + 1]).read_text(encoding="utf-8")))
result_path = Path(sys.argv[sep + 2])
started = time.perf_counter()
try:
    result = ns["render"](ARGS)
except Exception as error:
    import traceback
    traceback.print_exc()
    result = {"error": f"{type(error).__name__}: {error}"}
timing["total_s"] = time.perf_counter() - started
if "loop_end" in timing:
    timing["loop_s"] = timing.pop("loop_end") - timing.pop("loop_start")
result["timing"] = timing
result["held_materials"] = held_numbers
result_path.write_text(json.dumps(result), encoding="utf-8")
