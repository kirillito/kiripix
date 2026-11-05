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


def test_negative_clicks_refine_a_layer(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    click(project, "lamp", 8, 8, positive=False)  # the fake clears a square of half the size around it
    lift(project)

    alpha = alpha_of(folder, "lamp")
    assert not alpha[8, 8] and alpha[5, 6], "the middle was taken away, the rest stays"
    assert (recomposed(folder) == rgba(folder / "work" / "fit" / "fit.png")).all()


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


def test_a_negative_click_with_no_positive_before_it_needs_the_owner(project: Kiripix) -> None:
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
