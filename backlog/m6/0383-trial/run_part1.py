"""Trial 0383, part 1: everything that is free, in one go. Prototype (not Kiripix code); reads the art Project, writes only the scratch
folder and this folder.

    uv run python run_part1.py <scratch folder>

1. render_views.py: the four views of mc03_female's body (analysis and the colour self-test on) -> <scratch>/views
2. project_views.py with the unpainted views (identity round trip) -> <scratch>/proj_id, re-render -> <scratch>/rt_id, measure
3. synth_paintings.py, project_views.py with them -> <scratch>/proj_syn, re-render (also from other angles) -> <scratch>/rt_syn, measure
4. make_visual.py -> results/roundtrip_sheet.png
5. test_measure_drift.py on the stick figure and the real front mask -> results/test_measure_drift.json
6. copies what the Owner and the ticket need: views/ (colour, mask, camera.json) and results/.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
MODEL = "C:/Workspace/urban-mystery-club-art/assets/character/mc03_female/work/model/model.blend"  # opened, never saved
VIEWS = ["front", "back", "left", "right"]


def blender(script: str, args: dict, scratch: Path, tag: str) -> dict:
    a, r = scratch / f"{tag}_args.json", scratch / f"{tag}_result.json"
    a.write_text(json.dumps(args))
    done = subprocess.run([BLENDER, "-b", "-P", str(HERE / script), "--python-exit-code", "1", "--", str(a), str(r)], capture_output=True, text=True)
    if done.returncode != 0:
        sys.exit(done.stdout[-3000:] + done.stderr[-2000:])
    return json.loads(r.read_text())


def python(script: str, *args: str) -> str:
    done = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True)
    if done.returncode != 0:
        sys.exit(done.stdout[-3000:] + done.stderr[-2000:])
    return done.stdout


def main() -> None:
    scratch = Path(sys.argv[1]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    s = scratch.as_posix()
    results = HERE / "results"
    results.mkdir(exist_ok=True)

    render = blender("render_views.py", {"model": MODEL, "out": f"{s}/views", "views": VIEWS, "analyse": True, "selftest": True}, scratch, "render")
    (results / "model_report.json").write_text(json.dumps(render, indent=1))

    painted_id = {v: f"{s}/views/{v}_color_exact.png" for v in VIEWS}
    blender("project_views.py", {"model": MODEL, "views_dir": f"{s}/views", "out": f"{s}/proj_id", "painted": painted_id}, scratch, "proj_id")
    blender("render_views.py", {"model": f"{s}/proj_id/model_uv.blend", "out": f"{s}/rt_id", "views": VIEWS, "uv": "kpx_paint",
                                "texture": f"{s}/proj_id/texture.png"}, scratch, "rt_id")
    python("roundtrip_measure.py", f"{s}/views", f"{s}/rt_id", "--out", str(results / "roundtrip_identity.json"))
    shutil.copy(scratch / "proj_id" / "texture_stats.json", results / "projection_identity_stats.json")

    python("synth_paintings.py", f"{s}/views", f"{s}/synth")
    blender("project_views.py", {"model": MODEL, "views_dir": f"{s}/views", "out": f"{s}/proj_syn",
                                 "painted": {v: f"{s}/synth/{v}_painted.png" for v in VIEWS}}, scratch, "proj_syn")
    blender("render_views.py", {"model": f"{s}/proj_syn/model_uv.blend", "out": f"{s}/rt_syn", "uv": "kpx_paint", "texture": f"{s}/proj_syn/texture.png",
                                "views": VIEWS + ["q45", "q135", "q225", "q315", "top"]}, scratch, "rt_syn")
    python("roundtrip_measure.py", f"{s}/synth", f"{s}/rt_syn", "--out", str(results / "roundtrip_synthetic.json"))
    shutil.copy(scratch / "proj_syn" / "texture_stats.json", results / "projection_synthetic_stats.json")
    python("make_visual.py", f"{s}/views", f"{s}/rt_id", f"{s}/synth", f"{s}/rt_syn", str(results / "roundtrip_sheet.png"))
    for name in ("texture", "texture_coverage", "texture_winner"):
        shutil.copy(scratch / "proj_id" / f"{name}.png", results / f"identity_{name}.png")

    # a constant texture must come back byte for byte
    blender("render_views.py", {"model": f"{s}/proj_id/model_uv.blend", "out": f"{s}/rt_const", "views": ["front"], "uv": "kpx_paint",
                                "texture": "const:200,100,50"}, scratch, "rt_const")

    print(python("test_measure_drift.py", f"{s}/views/front_mask.png"))

    views = HERE / "views"
    views.mkdir(exist_ok=True)
    for v in VIEWS:
        shutil.copy(scratch / "views" / f"{v}_color.png", views / f"{v}_color.png")
        shutil.copy(scratch / "views" / f"{v}_mask.png", views / f"{v}_mask.png")
    shutil.copy(scratch / "views" / "camera.json", views / "camera.json")
    packet = HERE / "packet"
    packet.mkdir(exist_ok=True)
    shutil.copy(scratch / "views" / "front_color.png", packet / "front_view.png")


if __name__ == "__main__":
    main()
