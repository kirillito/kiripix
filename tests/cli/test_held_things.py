"""Importing a held thing (ticket 0301, 0238): `import --role thing --thing <id>` stores a mesh in `src/things/<id>/`, `show`
lists the things with their materials numbered after the Model's, and a thing a clip attaches can not be removed."""

import json
import struct
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_character_clips import HIT, clip, rigged_hero
from test_character_model import HERO
from test_clip_attach import attached, held


def glb(*materials: str, unused: str | None = None) -> bytes:
    """A minimal .glb whose one mesh uses `materials` (and one more, `unused`, that no mesh uses)."""
    names = [*materials, *([unused] if unused else [])]
    document = {"asset": {"version": "2.0"}, "materials": [{"name": n} for n in names],
                "meshes": [{"primitives": [{"material": i} for i in range(len(materials))]}]}
    text = json.dumps(document).encode("utf-8")
    text += b" " * (-len(text) % 4)
    return b"glTF" + struct.pack("<II", 2, 12 + 8 + len(text)) + struct.pack("<II", len(text), 0x4E4F534A) + text


def thing_file(project: Kiripix, name: str, *materials: str, **kw: Any) -> Path:
    path = project.cwd / name
    path.write_bytes(glb(*materials, **kw))
    return path


def things(project: Kiripix) -> dict[str, dict[str, Any]]:
    return {t["thing"]: t for t in project.json("show", HERO)["data"]["things"]}


def variant_name(result: dict[str, Any]) -> str:
    return str(result["file"]).rsplit("/", 1)[-1].split(".")[0]


def test_a_thing_is_imported_and_listed_with_its_materials(project: Kiripix) -> None:
    folder = rigged_hero(project)
    path = thing_file(project, "phone.glb", "screen", "body", unused="spare")

    result = project.json("import", HERO, path, "--role", "thing", "--thing", "phone")

    data = result["data"]
    assert data["role"] == "thing" and data["thing"] == "phone" and data["created"] is True
    assert data["thing_materials"] == ["body", "screen"], "the materials the meshes use, sorted"
    assert [p.suffix for p in (folder / "src" / "things" / "phone").iterdir()] == [".glb"]
    shown = things(project)["phone"]
    assert [(m["name"], m["number"]) for m in shown["materials"]] == [("body", 1), ("screen", 2)]
    assert shown["materials_known"] is True and shown["attached_by"] == []
    assert shown["variants"][0]["imported_as"] == "phone.glb"
    assert [m["index"] for m in shown["materials"]] == [None, None], "the Model's count isn't known before render"


def test_materials_are_numbered_in_the_order_the_things_came_and_no_earlier_number_moves(project: Kiripix) -> None:
    rigged_hero(project)
    project.json("import", HERO, thing_file(project, "stick.glb", "wood", "grip"), "--role", "thing", "--thing", "stick")
    before = things(project)["stick"]["materials"]

    project.json("import", HERO, thing_file(project, "ahead.glb", "metal"), "--role", "thing", "--thing", "ahead")

    shown = things(project)
    assert list(shown) == ["stick", "ahead"], "first-import order, not by ID"
    assert shown["stick"]["materials"] == before
    assert [(m["name"], m["number"]) for m in shown["ahead"]["materials"]] == [("metal", 3)]


def test_importing_under_the_same_id_makes_a_new_variant_and_the_newest_is_current(project: Kiripix) -> None:
    rigged_hero(project)
    first = project.json("import", HERO, thing_file(project, "a.glb", "wood"), "--role", "thing", "--thing", "rake")["data"]
    second = project.json("import", HERO, thing_file(project, "b.glb", "wood", "tines"), "--role", "thing",
                          "--thing", "rake")["data"]

    assert second["created"] is True and len(second["thing_variants"]) == 2
    shown = things(project)["rake"]
    assert len(shown["variants"]) == 2 and shown["current"] == variant_name(second)
    assert [m["name"] for m in shown["materials"]] == ["tines", "wood"]

    again = project.json("import", HERO, thing_file(project, "a.glb", "wood"), "--role", "thing", "--thing", "rake")["data"]

    assert again["created"] is False and len(again["thing_variants"]) == 2, "the same mesh again adds nothing"
    assert things(project)["rake"]["current"] == variant_name(first), "and is current again"


def test_a_bad_id_a_bad_file_and_a_missing_thing_option_are_refused(project: Kiripix) -> None:
    rigged_hero(project)
    path = thing_file(project, "phone.glb", "a")
    (project.cwd / "note.txt").write_text("x", encoding="utf-8")

    bad = project.json("import", HERO, path, "--role", "thing", "--thing", "Phone 2", expect=1)
    other = project.json("import", HERO, project.cwd / "note.txt", "--role", "thing", "--thing", "note", expect=1)
    alone = project.json("import", HERO, path, "--role", "thing", expect=1)
    stray = project.json("import", HERO, path, "--thing", "phone", expect=1)

    assert bad["findings"][0]["code"] == "thing.invalid_id"
    assert other["findings"][0]["code"] == "import.not_a_thing_model"
    assert alone["findings"][0]["code"] == stray["findings"][0]["code"] == "import.thing_needs_role"


def test_only_a_character_takes_a_thing(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    path = thing_file(project, "phone.glb", "a")

    result = project.json("import", "prop.bench", path, "--role", "thing", "--thing", "phone", expect=1)

    assert result["findings"][0]["code"] == "import.role_needs_character"


def test_a_thing_that_a_clip_attaches_is_listed_as_held_and_cannot_be_removed(project: Kiripix) -> None:
    folder = rigged_hero(project)
    project.json("import", HERO, thing_file(project, "phone.glb", "a"), "--role", "thing", "--thing", "phone")
    project.json("import", HERO, thing_file(project, "stick.glb", "b"), "--role", "thing", "--thing", "stick")
    clip(project, attached(held("phone"), base=HIT))
    assert things(project)["phone"]["attached_by"] == ["hit"] and things(project)["stick"]["attached_by"] == []

    refused = project.json("thing-remove", HERO, "phone", expect=1)

    assert refused["findings"][0]["code"] == "thing.attached" and "hit" in refused["findings"][0]["message"]
    assert (folder / "src" / "things" / "phone").is_dir()
    gone = project.json("thing-remove", HERO, "stick")["data"]
    assert gone["things"] == ["phone"] and not (folder / "src" / "things" / "stick").exists()
    unknown = project.json("thing-remove", HERO, "stick", expect=1)
    assert unknown["findings"][0]["code"] == "thing.unknown"


def test_a_thing_a_clip_lets_go_of_can_be_removed(project: Kiripix) -> None:
    folder = rigged_hero(project)
    project.json("import", HERO, thing_file(project, "phone.glb", "a"), "--role", "thing", "--thing", "phone")
    clip(project, attached(held("phone"), base=HIT))
    clip(project, HIT)  # the same clip decided again, holding nothing

    assert things(project)["phone"]["attached_by"] == []
    project.json("thing-remove", HERO, "phone")
    assert not (folder / "src" / "things" / "phone").exists()


def test_a_thing_imported_is_what_a_clip_may_attach(project: Kiripix) -> None:
    rigged_hero(project)
    refused = clip(project, attached(held("phone")), expect=1)
    assert refused["findings"][0]["code"] == "clips.unknown_thing"

    project.json("import", HERO, thing_file(project, "phone.glb", "a"), "--role", "thing", "--thing", "phone")

    clip(project, attached(held("phone")))


def test_copying_a_clip_that_holds_a_thing_warns_when_the_target_lacks_it(project: Kiripix) -> None:
    rigged_hero(project)
    project.json("import", HERO, thing_file(project, "phone.glb", "a"), "--role", "thing", "--thing", "phone")
    clip(project, attached(held("phone"), base=HIT))
    project.json("new", "character", "twin")

    result = project.json("clips", "copy", "character.twin", "--from", HERO)

    [finding] = [f for f in result["findings"] if f["code"] == "clips.copy_thing_missing"]
    assert finding["severity"] == "warning" and "phone" in finding["message"]
    assert "--role thing --thing phone" in finding["owner_action"]
