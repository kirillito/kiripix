"""A Stage output from an older Kiripix is refused as a finding naming its rebuild, never `internal.error`, by every Command
that reads it: an M4-era room's `markers.json` (schema 1 or 2) after 0314's schema 3 (found by 0315 on the laneway)."""

import json

from conftest import Kiripix
from test_layers_stage import ROOM
from test_look_markers import run_place, walled_room_with_a_look


def test_an_old_markers_file_is_no_internal_error_in_show_status_or_check(project: Kiripix) -> None:
    folder = walled_room_with_a_look(project)
    run_place(project)
    path = folder / "work" / "place" / "markers.json"
    old = json.loads(path.read_text("utf-8"))
    old["schema_version"] = 1
    for each in old["markers"]:
        each.pop("look", None)
    path.write_text(json.dumps(old), "utf-8")

    for command in (("show", ROOM), ("status", ROOM), ("check", ROOM), ("check", "--all")):
        result = project(*command, "--json")
        codes = [finding["code"] for finding in result.json["findings"]]
        assert "internal.error" not in codes, (command, result.json["findings"])
    shown = project.json("show", ROOM)
    assert shown["ok"] is True
