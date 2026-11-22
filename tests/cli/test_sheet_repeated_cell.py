"""The `sheet` packs a repeated cell once (ticket 0375). A `still` clip holds one pose for N frames, so its N cells are one image
(two with a `blink`): the atlas holds each once, every frame names the same `rect`, and the frame list, its order and its count
are unchanged. The export gives one AtlasTexture to each distinct region and plays all N frames."""

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_character_eyes import STILL, stamped
from test_character_model import HERO
from test_character_sheet import load, restored
from test_export import godot_project, set_target

FRAMES = "game/kiripix/character/hero/frames.tres"
DIRECTIONS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]


def stamped_sheet(project: Kiripix, *clips: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    folder = stamped(project, clips=clips)
    project.json("run", HERO, "sheet")
    return folder, load(folder)


def rects(frames: list[dict[str, Any]]) -> list[tuple[int, int, int, int]]:
    return [(f["rect"]["x"], f["rect"]["y"], f["rect"]["width"], f["rect"]["height"]) for f in frames]


def test_a_still_clip_packs_one_cell_and_a_blink_a_second_a_direction(project: Kiripix) -> None:
    folder, sheet = stamped_sheet(project, STILL)

    [clip] = sheet["clips"]
    colour = np.array(Image.open(folder / "work" / "sheet" / "color.png").convert("RGBA"))
    for direction in DIRECTIONS:
        frames = clip["directions"][direction]
        assert [f["index"] for f in frames] == list(range(6))  # the frame list is unchanged
        shown = rects(frames)
        assert shown[0] == shown[1] == shown[2] == shown[3] == shown[5]
        # the blink is frame 4; a Direction facing away (`n`) paints no eyes, so it has nothing to blink
        assert len(set(shown)) == (1 if direction == "n" else 2) and (shown[4] != shown[0]) == (direction != "n")
        for frame in frames:  # each frame still restores its own finished cell
            source = np.array(Image.open(folder / "work" / "finish" / "color" / "idle" / direction / f"{frame['index']:03d}.png"))
            assert (restored(colour, frame) == source).all()
    distinct = {r for fs in clip["directions"].values() for r in rects(fs)}
    assert len(distinct) < 2 * len(DIRECTIONS)  # directions rendered alike share too (the fake render tints by the name's length)
    assert len(distinct) == 4  # the fake render tints by the Direction name's length, so two images, each open and blinking


def test_a_clip_without_a_repeated_cell_is_packed_as_before(project: Kiripix) -> None:
    _, sheet = stamped_sheet(project, {**STILL, "still": 1, "blink": []})

    [clip] = sheet["clips"]
    assert all(len(fs) == 1 for fs in clip["directions"].values())
    assert len({r for fs in clip["directions"].values() for r in rects(fs)}) < len(DIRECTIONS)  # an identical direction shares


def test_the_export_plays_every_frame_from_one_atlas_texture_for_each_region(project: Kiripix) -> None:
    stamped_sheet(project, STILL)
    godot_project(project)
    set_target(project)
    project.json("run", HERO)

    project.json("export", HERO)

    frames = (project.cwd / FRAMES).read_text("utf-8")
    built = json.loads((project.cwd / "assets" / "character" / "hero" / "out" / "export" / "character.json").read_text("utf-8"))
    [clip] = built["clips"]
    assert frames.count("[sub_resource") == len({r for fs in clip["directions"].values() for r in rects(fs)}) == 4
    played = re.findall(r'"frames": \[(.*?)\],\n"loop"', frames, flags=re.S)
    assert len(played) == len(DIRECTIONS)
    for animation in played:
        textures = re.findall(r'"texture": SubResource\("([^"]+)"\)', animation)
        assert len(textures) == 6 and len(set(textures)) in (1, 2)
        assert textures[0] == textures[3] == textures[5]
        assert animation.count('"duration": 1.0') == 6  # no run is collapsed into a longer duration
    ident = re.findall(r'\[sub_resource type="AtlasTexture" id="([^"]+)"\]', frames)
    assert len(ident) == len(set(ident))
    assert all(len(fs) == 6 for fs in clip["directions"].values())
