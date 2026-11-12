"""`kiripix clips copy` (ticket 0171, spec §6.3): a character's clips copied to another character as `clip` Decisions,
with the clip-source files they name. On the fake Blender of `kiripix_test_recipes.py` (see test_character_clips.py)."""

import json
import shutil
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_character_clips import HERO, IDLE, WALK, add_source, clip, clips_json, rigged_hero
from test_character_model import FIXTURES

TWIN = "character.twin"
WAVE = {"name": "wave", "source": "wave", "start": 1, "end": 31, "fps": 10, "loop": False}
ACTIONS = [{"name": "Armature|mixamo.com|Layer0", "start": 1, "end": 31, "travel": 0.0}]


def hero_with_three_clips(project: Kiripix) -> Path:
    """The hero with idle and walk (actions of the rig) and wave (a clip-source file)."""
    folder = rigged_hero(project)
    add_source(project, "wave", actions=ACTIONS)
    for data in (IDLE, WALK, WAVE):
        clip(project, data)
    return folder


def rigged_twin(project: Kiripix) -> Path:
    project.json("new", "character", "twin")
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "twin.glb")
    project.json("pick", TWIN, project.json("import", TWIN, "twin.glb")["data"]["variant"])
    project.json("run", TWIN, "model")
    project.json("run", TWIN, "rig")
    return project.cwd / "assets" / "character" / "twin"


def current_clips(project: Kiripix, asset: str) -> list[dict[str, Any]]:
    shown = project.json("show", asset)["data"]
    named: dict[str, dict[str, Any]] = {}  # a repeated name replaces the clip and keeps its place (0156)
    for decision in next(s for s in shown["stages"] if s["stage"] == "clips")["decisions"]:
        named[decision["data"]["name"]] = decision["data"]
    return list(named.values())


def copy(project: Kiripix, *args: str, expect: int = 0) -> dict[str, Any]:
    return project.json("clips", "copy", TWIN, "--from", HERO, *args, expect=expect)


def test_copying_three_clips_gives_the_same_clips_json_and_undo_removes_them_one_by_one(project: Kiripix) -> None:
    hero = hero_with_three_clips(project)
    twin = rigged_twin(project)
    project.json("run", HERO, "clips")

    result = copy(project)

    data = result["data"]
    assert result["findings"] == [] and data["dry_run"] is False
    assert data["copied"] == ["idle", "walk", "wave"] and data["skipped"] == [] and data["replaced"] == []
    [source] = data["files"]
    assert source.startswith("assets/character/twin/src/clips/wave.") and source.endswith(".fbx")
    assert len(list((twin / "src" / "clips").glob("wave.*"))) == 1  # the same bytes, so the same hashed name
    assert (twin / "src" / "clips" / Path(source).name).read_bytes() == next(
        (hero / "src" / "clips").glob("wave.*")).read_bytes()
    assert current_clips(project, TWIN) == [IDLE, WALK, WAVE]

    project.json("run", TWIN, "clips")
    assert clips_json(twin) == clips_json(hero)
    for left in (2, 1, 0):
        project.json("undo", TWIN, "clips")
        assert len(current_clips(project, TWIN)) == left
    assert len(current_clips(project, HERO)) == 3, "the other character is only read"


def test_an_existing_clip_is_skipped_with_a_warning_and_replace_takes_the_others_range(project: Kiripix) -> None:
    hero_with_three_clips(project)
    twin = rigged_twin(project)
    shorter = {**IDLE, "end": 12}
    project.json("decide", TWIN, "clips", "--decision", json.dumps({"decision": "clip", "data": shorter}))

    result = copy(project)

    [finding] = result["findings"]
    assert finding["severity"] == "warning" and finding["code"] == "clips.copy_skipped" and "idle" in finding["message"]
    assert finding["fix"] and "--replace" in finding["fix"]
    assert result["data"]["skipped"] == ["idle"] and result["data"]["copied"] == ["walk", "wave"]
    assert current_clips(project, TWIN)[0] == shorter

    result = copy(project, "--replace")

    assert result["findings"] == [] and result["data"]["replaced"] == ["idle", "walk", "wave"] and result["data"]["copied"] == []
    assert current_clips(project, TWIN)[0] == IDLE, "a replacement keeps its place and its name"
    assert [c["name"] for c in current_clips(project, TWIN)] == ["idle", "walk", "wave"]
    project.json("run", TWIN, "clips")
    assert next(c for c in clips_json(twin)["clips"] if c["name"] == "idle")["end"] == 24


def test_clip_picks_some_and_dry_run_writes_nothing(project: Kiripix) -> None:
    hero_with_three_clips(project)
    twin = rigged_twin(project)

    dry = copy(project, "--dry-run")["data"]

    assert dry["dry_run"] is True and dry["copied"] == ["idle", "walk", "wave"] and len(dry["files"]) == 1
    assert current_clips(project, TWIN) == [] and not (twin / "src" / "clips").exists()

    copy(project, "--clip", "walk,idle")  # the other's order, not the order given

    assert current_clips(project, TWIN) == [IDLE, WALK]
    assert not (twin / "src" / "clips").exists(), "no copied clip names the file, so it isn't copied"


def test_an_unknown_clip_is_refused(project: Kiripix) -> None:
    hero_with_three_clips(project)
    rigged_twin(project)

    [finding] = copy(project, "--clip", "idle,run", expect=1)["findings"]

    assert finding["code"] == "clips.unknown_clip" and "run" in finding["message"] and finding["fix"]
    assert current_clips(project, TWIN) == []


def test_a_clip_source_that_differs_is_not_overwritten_without_replace(project: Kiripix) -> None:
    hero = hero_with_three_clips(project)
    twin = rigged_twin(project)
    path = project.cwd / "wave.fbx"
    path.write_text(json.dumps({"actions": ACTIONS, "fps": 24}), encoding="utf-8")
    project.json("import", TWIN, str(path), "--role", "clip-source")
    own = next((twin / "src" / "clips").glob("wave.*")).read_bytes()

    [finding] = copy(project, expect=1)["findings"]

    assert finding["code"] == "clips.source_differs" and "wave" in finding["message"]
    assert current_clips(project, TWIN) == []
    copy(project, "--replace")
    assert next((twin / "src" / "clips").glob("wave.*")).read_bytes() == next(
        (hero / "src" / "clips").glob("wave.*")).read_bytes() != own


def test_copying_from_or_to_a_room_names_its_kind(project: Kiripix) -> None:
    rigged_hero(project)
    project.json("new", "room", "alley", "--view", "top")

    [finding] = project.json("clips", "copy", HERO, "--from", "room.alley", expect=1)["findings"]
    assert finding["code"] == "clips.not_character" and "room" in finding["message"] and "room.alley" in finding["message"]

    [finding] = project.json("clips", "copy", "room.alley", "--from", HERO, expect=1)["findings"]
    assert finding["code"] == "clips.not_character" and "room" in finding["message"]


def test_copying_to_itself_is_refused(project: Kiripix) -> None:
    rigged_hero(project)

    [finding] = project.json("clips", "copy", HERO, "--from", HERO, expect=1)["findings"]

    assert finding["code"] == "clips.copy_itself"
