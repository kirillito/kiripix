"""A character's stamped eyes, its blinks and its still and faster clips (ticket 0203, spec §6.3). The fake Blender puts two
eyes round the pivot's column in every frame when `render`'s `eyes` names one of its materials (`cloth`, `skin`); its material
pass is `cloth` everywhere, so `eyes=cloth` makes the whole frame the eye material, which is then filled with nothing (no
other pixel to fill it from) and painted."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_character_clips import IDLE, clip, clips_json, rigged_hero
from test_character_model import HERO
from test_character_palette import project_palette
from test_character_render import ready, render_calls, render_json

STILL = {"name": "idle", "source": "idle", "start": 3, "end": 3, "fps": 8, "loop": True, "stationary": True, "still": 6,
         "blink": [4]}


def read(path: Path) -> np.ndarray:
    return np.array(Image.open(path))


def stamped(project: Kiripix, *finish: str, clips: tuple[dict[str, Any], ...] = (STILL,)) -> Path:
    folder = ready(project, *clips)
    project.json("set", HERO, "render", "eyes=cloth")
    project.json("set", HERO, "finish", "eyes=stamp", "outline=false", *finish)
    for stage in ("render", "palette", "finish"):
        project.json("run", HERO, stage)
    return folder


def colours(project: Kiripix, folder: Path) -> tuple[tuple[int, ...], tuple[int, ...]]:
    drawn = json.loads((folder / "work" / "finish" / "finish.json").read_text("utf-8"))["eyes"]
    palette = project_palette(project)
    assert tuple(drawn["pupil"]["rgb"]) == tuple(int(v) for v in palette[drawn["pupil"]["colour"]])
    return tuple(drawn["pupil"]["rgb"]), tuple(drawn["white"]["rgb"])


# clips ---------------------------------------------------------------------------------------------------------------


def test_a_still_clip_is_one_pose_held_and_keeps_its_blink(project: Kiripix) -> None:
    folder = rigged_hero(project)
    clip(project, STILL)

    project.json("run", HERO, "clips")

    [entry] = clips_json(folder)["clips"]
    assert entry["frames"] == [3] * 6 and entry["still"] == 6 and entry["blink"] == [4]
    assert entry["events"] == {"foot": []}


def test_a_clip_without_the_new_keys_is_the_entry_it_always_was(project: Kiripix) -> None:
    folder = rigged_hero(project)
    clip(project, IDLE)

    project.json("run", HERO, "clips")

    [entry] = clips_json(folder)["clips"]
    assert not {"speed", "still", "blink"} & set(entry)


def test_speed_plays_the_action_faster_so_the_clip_has_fewer_frames(project: Kiripix) -> None:
    folder = rigged_hero(project)
    clip(project, {**IDLE, "speed": 2})

    project.json("run", HERO, "clips")

    [entry] = clips_json(folder)["clips"]
    assert entry["frames"] == [0, 5, 10, 15, 20] and entry["speed"] == 2  # every 5th frame of 30 a second, at 12 a second


def test_a_blink_past_the_clips_last_frame_fails_with_a_fix(project: Kiripix) -> None:
    rigged_hero(project)
    clip(project, {**STILL, "blink": [6]})

    result = project.json("run", HERO, "clips", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "clips.blink_range"]
    assert "0 to 5" in finding["message"] and finding["fix"] == f"kiripix undo {HERO} clips"


# render --------------------------------------------------------------------------------------------------------------


def test_render_follows_the_named_eyes_and_copies_the_blink(project: Kiripix) -> None:
    folder = ready(project, STILL)
    project.json("set", HERO, "render", "eyes=cloth, iris")

    project.json("run", HERO, "render")

    assert render_calls(project)[-1]["args"]["eyes"] == ["cloth", "iris"]
    document = render_json(folder)
    [entry] = document["clips"]
    assert document["eyes"] == ["cloth", "iris"] and entry["blink"] == [4]
    pivot = document["pivot"]
    first = entry["directions"]["s"][0]["eyes"]
    assert [(e["x"], e["y"]) for e in first] == [(pivot[0] - 1.5, pivot[1] - 40.4), (pivot[0] + 1.8, pivot[1] - 40.4)]


def test_without_the_parameter_render_json_has_no_eyes(project: Kiripix) -> None:
    folder = ready(project, IDLE)

    project.json("run", HERO, "render")

    document = render_json(folder)
    assert "eyes" not in document and "eyes" not in document["clips"][0]["directions"]["s"][0]
    assert "eyes" not in render_calls(project)[-1]["args"]


def test_eyes_that_name_no_material_fail_with_a_fix(project: Kiripix) -> None:
    ready(project, IDLE)
    project.json("set", HERO, "render", "eyes=pupil")

    result = project.json("run", HERO, "render", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "render.eyes_unknown"]
    assert "cloth, skin" in finding["message"] and finding["fix"] == f"kiripix set {HERO} render eyes="


# finish --------------------------------------------------------------------------------------------------------------


def test_stamp_paints_a_pupil_and_a_white_per_eye_on_whole_pixels(project: Kiripix) -> None:
    folder = stamped(project)

    pupil, white = colours(project, folder)
    x, y = (int(v) for v in render_json(folder)["pivot"])
    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    mapped = read(folder / "work" / "palette" / "color" / "idle" / "s" / "000.png")
    for row in (y - 41, y - 40):  # two rows; the pupils toward each other, a pixel between the eyes
        assert [tuple(int(v) for v in frame[row, column, :3]) for column in range(x - 2, x + 3)] == [
            white, pupil, tuple(int(v) for v in mapped[row, x, :3]), pupil, white]
    changed = (frame != mapped).any(axis=-1)
    assert changed.sum() <= 8 and not changed[:y - 41].any() and not changed[y - 39:].any()


def test_the_eyes_are_the_same_pixels_in_every_frame_but_the_blink(project: Kiripix) -> None:
    folder = stamped(project)

    pupil, _ = colours(project, folder)
    x, y = (int(v) for v in render_json(folder)["pivot"])
    frames = [read(folder / "work" / "finish" / "color" / "idle" / "s" / f"{i:03d}.png") for i in range(6)]
    eyes = [f[y - 41:y - 39, [x - 2, x - 1, x + 1, x + 2], :3] for f in frames]  # the four painted columns
    assert all((eyes[i] == eyes[0]).all() for i in (1, 2, 3, 5))
    closed, mapped = eyes[4], read(folder / "work" / "palette" / "color" / "idle" / "s" / "004.png")
    assert [tuple(int(v) for v in p) for p in closed[1]] == [pupil] * 4, "a closed eye is a line on its bottom row"
    assert (closed[0] == mapped[y - 41, [x - 2, x - 1, x + 1, x + 2], :3]).all(), "and the row above it is the lid: the frame's own pixels"


def test_a_wink_closes_one_eye(project: Kiripix) -> None:
    folder = stamped(project, clips=({**STILL, "blink": [], "wink_left": [2]},))

    pupil, white = colours(project, folder)
    x, y = (int(v) for v in render_json(folder)["pivot"])
    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "002.png")
    mapped = read(folder / "work" / "palette" / "color" / "idle" / "s" / "002.png")
    top, bottom = ([tuple(int(v) for v in frame[row, column, :3]) for column in range(x - 2, x + 3)] for row in (y - 41, y - 40))
    skin = tuple(int(v) for v in mapped[y - 41, x + 1, :3])
    assert top[:2] == [white, pupil] and bottom[:2] == [white, pupil], "the Model's right eye, on the screen's left, is open"
    assert bottom[3:] == [pupil, pupil] and top[3] == skin, "its left eye is a line"


def test_an_eye_that_faces_away_is_not_painted(project: Kiripix) -> None:
    folder = stamped(project)

    for name in ("000.png", "004.png"):
        assert (read(folder / "work" / "finish" / "color" / "idle" / "n" / name)
                == read(folder / "work" / "palette" / "color" / "idle" / "n" / name)).all()


def test_pupils_leaves_the_whites_out_and_the_colours_can_be_chosen(project: Kiripix) -> None:
    folder = stamped(project, "eyes=pupils", "eye_colour=1")

    drawn = json.loads((folder / "work" / "finish" / "finish.json").read_text("utf-8"))["eyes"]
    assert drawn["mode"] == "pupils" and drawn["white"] is None and drawn["pupil"]["colour"] == 1
    rgb = tuple(int(v) for v in project_palette(project)[1])
    x, y = (int(v) for v in render_json(folder)["pivot"])
    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    mapped = read(folder / "work" / "palette" / "color" / "idle" / "s" / "000.png")
    painted = np.argwhere((frame != mapped).any(axis=-1) | (frame[..., :3] == rgb).all(axis=-1))
    assert {(int(r), int(c)) for r, c in painted} >= {(y - 41, x - 2), (y - 40, x - 2), (y - 41, x + 1), (y - 40, x + 1)}
    assert (frame != mapped).any(axis=-1).sum() <= 4, "one column per eye, two rows"
    assert project.json("check", HERO)["findings"] == [] or all(
        f["code"] != "palette.off_palette" for f in project.json("check", HERO)["findings"])


def test_stamp_without_followed_eyes_fails_and_the_fix_leaves_them_as_rendered(project: Kiripix) -> None:
    ready(project, IDLE)
    project.json("set", HERO, "finish", "eyes=stamp")

    result = project.json("run", HERO, expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "finish.eyes_not_followed"]
    assert "render eyes=" in finding["message"] and finding["fix"] == f"kiripix set {HERO} finish eyes=render"
    assert stage_status(project, HERO)["finish"] == "failed"


def test_an_eye_colour_outside_the_palette_fails_with_a_fix(project: Kiripix) -> None:
    ready(project, STILL)
    project.json("set", HERO, "render", "eyes=cloth")
    project.json("set", HERO, "finish", "eyes=stamp", "eye_white=9999")

    result = project.json("run", HERO, expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "finish.eye_colour_unknown"]
    assert finding["fix"] == f"kiripix set {HERO} finish eye_white=-1"
