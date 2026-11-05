"""The room's `layers` Stage on the difference path (ticket 0044, D5): a `plate` Decision names a stored Plate image, a
click names the connected region of the difference under it as a Layer, and no Runner is called."""

import json
from pathlib import Path

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_layers_stage import (
    FLOOR,
    LAMP,
    ROOM,
    SCALE,
    alpha_of,
    built_room,
    calls,
    click,
    out,
    recomposed,
    rgba,
    target_image,
)


def plate_image(noise: bool = False) -> np.ndarray:
    """The Source without the lamp and the crate; with `noise`, a small change of colour far from them (below the
    threshold) and a clear one in the wall."""
    image = target_image()
    image[5:12, 6:11] = FLOOR
    image[21:28, 37:43] = FLOOR
    if noise:
        image[18, 20] = (FLOOR[0] - 3, FLOOR[1], FLOOR[2], 255)  # under the threshold
        image[2, 1] = (10, 200, 10, 255)  # over it, but never clicked
    return image


def save_plate(project: Kiripix, name: str, target: np.ndarray, scale: int = SCALE) -> None:
    Image.fromarray(np.repeat(np.repeat(target, scale, axis=0), scale, axis=1), "RGBA").save(project.cwd / name)


def import_plate(project: Kiripix, noise: bool = False) -> None:
    save_plate(project, "plate.png", plate_image(noise))
    project.json("plate-import", ROOM, "plate.png")


def lift(project: Kiripix) -> dict:
    return project.json("run", ROOM, "layers")


def test_a_full_image_and_a_plate_image_give_the_layers_and_no_runner_is_called(project: Kiripix) -> None:
    folder = built_room(project)
    import_plate(project)
    click(project, "lamp", 8, 8)
    click(project, "crate", 40, 24)

    lift(project)

    assert calls(project) == (0, 0)
    lamp, crate = alpha_of(folder, "lamp"), alpha_of(folder, "crate")
    expected_lamp = np.zeros_like(lamp)
    expected_lamp[5:12, 6:11] = True
    assert (lamp == expected_lamp).all()
    assert crate[21:28, 37:43].all() and crate.sum() == 7 * 6
    fit = rgba(folder / "work" / "fit" / "fit.png")
    assert (recomposed(folder) == fit).all()
    plate = rgba(out(folder) / "plate.png")
    assert (plate[lamp] == (*FLOOR[:3], 255)).all(), "the Plate behind the lamp is the Plate image's"
    assert [e["id"] for e in json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"]] == ["lamp", "crate"]
    assert stage_status(project, ROOM)["layers"] == "done", "no Runner made it, so nothing waits for review"


def test_the_difference_threshold_decides_what_differs(project: Kiripix) -> None:
    folder = built_room(project)
    near = plate_image()
    near[5:12, 6:11] = (250, 220, 41, 255)  # one step from the lamp's colour: under the default threshold
    save_plate(project, "plate.png", near)
    project.json("plate-import", ROOM, "plate.png")
    click(project, "lamp", 8, 8)

    project.json("run", ROOM, "layers", expect=3)
    assert "not on a region" in project.json("next", ROOM)["data"]["reason"]

    project.json("set", ROOM, "layers", "difference=0")
    lift(project)

    assert alpha_of(folder, "lamp")[5:12, 6:11].all()


def test_noise_outside_an_object_leaves_the_plate_equal_to_the_fit_image_and_recompose_passes(project: Kiripix) -> None:
    folder = built_room(project)
    import_plate(project, noise=True)
    click(project, "lamp", 8, 8)

    lift(project)

    fit = rgba(folder / "work" / "fit" / "fit.png")
    plate = rgba(out(folder) / "plate.png")
    lamp = alpha_of(folder, "lamp")
    assert (plate[~lamp] == fit[~lamp]).all()
    assert (recomposed(folder) == fit).all()
    assert not [f for f in project.json("check", ROOM)["findings"] if f["code"].startswith("layers.")]
    result = project.json("run", ROOM, "layers", "--force")
    assert not [f for f in result["findings"] if f["code"] == "layers.recompose_mismatch"]


def test_a_click_off_every_region_of_the_difference_is_needs_input_and_next_names_the_click(project: Kiripix) -> None:
    built_room(project)
    import_plate(project)
    click(project, "floor", 20, 15)

    project.json("run", ROOM, "layers", expect=3)

    advice = project.json("next", ROOM)["data"]
    assert advice["status"] == "needs-input" and "(20, 15)" in advice["reason"]
    assert "Runner" not in advice["reason"] and advice["owner_action"].startswith("Undo it")


def test_grow_widens_a_difference_layer_only_where_the_source_cell_is_partly_in_it(project: Kiripix) -> None:
    """One Source pixel above the lamp differs: its target cell is partly in the difference, so grow takes it in."""
    folder = built_room(project)
    plate = np.repeat(np.repeat(plate_image(), SCALE, axis=0), SCALE, axis=1)
    plate[9, 12] = LAMP  # the Source row above the lamp's first; its target cell is (x=6, y=4)
    Image.fromarray(plate, "RGBA").save(project.cwd / "plate.png")
    project.json("plate-import", ROOM, "plate.png")
    click(project, "lamp", 8, 8)
    project.json("set", ROOM, "layers", "grow=0")
    lift(project)
    zero = alpha_of(folder, "lamp")

    project.json("set", ROOM, "layers", "grow=1")
    lift(project)

    one = alpha_of(folder, "lamp")
    assert not zero[4, 6] and one[4, 6] and one.sum() == zero.sum() + 1
    assert calls(project) == (0, 0)
    assert (recomposed(folder) == rgba(folder / "work" / "fit" / "fit.png")).all()


def test_a_plate_image_of_the_wrong_size_is_needs_input_and_next_says_why(project: Kiripix) -> None:
    built_room(project)
    save_plate(project, "plate.png", plate_image(), scale=1)  # 48 x 32, the Source is 96 x 64
    project.json("plate-import", ROOM, "plate.png")

    advice = project.json("next", ROOM)["data"]

    assert advice["status"] == "needs-input"
    assert "48x32" in advice["reason"] and "96x64" in advice["reason"]
    assert "Runner" not in advice["reason"] and advice["owner_action"].startswith("Undo it")


def test_undoing_the_plate_decision_returns_to_the_state_before_it(project: Kiripix) -> None:
    folder = built_room(project)
    fit_bytes = (folder / "work" / "fit" / "fit.png").read_bytes()
    import_plate(project)
    click(project, "lamp", 8, 8)
    lift(project)
    assert alpha_of(folder, "lamp").any()

    project.json("undo", ROOM, "layers")  # the click
    project.json("undo", ROOM, "layers")  # the plate
    project.json("run", ROOM, "layers")

    assert (out(folder) / "plate.png").read_bytes() == fit_bytes
    assert json.loads((out(folder) / "layers.json").read_text("utf-8"))["layers"] == []
    assert calls(project) == (0, 0)


def test_a_negative_click_drops_the_region_it_is_on(project: Kiripix) -> None:
    folder = built_room(project)
    import_plate(project)
    click(project, "props", 8, 8)
    click(project, "props", 40, 24)
    click(project, "props", 40, 24, positive=False)

    lift(project)

    alpha = alpha_of(folder, "props")
    assert alpha[8, 8] and not alpha[24, 40]
    assert Path(out(folder) / "plate.png").is_file()
