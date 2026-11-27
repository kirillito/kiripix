"""`gen --motion skeleton` (ticket 0389): a sprite's clip from a character's `render`, through PixelLab's skeleton, over the fake
transport and the fake Blender. The fake Blender puts the k-th point of the character's `points` (k from 0) at 10 * (k + 1) + 0.4 px
right of the pivot and 29.3 px above it (depth 9), and each eye at 1.5 px left and 1.8 px right of the pivot, 40.4 px above it, so
the joints' fractions are known. The points to set are read from the `gen.render_points_missing` finding's `fix`."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_character_clips import IDLE
from test_character_model import HERO
from test_character_render import add_camera, ready, render_json
from test_gen import ledger
from test_gen_sprite import posts, sheet_entries, sprite
from test_sprite import FOUR, SPRITE, png_sheet, sheet_of

EIGHT = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
LABELS = ["NOSE", "NECK", "RIGHT SHOULDER", "RIGHT ELBOW", "RIGHT ARM", "LEFT SHOULDER", "LEFT ELBOW", "LEFT ARM", "RIGHT HIP",
          "RIGHT KNEE", "RIGHT LEG", "LEFT HIP", "LEFT KNEE", "LEFT LEG", "RIGHT EYE", "LEFT EYE", "RIGHT EAR", "LEFT EAR"]
SKELETON = ("--clip", "walk", "--motion", "skeleton", "--render", HERO)


def built_sprite(project: Kiripix, approve: str = "none", directions: list[str] = FOUR) -> Path:
    """A sprite whose `frames` are built: an idle clip, one 16 x 20 frame per direction."""
    folder = sprite(project, approve)
    if len(directions) == 8:
        project.json("set", SPRITE, "frames", "directions=8")
    png_sheet(project, sheet_of(directions, 1), 1, directions=directions)
    project.json("run", SPRITE, "frames")
    return folder


def points_to_set(project: Kiripix) -> str:
    """What the character's render has to record: the `fix` of `gen.render_points_missing`, which the fake Blender is given the
    bones of."""
    result = project("gen", SPRITE, *SKELETON, "--json")
    assert result.codes == ["gen.render_points_missing"]
    fix = result.json["findings"][0]["fix"]
    assert fix.startswith(f"kiripix set {HERO} render points=")
    points = fix.split("points=", 1)[1]
    bones = [entry.split("@")[1] for entry in points.split(",")]
    (project.cwd / "blender-bones").write_text(json.dumps(bones), encoding="utf-8")
    return points


def rendered(project: Kiripix, approve: str = "none", directions: list[str] = FOUR) -> tuple[Path, Path]:
    """The hero with a current render that records the points the skeleton needs, and its eyes; and the sprite whose `frames`
    are built. Returns the hero's folder and the sprite's."""
    folder = ready(project, IDLE)
    flat = built_sprite(project, approve, directions)
    project.json("run", HERO, "render")  # a render without the points
    points = points_to_set(project)
    project.json("set", HERO, "render", f"points={points}")
    project.json("set", HERO, "render", "eyes=skin")
    project.json("run", HERO, "render")
    return folder, flat


def fraction(value: float, size: int) -> float:
    return round(min(1.0, max(0.0, value / size)), 4)


def joints_of(plan: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    return {j["label"]: (j["x"], j["y"]) for j in plan}


def test_preview_writes_the_keypoints_and_the_overlay_and_sends_nothing(project: Kiripix) -> None:
    folder, _ = rendered(project)

    data = project.json("gen", SPRITE, *SKELETON, "--render-clip", "idle", "--frames", "3", "--directions", "s,e",
                        "--preview")["data"]

    assert data["sent"] is False and data["pending"] is None and data["estimated_usd"] == 0.0
    assert [p["direction"] for p in data["preview"]] == ["s", "e"]
    kept = project.cwd / ".kiripix" / "calls" / "preview" / SPRITE
    assert [p["keypoints"] for p in data["preview"]] == [f".kiripix/calls/preview/{SPRITE}/idle_{d}.json" for d in ("s", "e")]
    assert [p["overlay"] for p in data["preview"]] == [f".kiripix/calls/preview/{SPRITE}/idle_{d}_overlay.png" for d in ("s", "e")]
    assert (kept / "idle_s_overlay.png").is_file() and (kept / "idle_e_overlay.png").is_file()
    assert not (project.cwd / "pixellab-requests").exists() and ledger(project) == []
    assert not list((project.cwd / ".kiripix" / "calls").glob("*.json"))  # nothing is planned

    document = json.loads((kept / "idle_s.json").read_text("utf-8"))
    render = render_json(folder)
    width, height = render["frame"]["width"], render["frame"]["height"]
    frames = render["clips"][0]["directions"]["s"]
    count = len(frames)
    assert document["meta"]["frames"] == [frames[round(i * count / 3)]["index"] for i in range(3)]  # picked evenly
    assert len(document["keypoints"]) == 3 and all([j["label"] for j in k] == LABELS for k in document["keypoints"])
    first = frames[0]
    neck = joints_of(document["first_frame_keypoints"])["NECK"]
    assert neck == (fraction(first["pivot"][0] + 10.4, width), fraction(first["pivot"][1] - 29.3, height))  # the 1st point
    eyes = joints_of(document["first_frame_keypoints"])
    assert eyes["RIGHT EYE"] == (fraction(first["pivot"][0] - 1.5, width), fraction(first["pivot"][1] - 40.4, height))
    assert eyes["LEFT EYE"] == (fraction(first["pivot"][0] + 1.8, width), fraction(first["pivot"][1] - 40.4, height))
    assert eyes["RIGHT EYE"][0] < eyes["LEFT EYE"][0]  # the character's right is the image's left, facing the camera
    assert all(0.0 <= v <= 1.0 for x, y in eyes.values() for v in (x, y))
    assert sorted(j["z_index"] for j in document["first_frame_keypoints"]) == list(range(18))


def test_a_clip_by_skeleton_is_one_pending_call_of_two_jobs_per_direction_and_approve_stores_it(project: Kiripix) -> None:
    _, folder = rendered(project, approve="each")

    waiting = project.json("gen", SPRITE, *SKELETON, "--render-clip", "idle", "--frames", "3", "--directions", "s,e", expect=3)

    pending = waiting["data"]["pending"]
    assert waiting["data"]["jobs"] == 4 and waiting["data"]["operation"] == "motion" and waiting["data"]["preview"] == []
    assert [j["operation"] for j in pending["jobs"]] == ["estimate_skeleton", "animate_skeleton"] * 2
    assert [j["endpoint"] for j in pending["jobs"][:2]] == ["estimate-skeleton", "animate-with-skeleton-v3"]
    assert pending["jobs"][1]["needs"] == 0 and pending["jobs"][3]["needs"] == 2
    assert [j["direction"] for j in pending["jobs"]] == ["s", "s", "e", "e"]
    assert pending["estimated_usd"] == round(sum(j["estimate_usd"] for j in pending["jobs"]), 6) == 0.042
    assert [i["role"] for i in pending["inputs"]] == ["frame", "frame"]
    animate = pending["jobs"][1]["params"]
    assert len(animate["keypoints"]) == 3 and animate["retarget"]["target"] == [16, 20]  # the render's, not yet moved
    assert pending["params"]["motion"] == "skeleton" and pending["params"]["render"] == HERO
    assert not [p for p in posts(project) if "skeleton" in p["path"]] and ledger(project) == []

    sent = project.json("approve", waiting["data"]["call"], owner=True)["data"]["sent"]

    assert sent["sent"] is True and sent["clips"] == ["walk"] and sent["jobs"] == 4 and sent["usd"] == 0.042
    sent_posts = [p for p in posts(project) if "skeleton" in p["path"]]
    assert [p["path"] for p in sent_posts] == ["/estimate-skeleton", "/animate-with-skeleton-v3"] * 2
    body = sent_posts[1]["body"]
    assert body["direction"] == "south" and body["action"] == "walk" and "retarget" not in body and "write_motion_frames" not in body
    assert joints_of(body["first_frame_keypoints"])["NOSE"] == (0.5, 0.2)  # the estimate of the sprite's own frame
    moved = body["keypoints"]
    assert len(moved) == 3 and all([j["label"] for j in k] == LABELS for k in moved)
    assert joints_of(moved[0]) == joints_of(body["first_frame_keypoints"])  # the first pose is the sprite's own
    # the fake Blender's idle is still (each point at a fixed offset from an unmoving pivot), so the render's motion is none and
    # every frame retargets to the sprite's first pose
    assert all(joints_of(k) == joints_of(moved[0]) for k in moved)
    assert sent_posts[3]["body"]["direction"] == "east"
    assert sheet_entries(folder, sent["sheet"]) == sorted(
        f"animations/walk/{d}/frame_{n:03d}.png" for d in ("east", "south") for n in range(3))
    assert [line["operation"] for line in ledger(project)] == ["estimate-skeleton", "animate-with-skeleton-v3"] * 2

    project.json("run", SPRITE, "frames", expect=2)  # w and n have no walk (0179), as a rig's clip


def test_a_skeleton_motion_sends_the_stored_view_with_the_animation_only(project: Kiripix) -> None:
    rendered(project)
    project.json("gen", SPRITE, "--from-frames", "--view", "side")  # the view is set when the character is made

    project.json("gen", SPRITE, *SKELETON, "--render-clip", "idle", "--frames", "3", "--directions", "s")

    sent = {p["path"]: p["body"] for p in posts(project)}
    assert sent["/animate-with-skeleton-v3"]["view"] == "side" and "view" not in sent["/estimate-skeleton"]


def test_a_render_without_the_points_is_render_points_missing_with_the_fix(project: Kiripix) -> None:
    ready(project, IDLE)
    project.json("run", HERO, "render")
    built_sprite(project)

    result = project("gen", SPRITE, *SKELETON, "--json")

    assert result.codes == ["gen.render_points_missing"] and result.code == 1
    assert "neck" in result.json["findings"][0]["message"]
    assert result.json["findings"][0]["fix"].startswith(f"kiripix set {HERO} render points=neck@mixamorig:Neck,")
    assert not (project.cwd / "pixellab-requests").exists() and ledger(project) == []


def test_a_stale_render_is_render_stale_naming_the_run(project: Kiripix) -> None:
    rendered(project)
    project.json("set", HERO, "render", "eyes=cloth")  # the render is out of date

    result = project("gen", SPRITE, *SKELETON, "--render-clip", "idle", "--json")
    preview = project("gen", SPRITE, *SKELETON, "--render-clip", "idle", "--preview", "--json")

    assert result.codes == ["gen.render_stale"] and preview.codes == ["gen.render_stale"]
    assert result.json["findings"][0]["fix"] == f"kiripix run {HERO} render"
    assert not (project.cwd / "pixellab-requests").exists() and ledger(project) == []


def test_the_renders_directions_must_cover_the_sprites(project: Kiripix) -> None:
    rendered(project, directions=EIGHT)
    add_camera(project, "[character.camera.top34_4]\nelevation = 30\ndirections = 4\n")
    project.json("set", HERO, "render", "camera=top34_4")
    project.json("run", HERO, "render")

    result = project("gen", SPRITE, *SKELETON, "--render-clip", "idle", "--json")
    only = project("gen", SPRITE, *SKELETON, "--render-clip", "idle", "--directions", "s,e", "--preview", "--json")

    assert result.codes == ["gen.render_direction_missing"] and "sw" in result.json["findings"][0]["message"]
    assert only.code == 0


def test_flags_that_dont_fit_a_skeleton_are_refused_before_anything_is_read(project: Kiripix) -> None:
    built_sprite(project)

    no_render = project("gen", SPRITE, "--clip", "walk", "--motion", "skeleton", "--json")
    few = project("gen", SPRITE, *SKELETON, "--frames", "2", "--json")
    many = project("gen", SPRITE, *SKELETON, "--frames", "16", "--json")
    rig = project("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--render", HERO, "--prompt", "x", "--json")
    bare = project("gen", SPRITE, "--preview", "--json")

    assert no_render.codes == ["gen.render_needed"] and few.codes == ["gen.frames_range"] and many.codes == ["gen.frames_range"]
    assert rig.codes == ["gen.flag_unsupported"] and bare.codes == ["gen.preview_needs_skeleton"]
    assert not (project.cwd / "pixellab-requests").exists() and ledger(project) == []
