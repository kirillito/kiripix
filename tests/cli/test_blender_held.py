"""A clip's held things on the real Blender 5.2 (ticket 0302, spec §6.3): `render` draws a thing at its socket bone in the clips
that attach it, in every direction, and in no others, its materials numbered after the Model's. The render Model has no `grip_r`
bone, so the socket is its right hand bone. Skipped without Blender 5.2.x (`KIRIPIX_BLENDER` or PATH)."""

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix
from test_blender_render import (
    DIRECTIONS, FIXTURES, HERO, IDLE, clip, folder_of, frames_of, hero, mask_of, pass_of, render_json, run)

pytestmark = pytest.mark.blender

HAND = "mixamorig:RightHand"
BODY_MATERIALS = 4  # cloth, eye_iris, eye_white, skin


def import_thing(project: Kiripix, thing: str) -> None:
    shutil.copy(FIXTURES / "characters" / "render_thing.glb", project.cwd / f"{thing}.glb")
    run(project, "import", HERO, f"{thing}.glb", "--role", "thing", "--thing", thing)


@pytest.fixture(scope="module")
def held(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """One real render: `idle` holds nothing, `hold` (the same pose) holds the stick, and a second thing, `flag`, is on the Asset."""
    project = Kiripix(tmp_path_factory.mktemp("held"))
    project.json("init")
    folder = hero(project)
    import_thing(project, "stick")
    import_thing(project, "flag")
    clip(project, IDLE)
    clip(project, {**IDLE, "name": "hold", "attach": [{"thing": "stick", "socket": HAND, "turn": [90, 0, 0]}]})
    clip(project, {**IDLE, "name": "reach", "attach": [{"thing": "stick", "socket": HAND, "offset": [0, 0.5, 0]}]})  # out past the hand
    run(project, "run", HERO, "clips")
    run(project, "set", HERO, "render", "height=64")
    result = run(project, "run", HERO, "render", "--cpu", timeout=1800)
    assert result["findings"] == []
    return folder, render_json(folder)


def thing_pixels(folder: Path, frame: dict[str, Any], index: int) -> np.ndarray:
    return pass_of(folder, frame, "material") == index


def test_the_things_materials_follow_the_models_and_render_json_records_them_and_the_attach(
        held: tuple[Path, dict[str, Any]]) -> None:
    _, document = held
    assert len(document["materials"]) == BODY_MATERIALS  # the Model's own, unchanged
    # `flag` was imported after `stick` and no clip holds it, so it moves no number and isn't listed (ticket 0313)
    (stick,) = document["things"]
    assert stick["thing"] == "stick" and stick["materials"] == [{"index": 5, "name": "metal"}]
    assert next(c for c in document["clips"] if c["name"] == "hold")["attach"] == [
        {"thing": "stick", "socket": HAND, "turn": [90.0, 0.0, 0.0]}]
    assert "attach" not in next(c for c in document["clips"] if c["name"] == "idle")


def test_the_thing_shows_in_the_clip_that_holds_it_in_every_direction_and_in_no_other(held: tuple[Path, dict[str, Any]]) -> None:
    folder, document = held
    for direction in DIRECTIONS:
        [shown] = frames_of(document, "hold", direction)
        [bare] = frames_of(document, "idle", direction)
        assert thing_pixels(folder, shown, 5).sum() >= 3, direction  # end on (w, e) it is a 0.1 m square
        assert mask_of(folder, shown)[thing_pixels(folder, shown, 5)].all()  # it is in the object mask
        assert not (pass_of(folder, bare, "material") >= 5).any(), direction  # not in the clip that doesn't hold it
        assert not (pass_of(folder, shown, "material") == 6).any()  # and the other thing is in neither


def test_the_thing_sits_within_a_pixel_of_the_sockets_point(held: tuple[Path, dict[str, Any]]) -> None:
    """The stick is turned upright on the hand, so it rises out of the arm, which hides its grip end: in every direction an
    upright stick is one screen column, which is the grip's own, so its pixels' middle column is the point's, to a pixel."""
    folder, document = held
    assert {"name": "righthand", "target": HAND} in document["points"]  # a point per attached socket, by default
    for direction in DIRECTIONS:
        [frame] = frames_of(document, "hold", direction)
        point = frame["points"]["righthand"]
        rows, columns = np.nonzero(thing_pixels(folder, frame, 5))
        assert abs((columns.min() + columns.max() + 1) / 2 - point["x"]) <= 1.0, (direction, point, columns.min(), columns.max())
        assert abs(rows.min() - point["y"]) > 3 and np.hypot(columns - point["x"], rows - point["y"]).min() <= 5, direction


def test_the_thing_is_in_the_clips_measured_extent_so_the_cell_holds_it(held: tuple[Path, dict[str, Any]]) -> None:
    folder, document = held
    bounds = {c["name"]: c["bounds"] for c in document["clips"]}
    assert bounds["reach"][0] <= bounds["idle"][0] - 10  # the stick, held out past the hand, widens the clip's extent
    assert bounds["hold"][1] < bounds["idle"][1] - 2  # the stick turned up on the hand rises above the head
    for direction in DIRECTIONS:
        [shown] = frames_of(document, "reach", direction)
        pixels = thing_pixels(folder, shown, 5)
        rows, columns = np.nonzero(pixels)
        assert pixels.any() and columns.min() >= 1 and columns.max() <= pass_of(folder, shown, "color").shape[1] - 2, direction


def test_a_clip_whose_thing_reaches_past_the_bodys_cell_has_its_own_larger_cell(held: tuple[Path, dict[str, Any]]) -> None:
    """Ticket 0303: `reach` holds the stick out past the hand, so it doesn't fit the body's cell; the clips that fit keep it."""
    folder, document = held
    clips = {c["name"]: c for c in document["clips"]}
    body = document["frame"]["width"]
    assert clips["idle"]["frame"]["width"] == body and clips["idle"]["pivot"] == document["pivot"]
    for name in ("idle", "hold", "reach"):
        assert clips[name]["frame"]["width"] >= body and clips[name]["pivot"][0] == clips[name]["frame"]["width"] / 2, name
    assert clips["reach"]["frame"]["width"] > body or clips["reach"]["frame"]["height"] > body or clips["reach"]["pivot"][1] > document["pivot"][1]
    for name, entry in clips.items():
        for direction in DIRECTIONS:
            [frame] = frames_of(document, name, direction)
            image = pass_of(folder, frame, "color")
            assert image.shape[:2] == (entry["frame"]["height"], entry["frame"]["width"]), (name, direction)


def test_a_socket_the_rig_lacks_is_clips_unknown_socket_before_any_render(tmp_path: Path) -> None:
    project = Kiripix(tmp_path)
    project.json("init")
    folder = hero(project)
    import_thing(project, "stick")
    clip(project, IDLE)

    result = project.json("decide", HERO, "clips", "--decision", json.dumps({"decision": "clip", "data": {
        **IDLE, "name": "hold", "attach": [{"thing": "stick"}]}}), test_recipes=False, expect=1)  # grip_r is not a bone here

    [finding] = [f for f in result["findings"] if f["code"] == "clips.unknown_socket"]
    assert "grip_r" in finding["message"] and "mixamorig:Hips" in finding["message"]
    assert not (folder_of(project) / "work" / "render" / "render.json").exists()
