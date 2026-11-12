"""A sprite's export (ticket 0180, spec §9): the character's files, made by the character's functions, under `sprite/`."""

import json
import re
import shutil
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_export import GENERATED, node
from test_sprite import FOUR, SPRITE, decide, import_sheet, load, new_sprite, png_sheet, save, sheet_of

FOLDER = "game/kiripix/sprite/npc"
RES = "res://kiripix/sprite/npc"
MANIFEST = "game/kiripix/manifest/sprite.npc.json"
FILES = [f"{RES}/color.png", f"{RES}/frames.tres", f"{RES}/normal.png", f"{RES}/npc.tscn", f"{RES}/texture.tres"]


def manifest(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / MANIFEST).read_text("utf-8"))
    return value


def exportable_sprite(project: Kiripix, frames: int = 2) -> Path:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, frames), frames)
    project.json("run", SPRITE)
    return folder


def add_clip(project: Kiripix, clip: str, file: str, hop: int = 0) -> str:
    """Import a second PNG sheet of 4 directions and cut it as `clip` (`hop` makes its pixels differ from another's)."""
    name = import_sheet(project, save(project.cwd / file, sheet_of(FOUR, 1, hops={0: hop})))
    decide(project, "frames", "sheet", {"file": name, "clip": clip, "layout": "rows", "directions": FOUR, "frames": 1})
    return name


def test_a_sprite_exports_the_characters_files_under_sprite(project: Kiripix) -> None:
    folder = exportable_sprite(project)

    data = project.json("export", SPRITE)["data"]

    assert sorted(data["written"]) == FILES and data["counter"] == 1
    for res in FILES:
        assert (project.cwd / "game" / res.removeprefix("res://")).is_file()
    assert (project.cwd / FOLDER / "color.png").read_bytes() == (folder / "out" / "export" / "color.png").read_bytes()
    for path in ("npc.tscn", "frames.tres", "texture.tres"):
        text = (project.cwd / FOLDER / path).read_text("utf-8")
        assert text.startswith(GENERATED + "\n") and "\r" not in text
    texture = (project.cwd / FOLDER / "texture.tres").read_text("utf-8")
    assert f'path="{RES}/color.png"' in texture and f'path="{RES}/normal.png"' in texture
    scene = (project.cwd / FOLDER / "npc.tscn").read_text("utf-8")
    sprite = node(scene, "Sprite", ".")
    assert 'type="AnimatedSprite2D"' in sprite and "centered = false" in sprite
    pivot = load(folder / "out" / "export" / "character.json")["pivot"]
    assert f"offset = Vector2({-pivot['x']}, {-pivot['y']})" in sprite
    assert f'path="{RES}/frames.tres"' in scene
    record = manifest(project)
    assert record["asset"] == SPRITE and record["exported"] is True and sorted(record["files"]) == FILES


def test_a_four_direction_sprite_has_four_animations_per_clip(project: Kiripix) -> None:
    exportable_sprite(project)
    project.json("export", SPRITE)

    frames = (project.cwd / FOLDER / "frames.tres").read_text("utf-8")

    assert re.findall(r'"name": &"([a-z_]+)"', frames) == [f"idle_{d}" for d in FOUR]
    assert manifest(project)["ids"] == {"markers": [], "layers": [], "masks": [], "clips": sorted(f"idle_{d}" for d in FOUR)}
    assert frames.count("[sub_resource") == 4 * 2


def test_re_exporting_writes_nothing_and_a_rebuild_is_byte_identical(project: Kiripix) -> None:
    exportable_sprite(project)
    project.json("export", SPRITE)
    before = {n: (project.cwd / FOLDER / n).read_bytes() for n in ("npc.tscn", "frames.tres", "texture.tres")}

    project.json("run", SPRITE, "export", "--force")
    data = project.json("export", SPRITE)["data"]

    assert {n: (project.cwd / FOLDER / n).read_bytes() for n in before} == before
    assert data["written"] == [] and data["counter"] == 1


def test_a_clip_taken_away_is_refused_and_a_clip_added_is_fine(project: Kiripix) -> None:
    exportable_sprite(project)
    walk = add_clip(project, "walk", "walk.png", hop=1)
    project.json("run", SPRITE)
    project.json("export", SPRITE)
    assert len(manifest(project)["ids"]["clips"]) == 8

    decide(project, "frames", "sheet", {"file": walk, "clip": "stride", "layout": "rows", "directions": FOUR, "frames": 1})
    project.json("run", SPRITE)
    result = project.json("export", SPRITE, expect=2)

    frozen = [f for f in result["findings"] if f["code"] == "export.id_frozen"]
    assert sorted(f["message"].split("'")[1] for f in frozen) == [f"walk_{d}" for d in sorted(FOUR)]
    assert all(f["owner_action"] and f["fix"] is None for f in frozen)
    assert [f["code"] for f in project.json("check", SPRITE, expect=2)["findings"]].count("export.id_frozen") == 4

    decide(project, "frames", "sheet", {"file": walk, "clip": "walk", "layout": "rows", "directions": FOUR, "frames": 1})
    add_clip(project, "run", "run.png")
    project.json("run", SPRITE)
    data = project.json("export", SPRITE)["data"]
    assert data["counter"] == 2
    assert {f"run_{d}" for d in FOUR} <= set(manifest(project)["ids"]["clips"])


def test_editing_the_scene_refuses_force_backs_it_up_and_adopt_takes_an_unlisted_file(project: Kiripix) -> None:
    exportable_sprite(project)
    scene = project.cwd / FOLDER / "npc.tscn"
    scene.parent.mkdir(parents=True)
    scene.write_bytes(b"the game's own\n")

    unlisted = project.json("export", SPRITE, expect=3)
    assert [f["code"] for f in unlisted["findings"]] == ["export.file_unmanaged"]
    assert scene.read_bytes() == b"the game's own\n"

    project.json("export", SPRITE, "--adopt")
    assert scene.read_text("utf-8").startswith(GENERATED)
    original = scene.read_bytes()
    scene.write_bytes(original + b"edit\n")

    changed = project.json("export", SPRITE, expect=3)
    [finding] = [f for f in changed["findings"] if f["code"] == "export.file_changed"]
    assert f"{RES}/npc.tscn" in finding["message"] and "--force" in finding["owner_action"]

    project.json("export", SPRITE, "--force")
    assert scene.read_bytes() == original
    assert list((project.cwd / ".kiripix" / "backups").rglob("npc.tscn"))


def test_prune_removes_a_deleted_sprites_files(project: Kiripix) -> None:
    exportable_sprite(project)
    project.json("export", SPRITE)

    shutil.rmtree(project.cwd / "assets" / "sprite" / "npc")
    project.json("export", "--prune")

    assert not (project.cwd / FOLDER / "npc.tscn").exists() and not (project.cwd / MANIFEST).exists()


def test_a_sprite_not_built_is_not_ready_and_export_all_includes_sprites(project: Kiripix) -> None:
    new_sprite(project)
    [finding] = project.json("export", SPRITE, expect=3)["findings"]
    assert finding["code"] == "export.not_ready"

    png_sheet(project, sheet_of(FOUR, 1), 1)
    project.json("run", SPRITE)
    project.json("export", "--all")
    assert (project.cwd / FOLDER / "npc.tscn").is_file()
