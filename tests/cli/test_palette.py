"""The room's palette Stage (spec §6.1, ADR 0004): the Plate mapped to the palette, then orphan pixels removed."""

import json
from pathlib import Path

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_fit import ROOM, art, read, room_from, upscaled

DOWNSTREAM = ["palette", "place", "reach", "export"]


def palette_file(project: Kiripix) -> Path:
    return project.cwd / "style" / "palette.gpl"


def palette_colours(project: Kiripix) -> set[tuple[int, int, int]]:
    colours = set()
    for line in palette_file(project).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
            colours.add((int(parts[0]), int(parts[1]), int(parts[2])))
    return colours


def off_palette_art(width: int, height: int) -> np.ndarray:
    """Pixels of colours that are on no palette, with a single-pixel speck of another colour in a flat field."""
    rng = np.random.default_rng(5)
    rgba = np.full((height, width, 4), 255, dtype=np.uint8)
    rgba[..., :3] = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    return rgba


def fitted_room(project: Kiripix, width: int = 48, height: int = 32, source: np.ndarray | None = None) -> Path:
    pixels = off_palette_art(width, height) if source is None else source
    folder = room_from(project, upscaled(pixels, 2), width, height)
    project.json("set", ROOM, "fit", "scale=2")  # flat areas give grid detection nothing to find
    return folder


def test_a_fit_room_runs_through_palette_with_every_pixel_on_the_palette_and_check_is_clean(project: Kiripix) -> None:
    folder = fitted_room(project)

    project.json("run", ROOM, expect=3)  # stops only at the masks Stage's info

    assert stage_status(project, ROOM)["palette"] == "done"
    mapped = read(folder / "work" / "palette" / "palette.png")
    assert mapped.shape == (32, 48, 4) and (mapped[..., 3] == 255).all()
    colours = {tuple(int(c) for c in p) for p in mapped[..., :3].reshape(-1, 3)}
    assert colours <= palette_colours(project) and len(colours) > 1
    result = project.json("check", ROOM, expect=0)
    assert [f for f in result["findings"] if f["severity"] != "info"] == []


def test_a_plate_already_on_the_palette_is_unchanged_when_there_are_no_orphans(project: Kiripix) -> None:
    colours = sorted(palette_colours(project))[:3]
    pixels = np.full((32, 48, 4), 255, dtype=np.uint8)
    for i, colour in enumerate(colours):
        pixels[:, i * 16:(i + 1) * 16, :3] = colour
    folder = fitted_room(project, source=pixels)

    project.json("run", ROOM, expect=3)

    assert (read(folder / "work" / "palette" / "palette.png") == pixels).all()


def test_orphan_size_removes_a_speck_and_zero_keeps_it(project: Kiripix) -> None:
    colours = sorted(palette_colours(project))[:2]
    pixels = np.full((32, 48, 4), 255, dtype=np.uint8)
    pixels[..., :3] = colours[0]
    pixels[10, 10, :3] = colours[1]
    folder = fitted_room(project, source=pixels)
    mapped = folder / "work" / "palette" / "palette.png"

    project.json("run", ROOM, expect=3)
    assert (read(mapped)[10, 10, :3] == colours[0]).all()  # the default orphan_size is 1

    project.json("set", ROOM, "palette", "orphan_size=0")
    project.json("run", ROOM, expect=3)
    assert (read(mapped)[10, 10, :3] == colours[1]).all()


def test_dither_and_strength_are_parameters_and_change_the_result(project: Kiripix) -> None:
    gradient = np.full((32, 48, 4), 255, dtype=np.uint8)
    gradient[..., :3] = np.linspace(0, 255, 48, dtype=np.uint8)[None, :, None]
    folder = fitted_room(project, source=gradient)
    mapped = folder / "work" / "palette" / "palette.png"
    project.json("run", ROOM, expect=3)
    strict = read(mapped)

    project.json("set", ROOM, "palette", "dither=bayer4", "orphan_size=0")
    project.json("run", ROOM, expect=3)
    dithered = read(mapped)
    project.json("set", ROOM, "palette", "strength=0")
    project.json("run", ROOM, expect=3)
    project.json("set", ROOM, "palette", "dither=none")
    project.json("run", ROOM, expect=3)
    unfiltered = read(mapped)

    assert (dithered != strict).any()
    assert (unfiltered[..., :3] != strict[..., :3]).sum() <= (dithered[..., :3] != strict[..., :3]).sum()
    colours = {tuple(int(c) for c in p) for p in dithered[..., :3].reshape(-1, 3)}
    assert colours <= palette_colours(project)


def test_a_decide_on_masks_leaves_palette_done(project: Kiripix) -> None:
    fitted_room(project)
    project.json("run", ROOM, expect=3)
    assert stage_status(project, ROOM)["palette"] == "done"

    project.json("decide", ROOM, "masks", "--decision",
                 json.dumps({"decision": "flood", "data": {"x": 1, "y": 1, "mask": "solid"}}))

    status = stage_status(project, ROOM)
    assert status["masks"] == "stale"
    assert status["palette"] == "done"


def test_editing_the_palette_makes_palette_and_everything_downstream_stale(project: Kiripix) -> None:
    fitted_room(project)
    project.json("run", ROOM, expect=3)
    before = stage_status(project, ROOM)
    assert before["palette"] == "done"

    with palette_file(project).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("  1   2   3\tnew\n")

    after = stage_status(project, ROOM)
    assert all(after[stage] == "stale" for stage in DOWNSTREAM if before[stage] == "done" or stage == "palette")
    assert after["fit"] == "done" and after["layers"] == "done" and after["masks"] == before["masks"]


def test_check_reports_an_off_palette_pixel_with_the_command_that_rebuilds_the_stage(project: Kiripix) -> None:
    folder = fitted_room(project)
    project.json("run", ROOM, expect=3)
    path = folder / "work" / "palette" / "palette.png"
    mapped = read(path).copy()
    mapped[3, 4, :3] = (1, 2, 3)
    Image.fromarray(mapped, "RGBA").save(path)

    result = project.json("check", ROOM, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "palette.off_palette"]
    assert finding["fix"] == f"kiripix run {ROOM} palette --force"
    assert (finding["position"]["stage"], finding["position"]["x"], finding["position"]["y"]) == ("palette", 4, 3)
