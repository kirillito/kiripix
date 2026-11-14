"""A Look's edit Variants (ticket 0129, ADR 0009): `import --look` and `pick --look`, and what they do to the `looks`
Stage. The Stage's build is empty here; ticket 0130 builds a Look's image."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status
from PIL import Image
from test_masks import ROOM, built_room, plate

LOOK = "door_shut"


def edit(project: Kiripix, name: str = "edit.png", shift: int = 0) -> str:
    """An edit of the room's Source: the Plate with some pixels changed (`shift` makes another image)."""
    pixels = plate().copy()
    pixels[2:4, 2 + shift:4 + shift] = (255, 0, 77, 255)
    Image.fromarray(pixels, "RGBA").save(project.cwd / name)
    return name


def import_look(project: Kiripix, name: str = "edit.png", look: str = LOOK, expect: int = 0) -> dict[str, Any]:
    return project.json("import", ROOM, name, "--look", look, expect=expect)


def built(project: Kiripix) -> Path:
    """A room built to its last Stage that can be (the run stops at `reach`, with no Spawn or Exit)."""
    folder = built_room(project)
    project.json("run", ROOM, expect=3)
    return folder


def test_an_edit_is_stored_under_the_look_and_the_source_stays_done(project: Kiripix) -> None:
    folder = built(project)
    assert stage_status(project, ROOM)["looks"] == "done"  # no Looks: done at once

    data = import_look(project, edit(project))["data"]

    status = stage_status(project, ROOM)
    assert status["source"] == "done" and status["looks"] == "stale"
    assert status["palette"] == "done" and status["place"] == "done"  # nothing above `looks` moves
    assert data["look"] == LOOK and data["created"] and data["variants"] == [data["variant"]]
    assert (folder / "src" / "looks" / LOOK / f"{data['variant']}.png").is_file()
    assert data["file"] == f"assets/room/alley/src/looks/{LOOK}/{data['variant']}.png"
    assert data["variant"] not in [p.stem for p in (folder / "src").glob("*.png")]


def test_importing_the_same_edit_again_is_a_no_op_and_a_jpeg_is_stored_as_a_png(project: Kiripix) -> None:
    folder = built(project)
    first = import_look(project, edit(project))["data"]

    again = import_look(project, "edit.png")["data"]
    Image.open(project.cwd / "edit.png").convert("RGB").save(project.cwd / "edit.jpg", quality=95)
    jpeg = import_look(project, "edit.jpg", look="lamp")["data"]

    assert not again["created"] and again["variant"] == first["variant"]
    stored = folder / "src" / "looks" / "lamp" / f"{jpeg['variant']}.png"
    assert stored.read_bytes().startswith(b"\x89PNG")


def test_picking_the_edit_records_a_decision_in_the_looks_journal_with_the_source(project: Kiripix) -> None:
    folder = built(project)
    variant = import_look(project, edit(project))["data"]["variant"]

    data = project.json("pick", ROOM, variant, "--look", LOOK)["data"]

    entries = [json.loads(line) for line in (folder / "decisions" / "looks.jsonl").read_text("utf-8").splitlines()]
    assert data["look"] == LOOK and data["stage"] == "looks"
    assert len(entries) == 1 and entries[0]["decision"] == "pick"
    source_variant = next(p.stem for p in (folder / "src").glob("*.png"))
    assert entries[0]["data"] == {"look": LOOK, "variant": variant, "source": source_variant}
    assert stage_status(project, ROOM)["looks"] == "stale"  # the Pick is an input too
    project.json("run", ROOM, "looks")
    assert stage_status(project, ROOM)["looks"] == "done"


def test_a_new_source_stops_the_looks_with_the_reason(project: Kiripix) -> None:
    built(project)
    variant = import_look(project, edit(project))["data"]["variant"]
    project.json("pick", ROOM, variant, "--look", LOOK)
    project.json("run", ROOM, "looks")
    other = project.json("import", ROOM, edit(project, "other.png", shift=8))["data"]["variant"]

    project.json("pick", ROOM, other)

    row = next(a for a in project.json("status")["data"]["assets"] if a["asset"] == ROOM)
    looks = next(s for s in row["stages"] if s["stage"] == "looks")
    assert looks["status"] == "needs-input" and looks["reason"] == "the edit was made on another Source"
    result = project("run", ROOM, "--json")
    assert result.code == 3
    finding = next(f for f in result.json["findings"] if f["code"] == "stage.needs_input")
    assert finding["fix"] is None and LOOK in finding["owner_action"]


def test_a_new_pick_on_the_new_source_applies_again(project: Kiripix) -> None:
    built(project)
    variant = import_look(project, edit(project))["data"]["variant"]
    project.json("pick", ROOM, variant, "--look", LOOK)
    other = project.json("import", ROOM, edit(project, "other.png", shift=8))["data"]["variant"]
    project.json("pick", ROOM, other)

    project.json("pick", ROOM, variant, "--look", LOOK)  # made on the old Source, but recorded now against the new one

    assert stage_status(project, ROOM)["looks"] != "needs-input"


def test_a_picked_edit_that_was_deleted_stops_the_looks(project: Kiripix) -> None:
    folder = built(project)
    variant = import_look(project, edit(project))["data"]["variant"]
    project.json("pick", ROOM, variant, "--look", LOOK)

    (folder / "src" / "looks" / LOOK / f"{variant}.png").unlink()

    assert stage_status(project, ROOM)["looks"] == "needs-input"


def test_the_edits_of_two_looks_are_kept_apart(project: Kiripix) -> None:
    built(project)
    one = import_look(project, edit(project))["data"]
    two = import_look(project, edit(project, "other.png", shift=8), look="lamp")["data"]

    assert one["variants"] == [one["variant"]] and two["variants"] == [two["variant"]]
    refused = project.json("pick", ROOM, one["variant"], "--look", "lamp", expect=1)
    assert [f["code"] for f in refused["findings"]] == ["pick.unknown_variant"]


def test_an_edit_is_refused_on_a_non_room_and_on_a_room_with_no_picked_source(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    project.json("new", "room", "alley", "--view", "top")
    Image.fromarray(plate(), "RGBA").save(project.cwd / "edit.png")

    prop = project.json("import", "prop.bench", "edit.png", "--look", LOOK, expect=1)
    bare = project.json("import", ROOM, "edit.png", "--look", LOOK, expect=1)
    pick = project.json("pick", ROOM, "0123", "--look", LOOK, expect=1)

    assert [f["code"] for f in prop["findings"]] == ["import.look_needs_room"]
    assert [f["code"] for f in bare["findings"]] == ["import.look_needs_source"]
    assert [f["code"] for f in pick["findings"]] == ["pick.look_needs_source"]
    assert not (project.cwd / "assets" / "room" / "alley" / "src" / "looks").exists()


def test_an_edit_is_refused_when_the_only_source_is_not_picked_yet_with_a_fix(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    Image.fromarray(plate(), "RGBA").save(project.cwd / "edit.png")
    source = project.json("import", ROOM, "edit.png")["data"]["variant"]

    refused = import_look(project, expect=1)

    finding = refused["findings"][0]
    assert finding["fix"] == f"kiripix pick {ROOM} {source}" and finding["owner_action"] is None


def test_a_look_id_that_is_not_an_id_is_refused(project: Kiripix) -> None:
    built(project)

    refused = import_look(project, edit(project), look="../Door", expect=1)

    assert [f["code"] for f in refused["findings"]] == ["look.invalid_id"]


def test_describe_room_lists_the_looks_stage_with_its_pick_and_inputs(project: Kiripix) -> None:
    kind = project.json("describe", "room")["data"]["kinds"][0]

    looks = next(s for s in kind["stages"] if s["name"] == "looks")
    names = kind["recipe"]
    assert names.index("palette") + 1 == names.index("looks") == names.index("loops") - 1 == names.index("place") - 2
    assert [d["name"] for d in looks["decisions"]] == ["pick", "look", "polygon", "brush", "difference", "solid"]
    assert "src/looks/**/*.png" in json.dumps(looks)
