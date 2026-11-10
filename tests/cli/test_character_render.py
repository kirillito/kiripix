"""The `render` Stage (ticket 0104, spec §6.3). The CLI tests run on the fake Blender of `kiripix_test_recipes.py`, which writes
flat frames of the size it is asked for. The marked tests run the real Blender 5.2 on the fixture Models, at a low
resolution, and check sizes, passes, counts and the pivot, never pixels (ADR 0010)."""

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix, stage_status
from PIL import Image
from test_character_clips import HIT, IDLE, WALK, add_source, blender_script, clip, real_hero, rigged_hero
from test_character_model import FIXTURES, HERO, calls, set_blender
from test_locks import wait_for
from test_serve import Server, server  # noqa: F401 - the `server` fixture

DIRECTIONS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]


def render_json(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work" / "render" / "render.json").read_text("utf-8"))
    return document


def render_calls(project: Kiripix) -> list[dict[str, Any]]:
    return [c for c in calls(project) if c["script"] == "render_frames"]


def ready(project: Kiripix, *clips: dict[str, Any]) -> Path:
    folder = rigged_hero(project)
    for data in clips or (IDLE, HIT):
        clip(project, data)
    project.json("run", HERO, "clips")
    return folder


def add_camera(project: Kiripix, text: str) -> None:
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8") + "\n" + text, encoding="utf-8")


def test_run_writes_every_clip_direction_and_frame_and_render_json(project: Kiripix) -> None:
    folder = ready(project)

    result = project.json("run", HERO, "render")

    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("render", "done")]
    document = render_json(folder)
    assert document["schema_version"] == 1 and document["camera"] == "top34_8" and document["height"] == 52
    assert document["frame"] == {"width": 78, "height": 78} and document["directions"] == DIRECTIONS
    assert document["pivot"] == [39.0, 72.0] and document["depth_range"] == [8.0, 12.0]
    assert [c["name"] for c in document["clips"]] == ["hit", "idle"]
    hit = document["clips"][0]
    assert hit["fps"] == 15 and hit["loop"] is False and hit["stationary"] is False
    assert list(hit["directions"]) == DIRECTIONS and len(hit["directions"]["sw"]) == 4
    frame = hit["directions"]["sw"][2]
    assert frame["index"] == 2 and frame["source_frame"] == 4 and frame["pivot"] == [39.0, 72.0]
    assert frame["files"] == {p: f"{p}/hit/sw/002.png" for p in ("color", "normal", "depth", "mask")}
    assert len(document["clips"][1]["directions"]["s"]) == 10
    total = 0
    for entry in document["clips"]:
        for frames in entry["directions"].values():
            for item in frames:
                for name in item["files"].values():
                    path = folder / "work" / "render" / name
                    assert Image.open(path).size == (78, 78)
                    total += 1
    assert total == 8 * 14 * 4
    [call] = render_calls(project)
    assert call["args"]["device"] == "gpu" and call["args"]["elevation"] == 30
    assert [d["yaw"] for d in call["args"]["directions"]] == [0, -45, -90, -135, 180, 135, 90, 45]
    assert project.json("next", HERO)["data"]["stage"] == "palette"


def test_cpu_renders_without_the_gpu(project: Kiripix) -> None:
    ready(project)

    project.json("run", HERO, "render", "--cpu")

    assert render_calls(project)[0]["args"]["device"] == "cpu"


def test_the_stage_takes_the_gpu_lock(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "render")["data"]["kinds"]

    [stage] = kind["stages"]

    assert stage["gpu"] is True
    assert {p["name"] for p in stage["params"]} == {"height", "camera", "bands", "shadow"}
    by_name = {p["name"]: p for p in stage["params"]}
    assert (by_name["bands"]["minimum"], by_name["bands"]["maximum"], by_name["bands"]["default"]) == (2, 4, 3)


def test_the_same_inputs_are_skipped(project: Kiripix) -> None:
    ready(project)
    project.json("run", HERO, "render")

    again = project.json("run", HERO, "render")

    assert again["data"]["results"][0]["outcome"] == "skipped" and len(render_calls(project)) == 1


def test_moving_blender_leaves_every_blender_stage_done_and_a_new_version_makes_them_stale(project: Kiripix) -> None:
    ready(project)
    project.json("run", HERO, "render")
    stages = ("model", "rig", "clips", "render")
    assert [stage_status(project, HERO)[s] for s in stages] == ["done"] * 4

    set_blender(project, str(project.cwd / "elsewhere" / "blender.exe"))  # the same Blender, found at another path

    assert [stage_status(project, HERO)[s] for s in stages] == ["done"] * 4
    assert project.json("run", HERO, "render")["data"]["results"][0]["outcome"] == "skipped"
    (project.cwd / "blender-version").write_text("5.3", encoding="utf-8")  # the fake reports another Blender version

    assert [stage_status(project, HERO)[s] for s in stages] == ["stale"] * 4


def test_launch_still_gets_the_blender_path_from_the_setting(project: Kiripix) -> None:
    folder = ready(project)
    set_blender(project, "some/blender.exe")

    project.json("run", HERO, "render")

    assert {c["executable"] for c in calls(project)[-1:]} == {"some/blender.exe"}
    assert folder.is_dir()


def test_changing_the_camera_makes_render_stale(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")
    assert stage_status(project, HERO)["render"] == "done"

    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8").replace("elevation = 30", "elevation = 35"), encoding="utf-8")

    assert stage_status(project, HERO)["render"] == "stale"
    project.json("run", HERO, "render")
    assert render_json(folder)["elevation"] == 35 and render_calls(project)[-1]["args"]["elevation"] == 35


def test_a_camera_parameter_picks_another_preset_with_four_directions(project: Kiripix) -> None:
    folder = ready(project)
    add_camera(project, "[character.camera.top34_4]\nelevation = 30\ndirections = 4\n")
    project.json("set", HERO, "render", "camera=top34_4")

    project.json("run", HERO, "render")

    document = render_json(folder)
    assert document["camera"] == "top34_4" and document["directions"] == ["s", "w", "n", "e"]
    assert sorted(p.name for p in (folder / "work" / "render" / "color" / "hit").iterdir()) == ["e", "n", "s", "w"]


def test_toon_defaults_and_the_light_reach_blender(project: Kiripix) -> None:
    ready(project)

    project.json("run", HERO, "render")

    [call] = render_calls(project)
    assert call["args"]["toon"] == {"bands": 3, "shadow": 0.5, "light": {"angle": -45.0, "tilt": 35.0}}


def test_changing_bands_or_shadow_makes_render_stale_and_reaches_blender(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")
    assert stage_status(project, HERO)["render"] == "done"

    project.json("set", HERO, "render", "bands=4")
    assert stage_status(project, HERO)["render"] == "stale"
    project.json("run", HERO, "render")
    assert render_calls(project)[-1]["args"]["toon"]["bands"] == 4
    assert render_json(folder)["toon"]["bands"] == 4

    project.json("set", HERO, "render", "shadow=0.8")
    assert stage_status(project, HERO)["render"] == "stale"
    project.json("run", HERO, "render")
    assert render_calls(project)[-1]["args"]["toon"]["shadow"] == 0.8


def test_bands_outside_2_to_4_are_refused(project: Kiripix) -> None:
    ready(project)

    for value in ("1", "5"):
        result = project.json("set", HERO, "render", f"bands={value}", expect=1)
        assert result["ok"] is False and result["findings"]


def test_the_light_belongs_to_the_camera_preset(project: Kiripix) -> None:
    ready(project)
    path = project.cwd / "kiripix.toml"
    text = re.sub(r"(?m)^light_angle = -45\b", "light_angle = 60", path.read_text("utf-8"))
    path.write_text(re.sub(r"(?m)^light_tilt = 35\b", "light_tilt = 20", text), encoding="utf-8")
    assert stage_status(project, HERO)["render"] == "todo"

    project.json("run", HERO, "render")
    path.write_text(path.read_text("utf-8").replace("light_angle = 60", "light_angle = 80"), encoding="utf-8")

    assert render_calls(project)[0]["args"]["toon"]["light"] == {"angle": 60.0, "tilt": 20.0}
    assert stage_status(project, HERO)["render"] == "stale"


def test_height_sets_the_frame_size(project: Kiripix) -> None:
    folder = ready(project)
    project.json("set", HERO, "render", "height=26")

    project.json("run", HERO, "render")

    document = render_json(folder)
    assert document["height"] == 26 and document["frame"] == {"width": 40, "height": 40}
    assert document["pivot"] == [20.0, 37.0]
    assert render_calls(project)[0]["args"]["px_per_unit"] == pytest.approx(26 / (2.0 * 0.866025), abs=1e-4)


def test_an_unknown_camera_names_the_setting(project: Kiripix) -> None:
    folder = ready(project)
    project.json("set", HERO, "render", "camera=battle")

    [finding] = project.json("run", HERO, "render", expect=3)["findings"]

    assert finding["code"] == "render.camera_unknown" and finding["fix"] is None
    assert "[character.camera.battle]" in finding["owner_action"] and "top34_8" in finding["message"]
    assert not (folder / "work" / "render").exists()


def test_a_new_clip_makes_render_stale_and_is_rendered(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")

    clip(project, WALK)
    assert stage_status(project, HERO)["clips"] == "stale"
    project.json("run", HERO, "clips")
    assert stage_status(project, HERO)["render"] == "stale"
    project.json("run", HERO, "render")

    assert [c["name"] for c in render_json(folder)["clips"]] == ["hit", "idle", "walk"]
    assert [c["name"] for c in render_calls(project)[-1]["args"]["clips"]] == ["walk"]  # ticket 0119: the others are kept


def test_a_clip_source_file_and_root_motion_reach_blender(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_source(project, "stroll", height=2.0, actions=[{"name": "stroll", "start": 0, "end": 30, "travel": 1.5}])
    clip(project, {"name": "stroll", "source": "stroll", "start": 0, "end": 30, "fps": 10, "loop": True})
    clip(project, IDLE)
    project.json("run", HERO, "clips")

    project.json("run", HERO, "render")

    by_name = {c["name"]: c for c in render_calls(project)[0]["args"]["clips"]}
    assert by_name["stroll"]["file"].endswith(".fbx") and "clips" in Path(by_name["stroll"]["file"]).parts
    assert by_name["stroll"]["root_motion"] is True and by_name["idle"]["file"] is None
    assert by_name["idle"]["root_motion"] is False and by_name["idle"]["action"] == "idle"
    assert render_calls(project)[0]["args"]["rig_file"].endswith("model.blend")
    assert render_json(folder)["clips"][1]["root_motion"] is True


def test_a_cancelled_render_leaves_the_stage_as_it_was(project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = ready(project)
    hold = project.cwd / "hold-blender"
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": HERO, "stage": "render"}
    caller = threading.Thread(
        target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "r"})))
    try:
        caller.start()
        wait_for(project.cwd / "blender-holding")
        server.call("/api/jobs/r/cancel")
        caller.join(timeout=30)
    finally:
        hold.unlink(missing_ok=True)

    [reply] = replies
    assert reply.codes == ["run.cancelled"]
    assert stage_status(project, HERO)["render"] == "todo"
    assert not (folder / "work" / "render").exists()


# ticket 0119: render keeps the clips that didn't change


def tree(folder: Path) -> dict[str, bytes]:
    """Everything in the Stage's output but its stamp (which holds a time), by relative path."""
    root = folder / "work" / "render"
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and p.name != ".stage.json"}


def rendered(project: Kiripix) -> list[str]:
    return [c["name"] for c in render_calls(project)[-1]["args"]["clips"]]


def render_message(project: Kiripix, *args: str) -> str:
    return str(project.json("run", HERO, "render", *args)["data"]["results"][0]["message"])


def add_walk_and_run(project: Kiripix) -> None:
    clip(project, WALK)
    project.json("run", HERO, "clips")


def test_adding_a_clip_renders_only_that_clip_and_the_output_equals_a_full_rebuild(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")
    first = tree(folder)
    add_walk_and_run(project)

    message = render_message(project)

    assert rendered(project) == ["walk"] and len(render_calls(project)) == 2
    assert "16" in message and "reused" in message  # hit and idle, 8 directions each
    kept = tree(folder)
    assert all(kept[name] == data for name, data in first.items() if name != "render.json")
    assert [c["name"] for c in render_json(folder)["clips"]] == ["hit", "idle", "walk"]
    render_message(project, "--force")  # a full rebuild
    assert tree(folder) == kept


def test_a_changed_clip_alone_is_rendered_again(project: Kiripix) -> None:
    folder = ready(project, IDLE, HIT, WALK)
    project.json("run", HERO, "render")
    project.json("undo", HERO, "clips")  # walk goes, and comes back longer
    clip(project, {**WALK, "end": 20})
    project.json("run", HERO, "clips")

    project.json("run", HERO, "render")

    assert rendered(project) == ["walk"]
    kept = tree(folder)
    render_message(project, "--force")
    assert tree(folder) == kept


def test_a_camera_change_renders_every_clip(project: Kiripix) -> None:
    ready(project)
    project.json("run", HERO, "render")
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8").replace("elevation = 30", "elevation = 35"), encoding="utf-8")

    project.json("run", HERO, "render")

    assert rendered(project) == ["hit", "idle"]


def test_other_render_settings_render_every_clip(project: Kiripix) -> None:
    ready(project)
    project.json("run", HERO, "render")
    for setting in ("height=26", "bands=4", "shadow=0.8"):
        project.json("set", HERO, "render", setting)
        project.json("run", HERO, "render")
        assert rendered(project) == ["hit", "idle"], setting


def test_the_device_is_part_of_the_key(project: Kiripix) -> None:
    ready(project)
    project.json("run", HERO, "render")

    project.json("run", HERO, "render", "--force", "--cpu")
    assert rendered(project) == ["hit", "idle"]
    project.json("run", HERO, "render", "--force")  # GPU again: renders differ from CPU (ADR 0010)
    assert rendered(project) == ["hit", "idle"]


def test_frames_rendered_on_the_cpu_for_want_of_a_gpu_are_kept_as_cpu_frames(project: Kiripix) -> None:
    ready(project)
    (project.cwd / "blender-no-gpu").write_text("", encoding="utf-8")

    message = render_message(project)

    assert "no GPU" in message and "--cpu" in message
    add_walk_and_run(project)
    render_message(project, "--cpu")
    assert rendered(project) == ["walk"]  # hit and idle were CPU frames, so a CPU run keeps them


def test_a_new_blender_version_or_a_new_model_renders_every_clip(project: Kiripix) -> None:
    ready(project)
    project.json("run", HERO, "render")
    (project.cwd / "blender-version").write_text("5.3", encoding="utf-8")
    for stage in ("model", "rig", "clips", "render"):
        project.json("run", HERO, stage)

    assert rendered(project) == ["hit", "idle"]
    assert len(render_calls(project)) == 2


def test_force_renders_everything(project: Kiripix) -> None:
    ready(project)
    project.json("run", HERO, "render")

    message = render_message(project, "--force")

    assert rendered(project) == ["hit", "idle"] and "reused" not in message


def test_a_removed_clip_needs_no_blender_and_the_output_equals_a_full_rebuild(project: Kiripix) -> None:
    folder = ready(project, IDLE, HIT, WALK)
    project.json("run", HERO, "render")
    project.json("undo", HERO, "clips")  # the walk clip goes
    project.json("run", HERO, "clips")

    message = render_message(project)

    assert len(render_calls(project)) == 1 and "16" in message  # no clip changed: no Blender call
    assert not (folder / "work" / "render" / "color" / "walk").exists()
    assert [c["name"] for c in render_json(folder)["clips"]] == ["hit", "idle"]
    kept = tree(folder)
    render_message(project, "--force")
    assert tree(folder) == kept


def test_an_older_render_without_clip_keys_is_rendered_whole(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")
    path = folder / "work" / "render" / "render.json"
    document = json.loads(path.read_text("utf-8"))
    for entry in document["clips"]:
        del entry["key"]
    path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    add_walk_and_run(project)

    result = project.json("run", HERO, "render")

    assert result["ok"] is True and rendered(project) == ["hit", "idle", "walk"]


def test_a_damaged_previous_render_is_rendered_whole(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")
    (folder / "work" / "render" / "color" / "hit" / "s" / "000.png").unlink()  # a kept frame is missing
    add_walk_and_run(project)

    project.json("run", HERO, "render")

    assert rendered(project) == ["hit", "walk"]  # only the clip with a missing frame is made again
    assert (folder / "work" / "render" / "color" / "hit" / "s" / "000.png").is_file()


def test_progress_events_say_how_many_were_reused(project: Kiripix) -> None:
    ready(project)
    project.json("run", HERO, "render")
    add_walk_and_run(project)

    result = project("run", HERO, "render", "--json", "--progress", "jsonl")

    events = [json.loads(line) for line in result.stderr.splitlines()]
    assert any(e["event"] == "stage_progress" and "reused 16" in e["message"] for e in events)


# the real Blender


def real_frames(folder: Path) -> list[Path]:
    return sorted((folder / "work" / "render").rglob("*.png"))


@pytest.mark.blender
@pytest.mark.parametrize("file", ["rigged.fbx", "rigged.glb"])
def test_the_walk_fixture_renders_8_directions_at_the_target_size(project: Kiripix, file: str) -> None:
    folder = real_hero(project, file)
    clip(project, {"name": "walk", "source": "walk", "start": 1, "end": 25, "fps": 3, "loop": True}, test_recipes=False)
    clip(project, {"name": "idle", "source": "idle", "start": 1, "end": 25, "fps": 2, "loop": True, "stationary": True},
         test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("set", HERO, "render", "height=26", test_recipes=False)

    result = project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)

    assert result["findings"] == []
    document = render_json(folder)
    by_name = {c["name"]: c for c in document["clips"]}
    walk = by_name["walk"]["directions"]
    assert list(walk) == DIRECTIONS and all(len(frames) == len(by_name["walk"]["directions"]["s"]) for frames in walk.values())
    assert len(walk["s"]) >= 2
    size = (document["frame"]["width"], document["frame"]["height"])
    assert size == (40, 40)
    seen = 0
    for entry in document["clips"]:
        for frames in entry["directions"].values():
            for item in frames:
                colour = np.array(Image.open(folder / "work" / "render" / item["files"]["color"]))
                normal = np.array(Image.open(folder / "work" / "render" / item["files"]["normal"]))
                depth = Image.open(folder / "work" / "render" / item["files"]["depth"])
                mask = np.array(Image.open(folder / "work" / "render" / item["files"]["mask"]))
                assert colour.shape == (40, 40, 4) and normal.shape == colour.shape and depth.size == size
                assert depth.mode in ("I;16", "I") and mask.shape == (40, 40)
                assert set(np.unique(colour[..., 3])) <= {0, 255} and set(np.unique(normal[..., 3])) <= {0, 255}
                assert set(np.unique(mask)) <= {0, 255} and (mask == 255).sum() > 20
                assert ((colour[..., 3] == 255) == (mask == 255)).all()
                seen += 1
    assert seen == 8 * (len(walk["s"]) + len(by_name["idle"]["directions"]["s"]))
    # the pivot is the feet: fixed in a stationary clip, and in the same pixel from every direction
    pivots = {tuple(item["pivot"]) for frames in by_name["idle"]["directions"].values() for item in frames}
    xs, ys = [p[0] for p in pivots], [p[1] for p in pivots]
    assert max(xs) - min(xs) < 0.5 and max(ys) - min(ys) < 0.5
    assert pivots and abs(xs[0] - 20.0) < 0.5 and abs(ys[0] - document["pivot"][1]) < 0.5
    # the feet touch the ground at the pivot: the lowest opaque row is within a pixel or two of it
    mask = np.array(Image.open(folder / "work" / "render" / by_name["idle"]["directions"]["s"][0]["files"]["mask"]))
    assert abs(np.nonzero(mask.any(axis=1))[0].max() + 1 - document["pivot"][1]) <= 2


@pytest.mark.blender
def test_a_clip_source_file_poses_the_rig_as_its_own_action_does(project: Kiripix) -> None:
    folder = real_hero(project)
    copy = project.cwd / "stride.fbx"
    blender_script(project, (
        "import bpy\n"
        f"bpy.ops.import_scene.fbx(filepath={str(FIXTURES / 'rigged.fbx')!r})\n"
        "for a in list(bpy.data.actions):\n"
        "    if not a.name.endswith('walk'):\n"
        "        bpy.data.actions.remove(a)\n"
        f"bpy.ops.export_scene.fbx(filepath={str(copy)!r}, bake_anim=True, bake_anim_use_all_actions=False,\n"
        "                         bake_anim_use_nla_strips=False, add_leaf_bones=False)\n"), "make_stride")
    project.json("import", HERO, str(copy), "--role", "clip-source", test_recipes=False)
    clip(project, {"name": "walk", "source": "walk", "start": 8, "end": 8, "fps": 6, "loop": False}, test_recipes=False)
    clip(project, {"name": "stride", "source": "stride", "start": 8, "end": 8, "fps": 6, "loop": False}, test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("set", HERO, "render", "height=26", test_recipes=False)

    project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)

    root = folder / "work" / "render"
    rest = np.array(Image.open(root / "color" / "walk" / "e" / "000.png"))
    moved = np.array(Image.open(root / "color" / "stride" / "e" / "000.png"))
    assert (rest[..., 3] == 255).sum() > 20 and (moved[..., 3] == 255).sum() > 20
    changed = (rest != moved).any(axis=-1).sum()
    assert changed < 0.05 * 40 * 40  # the same pose, whatever file it came from (a frame or two of rounding at most)
    # and it isn't the rest pose: pose frame 8 differs from frame 1
    clip(project, {"name": "first", "source": "walk", "start": 1, "end": 1, "fps": 6, "loop": False}, test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)
    first = np.array(Image.open(root / "color" / "first" / "e" / "000.png"))
    assert (first != rest).any()


@pytest.mark.blender
def test_a_rigged_file_from_the_round_trip_is_normalised_and_rendered(project: Kiripix) -> None:
    folder = project.cwd / "assets" / "character" / "hero"
    project.json("new", "character", "hero", test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])
    (project.cwd / "plain.fbx").write_bytes((FIXTURES / "no_rig.fbx").read_bytes())
    variant = project.json("import", HERO, "plain.fbx", test_recipes=False)["data"]["variant"]
    project.json("pick", HERO, variant, test_recipes=False)
    project.json("run", HERO, "model", test_recipes=False, timeout=900)
    (project.cwd / "back.fbx").write_bytes((FIXTURES / "rigged.fbx").read_bytes())
    project.json("import", HERO, "back.fbx", "--role", "rigged", test_recipes=False)
    project.json("run", HERO, "rig", test_recipes=False, timeout=900)
    assert json.loads((folder / "work" / "rig" / "rig.json").read_text("utf-8"))["source"] == "rigged"
    clip(project, {"name": "idle", "source": "idle", "start": 1, "end": 1, "fps": 6, "loop": False, "stationary": True},
         test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("set", HERO, "render", "height=26", test_recipes=False)

    project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)

    mask = np.array(Image.open(folder / "work" / "render" / "mask" / "idle" / "s" / "000.png"))
    rows = np.nonzero(mask.any(axis=1))[0]
    assert 24 <= rows.max() - rows.min() + 1 <= 32  # about 26 px tall (a foot toward the camera adds a few): the target height


@pytest.mark.blender
def test_toon_shading_has_no_more_colours_per_part_than_bands(project: Kiripix) -> None:
    folder = real_hero(project, "rigged.fbx")
    clip(project, {"name": "pose", "source": "walk", "start": 8, "end": 8, "fps": 6, "loop": False}, test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("set", HERO, "render", "height=26", test_recipes=False)
    root = folder / "work" / "render"

    def render(bands: int, shadow: float) -> tuple[np.ndarray, np.ndarray]:
        project.json("set", HERO, "render", f"bands={bands}", f"shadow={shadow}", test_recipes=False)
        project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)
        colour = np.concatenate([np.array(Image.open(root / "color" / "pose" / d / "000.png")) for d in DIRECTIONS])
        normal = np.concatenate([np.array(Image.open(root / "normal" / "pose" / d / "000.png")) for d in DIRECTIONS])
        return colour, normal

    def colours(image: np.ndarray) -> set[tuple[int, ...]]:
        return {tuple(int(v) for v in pixel) for pixel in image[image[..., 3] == 255][:, :3]}

    flat, flat_normal = render(4, 0.0)  # no shadow: the Model's own colours, one per part
    two, two_normal = render(2, 0.6)
    four, four_normal = render(4, 0.6)

    own = colours(flat)
    assert len(own) >= 2

    def worst(toon: np.ndarray) -> int:
        """The most colours the toon frames show where the flat frames show one colour (one part of the Model)."""
        counts = []
        for colour in own:
            where = (flat[..., :3] == np.array(colour)).all(axis=-1) & (flat[..., 3] == 255)
            found = sorted({tuple(int(v) for v in p) for p in toon[where][:, :3]}, key=sum)
            steps = [found[0]] if found else []
            for item in found[1:]:  # one flat colour can be a few 8-bit levels apart in a gradient: cluster within 3 levels
                if max(abs(a - b) for a, b in zip(item, steps[-1])) > 3:
                    steps.append(item)
            counts.append(len(steps))
        return max(counts)

    assert worst(two) <= 2 and worst(four) <= 4
    assert worst(two) == 2 and worst(four) >= 3  # and the light does cut the Model into bands
    assert (flat_normal == two_normal).all() and (flat_normal == four_normal).all()  # the normal pass is untouched
    assert ((flat[..., 3] == 255) == (four[..., 3] == 255)).all()


# ticket 0121: the Model's facing, on the real Blender


def has_nose(frame: np.ndarray) -> bool:
    """The fixtures' red nose (ticket 0122), at any toon band: red dominant, almost no green or blue."""
    r, g, b, a = (frame[..., i].astype(int) for i in range(4))
    return bool(((a == 255) & (r >= 60) & (g * 3 < r) & (b * 3 < r)).any())


def turned_copy(project: Kiripix, source: str, degrees: float, name: str) -> Path:
    """A .blend of a fixture with everything in it turned `degrees` about +Z: the Model faces another way in its file."""
    target = project.cwd / name
    blender_script(project, (
        "import math, bpy\n"
        "from mathutils import Matrix\n"
        "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
        f"bpy.ops.import_scene.fbx(filepath={str(FIXTURES / source)!r})\n"
        f"turn = Matrix.Rotation(math.radians({degrees}), 4, 'Z')\n"
        "turner = bpy.data.objects.new('turner', None)\n"  # not the armature itself: its animation keys its own rotation
        "bpy.context.scene.collection.objects.link(turner)\n"
        "for obj in [o for o in bpy.data.objects if o.parent is None and o is not turner]:\n"
        "    obj.parent = turner\n"
        "turner.matrix_world = turn\n"
        "for action in bpy.data.actions:\n"
        "    action.use_fake_user = True\n"
        f"bpy.ops.wm.save_as_mainfile(filepath={str(target)!r})\n"), f"turn_{name}")
    return target


def pose_frames(folder: Path, directions: list[str]) -> dict[str, np.ndarray]:
    return {d: np.array(Image.open(folder / "work" / "render" / "color" / "pose" / d / "000.png")) for d in directions}


def render_pose(project: Kiripix, first: bool = True) -> dict[str, np.ndarray]:
    if first:
        clip(project, {"name": "pose", "source": "walk", "start": 8, "end": 8, "fps": 6, "loop": False}, test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("set", HERO, "render", "height=26", test_recipes=False)
    project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)
    return pose_frames(project.cwd / "assets" / "character" / "hero", DIRECTIONS)


def import_and_pick(project: Kiripix, path: Path) -> None:
    variant = project.json("import", HERO, str(path), test_recipes=False)["data"]["variant"]
    project.json("pick", HERO, variant, test_recipes=False)


@pytest.mark.blender
@pytest.mark.parametrize(("degrees", "facing"), [(0, "-y"), (180, "+y"), (90, "+x"), (-90, "-x")])
def test_a_turned_model_with_its_facing_renders_the_same_frames_as_the_original(
        project: Kiripix, degrees: int, facing: str) -> None:
    real_hero(project, "rigged.fbx")
    wanted = render_pose(project)
    assert all((frame[..., 3] == 255).sum() > 20 for frame in wanted.values())
    assert (wanted["s"] != wanted["n"]).any()  # the directions differ, so the comparison below means something
    assert has_nose(wanted["s"]) and not has_nose(wanted["n"])  # the face is toward the camera at `s`, away at `n`

    turned = turned_copy(project, "rigged.fbx", degrees, "turned.blend")
    import_and_pick(project, turned)
    project.json("set", HERO, "model", f"facing={facing}", test_recipes=False)
    project.json("run", HERO, "model", test_recipes=False, timeout=900)
    project.json("run", HERO, "rig", test_recipes=False, timeout=900)
    model = json.loads((project.cwd / "assets" / "character" / "hero" / "work" / "model" / "model.json").read_text("utf-8"))
    assert model["facing"] == facing

    got = render_pose(project, first=False)
    for direction in DIRECTIONS:
        assert (got[direction] != wanted[direction]).any(axis=-1).sum() <= 3, direction  # float noise in a turn, at most
    assert has_nose(got["s"]) and not has_nose(got["n"])  # `facing` put the face toward the camera again


@pytest.mark.blender
def test_without_the_facing_a_turned_model_renders_another_direction(project: Kiripix) -> None:
    real_hero(project, "rigged.fbx")
    wanted = render_pose(project)
    import_and_pick(project, turned_copy(project, "rigged.fbx", 180, "turned.blend"))
    project.json("run", HERO, "model", test_recipes=False, timeout=900)
    project.json("run", HERO, "rig", test_recipes=False, timeout=900)

    got = render_pose(project, first=False)

    assert (got["s"] != wanted["s"]).any()  # the back is rendered where the front should be


@pytest.mark.blender
def test_the_mixamo_upload_and_so_the_rigged_file_faces_the_way_the_render_expects(project: Kiripix) -> None:
    """The upload has the turn applied, so a rigged file Mixamo makes from it faces -Y whatever the Model's `facing` was:
    the same rigged file renders alike for the Model facing -Y and for the one turned and given `facing = "+y"`. So
    `render` turns nothing for a rigged file."""
    folder = project.cwd / "assets" / "character" / "hero"
    project.json("new", "character", "hero", test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])
    import_and_pick(project, FIXTURES / "no_rig.fbx")
    project.json("run", HERO, "model", test_recipes=False, timeout=900)
    project.json("import", HERO, str(FIXTURES / "rigged.fbx"), "--role", "rigged", test_recipes=False)
    project.json("run", HERO, "rig", test_recipes=False, timeout=900)
    wanted = render_pose(project)

    import_and_pick(project, turned_copy(project, "no_rig.fbx", 180, "turned.blend"))
    project.json("set", HERO, "model", "facing=+y", test_recipes=False)
    project.json("run", HERO, "model", test_recipes=False, timeout=900)
    project.json("run", HERO, "rig", test_recipes=False, timeout=900)
    assert json.loads((folder / "work" / "rig" / "rig.json").read_text("utf-8"))["source"] == "rigged"

    got = render_pose(project, first=False)

    for direction in DIRECTIONS:
        assert (got[direction] != wanted[direction]).any(axis=-1).sum() <= 3, direction


@pytest.mark.blender
def test_a_kept_clip_is_byte_equal_to_a_full_rebuild_on_the_real_blender(project: Kiripix) -> None:
    folder = real_hero(project, "rigged.fbx")
    clip(project, {"name": "walk", "source": "walk", "start": 1, "end": 9, "fps": 6, "loop": False}, test_recipes=False)
    clip(project, {"name": "idle", "source": "idle", "start": 1, "end": 7, "fps": 6, "loop": False, "stationary": True},
         test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("set", HERO, "render", "height=26", test_recipes=False)
    project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)
    clip(project, {"name": "pose", "source": "walk", "start": 8, "end": 8, "fps": 6, "loop": False}, test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)

    result = project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)
    incremental = tree(folder)

    assert "reused 16 of 24" in result["data"]["results"][0]["message"]
    assert len(incremental) > 100
    project.json("run", HERO, "render", "--cpu", "--force", test_recipes=False, timeout=1800)
    assert tree(folder) == incremental
