"""`area-settle` (ticket 0279, spec §6.1): the ambiguous cells of an area settled by majority, `polygon` Decisions, one per cell and Mask."""

import json
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_area import area, checked
from test_masks import ROOM, decide
from test_place import findings, walled_room

# walled_room: 48 x 32, `solid` on x 0 to 15. Cells of 5 at x 20, rows y 0, 5 and 10: 7, 13 and 17 of 25 pixels.
JOURNAL = "assets/room/alley/decisions/masks.jsonl"


def _cover(project: Kiripix, y: int, columns: int, extra: int) -> None:
    """Fill `columns` whole columns of the cell at (20, y), then `extra` pixels of the next one."""
    x = 20 + columns
    for box in ([[20, y], [19 + columns, y], [19 + columns, y + 4], [20, y + 4]],
                [[x, y], [x, y + extra - 1], [x, y + extra - 1]]):  # a line: its outline pixels are filled
        decide(project, "polygon", {"mask": "solid", "erase": False, "points": box})


def _three_cells(project: Kiripix) -> None:
    walled_room(project)
    _cover(project, 0, 1, 2)    # 7 of 25: 28 %
    _cover(project, 5, 2, 3)    # 13 of 25: 52 %
    _cover(project, 10, 3, 2)   # 17 of 25: 68 %
    area(project, "battle.yard", (20, 0, 24, 14), cell=5)


def _solid(project: Kiripix) -> Any:
    with Image.open(project.cwd / "assets" / "room" / "alley" / "work" / "masks" / "solid.png") as image:
        return np.asarray(image, dtype=np.bool_)


def test_three_ambiguous_cells_get_two_fills_and_one_clear_and_place_is_quiet(project: Kiripix) -> None:
    _three_cells(project)
    assert len(findings(checked(project).json, "area.ambiguous_cells")) == 1

    done = project.json("area-settle", ROOM, "battle.yard")["data"]

    assert [(c["x"], c["y"], c["action"], c["mask"]) for c in done["cells"]] == [
        (20, 0, "clear", "solid"), (20, 5, "fill", "solid"), (20, 10, "fill", "solid")]
    assert [round(c["coverage"], 2) for c in done["cells"]] == [0.28, 0.52, 0.68]
    assert done["decisions"] == 3
    assert findings(checked(project).json, "area.ambiguous_cells") == []
    solid = _solid(project)
    assert not solid[0:5, 20:25].any() and solid[5:10, 20:25].all() and solid[10:15, 20:25].all()


def test_dry_run_changes_nothing_and_undo_takes_the_decisions_back(project: Kiripix) -> None:
    _three_cells(project)
    project("run", ROOM, "--json")
    before = project.json("show", ROOM)["data"]["stages"]
    journal = project.cwd / JOURNAL
    entries = journal.read_text(encoding="utf-8")

    dry = project.json("area-settle", ROOM, "battle.yard", "--dry-run")["data"]
    assert dry["dry_run"] and dry["decisions"] == 0 and len(dry["cells"]) == 3
    assert project.json("show", ROOM)["data"]["stages"] == before
    assert journal.read_text(encoding="utf-8") == entries, "a dry run records nothing in the masks journal"

    project.json("area-settle", ROOM, "battle.yard")
    for _ in range(3):
        project.json("undo", ROOM, "masks")
    assert len(findings(checked(project).json, "area.ambiguous_cells")) == 1


def test_a_missing_area_an_area_without_a_cell_and_stale_masks_are_refused(project: Kiripix) -> None:
    walled_room(project)
    area(project, "battle.free", (20, 0, 29, 9))

    missing = project.json("area-settle", ROOM, "battle.none", expect=1)
    assert missing["findings"][0]["code"] == "area.unknown"
    free = project.json("area-settle", ROOM, "battle.free", expect=1)
    assert free["findings"][0]["code"] == "area.no_cell"
    area(project, "battle.cells", (20, 0, 29, 9), cell=10)
    stale = project.json("area-settle", ROOM, "battle.cells", expect=1)
    assert stale["findings"][0]["code"] == "area.masks_not_built" and stale["findings"][0]["fix"]
    json.dumps(stale)
