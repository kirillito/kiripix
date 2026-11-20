"""Ticket 0233: `status` reads agent work as work. A Stage that waits only for its Runner calls names the command that
makes them, and a Stage after the first one not done says it waits on that one, since what it shows is an older build."""

from conftest import Kiripix, stage_status
from test_masks import ROOM, built_room, decide


def status_lines(project: Kiripix) -> dict[str, str]:
    text = project("status").stdout
    return {line.split()[0]: line.strip() for line in text.splitlines()[2:] if line.startswith("    ") and line.split()}


def test_a_stage_waiting_for_its_runner_names_the_command_and_json_keeps_the_reason(project: Kiripix) -> None:
    built_room(project)
    decide(project, "click", {"x": 30, "y": 10, "mask": "solid", "positive": True})

    lines = status_lines(project)

    assert stage_status(project, ROOM)["masks"] == "needs-input"
    assert lines["masks"].startswith("masks      needs-input (run: kiripix run room.alley masks --rerun)"), lines["masks"]
    assert "Runner not run yet" in lines["masks"]
    row = next(a for a in project.json("status")["data"]["assets"] if a["asset"] == ROOM)
    masks = next(s for s in row["stages"] if s["stage"] == "masks")
    assert masks == {"stage": "masks", "status": "needs-input", "reason": "Runner not run yet"}


def test_a_stage_after_the_first_one_not_done_says_it_waits_on_it(project: Kiripix) -> None:
    built_room(project)
    decide(project, "click", {"x": 30, "y": 10, "mask": "solid", "positive": True})

    lines = status_lines(project)

    assert lines["reach"].startswith("reach      needs-input  (waits on masks; may change once masks is done: no Spawn"), lines
    assert "(waits on masks; may change once masks is done: no Godot project" in lines["export"]
    assert lines["palette"] == "palette    done", "palette doesn't read masks"
    assert "waits on" not in lines["masks"] and "waits on" not in lines["place"], "masks is the open one; place is stale"
    row = next(a for a in project.json("status")["data"]["assets"] if a["asset"] == ROOM)
    assert "waits_on" not in row and all("waits on" not in str(s) for s in row["stages"]), "the JSON is unchanged"
