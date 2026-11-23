"""The icon Kind (ticket 0262, spec §6.6): an icon fitted to a fixed square, centred in its padding, through `finish`."""

import json
import tomllib
from pathlib import Path

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_fit import read
from test_palette import palette_colours

ICON = "icon.key"
KEY = (0, 255, 0)
SUBJECT = (250, 10, 70)  # near the palette's red, and on no palette


def made_icon(project: Kiripix, size: int, source_side: int, *, scale: int = 2, **brief: str) -> Path:
    """An icon of `size`, its Source `source_side` px square: the key colour with a subject in the middle half."""
    project.json("new", "icon", "key")
    project.json("set", ICON, "brief", f"size={size}", *[f"{k}={v}" for k, v in brief.items()])
    project.json("set", ICON, "fit", f"scale={scale}")
    rgba = np.full((source_side, source_side, 4), 255, dtype=np.uint8)
    rgba[..., :3] = KEY
    quarter = source_side // 4
    rgba[quarter:source_side - quarter, quarter:source_side - quarter, :3] = SUBJECT
    Image.fromarray(rgba, "RGBA").save(project.cwd / "source.png")
    project.json("import", ICON, "source.png")
    [variant] = sorted((project.cwd / "assets" / "icon" / "key" / "src").glob("*.png"))
    project.json("pick", ICON, variant.stem)
    return project.cwd / "assets" / "icon" / "key"


def work(folder: Path, stage: str, name: str) -> Path:
    return folder / "work" / stage / name


def run_to_finish(project: Kiripix) -> None:
    for stage in ("brief", "source", "cutout", "fit", "palette", "finish"):
        project.json("run", ICON, stage)


def test_an_icon_builds_through_finish_at_16_and_32_centred_on_the_palette(project: Kiripix) -> None:
    folder = made_icon(project, 16, 28)

    run_to_finish(project)

    status = stage_status(project, ICON)
    assert [status[s] for s in ("brief", "source", "cutout", "fit", "palette", "finish")] == ["done"] * 6
    assert status["export"] == "needs-input"
    for stage, name in (("fit", "fit.png"), ("palette", "palette.png"), ("finish", "finish.png")):
        image = read(work(folder, stage, name))
        assert image.shape == (16, 16, 4)
        assert set(np.unique(image[..., 3])) == {0, 255}
    finished = read(work(folder, "finish", "finish.png"))
    opaque = finished[..., 3] == 255
    rows, columns = np.nonzero(opaque)
    assert (rows.min(), rows.max(), columns.min(), columns.max()) == (4, 11, 4, 11)  # an 8 px subject, centred
    assert not opaque[:1].any() and not opaque[-1:].any() and not opaque[:, :1].any() and not opaque[:, -1:].any()
    assert {tuple(int(c) for c in p) for p in finished[opaque][:, :3]} <= palette_colours(project)
    grid = json.loads(work(folder, "fit", "grid.json").read_text("utf-8"))
    assert grid["width"] == 14 and grid["inset"] == 1
    assert [f for f in project.json("check", ICON)["findings"] if f["code"] != "palette.mapping_error"] == []


def test_a_32_px_icon_is_centred_with_binary_alpha_and_its_outline_stays_in_the_padding(project: Kiripix) -> None:
    folder = made_icon(project, 32, 60)
    project.json("set", ICON, "finish", "outline=true", "outline_colour=7")

    run_to_finish(project)

    finished = read(work(folder, "finish", "finish.png"))
    assert finished.shape == (32, 32, 4) and set(np.unique(finished[..., 3])) == {0, 255}
    rows, columns = np.nonzero(finished[..., 3] == 255)
    assert rows.min() == columns.min() and rows.max() == columns.max() == 31 - rows.min()  # centred
    assert rows.min() == 7  # a 16 px subject from 8, and its outline one px further out
    assert {tuple(int(c) for c in p) for p in finished[finished[..., 3] == 255][:, :3]} <= palette_colours(project)


def test_the_brief_takes_the_projects_icon_size_unless_it_sets_one(project: Kiripix) -> None:
    project.json("new", "icon", "key")
    folder = project.cwd / "assets" / "icon" / "key"

    project.json("run", ICON, "brief")
    assert json.loads(work(folder, "brief", "brief.json").read_text("utf-8")) == {
        "width": 24, "height": 24, "size": 24, "padding": 1, "notes": ""}
    project.json("set", ICON, "brief", "size=32", "padding=2", "notes=a key")
    project.json("run", ICON, "brief")

    brief = json.loads(work(folder, "brief", "brief.json").read_text("utf-8"))
    assert (brief["size"], brief["padding"], brief["notes"]) == (32, 2, "a key")


def test_a_size_that_is_not_16_24_or_32_has_a_fix(project: Kiripix) -> None:
    project.json("new", "icon", "key")
    project.json("set", ICON, "brief", "size=20")

    result = project.json("run", ICON, "brief", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "brief.size_invalid" and finding["fix"] == f"kiripix set {ICON} brief size=16"


def test_an_icon_the_grid_leaves_larger_than_the_square_is_icon_size(project: Kiripix) -> None:
    made_icon(project, 16, 32, scale=1)  # every Source pixel is a cell: 32 x 32 cells for a 14 x 14 square

    for stage in ("brief", "source", "cutout"):
        project.json("run", ICON, stage)
    result = project.json("run", ICON, "fit", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "icon.size" and "32x32" in finding["message"] and "16x16" in finding["message"]
    assert finding["fix"] == f"kiripix set {ICON} fit mode=downscale"
    project.json("set", ICON, "fit", "mode=downscale")
    project.json("run", ICON, "fit")
    assert read(work(project.cwd / "assets" / "icon" / "key", "fit", "fit.png")).shape == (16, 16, 4)


def test_the_project_file_at_version_7_reads_with_the_default_icon_size(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8").replace("schema_version = 14", "schema_version = 7")
    path.write_text("\n".join(l for l in text.splitlines() if not l.startswith(("[icon]", "size = 24"))) + "\n",
                    encoding="utf-8")
    assert "icon" not in tomllib.loads(path.read_text(encoding="utf-8"))

    project.json("new", "icon", "key")
    project.json("run", ICON, "brief")

    assert stage_status(project, ICON)["brief"] == "done"


def test_new_help_lists_icon_and_describe_shows_the_recipe(project: Kiripix) -> None:
    assert "icon" in project("new", "--help").stdout

    [kind] = project.json("describe", "icon")["data"]["kinds"]

    assert kind["recipe"] == ["brief", "source", "cutout", "fit", "palette", "finish", "export"]
