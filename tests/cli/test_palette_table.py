"""The character `palette` Stage reads the Project's ramp table (ticket 0168, spec §6.3): `parts` names parts of the table, each
part's length and row come from it, a part with `rgb` is mapped onto the table's colours, and every `rgb` colour is kept out of
the character's other colours. On the fake Blender: with `blender-material-split`, material 1 is the left half of a frame and
2 the right; the hero's materials are `cloth` (1) and `skin` (2), the twin's `face` (1) and `jacket` (2)."""

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_character_model import HERO
from test_character_ramps import colours_of
from test_clips_copy import TWIN
from test_ramp_table import codes, hero, row, table, twin

STONE, DUSK, MIST = [95, 87, 79], [131, 118, 156], [194, 195, 199]
RUST, AMBER = [171, 82, 54], [255, 163, 0]  # the palette colours nearest the fake's left half, (200, 100, 50)
SKIN = [STONE, DUSK, MIST]


def palette_of(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work/palette/palette.json").read_text("utf-8"))
    return document


def parts_of(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["name"]: p for p in document["parts"]}


def twin_named_otherwise(project: Kiripix, parts: str) -> Path:
    (project.cwd / "blender-materials").write_text(json.dumps(["face", "jacket"]), encoding="utf-8")
    return twin(project, parts)


def test_two_characters_with_other_material_names_get_the_tables_rows_lengths_and_shared_colours(project: Kiripix) -> None:
    table(project, row("skin", 3, SKIN), row("top", 2))

    hero_dir = hero(project, "skin,top=cloth")
    twin_dir = twin_named_otherwise(project, "top=face,skin=jacket")

    first, second = parts_of(palette_of(hero_dir)), parts_of(palette_of(twin_dir))
    assert palette_of(hero_dir)["schema_version"] == 3
    for parts, skin, top in ((first, ["skin"], ["cloth"]), (second, ["jacket"], ["face"])):
        assert parts["skin"]["row"] == 0 and parts["skin"]["shared"] is True and parts["skin"]["materials"] == skin
        assert parts["top"]["row"] == 1 and parts["top"]["shared"] is False and parts["top"]["materials"] == top
        assert parts["skin"]["rgb"] == SKIN and len(parts["top"]["rgb"]) == 2
    for folder in (hero_dir, twin_dir):  # the skin (the right half) uses the table's colours, every one of them
        right: set[tuple[int, ...]] = set()
        for path in sorted((folder / "work/palette/color").rglob("*.png")):
            right |= colours_of(path, "right")
        assert right == {tuple(c) for c in SKIN}


def test_changing_the_table_makes_every_characters_palette_stale_and_no_render(project: Kiripix) -> None:
    table(project, row("skin", 3, SKIN), row("top", 2))
    hero(project, "skin,top=cloth")
    twin_named_otherwise(project, "top=face,skin=jacket")
    assert stage_status(project, HERO)["palette"] == stage_status(project, TWIN)["palette"] == "done"

    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8").replace("length = 2", "length = 3"), encoding="utf-8")

    for asset in (HERO, TWIN):
        status = stage_status(project, asset)
        assert status["palette"] == "stale" and status["render"] == "done", (asset, status)


def test_a_part_not_in_the_table_fails_naming_the_tables_parts_and_a_length_of_its_own_is_refused(project: Kiripix) -> None:
    table(project, row("skin", 3, SKIN), row("top", 2))
    hero(project, "skin")

    project.json("set", HERO, "palette", "parts=skin,hair=cloth")
    missing = project.json("run", HERO, "palette", expect=3)

    [finding] = [f for f in missing["findings"] if f["code"] == "palette.part_not_in_table"]
    assert "hair" in finding["message"] and "skin, top" in finding["message"]
    assert finding["fix"] is None and "ramps-add" in finding["owner_action"]
    project.json("set", HERO, "palette", "parts=skin:4")
    assert "palette.parts_invalid" in codes(project.json("run", HERO, "palette", expect=1))


def test_the_tables_colours_are_reserved_even_for_a_part_the_character_lacks(project: Kiripix) -> None:
    folder = hero(project, "skin")
    unreserved = {tuple(c) for c in colours_of(folder / "work/palette/color/idle/s/000.png", "left")}
    assert unreserved & {tuple(RUST), tuple(AMBER)}, unreserved  # the cloth would take one of hair's colours
    table(project, row("skin", 3, SKIN), row("hair", 2, [RUST, AMBER]))

    project.json("run", HERO, "palette")

    document = palette_of(folder)
    assert [p["name"] for p in document["parts"]] == ["skin"]
    taken = {tuple(c["rgb"]) for c in document["colors"]}
    assert taken.isdisjoint({tuple(RUST), tuple(AMBER)}) and taken.isdisjoint({tuple(c) for c in SKIN})
    for path in sorted((folder / "work/palette/color").rglob("*.png")):
        assert colours_of(path, "left").isdisjoint({tuple(RUST), tuple(AMBER)}), path
    assert project.json("check", HERO, expect=0)["findings"] == []


def test_the_check_finds_a_pixel_in_a_reserved_colour_and_finish_refuses_it_as_the_outline(project: Kiripix) -> None:
    table(project, row("skin", 3, SKIN), row("hair", 2, [RUST, AMBER]))
    folder = hero(project, "skin")
    path = folder / "work" / "palette" / "color" / "idle" / "s" / "003.png"
    image = np.array(Image.open(path))
    image[0, 0, :3] = RUST  # a pixel of cloth, in hair's colour
    Image.fromarray(image, "RGBA").save(path)

    result = project.json("check", HERO, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "palette.ramp_shared"]
    assert "hair" in finding["message"] and finding["fix"]
    project.json("set", HERO, "palette", "colors=4")  # so some colour is free for the outline
    project.json("run", HERO, "palette")
    project.json("set", HERO, "finish", "outline_colour=8")  # rust
    refused = project.json("run", HERO, "finish", expect=1)
    [outline] = [f for f in refused["findings"] if f["code"] == "finish.outline_in_ramp"]
    assert "hair" in outline["message"] and re.fullmatch(rf"kiripix set {HERO} finish outline_colour=\d+", outline["fix"])


def test_with_an_empty_table_a_part_may_still_join_materials_under_a_name_of_its_own(project: Kiripix) -> None:
    folder = hero(project, "body=cloth+skin")

    [part] = palette_of(folder)["parts"]

    assert part["name"] == "body" and part["materials"] == ["cloth", "skin"] and part["row"] == 0
    assert part["shared"] is False and len(part["rgb"]) == 3

