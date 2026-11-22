"""A Look's own Markers, walkable and clear on `place` (ticket 0314, ADR 0013), and `look.overlap` on `looks`."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_layers_stage import ROOM
from test_looks_build import LAMP_BOX, edited, import_and_pick, room_with_a_lamp_layer
from test_looks_build import decide as decide_look

LOOK = "gate_open"
OTHER = "lamp_dim"
WALL = [[20, 0], [27, 0], [27, 31], [20, 31]]  # a wall down the room, 8 px wide
OPENING = {"look": LOOK, "erase": True, "radius": 9, "points": [[24, 16]]}


def decide_place(project: Kiripix, decision: str, data: dict[str, Any], expect: int = 0) -> dict[str, Any]:
    return project.json("decide", ROOM, "place", "--decision", json.dumps({"decision": decision, "data": data}),
                        expect=expect)


def marker(project: Kiripix, marker_id: str, marker_type: str, expect: int = 0, **fields: Any) -> dict[str, Any]:
    return decide_place(project, "marker", {"id": marker_id, "type": marker_type, "x": 10, "y": 10, **fields}, expect)


def walled_room_with_a_look(project: Kiripix, opening: bool = True) -> Path:
    """The lamp room with a wall of `solid` and a Look that has its own `solid`, with the wall opened."""
    folder = room_with_a_lamp_layer(project)
    project.json("decide", ROOM, "masks", "--decision",
                 json.dumps({"decision": "polygon", "data": {"mask": "solid", "erase": False, "points": WALL}}))
    import_and_pick(project, edited(), LOOK)
    decide_look(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    if opening:
        decide_look(project, "solid", OPENING)
    return folder


def run_place(project: Kiripix) -> dict[str, Any]:
    """Build down to `place`; its Checks may fail (a Layer with no y-sort line), so the exit code isn't asserted."""
    for stage in ("masks", "palette", "looks"):
        project.json("run", ROOM, stage)
    result = project("run", ROOM, "place", "--json")
    assert result.code in (0, 2), result.json
    return dict(result.json)


def markers_file(folder: Path) -> dict[str, Any]:
    built: dict[str, Any] = json.loads((folder / "work" / "place" / "markers.json").read_text("utf-8"))
    return built


def mask(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        assert image.mode == "1"
        return np.asarray(image, dtype=np.bool_)


def codes(project: Kiripix, prefix: str) -> list[str]:
    return [f["code"] for f in project("check", ROOM, "--json").json["findings"] if f["code"].startswith(prefix)]


def test_a_light_with_a_look_is_written_with_it_and_every_other_marker_has_null(project: Kiripix) -> None:
    folder = walled_room_with_a_look(project)
    marker(project, "lamp.main", "light", colour="#FFAA00", radius=20, energy=1.0)
    marker(project, "lamp.gate", "light", colour="#FFAA00", radius=20, energy=1.0, look=LOOK)
    marker(project, "chest", "interactable")
    marker(project, "torch", "emitter", name="sparks", look=LOOK)

    run_place(project)

    built = markers_file(folder)
    assert built["schema_version"] == 4
    assert {m["id"]: m["look"] for m in built["markers"]} == {
        "lamp.main": None, "lamp.gate": LOOK, "chest": None, "torch": LOOK}


def test_a_look_on_a_spawn_an_exit_or_an_area_is_refused_and_not_recorded(project: Kiripix) -> None:
    walled_room_with_a_look(project)

    for kind, extra in (("spawn", {}), ("exit", {"target_room": "room.other", "target_exit": "back"}),
                        ("area", {"x2": 20, "y2": 20})):
        refused = marker(project, f"bad.{kind}", kind, expect=1, look=LOOK, **extra)
        assert [f["code"] for f in refused["findings"]] == ["marker.look_type"]
        assert all((f["fix"] is None) != (f["owner_action"] is None) for f in refused["findings"])

    shown = project.json("show", ROOM)["data"]["stages"]
    assert next(s for s in shown if s["stage"] == "place")["markers"] == []


def test_a_look_that_no_pick_built_is_refused_and_not_recorded(project: Kiripix) -> None:
    walled_room_with_a_look(project)

    refused = marker(project, "lamp.gate", "light", expect=1, colour="#FFAA00", radius=20, energy=1.0, look="nope")

    assert [f["code"] for f in refused["findings"]] == ["marker.unknown_look"]
    shown = project.json("show", ROOM)["data"]["stages"]
    assert next(s for s in shown if s["stage"] == "place")["markers"] == []


def test_a_marker_id_used_by_the_room_and_a_look_is_a_duplicate_and_the_same_id_and_type_moves_it(
        project: Kiripix) -> None:
    folder = walled_room_with_a_look(project)
    marker(project, "glow", "light", colour="#FFAA00", radius=20, energy=1.0)
    marker(project, "glow", "emitter", name="sparks", look=LOOK)

    run_place(project)
    assert "marker.duplicate_id" in codes(project, "marker.")

    # the same ID and type again, now in the Look: one Marker, moved
    marker(project, "glow", "light", colour="#FFAA00", radius=20, energy=1.0, look=LOOK)
    decide_place(project, "marker", {"id": "glow", "type": "emitter", "x": 10, "y": 10, "name": "sparks"})
    run_place(project)
    assert "marker.duplicate_id" in codes(project, "marker.")  # still a light and an emitter of one ID
    placed = {(m["id"], m["type"]): m["look"] for m in markers_file(folder)["markers"]}
    assert placed == {("glow", "light"): LOOK, ("glow", "emitter"): None}

    # and a move out of the Look
    marker(project, "glow", "light", colour="#FFAA00", radius=20, energy=1.0)
    run_place(project)
    assert {(m["id"], m["type"]): m["look"] for m in markers_file(folder)["markers"]}[("glow", "light")] is None


def test_a_look_that_clears_solid_gets_its_own_walkable_and_clear_and_one_without_gets_neither(
        project: Kiripix) -> None:
    folder = walled_room_with_a_look(project)
    import_and_pick(project, edited(), OTHER)
    decide_look(project, "polygon", {"look": OTHER, "points": LAMP_BOX})

    run_place(project)

    place = folder / "work" / "place"
    room_walkable, room_clear = mask(place / "walkable.png"), mask(place / "clear.png")
    own_walkable, own_clear = mask(place / "looks" / LOOK / "walkable.png"), mask(place / "looks" / LOOK / "clear.png")
    assert own_walkable.shape == room_walkable.shape
    assert (own_walkable >= room_walkable).all() and own_walkable.sum() > room_walkable.sum()
    assert (own_clear >= room_clear).all() and own_clear.sum() > room_clear.sum()
    assert own_walkable[:, 20:28].any(), "the opening is walkable"
    assert not room_walkable[:, 20:28].any()
    assert not (place / "looks" / OTHER).exists()


def test_two_looks_with_overlapping_regions_warn_look_overlap_naming_both(project: Kiripix) -> None:
    walled_room_with_a_look(project)
    import_and_pick(project, edited(), OTHER)
    decide_look(project, "polygon", {"look": OTHER, "points": LAMP_BOX})
    project.json("run", ROOM, "masks")
    project.json("run", ROOM, "palette")
    project.json("run", ROOM, "looks")

    found = [f for f in project("check", ROOM, "--json").json["findings"] if f["code"] == "look.overlap"]

    [finding] = found
    assert finding["severity"] == "warning"
    assert LOOK in finding["message"] and OTHER in finding["message"]
    assert (finding["fix"] is None) != (finding["owner_action"] is None)


def test_looks_that_do_not_overlap_give_no_look_overlap(project: Kiripix) -> None:
    walled_room_with_a_look(project)
    import_and_pick(project, edited(), OTHER)
    decide_look(project, "polygon", {"look": OTHER, "points": [[40, 24], [44, 24], [44, 28], [40, 28]]})
    project.json("run", ROOM, "masks")
    project.json("run", ROOM, "palette")
    project.json("run", ROOM, "looks")

    assert codes(project, "look.overlap") == []


def test_a_schema_2_markers_file_is_refused_naming_the_rebuild_and_a_look_edit_makes_place_stale(
        project: Kiripix) -> None:
    folder = walled_room_with_a_look(project)
    run_place(project)
    assert stage_status(project, ROOM)["place"] == "done"

    path = folder / "work" / "place" / "markers.json"
    old = json.loads(path.read_text("utf-8"))
    old["schema_version"] = 2
    for each in old["markers"]:
        each.pop("look", None)
    path.write_text(json.dumps(old), "utf-8")
    refused = project.json("check", ROOM, expect=2)  # a finding naming the rebuild, not internal.error
    assert any(f["code"] == "stage.output_unreadable" and f["fix"].startswith(f"kiripix run {ROOM} place")
               for f in refused["findings"])
    assert any(f"kiripix run {ROOM} place" in json.dumps(f) for f in refused["findings"])

    run_place(project)
    decide_look(project, "solid", {"look": LOOK, "points": [[2, 2], [4, 2], [4, 4], [2, 4]]})
    project.json("run", ROOM, "looks")
    assert stage_status(project, ROOM)["place"] == "stale"
