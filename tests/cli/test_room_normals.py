"""The room's `normals` Stage (ticket 0341, ADR 0014), with the fake depth Runner (a ramp, 0 at the left and 1 at the right, so
every floor pixel is steeply tilted): `mode` `off` is done with no output and no Runner call; `depth` pins one call (its `size`
in the key), waits for the Owner's accept, and writes one `normal.png` of the room's size; `normals.not_flat_walkable` finds the
tilted walkable ground and its `fix`, a `flatten` Decision, clears it; a palette change leaves the Stage done; the preview shows
the normals and the room lit."""

import json
import shlex
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_masks import ROOM
from test_matter import calls, pinned
from test_place import findings, walled_room

CODE = "normals.not_flat_walkable"
FLAT = (128, 128, 255, 255)
WALKABLE = (slice(4, 29), slice(22, 43))  # the walled room's walkable spots: y 4 to 28, x 22 to 42 (see test_place)


def normal_of(folder: Path) -> np.ndarray:
    with Image.open(folder / "work" / "normals" / "normal.png") as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8)


def lit_room(project: Kiripix) -> Path:
    """The walled room with `mode` `depth`, the depth pinned and accepted, run on."""
    folder = walled_room(project)
    project.json("set", ROOM, "normals", "mode=depth")
    project.json("run", ROOM, expect=3)  # masks, then normals waits for its Runner
    project.json("run", ROOM, "normals", "--rerun", expect=3)
    project.json("accept", ROOM, "normals", owner=True)
    project.json("run", ROOM, expect=3)
    return folder


def flatten(project: Kiripix, **data: Any) -> None:
    project.json("decide", ROOM, "normals", "--decision", json.dumps({"decision": "flatten", "data": data}))
    project.json("run", ROOM, expect=3)


def test_off_is_done_with_no_output_and_no_runner_call(project: Kiripix) -> None:
    folder = walled_room(project)

    project.json("run", ROOM, expect=3)

    status = stage_status(project, ROOM)
    assert status["normals"] == "done" and status["palette"] == "done"
    assert [p.name for p in (folder / "work" / "normals").iterdir() if not p.name.startswith(".")] == []
    assert calls(project) == [] and pinned(folder) == []
    assert project.json("preview", ROOM, "--stage", "normals", expect=1)["findings"][0]["code"] == "preview.no_image"
    assert project.json("preview", ROOM, "--overlay", "lit", expect=1)["findings"][0]["code"] == "preview.no_normals"


def test_depth_pins_one_call_waits_for_the_owner_then_writes_one_normal_map_of_the_rooms_size(project: Kiripix) -> None:
    folder = walled_room(project)
    project.json("set", ROOM, "normals", "mode=depth")

    project.json("run", ROOM, expect=3)
    assert stage_status(project, ROOM)["normals"] == "needs-input" and calls(project) == []
    assert project.json("next", ROOM)["data"]["command"] == f"kiripix run {ROOM} normals --rerun"

    project.json("run", ROOM, "normals", "--rerun", expect=3)
    [call] = calls(project)
    assert call["params"] == {"size": 1036} and len(pinned(folder)) == 1
    assert stage_status(project, ROOM)["normals"] == "needs-review"

    project.json("accept", ROOM, "normals", owner=True)
    project.json("run", ROOM, expect=3)

    status = stage_status(project, ROOM)
    assert status["normals"] == "done" and status["palette"] == "done" and len(calls(project)) == 1
    normal = normal_of(folder)
    assert normal.shape == (32, 48, 4) and (normal[..., 3] == 255).all()
    assert (normal[16, 30] != FLAT).any(), "the ramp tilts the floor"
    assert sorted(p.name for p in (folder / "work" / "normals").iterdir() if not p.name.startswith(".")) == [
        "depth.png", "normal.png"]
    with Image.open(folder / "work" / "normals" / "depth.png") as picture:
        assert picture.mode == "RGBA" and np.asarray(picture)[16, 0, 0] < np.asarray(picture)[16, 47, 0]


def test_a_flatten_takes_a_tilted_walkable_area_out_of_the_finding_and_a_palette_change_leaves_the_stage_done(
        project: Kiripix) -> None:
    folder = lit_room(project)
    before = findings(project.json("check", ROOM), CODE)
    assert before and before[0]["severity"] == "warning" and before[0]["position"]["stage"] == "normals"
    assert before[0]["fix"].startswith(f"kiripix decide {ROOM} normals --decision ")

    for finding in before:  # the fix of each area is a runnable `flatten` over it
        *_, decision = shlex.split(finding["fix"])
        project.json("decide", ROOM, "normals", "--decision", decision)
    project.json("run", ROOM, expect=3)

    assert findings(project.json("check", ROOM), CODE) == []
    assert (normal_of(folder)[WALKABLE] == FLAT).all()
    assert len(calls(project)) == 1, "a flatten replays with no Runner call"

    project.json("set", ROOM, "palette", "orphan_size=2")
    project.json("run", ROOM, expect=3)
    assert stage_status(project, ROOM)["normals"] == "done" and stage_status(project, ROOM)["palette"] == "done"
    assert len(calls(project)) == 1


def test_an_erase_gives_the_stages_normals_back_and_a_wall_in_the_shape_stays_with_walkable(project: Kiripix) -> None:
    folder = lit_room(project)
    made = normal_of(folder)
    square = [[0, 0], [47, 0], [47, 31], [0, 31]]

    flatten(project, shape="polygon", points=square, walkable=True)
    walked = normal_of(folder)
    assert (walked[WALKABLE] == FLAT).all() and (walked[:, :4] == made[:, :4]).all(), "the wall isn't walkable: it stays"

    flatten(project, shape="polygon", points=square, erase=True)
    assert (normal_of(folder) == made).all()

    flatten(project, shape="brush", points=[[5, 5], [9, 5]], radius=1)
    assert (normal_of(folder)[5, 5:10] == FLAT).all()


def test_a_flatten_with_a_brush_and_no_radius_or_a_short_polygon_is_refused(project: Kiripix) -> None:
    walled_room(project)
    for data in ({"shape": "brush", "points": [[1, 1]]}, {"shape": "polygon", "points": [[1, 1], [4, 4]]},
                 {"shape": "polygon", "points": [[1, 1], [4, 4], [4, 1]], "radius": 2}):
        result = project.json("decide", ROOM, "normals", "--decision", json.dumps({"decision": "flatten", "data": data}),
                              expect=1)
        assert result["ok"] is False and result["findings"]


def test_the_preview_shows_the_normals_and_the_room_lit(project: Kiripix) -> None:
    lit_room(project)

    normals = project.json("preview", ROOM, "--stage", "normals", "--zoom", "2")["data"]
    lit = project.json("preview", ROOM, "--stage", "palette", "--overlay", "lit", "--zoom", "2")["data"]
    plain = project.json("preview", ROOM, "--stage", "palette", "--zoom", "2")["data"]

    assert (normals["width"], normals["height"]) == (96, 64) and lit["overlay"] == "lit"
    shown = np.asarray(Image.open(project.cwd / lit["path"]).convert("RGBA"))
    unlit = np.asarray(Image.open(project.cwd / plain["path"]).convert("RGBA"))
    assert shown.shape == unlit.shape and (shown != unlit).any(), "the normals change the light"


def test_a_depth_the_gpu_has_no_room_for_gives_a_fix_that_sets_size_to_518(project: Kiripix) -> None:
    walled_room(project)
    project.json("set", ROOM, "normals", "mode=depth")
    project.json("run", ROOM, expect=3)
    (project.cwd / "runner-out-of-memory").write_text("", encoding="utf-8")

    result = project.json("run", ROOM, "normals", "--rerun", expect=1)

    [failure] = [f for f in result["findings"] if f["code"] == "stage.failed"]
    assert failure["fix"] == f"kiripix set {ROOM} normals size=518" and "`size`" in failure["message"]
    project.json("set", ROOM, "normals", "size=518")
    (project.cwd / "runner-out-of-memory").unlink()
    project.json("run", ROOM, "normals", "--rerun", expect=3)
    assert [c["params"] for c in calls(project)] == [{"size": 1036}, {"size": 518}], "the failed call, then the one at 518"
