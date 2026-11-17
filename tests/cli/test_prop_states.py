"""A Prop's states, declared and picked (tickets 0257 and 0258): the `state` Decision on `source`, `import --state`,
`pick --state`, `show`, and the findings. The Stages per state are ticket 0259's."""

import json
from typing import Any

from conftest import Kiripix, save_image
from test_export_prop import exportable_prop
from test_prop import PROP, built_prop

MANIFEST = "game/kiripix/manifest/prop.bench.json"


def declare(project: Kiripix, state: str, width: int = 8, height: int = 8, *, expect: int = 0) -> dict[str, Any]:
    entry = json.dumps({"decision": "state", "data": {"id": state, "width": width, "height": height}})
    return project.json("decide", PROP, "source", "--decision", entry, expect=expect)


def edit(project: Kiripix, decision: str, **data: Any) -> dict[str, Any]:
    return project.json("decide", PROP, "source", "--decision", json.dumps({"decision": decision, "data": data}), expect=0)


def an_image(project: Kiripix, name: str, colour: tuple[int, int, int, int]) -> str:
    save_image(project.cwd / name, (32, 32), colour)
    return name


def finding_codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"]]


def run_source(project: Kiripix, *, expect: int = 0) -> dict[str, Any]:
    project.json("run", PROP, "brief")
    return project.json("run", PROP, "source", expect=expect)


def states_of(project: Kiripix) -> dict[str, dict[str, Any]]:
    return {s["state"]: s for s in project.json("show", PROP)["data"]["states"]}


def test_two_declared_states_each_imported_and_picked_show_in_show(project: Kiripix) -> None:
    built_prop(project)
    declare(project, "toppled", 12, 6)
    declare(project, "dented")
    toppled = project.json("import", PROP, an_image(project, "t.png", (255, 0, 77, 255)), "--state", "toppled")
    dented = project.json("import", PROP, an_image(project, "d.png", (0, 135, 81, 255)), "--state", "dented")
    one = project.json("pick", PROP, toppled["data"]["variant"], "--state", "toppled")
    project.json("pick", PROP, dented["data"]["variant"], "--state", "dented")

    shown = project.json("show", PROP)["data"]

    assert one["data"]["state"] == "toppled" and one["data"]["stage"] == "source"
    assert toppled["data"]["state"] == "toppled" and toppled["data"]["file"].replace("\\", "/").endswith(
        f"src/states/toppled/{toppled['data']['variant']}.png")
    assert shown["default_state"] == "default"
    assert [(s["state"], s["width"], s["height"]) for s in shown["states"]] == [("toppled", 12, 6), ("dented", 8, 8)]
    assert [s["picked"] for s in shown["states"]] == [toppled["data"]["variant"], dented["data"]["variant"]]
    assert [v["name"] for v in shown["states"][0]["variants"]] == [toppled["data"]["variant"]]
    assert len(shown["variants"]) == 1  # the default's Variants are unchanged
    assert run_source(project)["ok"]


def test_a_prop_without_a_state_decision_shows_none_and_has_the_brief_it_always_had(project: Kiripix) -> None:
    built_prop(project)
    project.json("run", PROP, "brief")

    shown = project.json("show", PROP)["data"]

    assert shown["states"] == []
    brief = json.loads((project.cwd / "assets/prop/bench/work/brief/brief.json").read_text("utf-8"))
    assert brief == {"width": 8, "height": 8, "angle": "top34"}


def test_an_unpicked_state_holds_source_back_and_a_lone_variant_has_a_pick_fix(project: Kiripix) -> None:
    built_prop(project)
    declare(project, "toppled")

    result = run_source(project, expect=3)
    [finding] = [f for f in result["findings"] if f["code"] == "prop.state_unpicked"]
    assert "toppled" in finding["message"] and finding["fix"] == f"kiripix import {PROP} <file> --state toppled"

    variant = project.json("import", PROP, an_image(project, "t.png", (255, 0, 77, 255)), "--state", "toppled")["data"]["variant"]
    result = run_source(project, expect=3)
    assert [f["fix"] for f in result["findings"] if f["code"] == "prop.state_unpicked"] == [
        f"kiripix pick {PROP} {variant} --state toppled"]

    two = project.json("import", PROP, an_image(project, "t2.png", (0, 0, 0, 255)), "--state", "toppled")["data"]["variant"]
    result = run_source(project, expect=3)
    [finding] = [f for f in result["findings"] if f["code"] == "prop.state_unpicked"]
    assert "fix" not in finding or finding["fix"] is None
    assert two in finding["owner_action"]


def test_an_import_for_an_undeclared_state_fails_with_the_fix_that_declares_it(project: Kiripix) -> None:
    built_prop(project)
    image = an_image(project, "t.png", (255, 0, 77, 255))

    result = project.json("import", PROP, image, "--state", "toppled", expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "prop.state_unknown"
    assert finding["fix"].startswith(f"kiripix decide {PROP} source --decision ")
    assert '"id": "toppled"' in finding["fix"] and '"width": 8' in finding["fix"]
    project.json("pick", PROP, "abc", "--state", "toppled", expect=1)
    assert not (project.cwd / "assets/prop/bench/src/states").exists()


def test_a_state_id_equal_to_the_defaults_is_refused_everywhere(project: Kiripix) -> None:
    built_prop(project)
    image = an_image(project, "t.png", (255, 0, 77, 255))

    assert finding_codes(declare(project, "default", expect=1)) == ["prop.state_duplicate"]
    assert finding_codes(project.json("import", PROP, image, "--state", "default", expect=1)) == ["prop.state_duplicate"]
    project.json("set", PROP, "brief", "state=upright")
    declare(project, "default")  # no longer the default's ID
    assert finding_codes(declare(project, "upright", expect=1)) == ["prop.state_duplicate"]


def test_a_duplicate_declaration_a_bad_id_and_a_size_over_the_resolution_are_refused(project: Kiripix) -> None:
    built_prop(project)
    declare(project, "toppled")

    assert finding_codes(declare(project, "toppled", expect=1)) == ["prop.state_duplicate"]
    assert finding_codes(declare(project, "Toppled", expect=1)) == ["decision.invalid"]
    result = declare(project, "huge", 700, 8, expect=1)
    assert finding_codes(result) == ["prop.state_larger_than_resolution"]
    assert '"width": 640' in result["findings"][0]["fix"]


def test_remove_and_rename_apply_before_export_and_a_pick_of_an_unknown_state_is_refused(project: Kiripix) -> None:
    built_prop(project)
    declare(project, "toppled")
    declare(project, "dented")
    variant = project.json("import", PROP, an_image(project, "t.png", (255, 0, 77, 255)), "--state", "toppled")["data"]["variant"]
    project.json("pick", PROP, variant, "--state", "toppled")

    edit(project, "state_rename", id="toppled", to="fallen")
    edit(project, "state_remove", id="dented")

    shown = states_of(project)
    assert list(shown) == ["fallen"] and shown["fallen"]["picked"] == variant  # the rename keeps its Variants and Pick
    assert run_source(project)["ok"]
    unknown = project.json("decide", PROP, "source", "--decision", json.dumps(
        {"decision": "state_pick", "data": {"state": "dented", "variant": "x"}}), expect=1)
    assert finding_codes(unknown) == ["prop.state_unknown"] and "dented" in unknown["findings"][0]["fix"]
    for entry in ({"decision": "state_remove", "data": {"id": "nope"}},
                  {"decision": "state_rename", "data": {"id": "fallen", "to": "default"}}):
        project.json("decide", PROP, "source", "--decision", json.dumps(entry), expect=1)
    project.json("undo", PROP, "source")
    project.json("undo", PROP, "source")
    assert list(states_of(project)) == ["toppled", "dented"]


def test_an_exported_state_id_is_frozen_and_remove_or_rename_is_refused_before_it_is_recorded(project: Kiripix) -> None:
    exportable_prop(project)
    project.json("export", PROP)
    declare(project, "toppled")
    path = project.cwd / MANIFEST
    value = json.loads(path.read_text("utf-8"))
    value["ids"]["states"] = ["toppled"]  # what the export of a Prop with states records (ticket 0260)
    path.write_text(json.dumps(value, indent=2) + "\n", "utf-8")

    for entry in ({"decision": "state_remove", "data": {"id": "toppled"}},
                  {"decision": "state_rename", "data": {"id": "toppled", "to": "fallen"}}):
        result = project.json("decide", PROP, "source", "--decision", json.dumps(entry), expect=1)
        assert finding_codes(result) == ["export.id_frozen"] and "toppled" in result["findings"][0]["message"]
    assert list(states_of(project)) == ["toppled"]


def test_state_is_for_a_prop_and_takes_one_image(project: Kiripix) -> None:
    built_prop(project)
    declare(project, "toppled")
    image = an_image(project, "t.png", (255, 0, 77, 255))
    project.json("new", "room", "alley", "--view", "top")

    assert project.json("import", "room.alley", image, "--state", "toppled", expect=1)["findings"][0]["code"] == (
        "import.state_needs_prop")
    assert project.json("import", PROP, image, "--state", "toppled", "--look", "door", expect=1)["findings"][0][
        "code"] == "import.state_takes_one_image"


def test_a_default_state_id_that_isnt_snake_case_is_a_finding_with_its_fix(project: Kiripix) -> None:
    built_prop(project)
    project.json("set", PROP, "brief", "state=Standing Up")

    result = project.json("run", PROP, "brief", expect=2)

    finding = next(f for f in result["findings"] if f["code"] == "brief.state_invalid")
    assert finding["fix"] == f"kiripix set {PROP} brief state=standing_up" and finding["owner_action"] is None
