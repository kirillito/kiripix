"""Ticket 0344: `masks-add` adds a named terrain Mask to kiripix.toml, and the `masks` Stage paints it. Kiripix gives it no
meaning: it never blocks anything."""

import tomllib
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from test_masks import ROOM, built_room, decide, read_mask

COVER = ["masks-add", "cover", "--colour", "#00AA00", "--meaning", "half cover for a grid battle"]


def codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"]]


def test_a_named_mask_is_painted_and_built_in_the_masks_stage_and_solid_is_unchanged(project: Kiripix) -> None:
    folder = built_room(project)
    solid_before = read_mask(folder)

    added = project.json(*COVER)

    assert added["data"]["mask"] == {"view": "top", "name": "cover", "colour": "#00AA00",
                                     "meaning": "half cover for a grid battle", "derived": False, "blocks": False}
    settings = tomllib.loads((project.cwd / "kiripix.toml").read_text(encoding="utf-8"))
    assert settings["masks"]["top"]["cover"] == {"colour": "#00AA00", "meaning": "half cover for a grid battle"}
    decide(project, "brush", {"mask": "cover", "points": [[20, 10], [30, 10]], "radius": 2, "erase": False})
    project.json("run", ROOM, "masks")

    cover = read_mask(folder, "cover")
    assert cover[10, 25] and not cover[25, 5]
    assert np.array_equal(read_mask(folder), solid_before)


def test_the_file_keeps_its_comments_and_a_new_mask_is_the_last_of_its_view(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    before = path.read_text(encoding="utf-8")

    project.json(*COVER)

    after = path.read_text(encoding="utf-8")
    kept = iter(after.splitlines())
    assert all(line in kept for line in before.splitlines())
    assert "derived = false" not in after
    assert "cover" in tomllib.loads(after)["masks"]["top"]


def test_a_side_view_mask_goes_to_the_side_view(project: Kiripix) -> None:
    project.json(*COVER, "--view", "side")

    masks = tomllib.loads((project.cwd / "kiripix.toml").read_text(encoding="utf-8"))["masks"]
    assert "cover" in masks["side"] and "cover" not in masks["top"]


def test_a_taken_colour_and_a_reserved_or_existing_name_are_refused(project: Kiripix) -> None:
    taken = project.json("masks-add", "cover", "--colour", "#ff0000", "--meaning", "x", expect=1)
    imported = project.json("masks-add", "cover", "--colour", "#FFFF00", "--meaning", "x", expect=1)
    assert codes(taken) == ["masks.colour_taken"] and codes(imported) == ["masks.colour_taken"]
    for name in ("walkable", "foreground", "solid"):
        refused = project.json("masks-add", name, "--colour", "#123456", "--meaning", "x", expect=1)
        assert codes(refused) == ["masks.name_taken"]
    assert codes(project.json("masks-add", "Bad Name", "--colour", "#123456", "--meaning", "x", expect=1)) == ["masks.name_invalid"]
    assert codes(project.json("masks-add", "cover", "--colour", "green", "--meaning", "x", expect=1)) == ["masks.colour_invalid"]
    assert "cover" not in (project.cwd / "kiripix.toml").read_text(encoding="utf-8")


def test_the_same_colour_is_fine_in_the_other_view_and_a_second_add_of_the_name_is_refused(project: Kiripix) -> None:
    project.json(*COVER)
    project.json(*COVER[:3], "#00AA01", "--meaning", "x", "--view", "side")
    again = project.json(*COVER, expect=1)
    assert codes(again) == ["masks.name_taken"]


def test_describe_room_lists_the_masks_with_view_colour_and_meaning(project: Kiripix) -> None:
    project.json(*COVER)

    data = project.json("describe", "room")["data"]

    rows = {(m["view"], m["name"]): m for m in data["masks"]}
    assert rows[("top", "cover")] == {"view": "top", "name": "cover", "colour": "#00AA00",
                                      "meaning": "half cover for a grid battle", "derived": False, "blocks": False}
    assert rows[("top", "solid")]["blocks"] is True and rows[("top", "pit")]["blocks"] is True
    assert rows[("top", "walkable")]["derived"] is True and rows[("top", "walkable")]["colour"] is None
    assert ("side", "oneway") in rows
    assert "cover" in project("describe", "room").stdout


def test_a_decision_on_a_mask_removed_by_hand_fails_the_stage_as_masks_unknown(project: Kiripix) -> None:
    built_room(project)
    project.json(*COVER)
    decide(project, "brush", {"mask": "cover", "points": [[20, 10]], "radius": 2, "erase": False})
    path: Path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")
    start = text.index("[masks.top.cover]")
    path.write_text(text[:start] + text[text.index("[masks.side]"):], encoding="utf-8")  # the Owner deletes the table

    result = project.json("run", ROOM, "masks", expect=3)  # the Owner's to settle

    finding = result["findings"][-1]
    assert finding["code"] == "masks.unknown"
    assert "'cover'" in finding["message"] and "brush" in finding["message"]
    assert "kiripix undo room.alley masks" in finding["owner_action"] and "masks-add cover" in finding["owner_action"]
    assert not finding.get("fix")
