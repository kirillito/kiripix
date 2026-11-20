"""What the 2026-11-18 review found in `render` and `finish` about held things (ticket 0313), on the fake Blender."""

import json
from pathlib import Path

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_character_clips import HIT, IDLE, clip, rigged_hero
from test_character_model import HERO
from test_character_render import render_calls, render_json
from test_clip_attach import SOCKET, add_thing, attached, held
from test_render_held import built, laid

DIRECTIONS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
SWING = {"name": "swing", "source": "walk", "start": 0, "end": 6, "fps": 15, "loop": False}


def test_a_given_point_named_like_the_socket_but_aimed_elsewhere_leaves_the_socket_its_own_point(project: Kiripix) -> None:
    folder = built(project, "phone")
    project.json("set", HERO, "render", "points=rightforearm@root")  # the name the socket would take, on another bone

    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")

    points = render_json(folder)["points"]
    assert {"name": "rightforearm", "target": "root"} in points
    [socket] = [p for p in points if p["target"] == SOCKET]
    assert socket["name"] not in {"rightforearm"} and socket["name"].startswith("socket_")
    assert all(socket["name"] in f["points"] for c in render_json(folder)["clips"]
               for frames in c["directions"].values() for f in frames)


def finished_hit(project: Kiripix) -> np.ndarray:
    """The finished first frame of `hit` (hat, then the stick whose one material is named `cloth`, as a Model's is)."""
    folder = rigged_hero(project)
    cwd = project.cwd
    (cwd / "blender-bones").write_text(json.dumps(["root", SOCKET]), encoding="utf-8")
    (cwd / "blender-materials").write_text(json.dumps(["cloth", "hat", "skin"]), encoding="utf-8")
    (cwd / "blender-thing-materials").write_text(json.dumps({"stick": "cloth"}), encoding="utf-8")
    (cwd / "blender-material-frames").write_text(json.dumps({f"hit/{d}": [2, 4] for d in DIRECTIONS}), encoding="utf-8")
    laid(folder, "stick")
    clip(project, IDLE)
    clip(project, attached(held("stick"), base=HIT))
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", "colors=6")
    project.json("run", HERO, "palette")
    project.json("set", HERO, "finish", "outline=false", "inner_lines=outline", "outline_colour=1")
    return rerun_finish(project)


def rerun_finish(project: Kiripix) -> np.ndarray:
    project.json("run", HERO, "finish")
    return np.array(Image.open(project.cwd / "assets" / "character" / "hero" / "work" / "finish" / "color" / "hit" / "s" / "000.png"))


def test_line_skip_on_a_name_the_model_and_a_thing_share_skips_both(project: Kiripix) -> None:
    drawn = finished_hit(project)
    project.json("set", HERO, "finish", "line_skip=cloth")
    skipped = rerun_finish(project)

    assert (drawn != skipped).any()  # the border of the hat and the stick is a line unless the stick's `cloth` is skipped too


def clip_names(project: Kiripix) -> list[str]:
    return sorted(c["name"] for c in render_calls(project)[-1]["args"]["clips"])


def test_importing_a_thing_no_clip_holds_renders_no_clip_and_a_new_hold_renders_only_its_clip(project: Kiripix) -> None:
    folder = built(project, "phone")
    count = len(render_calls(project))

    add_thing(folder, "stick", b"new")  # no clip holds it
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    assert len(render_calls(project)) == count and stage_status(project, HERO)["render"] == "done"

    laid(folder, "phone", "stick")  # a clip now holds the stick, numbered after the phone
    clip(project, attached(held("stick"), base=SWING))
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    assert len(render_calls(project)) == count + 1 and clip_names(project) == ["swing"]
    assert [t["thing"] for t in render_json(folder)["things"]] == ["phone", "stick"]
    assert [m["index"] for t in render_json(folder)["things"] for m in t["materials"]] == [3, 4]
