"""The room's brief and source Stages, `import` and `pick` (spec §6.1, §10.5), on small fixture images."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix, save_image, stage_status

ROOM = "room.alley"


def make_room(project: Kiripix) -> Path:
    project.json("new", "room", "alley", "--view", "top")
    return project.cwd / "assets" / "room" / "alley"


def variant(project: Kiripix, name: str = "made.png", colour: tuple[int, int, int, int] = (255, 0, 77, 255)) -> str:
    """Import a 4x4 image as a Variant; returns the Variant's name."""
    save_image(project.cwd / name, colour=colour)
    data: dict[str, Any] = project.json("import", ROOM, name)["data"]
    return str(data["variant"])


# brief


def test_brief_writes_the_size_view_and_mood(project: Kiripix) -> None:
    folder = make_room(project)
    project.json("set", ROOM, "brief", "width=480", "height=272", "mood=rainy neon")

    project.json("run", ROOM, "brief")

    brief = json.loads((folder / "work" / "brief" / "brief.json").read_text(encoding="utf-8"))
    assert brief == {"width": 480, "height": 272, "view": "top", "mood": "rainy neon", "tile": 16}


def test_a_brief_that_is_not_whole_tiles_reports_size_not_tiles_with_a_fix(project: Kiripix) -> None:
    make_room(project)
    project.json("set", ROOM, "brief", "width=481", "height=272")

    result = project.json("run", ROOM, expect=2)

    finding = next(f for f in result["findings"] if f["code"] == "brief.size_not_tiles")
    assert "481" in finding["message"] and "16" in finding["message"]
    assert finding["fix"] == f"kiripix set {ROOM} brief width=480 height=272"
    assert finding["position"]["stage"] == "brief"
    step = project.json("next", ROOM)["data"]
    assert step["stage"] == "brief" and step["command"] == finding["fix"]


# import


def test_import_copies_a_png_into_src_named_by_its_hash_and_twice_is_a_no_op(project: Kiripix) -> None:
    folder = make_room(project)
    save_image(project.cwd / "made.png")

    first = project.json("import", ROOM, "made.png")["data"]
    again = project.json("import", ROOM, "made.png")["data"]

    stored = project.cwd / first["file"]
    assert stored.parent == folder / "src" and stored.name == f"{first['variant']}.png"
    assert stored.read_bytes() == (project.cwd / "made.png").read_bytes()
    assert first["created"] is True and again["created"] is False and again["variant"] == first["variant"]
    assert [p.name for p in (folder / "src").iterdir()] == [stored.name]


def test_import_refuses_a_file_that_is_not_a_png(project: Kiripix) -> None:
    folder = make_room(project)
    (project.cwd / "made.jpg").write_bytes(b"\xff\xd8\xff\xe0 not a png")

    result = project.json("import", ROOM, "made.jpg", expect=1)

    assert result["findings"][0]["code"] == "image.not_png"
    assert not (folder / "src").exists() or list((folder / "src").iterdir()) == []


# pick and source


def test_pick_records_the_pick_decision_on_source(project: Kiripix) -> None:
    folder = make_room(project)
    name = variant(project)

    data = project.json("pick", ROOM, name)["data"]

    [line] = [json.loads(x) for x in (folder / "decisions" / "source.jsonl").read_text(encoding="utf-8").splitlines()]
    assert line["decision"] == "pick" and line["data"] == {"variant": name} and line["id"] == data["id"]
    assert data["stage"] == "source"


def test_pick_of_an_unknown_variant_fails(project: Kiripix) -> None:
    make_room(project)
    name = variant(project)

    result = project.json("pick", ROOM, "nope", expect=1)

    assert result["findings"][0]["code"] == "pick.unknown_variant" and name in result["findings"][0]["message"]


def test_brief_import_pick_run_leaves_brief_and_source_done_and_fit_next(project: Kiripix) -> None:
    folder = make_room(project)
    project.json("set", ROOM, "brief", "width=480", "height=272")
    name = variant(project)
    project.json("pick", ROOM, name)

    project.json("run", ROOM, expect=2)  # fit reports size_mismatch: the 4x4 Variant is not the brief size

    status = stage_status(project, ROOM)
    assert status["brief"] == "done" and status["source"] == "done"
    assert (folder / "work" / "source" / "source.png").read_bytes() == (folder / "src" / f"{name}.png").read_bytes()
    assert project.json("next", ROOM)["data"]["stage"] == "fit"


def test_without_a_variant_source_needs_input_and_next_says_import(project: Kiripix) -> None:
    make_room(project)
    project.json("set", ROOM, "brief", "width=480", "height=272")

    result = project.json("run", ROOM, expect=3)

    assert result["data"]["results"][-1] == {**result["data"]["results"][-1], "stage": "source",
                                             "outcome": "needs-input", "message": "no Source picked"}
    step = project.json("next", ROOM)["data"]
    assert step["stage"] == "source" and step["reason"] == "no Source picked"
    assert step["command"] == f"kiripix import {ROOM} <file>"


def test_next_gives_the_pick_command_for_one_variant_and_an_owner_action_for_several(project: Kiripix) -> None:
    make_room(project)
    project.json("set", ROOM, "brief", "width=480", "height=272")
    first = variant(project)
    project.json("run", ROOM, expect=3)

    one = project.json("next", ROOM)["data"]
    second = variant(project, "other.png", (41, 173, 255, 255))
    several = project.json("next", ROOM)["data"]

    assert one["command"] == f"kiripix pick {ROOM} {first}"
    assert several["command"] is None
    assert first in several["owner_action"] and second in several["owner_action"]
    assert f"kiripix pick {ROOM}" in several["owner_action"]


def test_a_pick_of_a_deleted_variant_needs_input_with_that_reason(project: Kiripix) -> None:
    folder = make_room(project)
    name = variant(project)
    project.json("pick", ROOM, name)
    (folder / "src" / f"{name}.png").unlink()

    states = {s["stage"]: s for s in project.json("status")["data"]["assets"][0]["stages"]}

    assert states["source"]["status"] == "needs-input"
    assert states["source"]["reason"] == f"the picked Variant {name} was deleted"


def test_importing_and_picking_a_second_variant_makes_source_and_below_stale(project: Kiripix) -> None:
    make_room(project)
    project.json("set", ROOM, "brief", "width=480", "height=272")
    project.json("pick", ROOM, variant(project))
    project.json("run", ROOM, expect=2)

    project.json("pick", ROOM, variant(project, "other.png", (41, 173, 255, 255)))

    status = stage_status(project, ROOM)
    assert status["brief"] == "done" and status["source"] == "stale"
    assert set(status.values()) - {"done", "stale"} == {"needs-input"}  # the Stages below aren't built in M1 yet
    project.json("run", ROOM, expect=2)
    assert stage_status(project, ROOM)["source"] == "done"


def test_a_picked_variant_edited_in_place_fails_the_source_stage(project: Kiripix) -> None:
    folder = make_room(project)
    project.json("set", ROOM, "brief", "width=480", "height=272")
    name = variant(project)
    project.json("pick", ROOM, name)
    save_image(folder / "src" / f"{name}.png", colour=(0, 0, 0, 255))

    result = project.json("run", ROOM, expect=1)

    assert result["findings"][-1]["code"] == "stage.failed" and "immutable" in result["findings"][-1]["message"]
