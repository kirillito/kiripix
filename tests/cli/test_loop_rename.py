"""Rename and remove a Loop (ticket 0207): two `loops` Decisions that the Stage replays, so the Loop's earlier Decisions
follow its new ID or stop applying. An exported Loop's ID is frozen, and the edit is refused before it is recorded."""

import json
from typing import Any

from conftest import Kiripix, stage_status
from test_export_loops import ON_LAYER, looping_room
from test_layers_stage import ROOM
from test_loop_kit import KIT, TRIANGLE, a_frame_loop, painted, write_kit
from test_loops import LOOP, WHOLE, build, colours, decide, out, record
from test_looks_build import LAMP_BOX, LOOK, edited, import_and_pick
from test_looks_build import decide as decide_look

NEW = "lantern"


def ids(folder: Any) -> list[str]:
    built = json.loads((out(folder) / "loops.json").read_text("utf-8"))
    return sorted(entry["id"] for entry in built["loops"])


def journal(project: Kiripix) -> bytes:
    return next(project.cwd.glob("**/decisions/loops.jsonl")).read_bytes()


def a_cycle_loop(project: Kiripix) -> Any:
    folder = looping_room(project, plain=True)
    c = colours(folder)
    decide(project, "loop", {"loop": LOOP})
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "cycle", {"loop": LOOP, "colours": [c["floor"], c["lamp"], c["wall"]]})
    decide(project, "timing", {"loop": LOOP, "ticks": 6})
    decide(project, "loop", {"loop": "crate_glow"})
    decide(project, "flood", {"loop": "crate_glow", "x": 40, "y": 24})
    decide(project, "cycle", {"loop": "crate_glow", "colours": [c["crate"], c["floor"]]})
    return folder


def test_a_renamed_cycle_loop_keeps_its_frames_and_undo_brings_the_old_id_back(project: Kiripix) -> None:
    folder = a_cycle_loop(project)
    build(project)
    before = record(folder)
    strip = (out(folder) / before["plate"]).read_bytes()

    decide(project, "rename", {"loop": LOOP, "to": NEW})
    project.json("run", ROOM, "loops")

    assert ids(folder) == sorted([NEW, "crate_glow"])
    after = record(folder, NEW)
    assert after["frames"] == before["frames"] == 3 and after["sequence"] == before["sequence"]
    assert (out(folder) / after["plate"]).read_bytes() == strip
    decide(project, "timing", {"loop": NEW, "ticks": 9})  # a Decision after the rename names the new ID
    project.json("run", ROOM, "loops")
    assert record(folder, NEW)["ticks"] == 27 and record(folder, "crate_glow")["frames"] == 2
    project.json("undo", ROOM, "loops")
    project.json("undo", ROOM, "loops")  # the timing, then the rename
    project.json("run", ROOM, "loops")
    assert ids(folder) == sorted([LOOP, "crate_glow"]) and record(folder)["ticks"] == before["ticks"]


def test_a_renamed_kit_loop_keeps_its_imported_frames(project: Kiripix) -> None:
    folder = a_frame_loop(project, TRIANGLE, lamp_layer=False)
    write_kit(project, 3)
    painted(project, 1)
    painted(project, 2)
    project.json("import", ROOM, project.cwd / KIT / "frame_001.png", project.cwd / KIT / "frame_002.png", "--loop", LOOP)
    build(project)
    before = record(folder)
    strip = (out(folder) / before["plate"]).read_bytes()

    decide(project, "rename", {"loop": LOOP, "to": NEW})
    project.json("run", ROOM, "loops")

    assert ids(folder) == [NEW] and stage_status(project, ROOM)["loops"] == "done"
    assert record(folder, NEW)["frames"] == 3 and (out(folder) / record(folder, NEW)["plate"]).read_bytes() == strip
    assert (folder / "src" / "loops" / LOOP).is_dir(), "the imported files stay where they were"
    project.json("undo", ROOM, "loops")
    project.json("run", ROOM, "loops")
    assert ids(folder) == [LOOP] and record(folder)["frames"] == 3


def test_a_removed_loop_is_gone_and_the_others_are_unchanged(project: Kiripix) -> None:
    folder = a_cycle_loop(project)
    build(project)
    other = (out(folder) / record(folder, "crate_glow")["plate"]).read_bytes()

    decide(project, "remove", {"loop": LOOP})
    project.json("run", ROOM, "loops")

    assert ids(folder) == ["crate_glow"]
    assert (out(folder) / record(folder, "crate_glow")["plate"]).read_bytes() == other
    decide(project, "loop", {"loop": LOOP})  # declared again after the remove: a new, empty Loop
    project.json("run", ROOM, "loops", expect=2)
    assert record(folder)["held"] and "no cycle" in record(folder)["held"]
    project.json("undo", ROOM, "loops")
    project.json("undo", ROOM, "loops")
    project.json("run", ROOM, "loops")
    assert ids(folder) == sorted([LOOP, "crate_glow"]) and record(folder)["frames"] == 3


def test_a_rename_to_a_look_or_another_loop_or_of_an_unknown_loop_is_refused(project: Kiripix) -> None:
    a_cycle_loop(project)
    import_and_pick(project, edited())
    decide_look(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    kept = journal(project)

    for data in ({"loop": LOOP, "to": LOOK}, {"loop": LOOP, "to": "crate_glow"}, {"loop": "nothing", "to": NEW},
                 {"loop": LOOP, "to": LOOP}):
        result = decide(project, "rename", data, expect=1)
        [found] = result["findings"]
        assert found["code"].startswith("loop.") and bool(found["fix"]) != bool(found["owner_action"])
    assert decide(project, "remove", {"loop": "nothing"}, expect=1)["findings"]
    assert decide(project, "rename", {"loop": LOOP, "to": "Not An Id"}, expect=1)["findings"]
    assert journal(project) == kept, "nothing was recorded"


def test_an_exported_loop_cannot_be_removed_or_renamed(project: Kiripix) -> None:
    looping_room(project)
    project.json("export", ROOM)
    kept = journal(project)

    for decision, data in (("remove", {"loop": ON_LAYER}), ("rename", {"loop": ON_LAYER, "to": NEW})):
        result = decide(project, decision, data, expect=1)
        [found] = result["findings"]
        assert found["code"] == "export.id_frozen" and ON_LAYER in found["message"] and found["owner_action"]
    assert journal(project) == kept
    # an array with a frozen edit is refused whole
    decide_all = project.json("decide", ROOM, "loops", "--decision", json.dumps([
        {"decision": "loop", "data": {"loop": "extra"}}, {"decision": "remove", "data": {"loop": LOOP}}]), expect=1)
    assert decide_all["findings"][0]["code"] == "export.id_frozen" and journal(project) == kept
    # a Loop the game doesn't have yet can be renamed freely
    decide(project, "loop", {"loop": "extra"})
    decide(project, "rename", {"loop": "extra", "to": "extra_two"})


def test_redoing_a_remove_of_a_loop_exported_since_is_refused(project: Kiripix) -> None:
    looping_room(project)
    decide(project, "remove", {"loop": LOOP})
    project.json("undo", ROOM, "loops")  # the remove waits to be redone
    project.json("run", ROOM)
    project.json("export", ROOM)
    kept = journal(project)

    result = project.json("redo", ROOM, "loops", expect=1)

    assert result["findings"][0]["code"] == "export.id_frozen" and journal(project) == kept


def test_redoing_a_rename_to_an_id_taken_since_is_refused(project: Kiripix) -> None:
    a_cycle_loop(project)
    decide(project, "rename", {"loop": LOOP, "to": NEW})
    project.json("undo", ROOM, "loops")  # the rename waits to be redone
    decide(project, "loop", {"loop": NEW})  # and its new ID is taken meanwhile
    kept = journal(project)

    result = project.json("redo", ROOM, "loops", expect=1)

    assert [f["code"] for f in result["findings"]] == ["loop.id_taken"] and journal(project) == kept
