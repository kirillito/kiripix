"""Named points: `render points=...` records each point's place in every frame, `sheet` carries it relative to the pivot and
`character.json` exports it (ticket 0237, spec §6.3 and §9). The fake Blender has the bones `hips`, `hand_r` and `head`, and puts
the k-th point 10 * k + 0.4 px right of the pivot and 30 - 0.7 px above it, hidden in the direction `n`."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_character_clips import IDLE
from test_character_model import HERO
from test_character_render import ready, render_calls, render_json
from test_export import godot_project, set_target


def exported(project: Kiripix, *points: str) -> tuple[Path, dict[str, Any]]:
    folder = ready(project, IDLE)
    if points:
        project.json("set", HERO, "render", f"points={','.join(points)}")
    godot_project(project)
    set_target(project)
    project.json("run", HERO)
    character: dict[str, Any] = json.loads((folder / "out" / "export" / "character.json").read_text("utf-8"))
    return folder, character


def test_render_records_every_point_in_every_frame(project: Kiripix) -> None:
    folder = ready(project, IDLE)
    project.json("set", HERO, "render", "points=hand_r@hand_r, head@head")

    project.json("run", HERO, "render")

    assert render_calls(project)[-1]["args"]["points"] == [{"name": "hand_r", "target": "hand_r"},
                                                          {"name": "head", "target": "head"}]
    document = render_json(folder)
    assert document["points"] == [{"name": "hand_r", "target": "hand_r"}, {"name": "head", "target": "head"}]
    pivot = document["pivot"]
    for clip in document["clips"]:
        for frames in clip["directions"].values():
            for frame in frames:
                assert set(frame["points"]) == {"hand_r", "head"}
                assert frame["points"]["head"]["x"] == frame["pivot"][0] + 20.4
    assert document["clips"][0]["directions"]["s"][0]["points"]["hand_r"] == {
        "x": pivot[0] + 10.4, "y": pivot[1] - 29.3, "depth": 9.0, "hidden": False}


def test_character_json_has_the_points_relative_to_the_pivot(project: Kiripix) -> None:
    folder, character = exported(project, "hand_r@hand_r")

    assert character["schema_version"] == 5
    pivot = render_json(folder)["pivot"]
    for clip in character["clips"]:
        for direction, frames in clip["directions"].items():
            for frame in frames:
                # the pixel that holds 10.4 px right of the pivot and 29.3 px above it, from the pivot, y down
                assert frame["points"] == {"hand_r": {"x": 10, "y": -30, "hidden": direction == "n"}}
    assert pivot  # the cell's pivot is the pivot of every frame of a stationary clip


def test_the_points_reach_the_game_in_its_character_json(project: Kiripix) -> None:
    folder, character = exported(project, "hand_r@hand_r", "hand_l@head")

    data = project.json("export", HERO)["data"]

    game = project.cwd / "game/kiripix/character/hero/character.json"
    assert "res://kiripix/character/hero/character.json" in data["written"]
    assert game.read_bytes() == (folder / "out" / "export" / "character.json").read_bytes()
    frame = json.loads(game.read_text("utf-8"))["clips"][0]["directions"]["s"][0]
    assert set(frame["points"]) == {"hand_r", "hand_l"} and frame["points"]["hand_r"] == character["clips"][0][
        "directions"]["s"][0]["points"]["hand_r"]
    again = project.json("export", HERO)["data"]
    assert again["written"] == [] and "res://kiripix/character/hero/character.json" in again["unchanged"]


def test_without_the_parameter_nothing_is_written_and_character_json_is_as_before(project: Kiripix) -> None:
    folder, character = exported(project)

    assert character["schema_version"] == 4
    assert "points" not in render_json(folder) and "points" not in render_calls(project)[-1]["args"]
    assert "points" not in render_json(folder)["clips"][0]["directions"]["s"][0]
    sheet = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    assert all("points" not in f for c in sheet["clips"] for frames in c["directions"].values() for f in frames)
    assert all("points" not in f for c in character["clips"] for frames in c["directions"].values() for f in frames)


def test_an_unknown_bone_fails_listing_the_bones(project: Kiripix) -> None:
    ready(project, IDLE)
    project.json("set", HERO, "render", "points=thumb@thumb_r")

    result = project.json("run", HERO, "render", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "render.point_unknown"]
    assert "thumb_r" in finding["message"] and "hips, hand_r, head" in finding["message"]
    assert finding["fix"] == f"kiripix set {HERO} render points="


def test_a_bad_name_or_entry_is_refused_with_a_fix(project: Kiripix) -> None:
    ready(project, IDLE)
    for bad in ("Hand@hand_r", "hand_r", "hand r@hand_r", "1a@hand_r", "a@hand_r,a@head"):
        project.json("set", HERO, "render", f"points={bad}")

        result = project.json("run", HERO, "render", expect=1)

        [finding] = [f for f in result["findings"] if f["code"] == "render.point_invalid"]
        assert finding["fix"] == f"kiripix set {HERO} render points="


def test_changing_the_points_renders_again(project: Kiripix) -> None:
    ready(project, IDLE)
    project.json("run", HERO, "render")
    project.json("set", HERO, "render", "points=head@head")

    project.json("run", HERO, "render")

    assert len(render_calls(project)) == 2 and "points" in render_calls(project)[-1]["args"]
