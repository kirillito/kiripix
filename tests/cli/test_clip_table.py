"""The Project clip table (ticket 0239, spec §6.3): `[[character.clips]]` in kiripix.toml, `clips-add` that fills it (an agent may run it)
from a character's decided and built clips, and the Project check `clips.timing_differs` run by `check --all` and `export --all`.
On the fake Blender; `idle` is the fixture's 0-24 frames at 12 fps."""

import json
import shlex
import shutil
import tomllib
from typing import Any

from conftest import Kiripix
from test_character_clips import IDLE, WALK
from test_character_model import FIXTURES, HERO
from test_clips_copy import TWIN
from test_export import godot_project, set_target
from test_export_sprite import exportable_sprite
from test_ramp_table import codes, hero, table
from test_settings_comments import annotate, comments
from test_sprite import SPRITE


def clip_row(name: str, frames: int, fps: int, loop: bool = True, foot: bool = False) -> str:
    return (f'[[character.clips]]\nname = "{name}"\nframes = {frames}\nfps = {fps}\nloop = {str(loop).lower()}\n'
            f"foot = {str(foot).lower()}\n")


def twin(project: Kiripix, data: dict[str, Any]) -> None:
    """A second character whose clips are built from `data`."""
    project.json("new", "character", "twin")
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "twin.glb")
    project.json("pick", TWIN, project.json("import", TWIN, "twin.glb")["data"]["variant"])
    project.json("run", TWIN, "model")
    project.json("run", TWIN, "rig")
    project.json("decide", TWIN, "clips", "--decision", json.dumps({"decision": "clip", "data": data}))
    project.json("run", TWIN, "clips")


def frames_of(project: Kiripix, asset: str, name: str = "idle") -> int:
    path = project.cwd / "assets" / "character" / asset.split(".")[1] / "work" / "clips" / "clips.json"
    entry = next(c for c in json.loads(path.read_text("utf-8"))["clips"] if c["name"] == name)
    return len(entry["frames"])


def test_clips_add_writes_rows_from_the_built_clips_and_again_writes_nothing(project: Kiripix) -> None:
    hero(project)
    wanted = frames_of(project, HERO)

    added = project.json("clips-add", HERO, "--clips", "idle")["data"]

    assert added["added"] == ["idle"] and added["wrote"]
    rows = tomllib.loads((project.cwd / "kiripix.toml").read_text("utf-8"))["character"]["clips"]
    assert rows == [{"name": "idle", "frames": wanted, "fps": 12, "loop": True, "foot": False}]
    again = project.json("clips-add", HERO, "--clips", "idle")["data"]
    assert again["added"] == [] and again["unchanged"] == ["idle"] and not again["wrote"]
    described = project.json("describe", "project")["data"]
    assert described["clips"] == [{"name": "idle", "frames": wanted, "fps": 12, "loop": True, "foot": False}]
    assert "clips-add" in described["clips_example"]


def test_clips_add_refuses_a_clip_not_decided(project: Kiripix) -> None:
    hero(project)
    before = (project.cwd / "kiripix.toml").read_text("utf-8")

    refused = project.json("clips-add", HERO, "--clips", "idle,phone", expect=1)

    assert codes(refused) == ["clips.not_decided"] and "phone" in refused["findings"][0]["message"]
    assert (project.cwd / "kiripix.toml").read_text("utf-8") == before
    foot = project.json("clips-add", HERO, "--clips", "idle", "--foot", "idle", expect=1)
    assert codes(foot) == ["clips.no_foot_frames"]
    dry = project.json("clips-add", HERO, "--clips", "idle", "--dry-run")["data"]
    assert dry["added"] == ["idle"] and not dry["wrote"] and (project.cwd / "kiripix.toml").read_text("utf-8") == before


def test_clips_add_refuses_a_row_that_differs(project: Kiripix) -> None:
    hero(project)
    table(project, clip_row("idle", 3, 12))

    refused = project.json("clips-add", HERO, "--clips", "idle", expect=1)

    assert codes(refused) == ["clips.row_differs"] and "the table's are 3" in refused["findings"][0]["message"]


def test_a_clip_table_with_a_name_twice_fails_to_load(project: Kiripix) -> None:
    table(project, clip_row("idle", 3, 12), clip_row("idle", 4, 12))

    result = project.json("status", expect=1)

    assert codes(result) == ["clips.name_twice"] and result["findings"][0]["owner_action"]


def test_the_character_that_differs_raises_one_finding_and_the_one_without_the_clip_none(project: Kiripix) -> None:
    hero(project)
    project.json("clips-add", HERO, "--clips", "idle")
    table(project, clip_row("walk", 8, 10))  # the hero has no walk: nothing to say about it
    twin(project, {**IDLE, "fps": 6})

    result = project.json("check", "--all", expect=2)

    found = [f for f in result["findings"] if f["code"] == "clips.timing_differs"]
    assert len(found) == 1 and found[0]["position"]["asset"] == TWIN and found[0]["severity"] == "error"
    assert "clip 'idle'" in found[0]["message"] and "fps is 6" in found[0]["message"]
    assert found[0]["owner_action"] is None
    command = shlex.split(found[0]["fix"])
    assert command[:4] == ["kiripix", "decide", TWIN, "clips"]
    project.json(*command[1:])  # the fix brings it in line
    project.json("run", TWIN, "clips")
    assert "clips.timing_differs" not in codes(project.json("check", "--all"))


def test_a_frame_count_only_the_owner_can_choose_is_an_owner_action(project: Kiripix) -> None:
    hero(project)
    project.json("clips-add", HERO, "--clips", "idle")
    twin(project, {**IDLE, "end": 12})

    result = project.json("check", "--all", expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "clips.timing_differs"]
    assert finding["fix"] is None and "Only the Owner" in finding["owner_action"] and "frames are" in finding["message"]


def test_a_missing_loop_and_foot_frames_are_found(project: Kiripix) -> None:
    hero(project)
    table(project, clip_row("idle", frames_of(project, HERO), 12, loop=False, foot=True))

    result = project.json("check", "--all", expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "clips.timing_differs"]
    assert "loop is true" in finding["message"] and "no foot frames" in finding["message"]
    assert finding["position"]["field"] == "clips.idle.loop,foot"


def test_export_all_runs_the_clip_table(project: Kiripix) -> None:
    hero(project)
    godot_project(project)
    set_target(project)
    table(project, clip_row("idle", frames_of(project, HERO), 5))

    result = project.json("export", "--all", expect=2)

    assert codes(result) == ["clips.timing_differs"]


def test_a_sprite_is_warned_not_failed(project: Kiripix) -> None:
    exportable_sprite(project)
    table(project, clip_row("idle", 4, 8))  # a sprite's default is 8 fps, looping

    result = project.json("check", "--all")  # exit 0: a warning

    [finding] = [f for f in result["findings"] if f["code"] == "clips.timing_differs"]
    assert finding["severity"] == "warning" and finding["position"]["asset"] == SPRITE
    assert "warned about, not failed" in finding["message"] and "frames are 2" in finding["message"]
    assert finding["fix"] is None and "cut it to 4 frames" in finding["owner_action"]


def test_a_sprite_whose_fps_differs_gets_a_fix(project: Kiripix) -> None:
    exportable_sprite(project)
    table(project, clip_row("idle", 2, 12))

    result = project.json("check", "--all")

    [finding] = [f for f in result["findings"] if f["code"] == "clips.timing_differs"]
    assert finding["severity"] == "warning" and "fps is 8" in finding["message"]
    command = shlex.split(finding["fix"])
    assert command[:4] == ["kiripix", "decide", SPRITE, "frames"]
    project.json(*command[1:])
    project.json("run", SPRITE)
    assert "clips.timing_differs" not in codes(project.json("check", "--all"))


def test_a_version_6_project_migrates_to_an_empty_clip_table_and_keeps_its_comments(project: Kiripix) -> None:
    hero(project)
    path = project.cwd / "kiripix.toml"
    text = annotate(path)
    old = text.replace("schema_version = 14", "schema_version = 6")
    assert old != text
    path.write_text(old, encoding="utf-8")
    assert project.json("describe", "project")["data"]["clips"] == []
    assert path.read_text("utf-8") == old  # the file is the Owner's until a writing Command saves it

    project.json("clips-add", HERO, "--clips", "idle")

    after = path.read_text("utf-8")
    assert comments(old) == comments(after)
    assert "schema_version = 14  # keep this" in after
    migrated = tomllib.loads(after)
    assert [c["name"] for c in migrated["character"]["clips"]] == ["idle"]
    assert {k: v for k, v in migrated.items() if k not in ("schema_version", "character")} == {
        k: v for k, v in tomllib.loads(old).items() if k not in ("schema_version", "character")}
    assert project.json("status")["ok"]


def test_walk_can_be_added_after_idle_and_the_table_keeps_its_order(project: Kiripix) -> None:
    hero(project)
    project.json("decide", HERO, "clips", "--decision", json.dumps({"decision": "clip", "data": WALK}))
    project.json("run", HERO, "clips")

    project.json("clips-add", HERO, "--clips", "walk")
    project.json("clips-add", HERO, "--clips", "idle")

    rows = tomllib.loads((project.cwd / "kiripix.toml").read_text("utf-8"))["character"]["clips"]
    assert [r["name"] for r in rows] == ["walk", "idle"]
