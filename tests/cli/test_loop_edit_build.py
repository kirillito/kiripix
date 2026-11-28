"""A Loop's edit frames, built (ticket 0220): each picked edit of the Source goes through the edit pipeline a Look's does,
the whole edit is mapped once, and the region is cut from it. `hold` keeps a part of the region still from one frame,
`loop.flicker` warns when the rest of the region redraws, `loop.misaligned` and `loop.drift` are per frame, and on a Layer
the frame is cut by the Layer's alpha (`loop.past_layer`)."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_layers_stage import CRATE, FLOOR, ROOM, rgba, target_image
from test_loop_edit_frames import edit_frame, pick_frame
from test_loop_kit import a_frame_loop
from test_loops import LOOP, decide, declare, findings, record
from test_looks_build import edited, room_with_a_lamp_layer, textured

REGION = [[2, 2], [40, 2], [40, 28], [2, 28]]  # rows 2 to 28, columns 2 to 40
BAND = [[2, 2], [40, 2], [40, 7], [2, 7]]  # the top 6 rows of it, 22 % of the region


def stripes(flip: bool) -> np.ndarray:
    """The room with the region redrawn as stripes 4 rows tall (flipped: the other way round), clear of the orphan rule."""
    image = target_image()
    rows = (np.arange(2, 29) // 4 % 2 == 1) ^ flip
    block = np.where(rows[:, None, None], np.array(CRATE, dtype=np.uint8), np.array(FLOOR, dtype=np.uint8))
    image[2:29, 2:41] = block
    return image


def two_redrawn_frames(project: Kiripix) -> list[str]:
    a_frame_loop(project, region=REGION, lamp_layer=False)
    decide(project, "frames", {"loop": LOOP, "source": "edits"})
    variants = []
    for number, flip in ((1, False), (2, True)):
        variant = str(edit_frame(project, f"edit{number}.png", stripes(flip), number)["data"]["variant"])
        pick_frame(project, variant, number)
        variants.append(variant)
    return variants


def build(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    project.json("run", ROOM, "masks")
    project.json("run", ROOM, "palette")
    project.json("run", ROOM, "looks")
    return project.json("run", ROOM, "loops", expect=expect)


def tile_of(folder: Path, loop: dict[str, Any], number: int) -> np.ndarray:
    x, y, width, height = loop["box"]
    strip = rgba(folder / "work" / "loops" / loop["plate"])
    columns = loop["columns"]
    row, column = divmod(number, columns)
    return strip[row * height:(row + 1) * height, column * width:(column + 1) * width]


def test_edit_frames_are_built_and_frame_zero_is_the_room(project: Kiripix) -> None:
    two_redrawn_frames(project)
    folder = project.cwd / "assets" / "room" / "alley"

    build(project)

    loop = record(folder)
    assert loop["held"] is None and loop["source"] == "edits" and loop["frames"] == 3
    assert [e["frame"] for e in loop["edits"]] == [1, 2]
    room = rgba(folder / "work" / "palette" / "palette.png")
    x, y, width, height = loop["box"]
    inside = room[y:y + height, x:x + width, 3] > 0
    assert (tile_of(folder, loop, 0) == 0).all(), "frame 0 is the room, which a strip leaves clear"
    one, two = tile_of(folder, loop, 1), tile_of(folder, loop, 2)
    assert (one[inside, :3] != two[inside, :3]).any(axis=1).mean() > 0.9, "the stripes swap in every row of the region"
    assert "loop.held" not in [f["code"] for f in findings(project)]


def test_a_redrawn_region_flickers_and_a_hold_over_all_but_a_band_clears_it(project: Kiripix) -> None:
    two_redrawn_frames(project)
    folder = project.cwd / "assets" / "room" / "alley"
    build(project)

    [flicker] = [f for f in findings(project) if f["code"] == "loop.flicker"]
    assert flicker["severity"] == "warning" and flicker["owner_action"] and "hold" in flicker["owner_action"]
    assert "1" in flicker["message"] and "2" in flicker["message"]
    assert record(folder)["flicker"][0]["share"] > 0.9

    held = [[2, 8], [40, 8], [40, 28], [2, 28]]
    decide(project, "hold", {"loop": LOOP, "frame": 1, "points": held})
    build(project)

    assert "loop.flicker" not in [f["code"] for f in findings(project)]
    loop = record(folder)
    one, two = tile_of(folder, loop, 1), tile_of(folder, loop, 2)
    x, y, width, height = loop["box"]
    rows = slice(8 - y, None)
    assert (one[rows] == two[rows]).all(), "outside the band the frames are equal"
    assert (one[:8 - y, :, :3] != two[:8 - y, :, :3]).any(), "the band still moves"
    assert loop["holds"]["pixels"] > 0 and loop["flicker"][0]["share"] < 0.3
    with Image.open(folder / "work" / "loops" / loop["holds"]["file"]) as image:
        mask = np.asarray(image.convert("L")) > 0  # the held pixels, room size, for the loops screen
    assert loop["holds"]["file"] == f"{LOOP}/hold.png" and int(mask.sum()) == loop["holds"]["pixels"]


def test_a_hold_outside_the_region_is_cut_to_it_with_an_info_finding(project: Kiripix) -> None:
    two_redrawn_frames(project)
    decide(project, "hold", {"loop": LOOP, "frame": 1, "points": [[0, 8], [47, 8], [47, 31], [0, 31]]})

    build(project)

    [found] = [f for f in findings(project) if f["code"] == "loop.hold_outside_region"]
    assert found["severity"] == "info" and found["owner_action"]


def test_a_hold_naming_a_frame_the_loop_lacks_holds_the_loop(project: Kiripix) -> None:
    two_redrawn_frames(project)
    decide(project, "hold", {"loop": LOOP, "frame": 5, "points": BAND})

    build(project, expect=2)

    [found] = [f for f in findings(project) if f["code"] == "loop.held"]
    assert "frame 5" in found["message"]


def test_an_edit_frame_shifted_past_the_limit_is_misaligned_on_that_frame_only(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", "width=96", "height=64")
    project.json("set", ROOM, "fit", "scale=4")
    big = np.repeat(np.repeat(textured(), 4, axis=0), 4, axis=1)
    Image.fromarray(big, "RGBA").save(project.cwd / "source.png")
    project.json("pick", ROOM, str(project.json("import", ROOM, "source.png")["data"]["variant"]))
    project.json("run", ROOM, expect=3)
    declare(project, form="frames")
    decide(project, "frames", {"loop": LOOP, "source": "edits"})
    decide(project, "polygon", {"loop": LOOP, "points": [[25, 49], [29, 49], [29, 53], [25, 53]]})
    for number, shift in ((1, 0), (2, 40)):  # 10 target px: over the 4 px limit
        image = np.roll(big, shift, axis=1)
        image[200:216, 100:116] = (255, 255, 255, 255) if number == 1 else (0, 0, 0, 255)
        Image.fromarray(image, "RGBA").save(project.cwd / f"edit{number}.png")
        variant = project.json("import", ROOM, f"edit{number}.png", "--loop", LOOP, "--frame", str(number))["data"]["variant"]
        pick_frame(project, variant, number)

    build(project, expect=2)

    found = [f for f in findings(project) if f["code"] == "loop.misaligned"]
    assert len(found) == 1 and found[0]["severity"] == "error" and found[0]["owner_action"]
    assert found[0]["position"]["field"] == f"loop.{LOOP}.frame.2"


def test_an_edit_frame_on_a_layer_is_cut_to_the_layers_alpha_and_change_past_it_is_reported(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    declare(project, form="frames", layer="lamp")
    decide(project, "polygon", {"loop": LOOP, "points": [[1, 1], [30, 1], [30, 30], [1, 30]]})
    decide(project, "frames", {"loop": LOOP, "source": "edits"})
    image = edited()
    image[20:26, 20:26] = CRATE  # in the region, outside the lamp's Layer
    variant = edit_frame(project, "edit1.png", image, 1)["data"]["variant"]
    pick_frame(project, variant, 1)

    build(project)

    loop = record(folder)
    alpha = rgba(next((folder / "work" / "layers").glob("*lamp*.png")))[..., 3] > 0
    x, y, width, height = loop["box"]
    strip = rgba(folder / "work" / "loops" / loop["layers"][0]["file"])
    assert loop["held"] is None and loop["plate"] is None
    for number in (0, 1):
        tile = strip[:height, number * width:(number + 1) * width] if loop["columns"] > 1 else strip
        assert ((tile[..., 3] > 0) == alpha[y:y + height, x:x + width]).all(), "cut by the Layer's still alpha"
    [found] = [f for f in findings(project) if f["code"] == "loop.past_layer"]
    assert found["severity"] == "warning" and found["owner_action"] and "36" in found["message"]


def test_an_edit_frame_that_changes_nothing_is_still(project: Kiripix) -> None:
    a_frame_loop(project, region=REGION, lamp_layer=False)
    decide(project, "frames", {"loop": LOOP, "source": "edits"})
    variant = edit_frame(project, "edit1.png", target_image(), 1)["data"]["variant"]
    pick_frame(project, variant, 1)

    build(project)

    assert "loop.still" in [f["code"] for f in findings(project)]


def test_describe_names_hold_and_says_frames_are_edits_of_the_source(project: Kiripix) -> None:
    text = json.dumps(project.json("describe", "room", "--stage", "loops"))
    assert '"hold"' in text and "not of each other" in text

