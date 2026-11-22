"""An NPC's `export` (ticket 0358, spec §9, ADR 0015): the one `npc/<name>/npc.json` the game gets, in the Manifest, refused with
`npc.base_not_exported` / `npc.wearable_not_exported` until each is in the game, and removed by `--prune`. On the fake Blender; one
built NPC serves the whole scenario, since the build is slow."""

import json
import shutil
from typing import Any

from conftest import Kiripix
from test_export import godot_project, set_target
from test_npc import BODY, HAIR, NPC, built, choose

FOLDER = "game/kiripix/npc/guard"
MANIFEST = "game/kiripix/manifest/npc.guard.json"
RES = "res://kiripix/npc/guard/npc.json"


def codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"]]


def manifest(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / MANIFEST).read_text("utf-8"))
    return value


def test_an_npc_exports_its_one_file_once_the_base_and_each_wearable_are_in_the_game(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR, "hair=auburn")
    godot_project(project)
    set_target(project)
    project.json("run", HAIR, "export")
    project.json("run", BODY, "export")
    project.json("run", NPC, "export")

    refused = project.json("export", NPC, expect=1)  # neither is in the game yet

    assert codes(refused) == ["npc.base_not_exported", "npc.wearable_not_exported"]
    assert [f["fix"] for f in refused["findings"]] == [f"kiripix export {BODY}", f"kiripix export {HAIR}"]
    assert not (project.cwd / FOLDER).exists()

    project.json("export", BODY)
    refused = project.json("export", NPC, expect=1)  # the base is, the Wearable is not

    assert codes(refused) == ["npc.wearable_not_exported"] and HAIR in refused["findings"][0]["message"]

    data = project.json("export", "--all")["data"]  # the Wearable and the NPC in one call: the NPC counts the Wearable

    assert [r["written"] for r in data["assets"] if r["asset"] == NPC] == [[RES]]
    record = json.loads((project.cwd / FOLDER / "npc.json").read_text("utf-8"))
    assert record == {
        "schema_version": 1, "asset": NPC, "base": BODY, "base_path": "res://kiripix/character/zed/zed.tscn",
        "wearables": [{"id": HAIR, "order": 10, "path": "res://kiripix/wearable/hair/hair.tscn"}],
        "colours": {"hair": {"choice": "auburn", "rgb": [[0, 0, 0], [29, 43, 83]]}}}
    assert sorted(p.name for p in (project.cwd / FOLDER).iterdir()) == ["npc.json"]  # no images, no scene
    assert (project.cwd / FOLDER / "npc.json").read_bytes().endswith(b"}\n") and b"\r" not in (project.cwd / FOLDER / "npc.json").read_bytes()
    assert manifest(project)["asset"] == NPC and list(manifest(project)["files"]) == [RES] and manifest(project)["exported"] is True

    before = (project.cwd / FOLDER / "npc.json").read_bytes()  # byte-identical after a rebuild, and nothing to write again
    project.json("run", NPC, "choose", "--force")
    project.json("run", NPC, "export", "--force")
    assert project.json("export", NPC)["data"]["written"] == [] and (project.cwd / FOLDER / "npc.json").read_bytes() == before

    (project.cwd / FOLDER / "npc.json").write_text("the game's own\n", "utf-8")  # the game's change is never overwritten
    changed = project.json("export", NPC, expect=3)
    assert changed["findings"][0]["code"] == "export.file_changed" and "npc.json" in changed["findings"][0]["message"]
    (project.cwd / FOLDER / "npc.json").write_bytes(before)

    shutil.rmtree(project.cwd / "assets" / "npc" / "guard")  # a deleted NPC
    project.json("export", "--all", "--prune")

    assert not (project.cwd / FOLDER).exists() and not (project.cwd / MANIFEST).exists()
    assert (project.cwd / "game" / "kiripix" / "wearable" / "hair" / "hair.tscn").is_file()
