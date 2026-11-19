"""`render` and a clip's held things (ticket 0302), on the fake Blender: what the Stage hands the script, records in `render.json`
and reuses. The real draw is in `test_blender_held.py`. The fake rig has the bones of `FAKE_BONES`; its things have one material."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status
from test_character_clips import HIT, IDLE, clip, rigged_hero
from test_character_model import HERO, calls
from test_character_render import render_calls, render_json
from test_clip_attach import SOCKET, add_thing, attached, held


def laid(folder: Path, *things: str) -> None:
    """Things as the import lays them out, and its journal: the order they were first imported."""
    for thing in things:
        add_thing(folder, thing, content=thing.encode())
    (folder / "imported.jsonl").write_text("".join(json.dumps({"schema_version": 1, "file": f"src/things/{t}/model.glb",
                                                               "imported_as": f"{t}.glb"}) + "\n" for t in things), encoding="utf-8")


def built(project: Kiripix, *things: str) -> Path:
    folder = rigged_hero(project)
    (project.cwd / "blender-bones").write_text(json.dumps(["root", SOCKET]), encoding="utf-8")  # the bones the fake render knows
    laid(folder, *things)
    clip(project, IDLE)
    clip(project, attached(held("phone"), base=HIT))
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    return folder


def test_the_script_gets_each_clips_attach_and_every_thing_in_numbering_order(project: Kiripix) -> None:
    folder = built(project, "stick", "phone")

    args = render_calls(project)[-1]["args"]

    by_name = {c["name"]: c for c in args["clips"]}
    assert by_name["hit"]["attach"] == [{"thing": "phone", "socket": SOCKET}] and "attach" not in by_name["idle"]
    assert [t["id"] for t in args["things"]] == ["stick", "phone"]  # first imported first, though only the phone is held
    assert all(Path(t["file"]).is_file() for t in args["things"])
    document = render_json(folder)
    assert [(t["thing"], t["file"], t["materials"]) for t in document["things"]] == [
        ("stick", "model.glb", [{"index": 3, "name": "metal"}]), ("phone", "model.glb", [{"index": 4, "name": "metal"}])]
    assert [m["name"] for m in document["materials"]] == ["cloth", "skin"]  # the Model's own, unchanged
    assert next(c for c in document["clips"] if c["name"] == "hit")["attach"] == [{"thing": "phone", "socket": SOCKET}]
    assert "attach" not in next(c for c in document["clips"] if c["name"] == "idle")


def test_the_current_variant_is_the_newest_import(project: Kiripix) -> None:
    folder = rigged_hero(project)
    (project.cwd / "blender-bones").write_text(json.dumps(["root", SOCKET]), encoding="utf-8")
    add_thing(folder, "phone", b"old")
    (folder / "src" / "things" / "phone" / "aaaa.glb").write_bytes(b"older")
    (folder / "imported.jsonl").write_text("".join(json.dumps({"schema_version": 1, "file": f"src/things/phone/{n}.glb"}) + "\n"
                                                  for n in ("model", "aaaa")), encoding="utf-8")
    clip(project, attached(held("phone")))

    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")

    assert [Path(t["file"]).name for t in render_calls(project)[-1]["args"]["things"]] == ["aaaa.glb"]
    # importing the other again makes it current: `render` is stale and draws it
    with (folder / "imported.jsonl").open("a", encoding="utf-8") as journal:
        journal.write(json.dumps({"schema_version": 1, "file": "src/things/phone/model.glb"}) + "\n")
    assert stage_status(project, HERO)["render"] == "stale"
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    assert [Path(t["file"]).name for t in render_calls(project)[-1]["args"]["things"]] == ["model.glb"]


def test_the_socket_a_clip_holds_at_is_a_point_by_default_and_a_given_point_there_is_not_doubled(project: Kiripix) -> None:
    folder = built(project, "phone")
    document = render_json(folder)
    assert document["points"] == [{"name": "rightforearm", "target": SOCKET}]
    assert all("rightforearm" in f["points"] for c in document["clips"] for frames in c["directions"].values() for f in frames)

    project.json("set", HERO, "render", f"points=hand_r@{SOCKET}")
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")

    assert render_json(folder)["points"] == [{"name": "hand_r", "target": SOCKET}]


def test_a_thing_changed_or_added_renders_again_and_one_nobody_holds_changes_no_clip(project: Kiripix) -> None:
    folder = built(project, "phone")
    count = len(render_calls(project))
    assert stage_status(project, HERO)["render"] == "done"

    add_thing(folder, "stick", b"new")  # a thing no clip holds: the Stage is stale (its input changed) but the clips are reused
    assert stage_status(project, HERO)["render"] == "stale"
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    assert len(render_calls(project)) == count + 1  # the numbering reads every thing, so the clips that hold are drawn again

    (folder / "src" / "things" / "phone" / "model.glb").write_bytes(b"changed")
    assert stage_status(project, HERO)["render"] == "stale"


def test_a_character_that_holds_nothing_has_no_things_and_the_script_gets_none(project: Kiripix) -> None:
    folder = rigged_hero(project)
    clip(project, IDLE)
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")

    assert "things" not in render_calls(project)[-1]["args"] and "things" not in render_json(folder)
    assert all("attach" not in c for c in calls(project)[-1]["args"].get("clips", []))
    args: dict[str, Any] = render_calls(project)[-1]["args"]
    assert "points" not in args
