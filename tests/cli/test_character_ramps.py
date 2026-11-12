"""The character `palette` Stage with `parts` (ticket 0150): a ramp of its own for each swappable part, and `finish`'s refusal of an
outline colour that is in one. The CLI tests run on the fake Blender, whose material pass is all material 1 (`cloth`), or, with
the file `blender-material-split`, material 1 on the left half of a frame and 2 (`skin`) on the right."""

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_character_model import HERO
from test_character_palette import frames, palette_findings, palette_json, project_palette
from test_character_render import ready, render_json


def split(project: Kiripix) -> None:
    (project.cwd / "blender-material-split").write_text("", encoding="utf-8")


def built_parts(project: Kiripix, parts: str, *params: str) -> Path:
    split(project)
    folder = ready(project)
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", f"parts={parts}", *params)
    project.json("run", HERO, "palette")
    return folder


def ramp_of(document: dict[str, Any], name: str) -> list[tuple[int, ...]]:
    [part] = [p for p in document["parts"] if p["name"] == name]
    return [tuple(rgb) for rgb in part["rgb"]]


def colours_of(path: Path, half: str) -> set[tuple[int, ...]]:
    image = np.array(Image.open(path))
    width = image.shape[1]
    side = image[:, : width // 2] if half == "left" else image[:, width // 2:]
    return {tuple(int(v) for v in p[:3]) for p in side.reshape(-1, 4)}


def test_the_stage_declares_parts_with_an_example(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "palette")["data"]["kinds"]

    [stage] = kind["stages"]

    by_name = {p["name"]: p for p in stage["params"]}
    assert by_name["parts"]["type"] == "str" and by_name["parts"]["default"] == ""
    assert "skin,hair,jacket+hood,jeans,boots" in by_name["parts"]["description"]
    assert "skin:4" in by_name["parts"]["description"]
    assert [c["code"] for c in stage["checks"]] == ["palette.off_palette", "palette.ramp_shared"]


def test_each_part_gets_a_ramp_of_its_own_and_no_colour_is_in_two(project: Kiripix) -> None:
    folder = built_parts(project, "cloth,skin")

    document = palette_json(folder)
    assert document["schema_version"] == 3
    assert [p["name"] for p in document["parts"]] == ["cloth", "skin"]
    palette = project_palette(project)
    seen: list[int] = []
    for part in document["parts"]:
        assert part["materials"] == [part["name"]]
        assert len(part["indexes"]) == len(part["rgb"]) == render_json(folder)["bands"] == 3
        for index, rgb in zip(part["indexes"], part["rgb"], strict=True):
            assert palette[index].tolist() == rgb
        seen += part["indexes"]
    assert len(seen) == len(set(seen)) == 6
    fixed = {c["index"] for c in document["colors"]}
    assert fixed.isdisjoint(seen)


def test_every_pixel_is_mapped_onto_its_own_parts_ramp(project: Kiripix) -> None:
    folder = built_parts(project, "cloth,skin")

    document = palette_json(folder)
    cloth, skin = set(ramp_of(document, "cloth")), set(ramp_of(document, "skin"))
    assert cloth.isdisjoint(skin)
    for path in frames(folder, "palette"):
        assert colours_of(path, "left") <= cloth
        assert colours_of(path, "right") <= skin
    assert palette_findings(project) == []


def test_a_part_may_set_its_own_ramp_length_and_a_part_may_join_materials(project: Kiripix) -> None:
    folder = built_parts(project, "skin:4,cloth")

    document = palette_json(folder)
    assert [(p["name"], len(p["rgb"])) for p in document["parts"]] == [("skin", 4), ("cloth", 3)]

    project.json("set", HERO, "palette", "parts=cloth+skin")
    project.json("run", HERO, "palette")

    [part] = palette_json(folder)["parts"]
    assert part["name"] == "cloth+skin" and part["materials"] == ["cloth", "skin"] and len(part["rgb"]) == 3
    for path in frames(folder, "palette"):
        assert colours_of(path, "left") | colours_of(path, "right") <= {tuple(rgb) for rgb in part["rgb"]}


def test_materials_in_no_part_share_the_fixed_subset_that_colors_counts_and_no_ramp_uses_it(project: Kiripix) -> None:
    folder = built_parts(project, "skin", "colors=2")

    document = palette_json(folder)
    assert len(document["colors"]) == 2
    skin = set(ramp_of(document, "skin"))
    fixed = {tuple(c["rgb"]) for c in document["colors"]}
    assert skin.isdisjoint(fixed)
    for path in frames(folder, "palette"):
        assert colours_of(path, "left") <= fixed
        assert colours_of(path, "right") <= skin
    assert palette_findings(project) == []


def test_with_no_parts_the_stage_does_what_it_did(project: Kiripix) -> None:
    folder = ready(project)
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", "colors=3")
    project.json("run", HERO, "palette")

    document = palette_json(folder)

    assert document["parts"] == [] and len(document["colors"]) == 3


def test_changing_parts_makes_palette_stale_and_leaves_render(project: Kiripix) -> None:
    built_parts(project, "cloth,skin")
    status = stage_status(project, HERO)
    assert status["render"] == "done" and status["palette"] == "done"

    project.json("set", HERO, "palette", "parts=cloth")

    status = stage_status(project, HERO)
    assert status["render"] == "done" and status["clips"] == "done" and status["palette"] == "stale"
    assert project.json("run", HERO, "palette")["data"]["results"][0]["outcome"] == "done"


def test_a_name_that_is_not_a_material_fails_with_the_materials(project: Kiripix) -> None:
    split(project)
    ready(project)
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", "parts=skin,hair")

    result = project.json("run", HERO, "palette", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "palette.part_unknown"]
    assert "hair" in finding["message"] and "cloth" in finding["message"] and "skin" in finding["message"]
    assert finding["fix"].startswith(f"kiripix set {HERO} palette parts=")
    assert stage_status(project, HERO)["palette"] != "done"


def test_a_material_in_two_parts_or_a_bad_length_fails(project: Kiripix) -> None:
    split(project)
    ready(project)
    project.json("run", HERO, "render")

    for parts in ("skin,skin+cloth", "skin:0", "skin:x"):
        project.json("set", HERO, "palette", f"parts={parts}")
        result = project.json("run", HERO, "palette", expect=1)
        assert [f for f in result["findings"] if f["code"] == "palette.parts_invalid"], parts


def test_a_part_that_cannot_get_enough_free_colours_fails_naming_it(project: Kiripix) -> None:
    split(project)
    ready(project)
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", f"parts=cloth,skin:{len(project_palette(project)) + 1}")

    result = project.json("run", HERO, "palette", expect=1)

    assert any("skin" in f["message"] for f in result["findings"])


def test_the_check_finds_a_colour_of_one_ramp_in_a_pixel_of_another_part(project: Kiripix) -> None:
    folder = built_parts(project, "cloth,skin")
    document = palette_json(folder)
    path = folder / "work" / "palette" / "color" / "idle" / "s" / "003.png"
    image = np.array(Image.open(path))
    image[0, 0, :3] = ramp_of(document, "skin")[0]  # a pixel of cloth, in skin's colour
    Image.fromarray(image, "RGBA").save(path)

    result = project.json("check", HERO, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "palette.ramp_shared"]
    assert "cloth" in finding["message"] and "skin" in finding["message"]
    assert finding["position"]["file"] == "color/idle/s/003.png" and finding["fix"]


def test_finish_refuses_an_outline_colour_that_is_in_a_ramp_and_names_a_free_one(project: Kiripix) -> None:
    folder = built_parts(project, "cloth,skin")
    document = palette_json(folder)
    taken = {i for p in document["parts"] for i in p["indexes"]} | {c["index"] for c in document["colors"]}
    in_ramp = [p for p in document["parts"] if p["name"] == "skin"][0]["indexes"][0]
    project.json("set", HERO, "finish", f"outline_colour={in_ramp}")

    result = project.json("run", HERO, "finish", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "finish.outline_in_ramp"]
    assert "skin" in finding["message"] and str(in_ramp) in finding["message"] and finding["owner_action"] is None
    match = re.fullmatch(rf"kiripix set {HERO} finish outline_colour=(\d+)", finding["fix"])
    assert match and int(match.group(1)) not in taken
    project.json("set", HERO, "finish", f"outline_colour={match.group(1)}")
    assert project.json("run", HERO, "finish")["data"]["results"][0]["outcome"] == "done"


def test_an_outline_colour_in_a_ramp_is_fine_when_there_is_no_outline_or_no_parts(project: Kiripix) -> None:
    folder = built_parts(project, "cloth,skin")
    in_ramp = palette_json(folder)["parts"][0]["indexes"][0]
    project.json("set", HERO, "finish", f"outline_colour={in_ramp}", "outline=false")

    assert project.json("run", HERO, "finish")["data"]["results"][0]["outcome"] == "done"
