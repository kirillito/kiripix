"""A held thing's colours (ticket 0305), on the fake Blender. The Model's materials are `cloth` 1, `hat` 2 and `skin` 3; a thing's
one material is numbered after them (`stick` 4, then `phone` 5). A frame's material pass is bands left to right: the clips
`idle` (cloth, hat), `hit` (cloth, the stick) and `swing` (cloth, the phone), and the left half of every frame is one colour,
so the body's cloth is the same pixels whatever clips are built. A class weapon is a row of the Project's ramp table; the phone
takes colours of its own outside every part."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_character_clips import HIT, IDLE, clip, rigged_hero
from test_character_model import HERO
from test_character_ramps import colours_of
from test_clip_attach import SOCKET, attached, held
from test_ramp_table import row, table
from test_render_held import laid

DIRECTIONS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
SWING = {"name": "swing", "source": "walk", "start": 0, "end": 6, "fps": 15, "loop": False}


def palette_of(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work/palette/palette.json").read_text("utf-8"))
    return document


def frames_of(folder: Path, clip_name: str) -> dict[str, bytes]:
    root = folder / "work" / "palette" / "color" / clip_name
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*.png"))}


def start(project: Kiripix) -> Path:
    """The hero with `idle` and `hit` (the stick on its row, held in `hit`), rendered and mapped."""
    folder = rigged_hero(project)
    cwd = project.cwd
    (cwd / "blender-bones").write_text(json.dumps(["root", SOCKET]), encoding="utf-8")
    (cwd / "blender-materials").write_text(json.dumps(["cloth", "hat", "skin"]), encoding="utf-8")
    (cwd / "blender-thing-materials").write_text(json.dumps({"stick": "stick", "phone": "phone"}), encoding="utf-8")
    (cwd / "blender-material-frames").write_text(json.dumps(
        {f"{name}/{d}": bands for d in DIRECTIONS for name, bands in (("idle", [1, 2]), ("hit", [1, 4]), ("swing", [1, 5]))}),
        encoding="utf-8")
    table(project, row("top", 2), row("stick", 2))
    laid(folder, "stick")
    clip(project, IDLE)
    clip(project, attached(held("stick"), base=HIT))
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    project.json("set", HERO, "palette", "parts=top=cloth,stick", "colors=6")  # of the 16 colours of the test palette
    project.json("run", HERO, "palette")
    return folder


def add_the_phone(project: Kiripix, folder: Path) -> None:
    laid(folder, "stick", "phone")  # the journal in the order they were imported
    clip(project, attached(held("phone"), base=SWING))
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")
    project.json("run", HERO, "palette")


def test_a_thing_on_a_ramp_row_is_mapped_to_the_rows_colours_and_no_fixed_colour_is_its(project: Kiripix) -> None:
    folder = start(project)

    document = palette_of(folder)
    parts = {p["name"]: p for p in document["parts"]}
    assert parts["stick"]["materials"] == ["stick"] and len(parts["stick"]["rgb"]) == 2
    assert "thing_colors" not in document  # the stick is in a part: nothing is left outside it
    right = set()
    for path in sorted((folder / "work/palette/color/hit").rglob("*.png")):
        right |= colours_of(path, "right")
    assert right and right <= {tuple(c) for c in parts["stick"]["rgb"]}  # the stick's pixels are on its row, nothing else
    assert project.json("check", HERO)["findings"] == []


def test_a_thing_added_later_moves_no_pixel_of_the_body_and_has_colours_of_its_own(project: Kiripix) -> None:
    folder = start(project)
    before = {name: frames_of(folder, name) for name in ("idle", "hit")}
    body_before = palette_of(folder)

    add_the_phone(project, folder)

    after = palette_of(folder)
    assert {name: frames_of(folder, name) for name in ("idle", "hit")} == before  # byte for byte, in the clips without the phone
    assert after["colors"] == body_before["colors"] and after["parts"] == body_before["parts"]
    owned = {tuple(c["rgb"]) for c in after["thing_colors"]}
    taken = {tuple(c["rgb"]) for c in after["colors"]} | {tuple(c) for p in after["parts"] for c in p["rgb"]}
    assert owned and owned.isdisjoint(taken) and after["thing_shares_body"] is False
    seen = set()
    for path in sorted((folder / "work/palette/color/swing").rglob("*.png")):
        seen |= colours_of(path, "right")
        assert colours_of(path, "left") <= taken  # the cloth is the part's
    assert seen and seen <= owned
    assert project.json("check", HERO)["findings"] == []


def test_a_thing_with_no_colour_left_shares_the_bodys_and_the_check_says_so_as_a_warning(project: Kiripix) -> None:
    folder = start(project)
    project.json("set", HERO, "palette", "colors=12")  # the body's fixed colours take every colour the ramps leave
    add_the_phone(project, folder)

    document = palette_of(folder)
    assert document["thing_shares_body"] is True and document["thing_colors"] == []
    result = project.json("check", HERO)
    [finding] = [f for f in result["findings"] if f["code"] == "palette.thing_colors_shared"]
    assert finding["severity"] == "warning" and finding["owner_action"] and finding["fix"] is None
    swing = np.array(Image.open(folder / "work/palette/color/swing/s/000.png"))
    assert (swing[..., 3] == 255).all()  # still every pixel opaque and on the palette: no `palette.off_palette`
    assert not [f for f in result["findings"] if f["code"] == "palette.off_palette"]


def test_finish_draws_a_things_inner_lines_and_tolerates_a_material_absent_from_most_clips(project: Kiripix) -> None:
    folder = start(project)
    add_the_phone(project, folder)
    project.json("set", HERO, "palette", "part_lines=true")
    project.json("set", HERO, "finish", "inner_lines=dark")
    project.json("run", HERO, "palette")

    project.json("run", HERO, "finish")

    status = stage_status(project, HERO)
    assert status["finish"] == "done" and status["palette"] == "done"
    drawn = json.loads((folder / "work/finish/finish.json").read_text("utf-8"))
    names = {c["material"]: n for n, c in drawn["inner_lines"]["colours"].items()}
    assert {"cloth", "stick", "phone"} <= set(names.values()), names  # the lines of a part, of a row, of a thing
    assert project.json("check", HERO)["findings"] == []
