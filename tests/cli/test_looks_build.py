"""The room's `looks` Stage builds a Look (ticket 0130, ADR 0009): an edit is fitted, registered and mapped with the
palette Stage's parameters, and cut to its region, one piece for the Plate and one per Layer the region meets."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_layers_stage import (
    HEIGHT,
    ROOM,
    SCALE,
    WIDTH,
    accept,
    built_room,
    click,
    lift,
    rgba,
    target_image,
)

LOOK = "lamp_off"
UNLIT = (60, 50, 20, 255)
LAMP_BOX = [[1, 1], [19, 1], [19, 19], [1, 19]]  # a polygon round the lamp and past the Layer the fake segmenter lifts


def room_with_a_lamp_layer(project: Kiripix) -> Path:
    """The `layers` room with the lamp lifted into a Layer and the palette built."""
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    project.json("run", ROOM, "masks")
    project.json("run", ROOM, "palette")
    return folder


def edited(**changes: Any) -> np.ndarray:
    """The room's image with the lamp unlit, and `changes` (a slice key to a colour) on top."""
    image = target_image()
    image[5:12, 6:11] = UNLIT
    for (ys, xs), colour in changes.items():
        image[ys, xs] = colour
    return image


def import_and_pick(project: Kiripix, image: np.ndarray, look: str = LOOK, scale: int = SCALE) -> str:
    Image.fromarray(np.repeat(np.repeat(image, scale, axis=0), scale, axis=1), "RGBA").save(project.cwd / "edit.png")
    variant = str(project.json("import", ROOM, "edit.png", "--look", look)["data"]["variant"])
    project.json("pick", ROOM, variant, "--look", look)
    return variant


def decide(project: Kiripix, decision: str, data: dict[str, Any], expect: int = 0) -> dict[str, Any]:
    return project.json("decide", ROOM, "looks", "--decision", json.dumps({"decision": decision, "data": data}),
                        expect=expect)


def out(folder: Path) -> Path:
    return folder / "work" / "looks"


def look_record(folder: Path, look: str = LOOK) -> dict[str, Any]:
    built = json.loads((out(folder) / "looks.json").read_text("utf-8"))
    return next(entry for entry in built["looks"] if entry["id"] == look)


def findings(project: Kiripix, prefix: str = "look.") -> list[dict[str, Any]]:
    return [f for f in project("check", ROOM, "--json").json["findings"] if f["code"].startswith(prefix)]


def codes(project: Kiripix) -> list[str]:
    return [f["code"] for f in findings(project)]


def run_looks(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    project.json("run", ROOM, "masks")  # what `looks` is built on, in case a Decision or a parameter made it stale
    project.json("run", ROOM, "palette")
    return project.json("run", ROOM, "looks", expect=expect)


# the pieces


def test_a_look_over_a_lifted_layer_gives_a_plate_piece_and_a_layer_piece_that_make_the_mapped_edit(
        project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})

    run_looks(project)

    record = look_record(folder)
    box = record["box"]
    assert box == [1, 1, 19, 19]  # the polygon's own box
    plate = rgba(out(folder) / record["plate"])
    assert record["plate"] == f"{LOOK}/plate.png" and record["layers"] == [
        {"id": "lamp", "file": f"{LOOK}/layer.lamp.png"}]
    piece = rgba(out(folder) / record["layers"][0]["file"])
    assert plate.shape == piece.shape == (19, 19, 4)  # both cropped to the region's box
    palette = rgba(folder / "work" / "palette" / "palette.png")
    layer_alpha = rgba(folder / "work" / "layers" / "layer.lamp.png")[..., 3] > 0
    x, y, width, height = box
    crop = (slice(y, y + height), slice(x, x + width))
    lamp_in_box, plate_in_box = layer_alpha[crop], ~layer_alpha[crop]
    assert ((plate[..., 3] > 0) == plate_in_box).all(), "the Plate piece is the region outside the Layer"
    assert ((piece[..., 3] > 0) == lamp_in_box).all(), "the Layer piece is the region in the Layer's alpha"
    together = np.where(lamp_in_box[..., None], piece, plate)
    assert (together[..., 3] == 255).all()
    lamp = np.zeros((HEIGHT, WIDTH), dtype=bool)
    lamp[5:12, 6:11] = True  # what the edit changed
    lamp = lamp[crop]
    assert (together[~lamp] == palette[crop][~lamp]).all(), "outside the lamp the edit is the room, mapped"
    assert (together[lamp] == together[lamp][0]).all() and (together[lamp] != palette[crop][lamp]).any(),         "the lamp is the edit's colour, mapped to one palette colour"
    assert record["changed"] == int(lamp.sum())
    assert stage_status(project, ROOM)["looks"] == "done" and "look.unchanged" not in codes(project)


def test_every_pixel_of_a_look_is_a_palette_colour(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    run_looks(project)

    for file in (out(folder) / LOOK).glob("*.png"):
        assert rgba(file)[..., 3].max() == 255
    assert "look.off_palette" not in codes(project)  # the Check reads every piece against the palette file


def test_a_brush_region_and_an_erase_replay_in_order(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    decide(project, "brush", {"look": LOOK, "radius": 0, "points": [[6, 5], [10, 5]]})
    decide(project, "brush", {"look": LOOK, "radius": 0, "erase": True, "points": [[8, 5]]})

    run_looks(project)

    record = look_record(folder)
    assert record["box"] == [6, 5, 5, 1]
    piece = rgba(out(folder) / record["layers"][0]["file"])
    assert (piece[0, :, 3] > 0).tolist() == [True, True, False, True, True]
    assert record["plate"] is None, "the region is wholly inside the Layer"


def test_a_difference_picks_out_the_changed_patch_and_the_condition_is_kept(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    decide(project, "look", {"look": LOOK, "condition": "circuit.hall:off"})
    decide(project, "difference", {"look": LOOK, "x0": 0, "y0": 0, "x1": 20, "y1": 20, "specks": 4})

    run_looks(project)

    record = look_record(folder)
    assert record["condition"] == "circuit.hall:off"
    x, y, width, height = record["box"]
    assert (x, y) == (6, 5) or (x >= 5 and y >= 4), record["box"]  # the lamp, 3x3 mean spreading it by a pixel at most
    assert 5 <= width <= 7 and 7 <= height <= 9
    assert record["layers"] and record["changed"] > 0


def test_a_look_with_a_pick_and_no_region_builds_nothing_and_says_so(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    import_and_pick(project, edited())

    run_looks(project)

    record = look_record(folder)
    assert record["box"] is None and record["plate"] is None and record["layers"] == []
    assert not (out(folder) / LOOK / "plate.png").exists()
    [finding] = [f for f in findings(project) if f["code"] == "look.no_region"]
    assert finding["severity"] == "warning" and finding["owner_action"]
    assert "look.drift" in codes(project), "with no region the whole redraw is outside it"


def test_a_region_where_the_edit_changed_nothing_is_look_unchanged(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    import_and_pick(project, target_image())  # the edit is the room itself
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})

    run_looks(project)

    [finding] = findings(project)
    assert finding["code"] == "look.unchanged" and finding["severity"] == "warning"
    assert finding["position"]["width"] == 19 and finding["owner_action"]


# drift


def test_redraw_outside_the_region_is_look_drift_with_its_box(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    import_and_pick(project, edited_with_crate())
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})

    run_looks(project)

    [finding] = findings(project)
    assert finding["code"] == "look.drift" and finding["severity"] == "warning" and finding["owner_action"]
    position = finding["position"]
    assert position["x"] <= 37 and position["y"] <= 21 and position["x"] + position["width"] >= 43
    assert "in 1 places" in finding["message"]


def edited_with_crate() -> np.ndarray:
    image = edited()
    image[21:28, 37:43] = (40, 200, 40, 255)  # the crate redrawn in another colour, outside the lamp's region
    return image


def test_noise_outside_the_region_is_not_drift(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    image = edited().astype(np.int16)
    image[..., :3] += np.random.default_rng(3).integers(-1, 2, size=image[..., :3].shape)  # about 1 level, as a model's
    import_and_pick(project, np.clip(image, 0, 255).astype(np.uint8))
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})

    run_looks(project)

    assert "look.drift" not in codes(project)


# registration


def textured(scale: int = 4) -> np.ndarray:
    """A room of random blocks, 96 x 64 target px of `scale` Source px each, with a plain 8 x 8 patch to redraw."""
    rng = np.random.default_rng(7)
    blocks = np.empty((64, 96, 4), dtype=np.uint8)
    blocks[..., :3] = rng.integers(40, 220, size=(64, 96, 3))
    blocks[..., 3] = 255
    return blocks


def test_an_edit_shifted_beyond_the_limits_fails_with_look_misaligned(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", "width=96", "height=64")
    project.json("set", ROOM, "fit", "scale=4")
    room = textured()
    scale = 4
    big = np.repeat(np.repeat(room, scale, axis=0), scale, axis=1)
    Image.fromarray(big, "RGBA").save(project.cwd / "source.png")
    project.json("pick", ROOM, str(project.json("import", ROOM, "source.png")["data"]["variant"]))
    project.json("run", ROOM, expect=3)
    shifted = np.roll(big, 40, axis=1)  # 10 target px: over the 4 px limit
    Image.fromarray(shifted, "RGBA").save(project.cwd / "edit.png")
    variant = str(project.json("import", ROOM, "edit.png", "--look", LOOK)["data"]["variant"])
    project.json("pick", ROOM, variant, "--look", LOOK)
    decide(project, "polygon", {"look": LOOK, "points": [[5, 5], [8, 5], [8, 8], [5, 8]]})

    result = run_looks(project, expect=2)

    misaligned = [f for f in result["findings"] if f["code"] == "look.misaligned"]
    assert len(misaligned) == 1 and misaligned[0]["severity"] == "error" and misaligned[0]["owner_action"]
    assert "shifted" in misaligned[0]["message"]


def test_an_edit_shifted_within_the_limits_is_registered_and_cut_cleanly(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", "width=96", "height=64")
    project.json("set", ROOM, "fit", "scale=4")
    big = np.repeat(np.repeat(textured(), 4, axis=0), 4, axis=1)
    Image.fromarray(big, "RGBA").save(project.cwd / "source.png")
    project.json("pick", ROOM, str(project.json("import", ROOM, "source.png")["data"]["variant"]))
    project.json("run", ROOM, expect=3)
    shifted = np.roll(big, 8, axis=1)  # 2 target px
    shifted[200:216, 100:116] = (255, 255, 255, 255)  # the redrawn patch
    Image.fromarray(shifted, "RGBA").save(project.cwd / "edit.png")
    variant = str(project.json("import", ROOM, "edit.png", "--look", LOOK)["data"]["variant"])
    project.json("pick", ROOM, variant, "--look", LOOK)
    decide(project, "polygon", {"look": LOOK, "points": [[25, 49], [29, 49], [29, 53], [25, 53]]})

    run_looks(project, expect=0)

    folder = project.cwd / "assets" / "room" / "alley"
    registration = look_record(folder)["registration"]
    assert registration["applied"] and not registration["problems"]
    assert abs(registration["shift"][0] - 8) < 0.5 and abs(registration["scale"][0] - 1) < 0.002
    assert "look.misaligned" not in codes(project)


# replay


def test_a_palette_change_rebuilds_the_looks_to_done_and_a_refit_sends_a_difference_to_needs_review(
        project: Kiripix) -> None:
    built_room(project)  # no Layer: a refit then needs no Runner
    import_and_pick(project, edited())
    decide(project, "difference", {"look": LOOK, "x0": 0, "y0": 0, "x1": 20, "y1": 20})
    run_looks(project)
    assert stage_status(project, ROOM)["looks"] == "done"

    project.json("set", ROOM, "palette", "dither=bayer2", "strength=1")
    assert stage_status(project, ROOM)["looks"] == "stale"
    run_looks(project)
    assert stage_status(project, ROOM)["looks"] == "done", "a palette change rebuilds, and a difference stays done"

    project.json("set", ROOM, "fit", "offset_x=2")
    for stage in ("fit", "layers", "masks", "palette"):
        project.json("run", ROOM, stage)
    project.json("run", ROOM, "looks", expect=3)
    assert stage_status(project, ROOM)["looks"] == "needs-review"


def test_no_looks_is_done_at_once_and_a_decision_without_a_pick_waits(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    run_looks(project)
    assert stage_status(project, ROOM)["looks"] == "done"
    assert json.loads((out(folder) / "looks.json").read_text("utf-8"))["looks"] == []

    decide(project, "polygon", {"look": "door", "points": LAMP_BOX})

    row = next(a for a in project.json("status")["data"]["assets"] if a["asset"] == ROOM)
    looks = next(s for s in row["stages"] if s["stage"] == "looks")
    assert looks["status"] == "needs-input" and "door" in looks["reason"]


def test_a_difference_box_off_the_plate_waits_for_the_owner(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    decide(project, "difference", {"look": LOOK, "x0": 0, "y0": 0, "x1": WIDTH, "y1": 5})

    row = next(a for a in project.json("status")["data"]["assets"] if a["asset"] == ROOM)
    looks = next(s for s in row["stages"] if s["stage"] == "looks")

    assert looks["status"] == "needs-input" and "outside" in looks["reason"]


# solid


def test_a_look_has_its_own_solid_only_when_it_has_a_solid_decision(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    project.json("decide", ROOM, "masks", "--decision",
                 json.dumps({"decision": "polygon", "data": {"mask": "solid", "erase": False,
                                                              "points": [[0, 0], [3, 0], [3, 3], [0, 3]]}}))
    import_and_pick(project, edited())
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    run_looks(project)
    assert not (out(folder) / LOOK / "solid.png").exists()

    decide(project, "solid", {"look": LOOK, "points": [[20, 20], [24, 20], [24, 24], [20, 24]]})
    decide(project, "solid", {"look": LOOK, "erase": True, "radius": 0, "points": [[0, 0]]})
    run_looks(project)

    with Image.open(out(folder) / LOOK / "solid.png") as image:
        assert image.mode == "1" and image.size == (WIDTH, HEIGHT)
        solid = np.asarray(image, dtype=bool)
    assert solid[20:25, 20:25].all(), "the polygon adds"
    assert solid[1:4, 1:4].all() and not solid[0, 0] and solid[0, 1], "the room's own solid stays, but the erased pixel is clear"
    assert look_record(folder)["solid"] == f"{LOOK}/solid.png"


def test_solid_snaps_to_the_masks_cell(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    project.json("set", ROOM, "masks", "snap_cell=8")
    import_and_pick(project, edited())
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    decide(project, "solid", {"look": LOOK, "points": [[16, 16], [23, 16], [23, 23], [16, 23]]})
    project.json("run", ROOM, "masks")

    run_looks(project)

    with Image.open(out(folder) / LOOK / "solid.png") as image:
        solid = np.asarray(image, dtype=bool)
    assert solid[16:24, 16:24].all() and solid.sum() == 64


def test_the_looks_files_are_the_same_on_a_second_run(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    run_looks(project)
    first = {p.name: p.read_bytes() for p in (out(folder) / LOOK).glob("*.png")}

    project.json("run", ROOM, "looks", "--force")

    assert {p.name: p.read_bytes() for p in (out(folder) / LOOK).glob("*.png")} == first
