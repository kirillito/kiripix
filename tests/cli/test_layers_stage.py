"""The room's `layers` Stage (ticket 0043, spec §6.1, ADR 0004), with the fake Runners: `click` lifts an object (one
segmentation, one fill per hole, both pinned), `grow` widens the alpha and the hole together, `trim` gives a rim back to
the Plate, and Plate and Layers recompose exactly to the fit image from the output files."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image

ROOM = "room.alley"
FLOOR, WALL, LAMP, CRATE = (200, 190, 170, 255), (40, 60, 200, 255), (250, 220, 40, 255), (200, 40, 40, 255)
WIDTH, HEIGHT = 48, 32
SCALE = 2  # the Source is 96 x 64: the fake segmenter's square has odd edges, so its border cells are partial
CHANGED = "Runner input changed"


def target_image() -> np.ndarray:
    """48 x 32: a floor with a wall on the left, a lamp near (8, 8) and a crate near (40, 24)."""
    image = np.full((HEIGHT, WIDTH, 4), FLOOR, dtype=np.uint8)
    image[:, :4] = WALL
    image[5:12, 6:11] = LAMP
    image[21:28, 37:43] = CRATE
    return image


def built_room(project: Kiripix) -> Path:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", f"width={WIDTH}", f"height={HEIGHT}")
    project.json("set", ROOM, "fit", f"scale={SCALE}")
    Image.fromarray(np.repeat(np.repeat(target_image(), SCALE, axis=0), SCALE, axis=1), "RGBA").save(
        project.cwd / "source.png")
    data: dict[str, Any] = project.json("import", ROOM, "source.png")["data"]
    project.json("pick", ROOM, str(data["variant"]))
    project.json("run", ROOM, expect=3)
    return project.cwd / "assets" / "room" / "alley"


def click(project: Kiripix, layer: str, x: int, y: int, positive: bool = True, expect: int = 0) -> dict[str, Any]:
    data = {"layer": layer, "x": x, "y": y, "positive": positive}
    return project.json("decide", ROOM, "layers", "--decision", json.dumps({"decision": "click", "data": data}),
                        expect=expect)


def trim(project: Kiripix, layer: str, points: list[list[int]], radius: int = 0) -> dict[str, Any]:
    data = {"layer": layer, "radius": radius, "points": points}
    return project.json("decide", ROOM, "layers", "--decision", json.dumps({"decision": "trim", "data": data}))


def add(project: Kiripix, layer: str, points: list[list[int]], radius: int = 0) -> dict[str, Any]:
    data = {"layer": layer, "radius": radius, "points": points}
    return project.json("decide", ROOM, "layers", "--decision", json.dumps({"decision": "add", "data": data}))


def lift(project: Kiripix) -> dict[str, Any]:
    """One `run --rerun` of `layers`, which lands in needs-review."""
    return project.json("run", ROOM, "layers", "--rerun", expect=3)


def calls(project: Kiripix) -> tuple[int, int]:
    """The segmentations and the fills the Runners were called for so far."""
    path = project.cwd / "runner-calls.jsonl"
    found = [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []
    fills = sum("crop" in c["params"] for c in found)
    return len(found) - fills, fills


def rgba(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.array(image.convert("RGBA"), dtype=np.uint8)


def out(folder: Path) -> Path:
    return folder / "work" / "layers"


def alpha_of(folder: Path, layer: str) -> np.ndarray:
    return rgba(out(folder) / f"layer.{layer}.png")[..., 3] > 0


def recomposed(folder: Path) -> np.ndarray:
    """The Plate with every Layer file laid over it, from the output files alone."""
    image = rgba(out(folder) / "plate.png")
    for entry in json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"]:
        layer = rgba(out(folder) / entry["file"])
        painted = layer[..., 3] > 0
        image[painted] = layer[painted]
    return image


def accept(project: Kiripix) -> None:
    project.json("accept", ROOM, "layers", owner=True)


# the lift


def test_a_click_then_one_rerun_pins_a_segmentation_and_a_fill_and_lands_in_needs_review(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    assert project.json("next", ROOM)["data"]["reason"] == "Runner not run yet"

    lift(project)

    assert calls(project) == (1, 1)
    assert len(list((folder / "pinned").glob("*.png"))) == 2
    assert stage_status(project, ROOM)["layers"] == "needs-review"

    accept(project)

    assert stage_status(project, ROOM)["layers"] == "done"
    files = sorted(p.name for p in out(folder).glob("*") if p.is_file() and not p.name.startswith("."))
    assert files == ["foreground.png", "layer.lamp.png", "layers.json", "plate.png"]
    listing = json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"]
    assert [entry["id"] for entry in listing] == ["lamp"]


def test_plate_and_layers_recompose_exactly_to_the_fit_image_from_the_output_files(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)

    fit = rgba(folder / "work" / "fit" / "fit.png")
    plate = rgba(out(folder) / "plate.png")
    alpha = alpha_of(folder, "lamp")
    assert alpha.any() and (alpha[5:12, 6:11]).all(), "the segmentation covers the lamp"
    assert (recomposed(folder) == fit).all()
    layer = rgba(out(folder) / "layer.lamp.png")
    assert (layer[alpha] == fit[alpha]).all() and not layer[~alpha].any(), "the fit image cut by alpha"
    assert (plate[~alpha] == fit[~alpha]).all(), "outside the hole the Plate is the fit image"
    assert (plate[alpha][:, 3] == 255).all(), "the hole is filled, and opaque"
    foreground = np.asarray(Image.open(out(folder) / "foreground.png"))
    assert Image.open(out(folder) / "foreground.png").mode == "1" and (foreground == alpha).all()
    assert [f["code"] for f in project.json("check", ROOM)["findings"] if f["code"].startswith("layers.")] == []


def test_a_negative_click_takes_its_object_away_from_the_layer_and_the_plate_hole(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 4, 8)
    click(project, "lamp", 10, 8)
    click(project, "lamp", 7, 8, positive=False)  # the overlap of the two, and what its own square reaches
    lift(project)

    alpha = alpha_of(folder, "lamp")
    assert alpha[8, 0] and alpha[8, 15] and not alpha[8, 7] and not alpha[8, 9]
    assert (np.asarray(Image.open(out(folder) / "foreground.png")) == alpha).all(), "the hole follows the Layer"
    assert (recomposed(folder) == rgba(folder / "work" / "fit" / "fit.png")).all()
    assert calls(project)[0] == 3

    project.json("accept", ROOM, "layers", owner=True)
    click(project, "lamp", 7, 8)  # added back: the same segmentation as the negative click's, pinned already
    lift(project)
    assert alpha_of(folder, "lamp")[8, 7] and calls(project)[0] == 3


def test_a_negative_click_at_the_pixel_of_a_positive_one_reuses_its_pinned_result(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    project.json("accept", ROOM, "layers", owner=True)

    click(project, "lamp", 8, 8, positive=False)
    project.json("run", ROOM, "layers")

    assert calls(project) == (1, 1), "no new Runner call"
    assert not alpha_of(folder, "lamp").any()
    assert not np.asarray(Image.open(out(folder) / "foreground.png")).any(), "the Plate's hole is gone too"


# grow


def test_grow_moves_the_alpha_and_the_hole_together_only_where_partial_and_remakes_only_the_fill(
        project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    project.json("set", ROOM, "layers", "grow=0")
    lift(project)
    zero = alpha_of(folder, "lamp")
    project.json("accept", ROOM, "layers", owner=True)

    project.json("set", ROOM, "layers", "grow=2")

    advice = project.json("next", ROOM)["data"]
    assert advice["reason"] == CHANGED and advice["command"] == f"kiripix run {ROOM} layers --rerun"
    lift(project)

    two = alpha_of(folder, "lamp")
    assert two.sum() > zero.sum() and (two | zero).sum() == two.sum(), "the alpha only grew"
    assert (two & ~zero).sum() <= 2 * 4 * 2 * 8, "and only along the one border of partial cells"
    assert calls(project) == (1, 2), "the segmentation was not made again; the fill was"
    foreground = np.asarray(Image.open(out(folder) / "foreground.png"))
    assert (foreground == two).all(), "the hole is the alpha"
    assert (recomposed(folder) == rgba(folder / "work" / "fit" / "fit.png")).all()


# several objects


def test_a_second_object_in_another_part_makes_one_new_segmentation_and_one_new_fill(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    first = rgba(out(folder) / "plate.png")

    click(project, "crate", 40, 24)
    lift(project)

    assert calls(project) == (2, 2)
    assert stage_status(project, ROOM)["layers"] == "needs-review"
    listing = json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"]
    assert [entry["id"] for entry in listing] == ["lamp", "crate"]
    assert (recomposed(folder) == rgba(folder / "work" / "fit" / "fit.png")).all()
    lamp = alpha_of(folder, "lamp")
    assert (rgba(out(folder) / "plate.png")[lamp] == first[lamp]).all(), "the lamp's fill is its earlier pinned result"
    assert not (alpha_of(folder, "lamp") & alpha_of(folder, "crate")).any()


def test_clicks_on_one_layer_id_are_added_together(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "props", 8, 8)
    click(project, "props", 40, 24)
    lift(project)

    alpha = alpha_of(folder, "props")
    assert alpha[8, 8] and alpha[24, 40]
    assert calls(project) == (2, 2), "one segmentation per positive click, one fill per hole"
    assert [e["id"] for e in json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"]] == ["props"]


# trim


def test_a_trim_gives_pixels_back_to_the_plate_with_no_new_runner_call(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    before = alpha_of(folder, "lamp")
    fit = rgba(folder / "work" / "fit" / "fit.png")
    y, x = (int(v) for v in np.argwhere(before)[0])  # the first pixel of the layer: a corner of the rim
    accept(project)

    trim(project, "lamp", [[x, y]], radius=1)
    project.json("run", ROOM, "layers")

    after = alpha_of(folder, "lamp")
    assert 0 < (before & ~after).sum() <= 9 and (after & ~before).sum() == 0
    assert calls(project) == (1, 1), "a trim makes no Runner call"
    plate = rgba(out(folder) / "plate.png")
    gone = before & ~after
    assert (plate[gone] == fit[gone]).all(), "a trimmed pixel is the fit image's in the Plate"
    assert (recomposed(folder) == fit).all()
    foreground = np.asarray(Image.open(out(folder) / "foreground.png"))
    assert (foreground == after).all()


def test_a_trim_on_a_layer_no_click_lifted_needs_the_owner_to_undo_it(project: Kiripix) -> None:
    built_room(project)
    trim(project, "ghost", [[1, 1]])

    advice = project.json("next", ROOM)["data"]

    assert "ghost" in advice["reason"] and advice["owner_action"].startswith("Undo it")


# add and min_piece (ticket 0087)


def findings_of(project: Kiripix) -> list[str]:
    return [f["code"] for f in project.json("check", ROOM)["findings"] if f["code"].startswith("layers.")]


def test_an_add_puts_its_pixels_in_the_layer_and_takes_them_from_the_plate(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    before = alpha_of(folder, "lamp")
    assert not before[20, 20]

    add(project, "lamp", [[20, 20]], radius=1)
    result = lift(project)

    after = alpha_of(folder, "lamp")
    assert after[19:22, 20].all() and after[20, 19:22].all() and (after & ~before).sum() == 5 and (before & ~after).sum() == 0
    fit = rgba(folder / "work" / "fit" / "fit.png")
    layer = rgba(out(folder) / "layer.lamp.png")
    assert (layer[after] == fit[after]).all() and (layer[after][:, 3] == 255).all()
    assert (np.asarray(Image.open(out(folder) / "foreground.png")) == after).all()
    assert (recomposed(folder) == fit).all()
    assert not [f for f in result["findings"] if f["code"].startswith("layers.")]
    assert findings_of(project) == []
    assert calls(project) == (1, 2), "the new hole is a fill of its own, the segmentation is not made again"


def test_a_trim_after_an_add_takes_the_added_pixels_away_again(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    before = alpha_of(folder, "lamp")

    add(project, "lamp", [[20, 20]], radius=1)
    trim(project, "lamp", [[20, 20]], radius=1)
    lift(project)

    assert (alpha_of(folder, "lamp") == before).all()
    assert (recomposed(folder) == rgba(folder / "work" / "fit" / "fit.png")).all()
    assert findings_of(project) == []


def test_an_add_that_needs_a_fill_stops_for_review_and_a_rebuild_with_it_pinned_makes_no_runner_call(
        project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    add(project, "lamp", [[20, 20]], radius=1)

    advice = project.json("next", ROOM)["data"]
    assert advice["reason"] == "Runner not run yet" and advice["command"] == f"kiripix run {ROOM} layers --rerun"
    lift(project)
    assert stage_status(project, ROOM)["layers"] == "needs-review"
    accept(project)

    project.json("run", ROOM, "layers", "--force")

    assert calls(project) == (1, 2)
    assert alpha_of(folder, "lamp")[20, 20]
    assert stage_status(project, ROOM)["layers"] == "done"


def test_an_add_on_a_layer_no_click_lifted_needs_the_owner_to_undo_it(project: Kiripix) -> None:
    built_room(project)
    add(project, "ghost", [[1, 1]])

    advice = project.json("next", ROOM)["data"]

    assert "ghost" in advice["reason"] and advice["owner_action"].startswith("Undo it")


def test_min_piece_sends_small_pieces_back_to_the_plate_and_leaves_larger_ones(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    add(project, "lamp", [[20, 20]], radius=0)  # a 1 px speck
    add(project, "lamp", [[30, 28], [32, 28]], radius=0)  # two 1 px specks, 2 px apart
    add(project, "lamp", [[40, 10], [41, 10], [40, 11], [41, 11]], radius=0)  # a piece of 4 px
    add(project, "lamp", [[30, 4]], radius=1)  # a piece of 5 px, the brush's plus
    lift(project)
    accept(project)
    made = calls(project)
    full = alpha_of(folder, "lamp")
    assert full[20, 20] and full[28, 30] and full[10:12, 40:42].all() and full[4, 30]

    project.json("set", ROOM, "layers", "min_piece=5")
    project.json("run", ROOM, "layers")

    kept = alpha_of(folder, "lamp")
    assert not kept[20, 20] and not kept[28, 30] and not kept[28, 32]
    assert not kept[10:12, 40:42].any(), "a piece of 4 px goes"
    assert kept[3:6, 30].all() and kept[4, 29:32].all(), "a piece of 5 px stays"
    assert kept[5:12, 6:11].all(), "the lamp stays"
    fit = rgba(folder / "work" / "fit" / "fit.png")
    assert (rgba(out(folder) / "plate.png")[full & ~kept] == fit[full & ~kept]).all(), "back in the Plate, as fit has it"
    assert (recomposed(folder) == fit).all()
    assert (np.asarray(Image.open(out(folder) / "foreground.png")) == kept).all()
    assert findings_of(project) == []
    assert calls(project) == made, "min_piece makes no Runner call"


def test_min_piece_counts_diagonal_neighbours_as_one_piece(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    add(project, "lamp", [[20, 20], [21, 21], [22, 22]], radius=0)  # 3 px joined diagonally
    lift(project)
    accept(project)

    project.json("set", ROOM, "layers", "min_piece=3")
    project.json("run", ROOM, "layers", "--force")
    assert alpha_of(folder, "lamp")[20:23, 20:23].diagonal().all()

    project.json("set", ROOM, "layers", "min_piece=4")
    project.json("run", ROOM, "layers", "--force")
    assert not alpha_of(folder, "lamp")[20:23, 20:23].any()


def test_min_piece_0_and_a_room_that_never_set_it_build_the_same_and_ask_for_no_review(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    built = {p.name: p.read_bytes() for p in out(folder).glob("*") if p.is_file() and not p.name.startswith(".")}

    project.json("set", ROOM, "layers", "min_piece=0")
    project.json("run", ROOM, "layers", "--force")

    assert stage_status(project, ROOM)["layers"] == "done"
    assert {p.name: p.read_bytes() for p in out(folder).glob("*") if p.is_file() and not p.name.startswith(".")} == built
    assert calls(project) == (1, 1)


# Checks


def test_an_override_outside_the_hole_fails_recompose_and_says_to_paint_on_fit(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    painted = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    painted[30, 30] = (255, 0, 77, 255)
    Image.fromarray(painted, "RGBA").save(project.cwd / "fix.png")

    project.json("override", ROOM, "layers", "fix.png")
    result = project.json("run", ROOM, "layers", expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "layers.recompose_mismatch"]
    assert finding["fix"] is None and "fit" in finding["owner_action"]
    assert (finding["position"]["x"], finding["position"]["y"]) == (30, 30)


def test_an_override_inside_the_hole_is_a_fix_to_the_fill_and_still_recomposes(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    painted = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    painted[8, 8] = (255, 0, 77, 255)
    Image.fromarray(painted, "RGBA").save(project.cwd / "fix.png")

    project.json("override", ROOM, "layers", "fix.png")
    result = project.json("run", ROOM, "layers", "--force")

    assert not [f for f in result["findings"] if f["code"].startswith("layers.")]
    assert tuple(rgba(out(folder) / "plate.png")[8, 8]) == (255, 0, 77, 255)
    assert (recomposed(folder) == rgba(folder / "work" / "fit" / "fit.png")).all()


# no Decisions, and M1 rooms


def test_with_no_decisions_the_plate_is_a_byte_copy_of_fit_and_masks_is_not_put_in_review(project: Kiripix) -> None:
    folder = built_room(project)
    project.json("decide", ROOM, "masks", "--decision",
                 json.dumps({"decision": "flood", "data": {"x": 20, "y": 2, "mask": "solid"}}))
    project.json("run", ROOM, "masks")
    assert stage_status(project, ROOM)["masks"] == "done"

    project.json("set", ROOM, "layers", "grow=2")  # what an M1 room sees: `layers`' input changed, so it is stale
    assert stage_status(project, ROOM)["layers"] == "stale"
    project.json("run", ROOM, expect=3)

    assert (out(folder) / "plate.png").read_bytes() == (folder / "work" / "fit" / "fit.png").read_bytes()
    assert json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"] == []
    assert stage_status(project, ROOM)["layers"] == "done"
    assert stage_status(project, ROOM)["masks"] == "done", "the same Plate, so the flood is not replayed on another image"


def test_a_lift_on_a_room_with_floods_puts_masks_in_review_with_no_runner_call_of_its_own(project: Kiripix) -> None:
    built_room(project)
    project.json("decide", ROOM, "masks", "--decision",
                 json.dumps({"decision": "flood", "data": {"x": 20, "y": 2, "mask": "solid"}}))
    project.json("run", ROOM, "masks")
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    made = calls(project)

    project.json("run", ROOM, "masks", expect=3)

    assert stage_status(project, ROOM)["masks"] == "needs-review"
    assert calls(project) == made


# the Runner behind the role


def test_another_inpainter_behind_the_role_is_input_changed_for_the_fill_only(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)

    (project.cwd / "inpainter-b").write_text("", encoding="utf-8")

    advice = project.json("next", ROOM)["data"]
    assert (advice["status"], advice["reason"]) == ("needs-input", CHANGED)
    lift(project)

    assert calls(project) == (1, 2)
    assert len(list((folder / "pinned").glob("*.png"))) == 3, "the old fill stays; the new one has its own key"
    assert stage_status(project, ROOM)["layers"] == "needs-review"


# Decisions


def test_plate_as_a_layer_id_is_refused(project: Kiripix) -> None:
    built_room(project)

    result = click(project, "plate", 8, 8, expect=1)

    assert result["findings"][0]["code"] == "decision.invalid"
    assert click(project, "Bad Id", 8, 8, expect=1)["findings"][0]["code"] == "decision.invalid"


def test_a_negative_click_with_no_positive_click_on_its_layer_needs_the_owner(project: Kiripix) -> None:
    built_room(project)
    click(project, "lamp", 8, 8, positive=False)

    advice = project.json("next", ROOM)["data"]

    assert "negative click" in advice["reason"] and "Undo it" in advice["owner_action"]


def test_a_failed_runner_call_pins_nothing_and_the_next_rerun_lifts(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    (project.cwd / "runner-fails").write_text("", encoding="utf-8")

    project.json("run", ROOM, "layers", "--rerun", expect=1)

    assert not list((folder / "pinned").glob("*.png")), "a failed call pins nothing"
    (project.cwd / "runner-fails").unlink()
    lift(project)
    assert calls(project)[0] >= 1 and stage_status(project, ROOM)["layers"] == "needs-review"
