"""The `transition` Decision of `clips` (ticket 0218, spec §6.3): a clip that blends one clip's pose into another's. The CLI
tests run on the fake Blender; the marked test runs the real Blender 5.2 on the fixture Model."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix
from PIL import Image
from test_character_clips import HIT, IDLE, WALK, clip, clips_json, real_hero, rigged_hero
from test_character_model import HERO
from test_character_render import DIRECTIONS, ready, render_calls, render_json, rendered
from test_export_character import FRAMES, exportable_character, manifest

IDLE_TO_HIT = {"name": "idle_to_hit", "from": {"clip": "idle"}, "to": {"clip": "hit", "frame": 0}, "length": 3}


def transition(project: Kiripix, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return project.json("decide", HERO, "clips", "--decision", json.dumps({"decision": "transition", "data": data}), **kwargs)


def entries(folder: Path) -> dict[str, dict[str, Any]]:
    return {c["name"]: c for c in clips_json(folder)["clips"]}


def clips_ready(project: Kiripix) -> Path:
    folder = rigged_hero(project)
    for data in (IDLE, HIT):
        clip(project, data)
    return folder


def test_a_transition_is_an_entry_with_both_ends_and_the_blend_positions(project: Kiripix) -> None:
    folder = clips_ready(project)
    transition(project, IDLE_TO_HIT)

    project.json("run", HERO, "clips")

    entry = entries(folder)["idle_to_hit"]
    assert list(entries(folder)) == ["hit", "idle", "idle_to_hit"]
    assert entry["frames"] == [0.25, 0.5, 0.75]
    assert "start" not in entry and "end" not in entry
    assert (entry["loop"], entry["fps"], entry["stationary"], entry["root_motion"], entry["events"]) == (
        False, 12, False, False, {"foot": []})  # the `from` clip's frame rate
    ends, length = (entry["transition"]["from"], entry["transition"]["to"]), entry["transition"]["length"]
    assert length == 3
    assert [(e["clip"], e["frame"], e["action"], e["action_frame"]) for e in ends] == [
        ("idle", 9, "idle", 22.5), ("hit", 0, "walk", 0)]
    assert all(len(e["source_hash"]) == 16 for e in ends) and ends[0]["source_hash"] == entries(folder)["idle"]["source_hash"]


def test_deciding_again_changes_it_and_undo_brings_the_first_back(project: Kiripix) -> None:
    folder = clips_ready(project)
    transition(project, IDLE_TO_HIT)
    project.json("run", HERO, "clips")

    transition(project, {**IDLE_TO_HIT, "length": 5, "fps": 20})
    project.json("run", HERO, "clips")
    assert len(entries(folder)["idle_to_hit"]["frames"]) == 5 and entries(folder)["idle_to_hit"]["fps"] == 20
    assert len(entries(folder)) == 3

    project.json("undo", HERO, "clips")
    project.json("run", HERO, "clips")
    assert len(entries(folder)["idle_to_hit"]["frames"]) == 3 and entries(folder)["idle_to_hit"]["fps"] == 12


def test_an_end_names_a_game_frame_of_its_clip(project: Kiripix) -> None:
    folder = clips_ready(project)
    transition(project, {**IDLE_TO_HIT, "from": {"clip": "idle", "frame": 2}, "to": {"clip": "hit", "frame": 3}})

    project.json("run", HERO, "clips")

    ends = entries(folder)["idle_to_hit"]["transition"]
    assert (ends["from"]["action_frame"], ends["to"]["action_frame"]) == (5, 6)  # idle samples 2.5 apart, hit 2 apart


@pytest.mark.parametrize("name", ["Idle To", "idle-to-hit", "idle_to_s", "", "x_ne"])
def test_a_bad_name_is_refused_at_decide(project: Kiripix, name: str) -> None:
    clips_ready(project)

    assert transition(project, {**IDLE_TO_HIT, "name": name}, expect=1)["findings"]


def test_a_length_below_1_is_refused_at_decide(project: Kiripix) -> None:
    clips_ready(project)

    assert transition(project, {**IDLE_TO_HIT, "length": 0}, expect=1)["findings"]


def finding(project: Kiripix, expect: int = 1) -> dict[str, Any]:
    [found] = project.json("run", HERO, "clips", expect=expect)["findings"]
    assert (found["fix"] is None) != (found["owner_action"] is None)
    return found


def test_a_missing_clip_fails_with_its_finding(project: Kiripix) -> None:
    clips_ready(project)
    transition(project, {**IDLE_TO_HIT, "to": {"clip": "attack"}})

    found = finding(project)

    assert found["code"] == "clips.transition_missing_clip" and "attack" in found["message"]
    assert found["fix"] == "kiripix undo character.hero clips"


def test_a_frame_out_of_range_fails_with_its_finding(project: Kiripix) -> None:
    clips_ready(project)
    transition(project, {**IDLE_TO_HIT, "to": {"clip": "hit", "frame": 4}})  # hit has 4 frames: 0 to 3

    found = finding(project)

    assert found["code"] == "clips.transition_frame" and "hit" in found["message"] and "0 to 3" in found["message"]


def test_a_transition_between_transitions_fails_with_its_finding(project: Kiripix) -> None:
    clips_ready(project)
    transition(project, IDLE_TO_HIT)
    transition(project, {"name": "hit_to_idle", "from": {"clip": "hit"}, "to": {"clip": "idle"}})
    transition(project, {"name": "again", "from": {"clip": "idle_to_hit"}, "to": {"clip": "hit_to_idle"}})

    found = finding(project)

    assert found["code"] == "clips.transition_loop" and "idle_to_hit" in found["message"]


def test_a_name_shared_with_a_clip_fails_clips_duplicate_name(project: Kiripix) -> None:
    clips_ready(project)
    transition(project, {**IDLE_TO_HIT, "name": "hit"})

    found = finding(project)

    assert found["code"] == "clips.duplicate_name" and "hit" in found["message"]


def test_a_transition_alone_is_not_a_clip_so_the_stage_still_needs_input(project: Kiripix) -> None:
    rigged_hero(project)
    transition(project, IDLE_TO_HIT)

    assert project.json("run", HERO, "clips", expect=3)["findings"][0]["code"] == "stage.needs_input"


def test_describe_says_what_a_transition_is_and_lists_its_checks(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "clips")["data"]["kinds"]
    [stage] = kind["stages"]

    by_name = {d["name"]: d for d in stage["decisions"]}

    decision = by_name["transition"]
    assert set(decision["entry_schema"]["properties"]) == {"name", "from", "to", "length", "fps"}
    assert decision["entry_schema"]["required"] == ["name", "from", "to"]
    assert "blends" in decision["description"] and "again under a name" in decision["description"]
    codes = [c["code"] for c in stage["checks"]]
    assert {"clips.transition_missing_clip", "clips.transition_frame", "clips.transition_loop",
            "clips.duplicate_name"} <= set(codes)


# render


def rendering(project: Kiripix) -> Path:
    folder = ready(project, IDLE, HIT)
    transition(project, IDLE_TO_HIT)
    project.json("run", HERO, "clips")
    return folder


def test_render_asks_blender_for_the_blend_and_writes_its_frames_in_every_direction(project: Kiripix) -> None:
    folder = rendering(project)

    project.json("run", HERO, "render")

    sent = {c["name"]: c for c in render_calls(project)[0]["args"]["clips"]}
    blend = sent["idle_to_hit"]
    assert blend["frames"] == [0.25, 0.5, 0.75] and blend["root_motion"] is False
    assert (blend["transition"]["from"]["action"], blend["transition"]["from"]["frame"]) == ("idle", 22.5)
    assert (blend["transition"]["to"]["action"], blend["transition"]["to"]["frame"]) == ("walk", 0)
    assert blend["transition"]["from"]["file"] is None and "transition" not in sent["idle"]
    entry = {c["name"]: c for c in render_json(folder)["clips"]}["idle_to_hit"]
    assert list(entry["directions"]) == DIRECTIONS and all(len(f) == 3 for f in entry["directions"].values())
    assert (entry["loop"], entry["fps"]) == (False, 12)
    size = render_json(folder)["frame"]
    assert Image.open(folder / "work" / "render" / entry["directions"]["s"][0]["files"]["color"]).size == (
        size["width"], size["height"])


def test_changing_the_clip_a_transition_reads_renders_it_again_and_no_other(project: Kiripix) -> None:
    folder = rendering(project)
    project.json("run", HERO, "render")
    clip(project, {**IDLE, "end": 12})
    project.json("run", HERO, "clips")

    project.json("run", HERO, "render")

    assert sorted(rendered(project)) == ["idle", "idle_to_hit"]
    assert len(render_json(folder)["clips"]) == 3


def test_a_transition_that_reads_only_the_other_clip_is_kept_when_the_first_changes(project: Kiripix) -> None:
    folder = ready(project, IDLE, HIT, WALK)
    transition(project, {"name": "hit_to_walk", "from": {"clip": "hit"}, "to": {"clip": "walk"}})
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    clip(project, {**IDLE, "end": 12})
    project.json("run", HERO, "clips")

    project.json("run", HERO, "render")

    assert rendered(project) == ["idle"]
    assert len(render_json(folder)["clips"]) == 4


# export


def test_export_gives_the_transition_its_ids_and_a_longer_one_keeps_them(project: Kiripix) -> None:
    exportable_character(project)
    transition(project, IDLE_TO_HIT)
    project.json("run", HERO)
    project.json("export", HERO)
    ids = manifest(project)["ids"]["clips"]
    assert {f"idle_to_hit_{d}" for d in DIRECTIONS} <= set(ids) and len(ids) == 24

    transition(project, {**IDLE_TO_HIT, "length": 5})
    project.json("run", HERO)
    project.json("export", HERO)

    assert manifest(project)["ids"]["clips"] == ids
    assert (project.cwd / FRAMES).read_text("utf-8").count("[sub_resource") == 8 * (4 + 10 + 5)


# the real Blender


@pytest.mark.blender
def test_the_blend_differs_from_both_ends_and_the_other_clips_are_unchanged_on_real_blender(project: Kiripix) -> None:
    folder = real_hero(project, "rigged.glb")
    clip(project, {"name": "idle", "source": "idle", "start": 1, "end": 25, "fps": 2, "loop": True, "stationary": True},
         test_recipes=False)
    clip(project, {"name": "walk", "source": "walk", "start": 1, "end": 25, "fps": 3, "loop": True}, test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("set", HERO, "render", "height=26", test_recipes=False)
    project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)
    before = {p.relative_to(folder / "work" / "render").as_posix(): p.read_bytes()
              for p in (folder / "work" / "render").rglob("*.png")}

    transition(project, {"name": "idle_to_walk", "from": {"clip": "idle"}, "to": {"clip": "walk", "frame": 0}, "length": 3},
               test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    result = project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)

    assert result["findings"] == []
    document = render_json(folder)
    by_name = {c["name"]: c for c in document["clips"]}
    blend = by_name["idle_to_walk"]["directions"]
    assert list(blend) == DIRECTIONS and all(len(frames) == 3 for frames in blend.values())
    root = folder / "work" / "render"

    def colour(item: dict[str, Any]) -> np.ndarray:
        return np.array(Image.open(root / item["files"]["color"]))

    idle_end, walk_start = colour(by_name["idle"]["directions"]["e"][-1]), colour(by_name["walk"]["directions"]["e"][0])
    first, last = colour(blend["e"][0]), colour(blend["e"][-1])
    assert first.shape == idle_end.shape
    assert not np.array_equal(first, idle_end) and not np.array_equal(first, walk_start)
    assert not np.array_equal(last, idle_end) and not np.array_equal(last, walk_start)
    assert not np.array_equal(first, last)
    for name, data in before.items():
        if name != "render.json" and name.split("/")[1] != "idle_to_walk":
            assert (root / name).read_bytes() == data, name
