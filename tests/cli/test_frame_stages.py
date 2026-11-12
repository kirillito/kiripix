"""The character's `palette`, `finish` and `sheet` read the frame list from a named Stage (ticket 0176, spec §6.3). The test Kind
`framed` builds them on a Stage called `fit`, as the sprite Recipe does, with no `clips` Stage."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image

ASSET = "framed.a"
FLAT = (128, 128, 255, 255)


def framed(project: Kiripix, frames: dict[str, Any] | None = None) -> Path:
    project.json("new", "framed", "a")
    folder = project.cwd / "assets" / "framed" / "a"
    (folder / "src").mkdir(exist_ok=True)
    (folder / "src" / "frames.json").write_text(json.dumps(frames or {}), encoding="utf-8")
    return folder


def run_to(project: Kiripix, stage: str, expect: int = 0) -> None:
    """Run the Stages up to `stage`, one at a time, as the tests that change a parameter in between need."""
    names = ["fit", "palette", "finish", "sheet"]
    for name in names[:names.index(stage)]:
        project.json("run", ASSET, name)
    project.json("run", ASSET, stage, expect=expect)


def read(path: Path) -> np.ndarray:
    return np.array(Image.open(path))


def test_the_stages_run_on_a_frame_list_from_fit(project: Kiripix) -> None:
    folder = framed(project)

    run_to(project, "sheet")

    sheet = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    assert [c["name"] for c in sheet["clips"]] == ["idle"] and sheet["cell"] == {"width": 12, "height": 12}
    assert project.json("check", ASSET)["findings"] == []


def test_the_finish_stage_declares_normals_and_relief_for_a_recipe_that_has_them(project: Kiripix) -> None:
    [kind] = project.json("describe", "framed", "--stage", "finish")["data"]["kinds"]

    [stage] = kind["stages"]

    by_name = {p["name"]: p for p in stage["params"]}
    assert by_name["normals"]["choices"] == ["pass", "height", "flat"] and by_name["relief"]["default"] == 0.0


def test_flat_normals_are_flat_on_every_opaque_pixel_of_the_colour_frame(project: Kiripix) -> None:
    folder = framed(project)
    project.json("set", ASSET, "finish", "normals=flat")

    run_to(project, "finish")

    for number in range(3):
        colour = read(folder / "work" / "finish" / "color" / "idle" / "s" / f"{number:03d}.png")
        normal = read(folder / "work" / "finish" / "normal" / "idle" / "s" / f"{number:03d}.png")
        assert normal.shape == colour.shape == (12, 12, 4)
        opaque = colour[..., 3] > 0
        assert opaque.sum() > 8 * 8  # the square and its outline
        assert (normal[opaque] == FLAT).all() and (normal[~opaque] == 0).all()
    assert project.json("check", ASSET)["findings"] == []


def test_height_normals_tilt_toward_the_silhouettes_edge_and_the_outline_faces_the_camera(project: Kiripix) -> None:
    folder = framed(project)
    project.json("set", ASSET, "finish", "normals=height")

    run_to(project, "finish")

    colour = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    normal = read(folder / "work" / "finish" / "normal" / "idle" / "s" / "000.png")
    assert normal.shape == colour.shape and (normal[..., 3] == colour[..., 3]).all()
    inside = normal[1:9, 2:10]
    assert (inside[..., 3] == 255).all() and not (inside[..., :3] == FLAT[:3]).all(), "the edge is not flat"
    assert tuple(normal[4, 2]) != FLAT and tuple(normal[0, 5]) == FLAT, "the outline ring faces the camera"
    assert normal[4, 2, 0] < 128 < normal[4, 9, 0], "the left edge faces left, the right edge right"
    assert project.json("check", ASSET)["findings"] == []


def test_relief_adds_the_colour_frames_lightness_to_the_height(project: Kiripix) -> None:
    folder = framed(project)
    project.json("set", ASSET, "finish", "normals=height")
    run_to(project, "finish")
    plain = read(folder / "work" / "finish" / "normal" / "idle" / "s" / "002.png")

    project.json("set", ASSET, "finish", "relief=1")
    run_to(project, "finish")

    relief = read(folder / "work" / "finish" / "normal" / "idle" / "s" / "002.png")
    assert relief.shape == plain.shape and not (relief == plain).all()


def test_pass_is_what_a_finish_does_without_the_parameter(project: Kiripix) -> None:
    folder = framed(project)
    run_to(project, "finish")
    default = read(folder / "work" / "finish" / "normal" / "idle" / "s" / "000.png")

    project.json("set", ASSET, "finish", "normals=pass")
    project.json("run", ASSET, "finish", "--force")

    assert (read(folder / "work" / "finish" / "normal" / "idle" / "s" / "000.png") == default).all()
    assert tuple(default[4, 5]) not in (FLAT, (0, 0, 0, 0)), "the normal pass of fit, quantised"


def test_a_frame_whose_feet_moved_is_pivot_drift_and_one_whose_pivot_alone_differs_is_not(project: Kiripix) -> None:
    framed(project, {"feet": {"idle/s/1": [6.0, 9.0], "idle/s/2": [6.0, 11.0]}, "pivots": {"idle/s/1": [7.0, 10.0]}})
    run_to(project, "sheet", expect=2)

    result = project.json("check", ASSET, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "sheet.pivot_drift"]
    assert finding["position"]["field"] == "idle/s/2" and "frame 2" in finding["message"]


def test_without_feet_the_pivot_is_compared(project: Kiripix) -> None:
    framed(project, {"pivots": {"idle/s/1": [7.0, 10.0]}})
    run_to(project, "sheet", expect=2)

    result = project.json("check", ASSET, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "sheet.pivot_drift"]
    assert finding["position"]["field"] == "idle/s/1"
