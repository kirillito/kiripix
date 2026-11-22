"""The NPC's Checks on `choose` (ticket 0357, spec §6.3): `npc.wearable_body`, `npc.colour_choice`, `npc.part_unset` and
`npc.stack`, through `kiripix check`. On the fake Blender; the built NPC is changed afterwards, as the Checks are about a built
choice whose inputs have moved. Slow; the setup is `test_npc.built`."""

import shlex
from typing import Any

from conftest import Kiripix
from test_npc import BODY, COAT, HAIR, NPC, built, choose
from test_wearable_stack import paint


def check(project: Kiripix) -> list[dict[str, Any]]:
    return [f for f in project("check", NPC, "--json").json["findings"] if f["code"].startswith("npc.")]


def edit(project: Kiripix, path: str, old: str, new: str) -> None:
    file = project.cwd / path
    text = file.read_text("utf-8")
    assert old in text
    file.write_text(text.replace(old, new), encoding="utf-8")


def test_a_clean_choice_has_no_error_and_an_unset_part_is_info(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR, "hair=auburn")

    found = check(project)

    assert [(f["code"], f["severity"]) for f in found] == [("npc.part_unset", "info")]
    assert found[0]["data"] == {"part": "top", "choices": ["red"]}
    assert found[0]["position"]["field"] == "colours/top" and found[0]["fix"] and not found[0].get("owner_action")


def test_a_wearable_moved_to_another_body_is_npc_wearable_body(project: Kiripix) -> None:
    built(project, (HAIR, COAT))
    choose(project, f"{HAIR},{COAT}", "hair=auburn,top=red")
    project.json("new", "character", "twin")
    edit(project, "assets/wearable/coat/asset.toml", BODY, "character.twin")

    found = [f for f in check(project) if f["code"] == "npc.wearable_body"]

    assert len(found) == 1 and found[0]["severity"] == "error"
    assert found[0]["data"] == {"wearable": COAT, "body": "character.twin", "base": BODY}
    position = found[0]["position"]
    assert (position["asset"], position["stage"], position["field"]) == (NPC, "choose", f"wearables/{COAT}")
    assert found[0]["fix"] == f"kiripix set {NPC} choose wearables={HAIR}"


def test_a_choice_removed_from_the_ramp_table_is_npc_colour_choice(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR, "hair=auburn,top=red")
    edit(project, "kiripix.toml", "auburn = [[0, 0, 0], [29, 43, 83]], ", "")

    found = [f for f in check(project) if f["code"] == "npc.colour_choice"]

    assert len(found) == 1 and found[0]["severity"] == "error"
    assert found[0]["data"] == {"part": "hair", "choice": "auburn", "choices": ["blond"], "reason": "choice_gone"}
    assert "blond" in found[0]["message"] and "hair" in found[0]["message"]
    assert found[0]["fix"] == f"kiripix set {NPC} choose colours=top=red"


def test_a_choice_given_another_ramp_is_npc_colour_choice(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR, "hair=auburn")
    edit(project, "kiripix.toml", "auburn = [[0, 0, 0], [29, 43, 83]]", "auburn = [[0, 0, 0], [95, 87, 79]]")

    found = [f for f in check(project) if f["code"] == "npc.colour_choice"]

    assert [f["data"]["reason"] for f in found] == ["choice_changed"]
    assert found[0]["fix"] == f"kiripix run {NPC} choose"


def test_a_wearable_the_order_buries_but_the_depth_shows_is_npc_stack(project: Kiripix) -> None:
    built(project, (HAIR, COAT))
    project.json("set", COAT, "sheet", "order=20")
    project.json("run", COAT, "sheet")
    choose(project, f"{HAIR},{COAT}")
    paint(project, BODY, 10, 30, 10, 30, (200, 160, 120), 100)
    paint(project, HAIR, 5, 20, 5, 20, (40, 90, 200), 10)  # nearest of all, under the coat by order
    paint(project, COAT, 5, 20, 5, 20, (180, 30, 60), 200)

    found = [f for f in check(project) if f["code"] == "npc.stack"]

    assert len(found) == 1 and found[0]["severity"] == "warning"
    data = found[0]["data"]
    assert data["wearable"] == HAIR and data["buried_frames"] == data["frames"] > 0
    assert data["worst"][0]["buried"] == data["worst"][0]["opaque"] == 225
    assert found[0]["position"]["field"] == f"wearables/{HAIR}"
    # the fix puts the hair over every other layer (one above the coat's 20) and leaves the coat's entry as it was
    assert found[0]["fix"] == f"kiripix set {NPC} choose wearables={HAIR}@21,{COAT}"
    project.json(*shlex.split(found[0]["fix"])[1:])
    project.json("run", NPC, "choose")
    assert [f for f in check(project) if f["code"] == "npc.stack"] == []
