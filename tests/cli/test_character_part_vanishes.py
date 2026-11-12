"""`sheet.part_vanishes` (ticket 0159, spec §6.3): a material seen in most frames of a clip and direction but missing from some.
The fake Blender writes the material pass chosen by `blender-material-frames`; its materials are 1 cloth and 2 skin."""

import json
from typing import Any

from conftest import Kiripix
from test_character_model import HERO
from test_character_palette import built

FRAMES = "blender-material-frames"


def frames_with(project: Kiripix, chosen: dict[str, list[int]]) -> None:
    (project.cwd / FRAMES).write_text(json.dumps(chosen), encoding="utf-8")


def vanishes(project: Kiripix, *params: str, build: bool = True) -> list[dict[str, Any]]:
    if build:
        built(project, "colors=3")
    for param in params:
        project.json("set", HERO, "finish", param)
    project.json("run", HERO, "finish", "--force")
    return [f for f in project.json("check", HERO)["findings"] if f["code"] == "sheet.part_vanishes"]


def test_the_stage_declares_the_watch_parameters_and_the_check(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "finish")["data"]["kinds"]

    [stage] = kind["stages"]

    by_name = {p["name"]: p for p in stage["params"]}
    assert by_name["watch_parts"]["default"] == "" and by_name["part_min_pixels"]["default"] == 1
    assert "sheet.part_vanishes" in [c["code"] for c in stage["checks"]]


def test_a_part_missing_from_two_frames_of_a_direction_is_one_warning_naming_them(project: Kiripix) -> None:
    frames_with(project, {"*": [1, 2], "idle/s/1": [1], "idle/s/3": [1]})

    [finding] = vanishes(project)

    assert finding["severity"] == "warning" and finding["owner_action"] and finding.get("fix") is None
    assert "skin" in finding["message"] and "clip idle, direction s:" in finding["message"]
    assert "1" in finding["message"] and "3" in finding["message"]
    assert finding["position"]["field"] == "idle/s" and finding["position"]["stage"] == "finish"
    assert "height" in finding["owner_action"]


def test_a_part_missing_from_every_frame_of_a_direction_is_not_flagged(project: Kiripix) -> None:
    frames_with(project, {"*": [1, 2], "hit/n": [1], "idle/n": [1]})  # the eyes facing away

    assert vanishes(project) == []


def test_watch_parts_limits_the_materials_and_part_min_pixels_sets_the_threshold(project: Kiripix) -> None:
    frames_with(project, {"*": [1, 2], "idle/s/1": [1], "idle/s/3": [1]})

    assert vanishes(project, "watch_parts=cloth") == []

    [finding] = vanishes(project, "watch_parts=skin", build=False)
    assert "skin" in finding["message"]

    # a band of skin is half of a 78 px frame, 3042 px; asking for more counts every frame as missing it, so none is odd one out
    assert vanishes(project, "part_min_pixels=3043", build=False) == []
