"""The painted-room look of the character Recipe (ticket 0382, spec §6.3): hue-shifted toon shading, longer ramps and a highlight band,
a sel-out outline and inner lines, and contact shading, each behind a parameter whose default leaves the output as it was.
The CLI tests run on the fake Blender, which, for a toon with a hue, paints the right half of a colour frame as three flat steps
(dark and cool, base, light and warm); the marked tests run the real Blender 5.2 on the fixture Models and check that the
shading changes pixels only when it is asked to (ADR 0010: never which pixels)."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix, restore_template, stage_status
from PIL import Image
from test_cast_stack import figure
from test_character_clips import clip, real_hero
from test_character_model import HERO
from test_character_palette import frames, palette_json, project_palette
from test_character_render import ready, render_calls, render_json

RENDER_DEFAULTS = {"highlight": "0", "highlight_gain": "0.35", "shadow_hue": "", "light_hue": "", "hue_strength": "0.25",
                   "contact": "false", "contact_distance": "0.05", "contact_threshold": "0.5"}
OLD_TOON_KEYS = {"bands", "shadow", "band_edge", "band_smooth", "light"}
HUES = ("shadow_hue=#5a6fa8", "light_hue=#ffd9a0", "hue_strength=0.4")
BORDER = 3


def split(project: Kiripix) -> None:
    (project.cwd / "blender-material-split").write_text("", encoding="utf-8")


def read(path: Path) -> np.ndarray:
    return np.array(Image.open(path))


def test_the_new_parameters_are_declared_and_off_by_default(project: Kiripix) -> None:
    [render] = project.json("describe", "character", "--stage", "render")["data"]["kinds"][0]["stages"]
    [finish] = project.json("describe", "character", "--stage", "finish")["data"]["kinds"][0]["stages"]

    by_name = {p["name"]: p for p in render["params"]}
    assert by_name["highlight"]["default"] == 0 and by_name["contact"]["default"] is False
    assert by_name["shadow_hue"]["default"] == "" and by_name["light_hue"]["default"] == ""
    assert (by_name["bands"]["minimum"], by_name["bands"]["maximum"]) == (2, 8)
    assert "render.hue_invalid" in [c["code"] for c in render["checks"]]
    from_ = {p["name"]: p for p in finish["params"]}["outline_from"]
    assert from_["choices"] == ["colour", "part"] and from_["default"] == "colour"


def test_every_new_parameter_at_its_default_leaves_the_render_as_it_was(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")
    before = {p.relative_to(folder): p.read_bytes() for p in (folder / "work" / "render").rglob("*") if p.is_file() and p.name != ".stage.json"}
    [call] = render_calls(project)
    assert set(call["args"]["toon"]) == OLD_TOON_KEYS, "no new key reaches Blender unless it is on"

    project.json("set", HERO, "render", *(f"{k}={v}" for k, v in RENDER_DEFAULTS.items()))

    assert stage_status(project, HERO)["render"] == "done", "a parameter at its default is no input"
    project.json("run", HERO, "render", "--force")
    after = {p.relative_to(folder): p.read_bytes() for p in (folder / "work" / "render").rglob("*") if p.is_file() and p.name != ".stage.json"}
    assert after == before
    assert set(render_calls(project)[-1]["args"]["toon"]) == OLD_TOON_KEYS
    assert set(render_json(folder)["toon"]) == OLD_TOON_KEYS and render_json(folder)["bands"] == 3


def test_every_new_finish_parameter_at_its_default_leaves_the_frames_as_they_were(project: Kiripix) -> None:
    folder = parts_finished(project)
    before = {p.relative_to(folder): p.read_bytes() for p in (folder / "work" / "finish").rglob("*") if p.is_file() and p.name != ".stage.json"}

    project.json("set", HERO, "finish", "outline_from=colour")

    assert stage_status(project, HERO)["finish"] == "done"
    project.json("run", HERO, "finish", "--force")
    assert {p.relative_to(folder): p.read_bytes() for p in (folder / "work" / "finish").rglob("*") if p.is_file() and p.name != ".stage.json"} == before
    assert "from" not in json.loads((folder / "work" / "finish" / "finish.json").read_text("utf-8"))["outline"]


def test_the_looks_that_are_on_reach_blender_and_render_json_and_make_the_render_stale(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")

    project.json("set", HERO, "render", *HUES, "highlight=0.9", "contact=true", "bands=6")

    assert stage_status(project, HERO)["render"] == "stale"
    project.json("run", HERO, "render")
    toon = render_calls(project)[-1]["args"]["toon"]
    assert toon["shadow_hue"] == "#5a6fa8" and toon["light_hue"] == "#ffd9a0" and toon["hue_strength"] == 0.4
    assert toon["highlight"] == 0.9 and toon["highlight_gain"] == 0.35 and toon["bands"] == 6
    assert toon["contact"] == {"distance": 0.05, "threshold": 0.5}
    document = render_json(folder)
    assert document["toon"] == toon and document["bands"] == 7, "a ramp holds the bands and the highlight"


def test_a_hue_that_is_not_a_colour_fails_with_the_fix(project: Kiripix) -> None:
    ready(project)
    project.json("set", HERO, "render", "shadow_hue=blue")

    [finding] = project.json("run", HERO, "render", expect=1)["findings"]

    assert finding["code"] == "render.hue_invalid" and "#rrggbb" in finding["message"]
    assert finding["fix"] == f"kiripix set {HERO} render shadow_hue="


def test_a_longer_ramp_follows_bands_and_the_highlight(project: Kiripix) -> None:
    split(project)
    folder = ready(project)
    project.json("set", HERO, "render", "bands=6", "highlight=0.9")
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", "parts=cloth,skin")

    project.json("run", HERO, "palette")

    assert [len(p["rgb"]) for p in palette_json(folder)["parts"]] == [7, 7]


# the sel-out outline ----------------------------------------------------------------------------------------------------


def build_parts_finished(project: Kiripix, *finish: str) -> None:
    """The hero with two parts, cloth on the left half of a frame and skin on the right, each with a line step, through
    `palette`; the opaque part is shrunk to leave a transparent border in the colour and material passes, as a render has."""
    split(project)
    ready(project)
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", "parts=cloth,skin", "part_lines=true", "colors=2")
    project.json("run", HERO, "palette")
    folder = project.cwd / "assets" / "character" / "hero"
    for path in frames(folder, "palette") + frames(folder, "render", "normal"):
        image = read(path)
        image[:BORDER], image[-BORDER:], image[:, :BORDER], image[:, -BORDER:] = 0, 0, 0, 0
        Image.fromarray(image, "RGBA").save(path)
    for path in frames(folder, "render", "material"):
        image = read(path)
        image[:BORDER], image[-BORDER:], image[:, :BORDER], image[:, -BORDER:] = 0, 0, 0, 0
        Image.fromarray(image).save(path)
    for path in frames(folder, "render", "depth"):
        depth = np.array(Image.open(path), dtype=np.uint16)
        depth[:BORDER], depth[-BORDER:], depth[:, :BORDER], depth[:, -BORDER:] = 65535, 65535, 65535, 65535
        Image.fromarray(depth).save(path)
    project.json("set", HERO, "finish", f"outline_colour={free_colour(project, folder)}", *finish)  # not in a ramp
    project.json("run", HERO, "finish")


def parts_finished(project: Kiripix, *finish: str) -> Path:
    restore_template(project, f"character-painted-{'-'.join(finish)}", lambda template: build_parts_finished(template, *finish))
    return project.cwd / "assets" / "character" / "hero"


def free_colour(project: Kiripix, folder: Path) -> int:
    """A palette index that no ramp or fixed colour of the hero uses, for a fixed outline colour."""
    document = palette_json(folder)
    used = {i for p in document["parts"] for i in p["indexes"]} | {c["index"] for c in document["colors"]}
    return next(i for i in range(len(project_palette(project))) if i not in used)


def first_colours(folder: Path) -> dict[str, tuple[int, ...]]:
    """Each part's first ramp colour: the line step."""
    return {p["name"]: tuple(p["rgb"][0]) for p in palette_json(folder)["parts"]}


def luma(rgb: tuple[int, ...]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def test_a_sel_out_outline_takes_the_colour_of_the_part_it_borders(project: Kiripix) -> None:
    folder = parts_finished(project, "outline_from=part", "outline_colour=1")

    ink = first_colours(folder)
    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    above = frame[BORDER - 1]  # the row above the silhouette: the outline pixels
    assert (above[BORDER:39, :3] == ink["cloth"]).all() and (above[39:-BORDER, :3] == ink["skin"]).all()
    assert (above[BORDER:-BORDER, 3] == 255).all()
    left = frame[BORDER:-BORDER, BORDER - 1]  # the column left of the silhouette: cloth
    assert (left[:, :3] == ink["cloth"]).all()
    below = frame[-BORDER]  # the row under the silhouette
    assert (below[BORDER:39, :3] == ink["cloth"]).all() and (below[39:-BORDER, :3] == ink["skin"]).all()
    outline = json.loads((folder / "work" / "finish" / "finish.json").read_text("utf-8"))["outline"]
    assert outline["from"] == "part" and set(outline["colours"]) == {"cloth", "skin"}


def test_sel_out_inner_lines_take_the_darker_of_the_two_parts(project: Kiripix) -> None:
    folder = parts_finished(project, "outline_from=part", "inner_lines=outline", "outline_colour=1")

    ink = first_colours(folder)
    darker = min(ink.values(), key=luma)
    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    assert (frame[BORDER:-BORDER, 39, :3] == darker).all(), "the border column's line is the darker part's"
    assert (frame[BORDER:-BORDER, 40:-BORDER, :3] != frame[BORDER, 39, :3]).any()


def test_the_fixed_outline_colour_stays_the_default(project: Kiripix) -> None:
    folder = parts_finished(project)
    free = free_colour(project, folder)

    palette = project_palette(project)
    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    assert (frame[BORDER - 1, BORDER:-BORDER, :3] == palette[free]).all()


# a swap recolours a hue-shifted ramp -------------------------------------------------------------------------------------


def test_a_part_swap_moves_every_pixel_of_a_hue_shifted_part_to_the_new_ramp_at_the_same_step(project: Kiripix) -> None:
    split(project)
    ready(project)
    project.json("set", HERO, "render", *HUES)
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", "parts=cloth,skin")
    project.json("run", HERO, "palette")
    folder = project.cwd / "assets" / "character" / "hero"
    project.json("set", HERO, "finish", f"outline_colour={free_colour(project, folder)}")
    project.json("run", HERO, "finish")
    project.json("run", HERO, "sheet")
    skin = [tuple(rgb) for rgb in next(p["rgb"] for p in palette_json(folder)["parts"] if p["name"] == "skin")]
    assert len(skin) == len(set(skin)) == 3, "the shadow, the base and the light are three colours of the ramp"
    new = [tuple(int(v) for v in rgb) for rgb in project_palette(project)[-3:]]
    assert not set(new) & set(skin)
    (project.cwd / "colours.json").write_text(json.dumps([{"skin": [list(c) for c in new]}]), encoding="utf-8")

    built = project.json("cast-sheet", HERO, "--clips", "idle")["data"]
    swapped = project.json("cast-sheet", HERO, "--clips", "idle", "--colours", "colours.json")["data"]

    before, after = figure(project, built), figure(project, swapped)
    seen = set()
    for y, x in np.argwhere(before[..., 3] > 0):
        colour = tuple(int(v) for v in before[y, x, :3])
        if colour in skin:
            step = skin.index(colour)
            seen.add(step)
            assert tuple(int(v) for v in after[y, x, :3]) == new[step], f"pixel {(x, y)} is step {step}"
        else:
            assert (after[y, x] == before[y, x]).all(), f"pixel {(x, y)} isn't skin and is unchanged"
    assert seen == {0, 1, 2}, "every step of the part was in the frame, so every step was swapped"
    assert swapped["cells"][0]["swapped"] == ["skin"]


# real Blender -------------------------------------------------------------------------------------------------------------


def real_render(project: Kiripix, folder: Path, *params: str) -> dict[str, np.ndarray]:
    """The hero's rendered colour frames with exactly these render parameters (the others back at their defaults)."""
    project.json("set", HERO, "render", "height=26", *(f"{k}={v}" for k, v in RENDER_DEFAULTS.items()), *params, test_recipes=False)
    project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)
    return {str(p.relative_to(folder)): read(p) for p in sorted((folder / "work" / "render" / "color").rglob("*.png"))}


@pytest.mark.blender
def test_on_real_blender_the_defaults_are_the_plain_render_and_each_look_changes_the_colour_pass(project: Kiripix) -> None:
    folder = real_hero(project, "rigged.fbx")
    clip(project, {"name": "idle", "source": "idle", "start": 1, "end": 25, "fps": 3, "loop": True, "stationary": True},
         test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)

    plain = real_render(project, folder)
    again = real_render(project, folder, *(f"{k}={v}" for k, v in RENDER_DEFAULTS.items()))
    shifted = real_render(project, folder, *HUES)
    lifted = real_render(project, folder, "highlight=0.8")
    closed = real_render(project, folder, "contact=true", "contact_threshold=0.2", "contact_distance=0.2")

    assert len(plain) > 0 and set(plain) == set(shifted) == set(lifted) == set(closed)
    assert all((plain[k] == again[k]).all() for k in plain), "every parameter at its default is the plain render, byte for byte"
    for name, looks in (("hue", shifted), ("highlight", lifted), ("contact", closed)):
        assert any((plain[k] != looks[k]).any() for k in plain), f"the {name} look changes a pixel"
        assert all((plain[k][..., 3] == looks[k][..., 3]).all() for k in plain), f"the {name} look keeps the silhouette"
