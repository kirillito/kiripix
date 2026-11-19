"""A `clip` Decision's `attach` (ticket 0300, 0238): the things a clip holds, at a socket bone. A held thing lives in
`src/things/<id>/` of the Asset (ticket 0301 imports it there), so these tests lay a file out as that import will. The CLI
tests run on the fake Blender, whose rig has the Mixamo bones of `FAKE_BONES`."""

from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status
from test_character_clips import HIT, IDLE, clip, clips_json, rigged_hero
from test_character_model import HERO
from test_character_transitions import IDLE_TO_HIT, entries, transition

SOCKET = "mixamorig:RightForeArm"  # a bone of the fake rig; the default `grip_r` is the chargen's to add (ticket 0238)


def add_thing(folder: Path, thing: str, content: bytes = b"glb") -> None:
    """A held thing as ticket 0301's import lays it out: a file in `src/things/<id>/`."""
    target = folder / "src" / "things" / thing
    target.mkdir(parents=True, exist_ok=True)
    (target / "model.glb").write_bytes(content)


def attached(*things: dict[str, Any], base: dict[str, Any] = HIT) -> dict[str, Any]:
    return {**base, "attach": list(things)}


def held(thing: str = "phone", **extra: Any) -> dict[str, Any]:
    return {"thing": thing, "socket": SOCKET, **extra}


def test_a_clip_with_attach_is_recorded_listed_by_show_and_written_to_clips_json(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_thing(folder, "phone")
    add_thing(folder, "stick")
    data = attached(held("phone", offset=[0, 0.01, -0.006], turn=[0, 90, 0]), held("stick"))

    clip(project, data)
    clip(project, IDLE)

    current = _current(project)
    assert current["hit"]["attach"] == data["attach"]
    assert "attach" not in current["idle"]
    project.json("run", HERO, "clips")
    by_name = entries(folder)
    assert by_name["hit"]["attach"] == [
        {"thing": "phone", "socket": SOCKET, "offset": [0.0, 0.01, -0.006], "turn": [0.0, 90.0, 0.0]},
        {"thing": "stick", "socket": SOCKET}]
    assert "attach" not in by_name["idle"], "a clip without `attach` holds nothing, and its entry is as it was"


def _current(project: Kiripix) -> dict[str, dict[str, Any]]:
    """The clips' current Decisions by name, as `show` lists them for the `clips` Stage."""
    [stage] = [s for s in project.json("show", HERO)["data"]["stages"] if s["stage"] == "clips"]
    return {d["data"]["name"]: d["data"] for d in stage["decisions"] if d["name"] == "clip"}


def test_an_unknown_thing_is_refused_when_decided(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_thing(folder, "phone")

    result = clip(project, attached(held("flute")), expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "clips.unknown_thing" and "flute" in finding["message"] and "phone" in finding["message"]
    assert finding["owner_action"] and not finding.get("fix")
    assert "--role thing --thing flute" in finding["owner_action"]


def test_an_unknown_socket_is_refused_when_decided_with_the_rig_bones_named(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_thing(folder, "phone")

    result = clip(project, attached({"thing": "phone", "socket": "grip_x"}), expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "clips.unknown_socket" and "grip_x" in finding["message"]
    assert SOCKET in finding["message"], "the message names the rig's bones"
    assert finding["fix"] and not finding.get("owner_action")


def test_the_default_socket_is_grip_r_so_a_rig_without_it_refuses(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_thing(folder, "phone")

    result = clip(project, attached({"thing": "phone"}), expect=1)

    assert result["findings"][0]["code"] == "clips.unknown_socket" and "grip_r" in result["findings"][0]["message"]


def test_a_thing_twice_in_one_clip_is_refused(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_thing(folder, "phone")

    result = clip(project, attached(held("phone"), held("phone", offset=[0, 0, 0])), expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "decision.invalid" and "phone" in finding["message"] and "more than once" in finding["message"]


def test_a_thing_taken_away_after_the_decision_fails_the_stage_with_its_finding(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_thing(folder, "phone")
    clip(project, attached(held("phone")))
    clip(project, IDLE)
    project.json("run", HERO, "clips")
    assert stage_status(project, HERO)["clips"] == "done"

    (folder / "src" / "things" / "phone" / "model.glb").unlink()

    assert stage_status(project, HERO)["clips"] == "stale", "a thing added or removed is an input of `clips`"
    result = project.json("run", HERO, "clips", expect=3)
    assert result["findings"][0]["code"] == "clips.unknown_thing"


def test_a_thing_added_later_makes_clips_stale_and_it_builds(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_thing(folder, "phone")
    clip(project, attached(held("phone")))
    project.json("run", HERO, "clips")

    add_thing(folder, "phone", b"another glb")

    assert stage_status(project, HERO)["clips"] == "stale"
    project.json("run", HERO, "clips")
    assert entries(folder)["hit"]["attach"][0]["thing"] == "phone"


def test_a_transition_holds_what_its_from_clip_holds(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_thing(folder, "phone")
    clip(project, attached(held("phone", offset=[0, 0.01, 0]), base=IDLE))
    clip(project, HIT)
    transition(project, IDLE_TO_HIT)

    project.json("run", HERO, "clips")

    by_name = entries(folder)
    assert by_name["idle_to_hit"]["attach"] == by_name["idle"]["attach"] == [
        {"thing": "phone", "socket": SOCKET, "offset": [0.0, 0.01, 0.0]}]
    assert "attach" not in by_name["hit"]
    assert clips_json(folder)["schema_version"] == 3


def test_describe_shows_the_field_and_its_checks(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "clips")["data"]["kinds"]
    [stage] = kind["stages"]

    entry = {d["name"]: d for d in stage["decisions"]}["clip"]["entry_schema"]

    attach = entry["properties"]["attach"]
    assert set(attach["items"]["properties"]) == {"thing", "socket", "offset", "turn"}
    assert attach["items"]["properties"]["socket"]["default"] == "grip_r"
    assert attach["items"]["required"] == ["thing"]
    assert {"clips.unknown_thing", "clips.unknown_socket"} <= {c["code"] for c in stage["checks"]}
