"""The room's `palette` Stage with Layers (ticket 0045, ADR 0004): `palette.png` is the whole composite mapped once; after
the Overrides, each Layer is that image cut by its alpha and the Plate is it outside the hole, so Plate and Layers
recompose exactly to `palette.png` with every pixel on the palette."""

import json
from pathlib import Path

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_layers_stage import ROOM, accept, built_room, calls, click, lift, rgba
from test_palette import palette_colours


def out(folder: Path) -> Path:
    return folder / "work" / "palette"


def lifted_and_mapped(project: Kiripix) -> Path:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    project.json("run", ROOM, "palette")
    return folder


def recomposed(folder: Path) -> np.ndarray:
    image = rgba(out(folder) / "plate.png")
    for entry in json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"]:
        layer = rgba(out(folder) / entry["file"])
        painted = layer[..., 3] > 0
        image[painted] = layer[painted]
    return image


def on_palette(project: Kiripix, image: np.ndarray) -> bool:
    opaque = image[image[..., 3] == 255][:, :3]
    return {tuple(int(c) for c in p) for p in opaque} <= palette_colours(project)


def test_plate_and_layers_recompose_exactly_to_palette_png_with_every_pixel_on_the_palette(project: Kiripix) -> None:
    folder = lifted_and_mapped(project)

    palette = rgba(out(folder) / "palette.png")
    assert (recomposed(folder) == palette).all()
    assert (out(folder) / "layer.lamp.png").is_file()
    layer = rgba(out(folder) / "layer.lamp.png")
    alpha = layer[..., 3] > 0
    assert alpha[8, 8] and (layer[alpha] == palette[alpha]).all() and not layer[~alpha].any(), "palette.png cut by alpha"
    plate = rgba(out(folder) / "plate.png")
    assert (plate[~alpha] == palette[~alpha]).all(), "outside the hole the Plate is palette.png"
    assert (plate[alpha][:, 3] == 255).all(), "the hole is filled"
    for image in (palette, plate, layer):
        assert on_palette(project, image)
    assert [f["code"] for f in project.json("check", ROOM)["findings"] if f["code"].startswith(("layers.", "palette."))] == []


def test_with_no_layers_the_plate_is_byte_identical_to_palette_png(project: Kiripix) -> None:
    folder = built_room(project)
    project.json("run", ROOM, "palette")

    assert (out(folder) / "plate.png").read_bytes() == (out(folder) / "palette.png").read_bytes()
    assert json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"] == []


def test_a_palette_override_over_a_layer_shows_in_the_layer_and_still_recomposes(project: Kiripix) -> None:
    folder = lifted_and_mapped(project)
    colour = sorted(palette_colours(project))[-1]
    painted = np.zeros((32, 48, 4), dtype=np.uint8)
    painted[8, 8] = (*colour, 255)
    Image.fromarray(painted, "RGBA").save(project.cwd / "fix.png")

    project.json("override", ROOM, "palette", "fix.png")
    result = project.json("run", ROOM, "palette", "--force")

    assert tuple(rgba(out(folder) / "layer.lamp.png")[8, 8]) == (*colour, 255)
    assert tuple(rgba(out(folder) / "palette.png")[8, 8]) == (*colour, 255)
    assert (recomposed(folder) == rgba(out(folder) / "palette.png")).all()
    assert not [f for f in result["findings"] if f["code"].startswith(("layers.", "palette."))]


def test_a_mask_edit_does_not_make_palette_stale(project: Kiripix) -> None:
    lifted_and_mapped(project)
    assert stage_status(project, ROOM)["palette"] == "done"

    project.json("decide", ROOM, "masks", "--decision",
                 json.dumps({"decision": "flood", "data": {"x": 20, "y": 2, "mask": "solid"}}))

    assert stage_status(project, ROOM)["palette"] == "done"


def test_a_palette_change_rebuilds_with_no_runner_call_and_no_needs_input(project: Kiripix) -> None:
    folder = lifted_and_mapped(project)
    before = calls(project)

    project.json("set", ROOM, "palette", "orphan_size=0")
    assert stage_status(project, ROOM)["palette"] == "stale"
    project.json("run", ROOM, "palette")

    assert stage_status(project, ROOM)["palette"] == "done"
    assert calls(project) == before
    assert (recomposed(folder) == rgba(out(folder) / "palette.png")).all()
