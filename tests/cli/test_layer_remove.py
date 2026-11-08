"""The `remove` Decision on `layers` (ticket 0091, spec §6.3, §9): the Layer's pixels go back to the Plate, its clicks and
trims stop counting, its y-sort line and flag in `place` stop counting, and an exported Layer's ID is frozen."""

import json
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_export_layers import layered_room
from test_layers_stage import ROOM, accept, alpha_of, built_room, calls, click, lift, out, recomposed, rgba
from test_place import sort_of


def remove(project: Kiripix, layer: str, expect: int = 0) -> dict[str, Any]:
    return project.json("decide", ROOM, "layers", "--decision",
                        json.dumps({"decision": "remove", "data": {"layer": layer}}), expect=expect)


def listed(folder: Any) -> list[str]:
    built = json.loads((out(folder) / "layers.json").read_text("utf-8"))
    return [entry["id"] for entry in built["layers"]]


def test_removing_a_layer_gives_its_pixels_back_to_the_plate_and_place_stops_asking_for_its_line(
        project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    click(project, "crate", 40, 24)
    lift(project)
    accept(project)
    both = calls(project)
    assert both == (2, 2) and stage_status(project, ROOM)["layers"] == "done"
    fit = rgba(folder / "work" / "fit" / "fit.png")

    remove(project, "crate")
    assert stage_status(project, ROOM)["layers"] != "done", "the Decision changes the Stage's input"
    project.json("run", ROOM, "layers")  # the pins the Owner accepted are all it uses: nothing to review
    assert stage_status(project, ROOM)["layers"] == "done"

    assert calls(project) == both, "nothing is made again: the lamp's pinned results are the ones used"
    assert listed(folder) == ["lamp"] and not (out(folder) / "layer.crate.png").exists()
    plate = rgba(out(folder) / "plate.png")
    lamp = alpha_of(folder, "lamp")
    assert (plate[~lamp] == fit[~lamp]).all(), "the crate's pixels are the fit image's again"
    assert (recomposed(folder) == fit).all()
    assert (np.asarray(Image.open(out(folder) / "foreground.png")) == lamp).all()

    # the same Plate as if only the lamp had been lifted: undo the removal and the crate's click
    project.json("undo", ROOM, "layers")
    project.json("undo", ROOM, "layers")
    project.json("run", ROOM, "layers")
    assert listed(folder) == ["lamp"] and (rgba(out(folder) / "plate.png") == plate).all()


def test_undo_brings_the_removed_layer_back_and_a_new_click_starts_a_new_layer(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    click(project, "crate", 40, 24)
    lift(project)
    accept(project)
    before = rgba(out(folder) / "layer.crate.png")
    made = calls(project)

    remove(project, "crate")
    project.json("run", ROOM, "layers")
    assert listed(folder) == ["lamp"]
    project.json("undo", ROOM, "layers")
    project.json("run", ROOM, "layers")

    assert listed(folder) == ["lamp", "crate"] and (rgba(out(folder) / "layer.crate.png") == before).all()
    assert calls(project) == made

    project.json("redo", ROOM, "layers")
    click(project, "crate", 8, 8)  # a new Layer: the lamp's object under the crate's ID
    lift(project)
    crate = alpha_of(folder, "crate")
    assert crate[8, 8] and not crate[24, 40], "the old crate's pixels didn't come back"
    assert (recomposed(folder) == rgba(folder / "work" / "fit" / "fit.png")).all()


def test_removing_a_layer_nothing_lifted_needs_the_owner(project: Kiripix) -> None:
    built_room(project)
    click(project, "lamp", 8, 8)
    remove(project, "crate")

    result = project.json("run", ROOM, "layers", expect=3)

    assert "crate" in json.dumps(result) and "comes before any click" in json.dumps(result)


def test_removed_layers_line_and_flag_stop_counting_in_place(project: Kiripix) -> None:
    folder = layered_room(project)
    assert [s["layer"] for s in sort_of(folder)] == ["lamp", "crate"]

    remove(project, "crate")
    project.json("run", ROOM, "layers")
    project.json("run", ROOM, expect=3)  # the Masks replay onto the changed Plate
    project.json("accept", ROOM, "masks", owner=True)
    result = project.json("run", ROOM)

    assert [s["layer"] for s in sort_of(folder)] == ["lamp"]
    findings = project.json("check", ROOM)["findings"]
    assert not [f for f in findings if f["code"] in ("layer.no_ysort", "ysort.unknown_layer")], result
    room = json.loads((folder / "out" / "export" / "room.json").read_text("utf-8"))
    assert [layer["id"] for layer in room["layers"]] == ["lamp"]


def test_removing_an_exported_layer_is_refused_naming_the_freeze(project: Kiripix) -> None:
    folder = layered_room(project)
    project.json("export", ROOM)
    sizes = {p: p.stat().st_size for p in folder.rglob("*.jsonl")}

    result = remove(project, "crate", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "export.id_frozen" and "'crate'" in finding["message"] and "removed" in finding["message"]
    assert finding["owner_action"] and not finding.get("fix")
    assert {p: p.stat().st_size for p in folder.rglob("*.jsonl")} == sizes, "nothing was recorded"


def test_a_remove_changes_the_runner_calls_the_stage_is_waiting_on(project: Kiripix) -> None:
    """The Runner calls are kept by what they derive from (ticket 0090); a `remove` is a Decision, so it is part of that:
    a removed Layer's lift needs no fill, and its undo needs it again."""
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    click(project, "crate", 40, 24)
    lift(project)
    accept(project)
    pins = len(list((folder / "pinned").glob("*.png")))
    assert pins == 4 and stage_status(project, ROOM)["layers"] == "done"

    click(project, "crate", 4, 8, positive=False)  # a call nobody made yet
    assert project.json("next", ROOM)["data"]["reason"] == "Runner not run yet"
    project.json("undo", ROOM, "layers")
    remove(project, "crate")
    assert stage_status(project, ROOM)["layers"] == "stale", "the crate's call is no longer needed, and the Stage changed"
    project.json("run", ROOM, "layers")
    assert stage_status(project, ROOM)["layers"] == "done"

    click(project, "crate", 8, 8)  # a new Layer needs a new segmentation (the lamp's pinned one) and a new fill
    assert project.json("next", ROOM)["data"]["reason"] == "Runner not run yet"
    assert len(list((folder / "pinned").glob("*.png"))) == pins


def test_redoing_the_remove_of_a_layer_exported_since_is_refused_naming_the_freeze(project: Kiripix) -> None:
    folder = layered_room(project)
    remove(project, "crate")
    project.json("undo", ROOM, "layers")
    project.json("export", ROOM)  # the undo left the Decisions as built, so `crate` is exported and frozen now
    sizes = {p: p.stat().st_size for p in folder.rglob("*.jsonl")}

    result = project.json("redo", ROOM, "layers", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "export.id_frozen" and "'crate'" in finding["message"]
    assert {p: p.stat().st_size for p in folder.rglob("*.jsonl")} == sizes, "nothing was recorded"
