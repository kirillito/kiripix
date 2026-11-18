"""Trial 0153 (not Kiripix code): kiripix/blender/render_frames.py unchanged, with two args added:
    "show": [object names that render; the rest are hidden from the render], "holdout": [object names that are holdouts]
The scene is set up (camera, depth range, material numbers) with every object visible, so every scenario has the same
camera, depth scale and material numbers; the hiding and the holdout come after. A holdout object hides what is behind it,
is not drawn, and is outside the object mask (index 0). Usage as render_frames.py; the result carries "timing"."""
import json, sys, time
from pathlib import Path

RENDER_FRAMES = Path("C:/Homespace/kiripix/kiripix/blender/render_frames.py")
_code = RENDER_FRAMES.read_text(encoding="utf-8").rstrip()
assert _code.endswith("main()")
_ns: dict = {"__name__": "render_frames_trial"}
exec(compile(_code[: -len("main()")], str(RENDER_FRAMES), "exec"), _ns)
import bpy  # noqa: E402

ARGS: dict = {}
timing: dict = {}
_set_up = _ns["set_up_scene"]


def set_up_scene(args, armature, root_bone):
    found = _set_up(args, armature, root_bone)
    show, holdout = args.get("show"), set(args.get("holdout") or [])
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if show is not None:
            obj.hide_render = obj.name not in show
        if obj.name in holdout:
            obj.is_holdout = True
            obj.pass_index = 0
    bpy.context.view_layer.update()
    return found


_begin = _ns["begin_clip"]
_end = _ns["end_clip"]


def begin_clip(armature, clip, root_bone, ground):
    timing.setdefault("loop_start", time.perf_counter())
    return _begin(armature, clip, root_bone, ground)


def end_clip(armature, state):
    _end(armature, state)
    timing["loop_end"] = time.perf_counter()


_ns.update(set_up_scene=set_up_scene, begin_clip=begin_clip, end_clip=end_clip)
sep = sys.argv.index("--")
args = json.loads(Path(sys.argv[sep + 1]).read_text(encoding="utf-8"))
result_path = Path(sys.argv[sep + 2])
started = time.perf_counter()
try:
    result = _ns["render"](args)
except Exception as error:
    import traceback
    traceback.print_exc()
    result = {"error": f"{type(error).__name__}: {error}"}
timing["total_s"] = time.perf_counter() - started
if "loop_end" in timing:
    timing["loop_s"] = timing.pop("loop_end") - timing.pop("loop_start")
result["timing"] = timing
result_path.write_text(json.dumps(result), encoding="utf-8")
