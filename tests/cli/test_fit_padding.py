"""Grid `fit` pads up to the brief (ticket 0127, spec §6.1): a grid output smaller than the brief gets a transparent strip
on the right and bottom, and the strip is solid, silent in the checks and refused as a click target."""

import json
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_export import godot_project, set_target
from test_masks import ROOM, decide, mask_import, read_mask
from test_place import ON_THE_FLOOR, place

# Colours of the default palette, so that an unpadded room has no `palette.mapping_error`.
NIGHT, STONE, WINE = (29, 43, 83, 255), (95, 87, 79, 255), (126, 37, 83, 255)


def cells(width: int, height: int) -> np.ndarray:
    """A wall on the left 16 columns, a floor, and a rug inside the floor: one pixel per target cell."""
    image = np.full((height, width, 4), STONE, dtype=np.uint8)
    image[:, :16] = NIGHT
    image[8:14, 24:36] = WINE
    return image


class Fixture(NamedTuple):
    """A room whose Source holds `cells_width` x `height` cells of `scale` px from `offset_x`, with a brief `width` wide."""

    cells_width: int
    height: int
    scale: int
    offset_x: int
    width: int


SMALL = Fixture(47, 32, 1, 0, 48)  # the brief asks for 48 columns, the Source holds 47
BEDROOM = Fixture(332, 192, 4, 48, 336)  # room.annex_bedroom: a 1376 x 768 Source, offset_x 48, brief 336 x 192


def padded_room(project: Kiripix, fixture: Fixture = SMALL) -> Path:
    """The room of `fixture`, its Source imported and picked; the Stages not yet run."""
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", f"width={fixture.width}", f"height={fixture.height}")
    project.json("set", ROOM, "fit", f"scale={fixture.scale}", f"offset_x={fixture.offset_x}")
    art = np.repeat(np.repeat(cells(fixture.cells_width, fixture.height), fixture.scale, axis=0), fixture.scale, axis=1)
    source = np.zeros((art.shape[0], fixture.offset_x + art.shape[1], 4), dtype=np.uint8)
    source[:, :fixture.offset_x] = (0, 0, 0, 255)
    source[:, fixture.offset_x:] = art
    Image.fromarray(source, "RGBA").save(project.cwd / "source.png")
    data: dict[str, Any] = project.json("import", ROOM, "source.png")["data"]
    project.json("pick", ROOM, str(data["variant"]))
    return project.cwd / "assets" / "room" / "alley"


def codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"]]


def test_fit_pads_right_and_says_so_and_records_the_padding(project: Kiripix) -> None:
    folder = padded_room(project, BEDROOM)

    result = project.json("run", ROOM, expect=3)

    fit = np.asarray(Image.open(folder / "work" / "fit" / "fit.png").convert("RGBA"))
    assert fit.shape == (192, 336, 4)
    assert (fit[:, 332:] == 0).all() and (fit[:, :332] == cells(332, 192)).all()
    grid = json.loads((folder / "work" / "fit" / "grid.json").read_text("utf-8"))
    assert (grid["width"], grid["height"], grid["pad_right"], grid["pad_bottom"]) == (336, 192, 4, 0)
    [padded] = [f for f in result["findings"] if f["code"] == "fit.padded"]
    assert padded["severity"] == "info" and "4 px on the right" in padded["message"]
    assert padded["owner_action"] and not padded.get("fix")
    assert "fit.size_mismatch" not in codes(result)


def test_the_strip_is_solid_and_silent_and_an_old_coordinate_stays_where_it_was(project: Kiripix) -> None:
    folder = padded_room(project, BEDROOM)
    project.json("run", ROOM, expect=3)
    decide(project, "flood", {"x": 0, "y": 0, "mask": "solid"})  # the wall on the left, before and after the strip
    place(project, "spawn.main", "spawn", at=ON_THE_FLOOR)
    godot_project(project)
    set_target(project)

    result = project.json("run", ROOM)

    solid = read_mask(folder)
    assert solid.shape == (192, 336) and solid[:, 332:].all()
    assert solid[:, :16].all() and not solid[:, 16:332].any()  # the wall is where the flood put it
    seen = set(codes(result)) | set(codes(project.json("check", ROOM)))
    assert not seen & {"reach.unreachable_island", "layers.plate_hole", "palette.off_palette",
                       "palette.mapping_error"}
    mapped = np.asarray(Image.open(folder / "work" / "palette" / "palette.png").convert("RGBA"))
    assert (mapped[:, 332:] == 0).all()
    assert not [f for f in result["findings"] if f["code"] == "masks.open_edge" and "right" in f["message"]]
    project.json("export", ROOM)
    assert stage_status(project, ROOM)["export"] == "done"


def layers_click(project: Kiripix, x: int, y: int) -> None:
    data = {"layer": "lamp", "x": x, "y": y, "positive": True}
    project.json("decide", ROOM, "layers", "--decision", json.dumps({"decision": "click", "data": data}))


def test_a_layers_click_in_the_strip_needs_input_that_names_the_strip_and_the_undo(project: Kiripix) -> None:
    padded_room(project)
    project.json("run", ROOM, expect=3)

    layers_click(project, 47, 5)
    result = project.json("run", ROOM, "layers", expect=3)

    assert stage_status(project, ROOM)["layers"] == "needs-input"
    advice = project.json("next", ROOM)["data"]
    assert "padded strip" in advice["reason"] + json.dumps(result)
    assert f"kiripix undo {ROOM} layers" in advice["owner_action"]


def test_a_click_on_the_last_real_column_reaches_the_same_source_point_as_before(project: Kiripix) -> None:
    padded_room(project, BEDROOM)
    project.json("run", ROOM, expect=3)

    layers_click(project, 331, 5)
    project.json("run", ROOM, "layers", "--rerun", expect=3)

    path = project.cwd / "runner-calls.jsonl"
    found = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    [segmentation] = [c for c in found if "points" in c["params"]]
    # the centre of cell 331: columns 48 + 331 * 4 = 1372 to 1376, rows 5 * 4 = 20 to 24; as on a room with no padding
    assert segmentation["params"]["points"] == [[1374.0, 22.0, True]]


def test_a_painted_mask_imported_at_the_old_size_is_padded_with_off(project: Kiripix) -> None:
    folder = padded_room(project)
    project.json("run", ROOM, expect=3)
    painted = np.zeros((32, 47, 4), dtype=np.uint8)
    painted[4:10, 2:12] = (255, 0, 0, 255)  # red is solid's colour
    mask_import(project, painted)

    project.json("run", ROOM, "masks")

    solid = read_mask(folder)
    expected = np.zeros((32, 48), dtype=np.bool_)
    expected[4:10, 2:12] = True
    expected[:, 47:] = True  # the strip is solid; the import keeps its coordinates
    assert (solid == expected).all()


def test_a_grid_larger_than_the_brief_offers_the_brief_rounded_up_and_the_fix_pads(project: Kiripix) -> None:
    folder = padded_room(project)
    project.json("set", ROOM, "brief", "width=32", "height=32")

    result = project.json("run", ROOM, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "fit.size_mismatch"]
    assert finding["fix"] == f"kiripix set {ROOM} brief width=48 height=32"
    assert "offset_x=15" in finding["message"]
    project.json("set", ROOM, "brief", "width=48", "height=32")
    project.json("run", ROOM, expect=3)
    assert stage_status(project, ROOM)["fit"] == "done"
    assert json.loads((folder / "work" / "fit" / "grid.json").read_text("utf-8"))["pad_right"] == 1
