"""The room's fit Stage and the layers pass-through (spec §6.1, ADR 0004), on generated pixel art."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image

ROOM = "room.alley"
PALETTE = np.array([[0, 0, 0], [255, 0, 77], [41, 173, 255], [0, 228, 54], [255, 236, 39]], dtype=np.uint8)


def art(width: int = 480, height: int = 272, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rgba = np.full((height, width, 4), 255, dtype=np.uint8)
    rgba[..., :3] = PALETTE[rng.integers(0, len(PALETTE), size=(height, width))]
    return rgba


def upscaled(image: np.ndarray, scale: int) -> np.ndarray:
    return np.repeat(np.repeat(image, scale, axis=0), scale, axis=1)


def read(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8)


def room_from(project: Kiripix, source: np.ndarray, width: int = 480, height: int = 272) -> Path:
    """A room whose brief is width x height, with `source` imported and picked; the Stages not yet run."""
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", f"width={width}", f"height={height}")
    Image.fromarray(source, "RGBA").save(project.cwd / "source.png")
    data: dict[str, Any] = project.json("import", ROOM, "source.png")["data"]
    project.json("pick", ROOM, str(data["variant"]))
    return project.cwd / "assets" / "room" / "alley"


def test_a_4x_upscaled_source_fits_exactly_and_layers_passes_the_image_through(project: Kiripix) -> None:
    pixels = art()
    folder = room_from(project, upscaled(pixels, 4))

    project.json("run", ROOM, expect=3)

    status = stage_status(project, ROOM)
    assert status["fit"] == "done" and status["layers"] == "done"
    fit = read(folder / "work" / "fit" / "fit.png")
    assert fit.shape == (272, 480, 4) and (fit == pixels).all()
    grid = json.loads((folder / "work" / "fit" / "grid.json").read_text(encoding="utf-8"))
    assert grid == {"mode": "grid", "source": [1920, 1088], "scale_x": 4, "scale_y": 4, "offset_x": 0,
                    "offset_y": 0, "width": 480, "height": 272}
    assert read(folder / "work" / "layers" / "plate.png").tobytes() == fit.tobytes()
    layers = json.loads((folder / "work" / "layers" / "layers.json").read_text(encoding="utf-8"))
    assert layers == {"schema_version": 1, "layers": []}
    assert project.json("next", ROOM)["data"]["stage"] == "reach"  # masks is done, empty; palette and place are built


def test_fit_finds_the_offset_of_a_padded_source(project: Kiripix) -> None:
    pixels = art(48, 32)
    padded = np.full((32 * 3 + 5, 48 * 3 + 2, 4), (131, 118, 156, 255), dtype=np.uint8)
    padded[2:2 + 96, 1:1 + 144] = upscaled(pixels, 3)
    folder = room_from(project, padded, 48, 32)

    project.json("run", ROOM, expect=2)  # the padded cells make the grid 48x32 plus: a mismatch is reported

    grid = json.loads((folder / "work" / "fit" / "grid.json").read_text(encoding="utf-8"))
    assert (grid["scale_x"], grid["offset_x"], grid["offset_y"]) == (3, 1, 2)


def test_explicit_scale_and_offsets_are_used_when_set(project: Kiripix) -> None:
    pixels = art(48, 32)
    folder = room_from(project, upscaled(pixels, 2)[:, :], 48, 32)
    project.json("set", ROOM, "fit", "scale=2", "offset_x=0", "offset_y=0")

    project.json("run", ROOM, expect=3)

    assert (read(folder / "work" / "fit" / "fit.png") == pixels).all()
    grid = json.loads((folder / "work" / "fit" / "grid.json").read_text(encoding="utf-8"))
    assert grid["scale_x"] == 2 and grid["width"] == 48


def test_a_size_mismatch_reports_a_fix_that_next_offers_and_that_works(project: Kiripix) -> None:
    folder = room_from(project, upscaled(art(240, 144), 4), 240, 144)
    project.json("set", ROOM, "fit", "scale=2")

    result = project.json("run", ROOM, expect=2)

    finding = next(f for f in result["findings"] if f["code"] == "fit.size_mismatch")
    assert "480x288" in finding["message"] and "240x144" in finding["message"]
    assert finding["position"]["stage"] == "fit"
    assert finding["fix"] == f"kiripix set {ROOM} fit scale=4"
    step = project.json("next", ROOM)["data"]
    assert step["stage"] == "fit" and step["command"] == finding["fix"]

    project.json("set", ROOM, "fit", "scale=4")
    project.json("run", ROOM, expect=3)

    assert read(folder / "work" / "fit" / "fit.png").shape == (144, 240, 4)
    assert project.json("next", ROOM)["data"]["stage"] == "reach"  # masks is done, empty; palette and place are built


def test_a_source_without_a_grid_suggests_downscale_and_downscale_fits_exactly(project: Kiripix) -> None:
    noise = np.random.default_rng(5).integers(0, 256, size=(300, 500, 4), dtype=np.uint8)
    noise[..., 3] = 255
    folder = room_from(project, noise, 160, 96)

    result = project.json("run", ROOM, expect=2)

    finding = next(f for f in result["findings"] if f["code"] == "fit.size_mismatch")
    assert finding["fix"] == f"kiripix set {ROOM} fit mode=downscale"

    project.json("set", ROOM, "fit", "mode=downscale")
    project.json("run", ROOM, expect=3)

    fit = read(folder / "work" / "fit" / "fit.png")
    assert fit.shape == (96, 160, 4) and set(np.unique(fit[..., 3])) == {255}
    grid = json.loads((folder / "work" / "fit" / "grid.json").read_text(encoding="utf-8"))
    assert grid["mode"] == "downscale" and grid["scale_x"] == "25/8" and grid["scale_y"] == "25/8"
    assert (grid["width"], grid["height"]) == (160, 96)


def test_downscale_of_a_source_smaller_than_the_brief_fails_the_stage(project: Kiripix) -> None:
    room_from(project, art(8, 8), 480, 272)
    project.json("set", ROOM, "fit", "mode=downscale")

    result = project.json("run", ROOM, expect=1)

    assert result["findings"][-1]["code"] == "stage.failed"
    assert "480x272" in result["findings"][-1]["message"]


def test_changing_fit_mode_makes_fit_and_everything_below_stale(project: Kiripix) -> None:
    room_from(project, upscaled(art(), 4))
    project.json("run", ROOM, expect=3)
    assert stage_status(project, ROOM)["layers"] == "done"

    project.json("set", ROOM, "fit", "mode=downscale")

    status = stage_status(project, ROOM)
    assert status["brief"] == "done" and status["source"] == "done"
    assert status["fit"] == "stale" and status["layers"] == "stale"
    project.json("run", ROOM, expect=3)
    assert stage_status(project, ROOM)["fit"] == "done" and stage_status(project, ROOM)["layers"] == "done"


def test_changing_the_brief_size_makes_fit_stale(project: Kiripix) -> None:
    room_from(project, upscaled(art(), 4))
    project.json("run", ROOM, expect=3)

    project.json("set", ROOM, "brief", "width=240", "height=272")

    assert stage_status(project, ROOM)["fit"] == "stale"


def test_describe_shows_palette_below_layers_not_masks(project: Kiripix) -> None:
    stages = {s["name"]: s for s in project.json("describe", "room")["data"]["kinds"][0]["stages"]}

    assert stages["palette"]["inputs"]["upstream"] == ["layers"]
    assert stages["masks"]["inputs"]["upstream"] == ["layers", "source", "fit"]  # its Runner works on the Source
    assert stages["fit"]["inputs"]["upstream"] == ["source", "brief"]
    assert stages["layers"]["available_from"] == "M1" and stages["layers"]["gpu"]  # it makes Runner calls
