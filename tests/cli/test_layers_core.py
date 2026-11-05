"""What Layers need from core (ticket 0038): the hook a Stage runs after core paints its Overrides and before its Checks,
and `plate-import`. Both on the test Kind `layered` (tests/fixtures/kiripix_test_recipes.py): its `layers` Stage copies
src/input.png to plate.png, takes the `plate` Decision, and has the hook."""

import hashlib
import json
from pathlib import Path

import numpy as np
from conftest import Kiripix, save_image, stage_status
from PIL import Image

ASSET = "layered.a"
GREEN, BLUE = (0, 228, 54, 255), (41, 173, 255, 255)


def make_layered(project: Kiripix) -> Path:
    project.json("new", "layered", "a")
    folder = project.cwd / "assets" / "layered" / "a"
    save_image(folder / "src" / "input.png")
    return folder


def pixels(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"))


def paint_corner(project: Kiripix) -> None:
    """fix.png: transparent but for a green pixel at (0, 0)."""
    painted = np.zeros((4, 4, 4), dtype=np.uint8)
    painted[0, 0] = GREEN
    Image.fromarray(painted, "RGBA").save(project.cwd / "fix.png")


def save_plate(project: Kiripix, name: str = "plate.png", colour: tuple[int, int, int, int] = BLUE) -> bytes:
    save_image(project.cwd / name, (8, 8), colour)
    return (project.cwd / name).read_bytes()


# the hook after Overrides


def test_the_hook_sees_the_image_with_the_overrides_painted_and_the_checks_see_what_it_wrote(project: Kiripix) -> None:
    folder = make_layered(project)
    project.json("run", ASSET, expect=2)
    paint_corner(project)
    project.json("override", ASSET, "layers", "fix.png")

    result = project.json("run", ASSET, "layers", expect=2)

    out = folder / "work" / "layers"
    assert json.loads((out / "hook.json").read_text(encoding="utf-8"))["corner"] == list(GREEN)  # saw the Override
    assert tuple(pixels(out / "plate.png")[3, 3]) == BLUE  # the hook's own write is in the image
    [finding] = [f for f in result["findings"] if f["code"] == "layered.hooked"]
    assert str(list(GREEN)) in finding["message"]  # the Check read the hook's file and the hook's pixel
    assert tuple(pixels(out / "plate.png")[0, 0]) == GREEN


def test_the_hook_does_not_change_what_the_unpainted_hash_means(project: Kiripix) -> None:
    make_layered(project)
    project.json("run", ASSET, expect=2)
    paint_corner(project)
    project.json("override", ASSET, "layers", "fix.png")
    project.json("run", ASSET, "layers", expect=2)

    assert stage_status(project, ASSET)["layers"] == "done"  # the Override is still on the image it was made on
    project.json("run", ASSET, "layers", "--force", expect=2)
    assert stage_status(project, ASSET)["layers"] == "done"


def test_a_stage_without_the_hook_is_untouched(project: Kiripix) -> None:
    from conftest import make_sketch

    folder = make_sketch(project)
    project.json("run", "sketch.a")
    paint_corner(project)
    project.json("override", "sketch.a", "draw", "fix.png")

    project.json("run", "sketch.a")

    assert tuple(pixels(folder / "work" / "draw" / "draw.png")[0, 0]) == GREEN
    assert not (folder / "work" / "draw" / "hook.json").exists()


# plate-import


def test_plate_import_stores_the_image_by_its_hash_and_journals_one_decision(project: Kiripix) -> None:
    folder = make_layered(project)
    data_bytes = save_plate(project)

    data = project.json("plate-import", ASSET, "plate.png")["data"]

    digest = hashlib.sha256(data_bytes).hexdigest()
    assert data["file"] == f"assets/layered/a/decisions/imports/{digest}.png" and data["stage"] == "layers"
    assert (project.cwd / data["file"]).read_bytes() == data_bytes
    entries = (folder / "decisions" / "layers.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(entries) == 1
    assert json.loads(entries[0])["decision"] == "plate" and json.loads(entries[0])["data"] == {"png": digest}
    assert {s["stage"]: s["status"] for s in data["stages"]}["layers"] == "todo"


def test_importing_the_same_plate_twice_stores_one_file(project: Kiripix) -> None:
    folder = make_layered(project)
    save_plate(project, "one.png")
    save_plate(project, "two.png")

    first = project.json("plate-import", ASSET, "one.png")["data"]
    second = project.json("plate-import", ASSET, "two.png")["data"]

    assert first["file"] == second["file"] and first["id"] != second["id"]
    assert len(list((folder / "decisions" / "imports").iterdir())) == 1
    assert len((folder / "decisions" / "layers.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_undo_takes_the_plate_decision_back(project: Kiripix) -> None:
    make_layered(project)
    save_plate(project)
    project.json("plate-import", ASSET, "plate.png")

    project.json("undo", ASSET, "layers")

    assert project.json("redo", ASSET, "layers")["ok"] is True


def test_plate_import_refuses_a_file_that_is_not_a_png_and_writes_nothing(project: Kiripix) -> None:
    folder = make_layered(project)
    (project.cwd / "plate.png").write_text("not an image", encoding="utf-8")

    result = project.json("plate-import", ASSET, "plate.png", expect=1)

    assert [f["code"] for f in result["findings"]] == ["image.not_png"]
    assert not (folder / "decisions" / "imports").exists() and not (folder / "decisions" / "layers.jsonl").exists()


def test_plate_import_on_a_kind_without_the_stage_exits_1_with_a_fix_and_writes_nothing(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    save_plate(project)

    result = project.json("plate-import", "prop.bench", "plate.png", expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "plate_import.no_layers_stage" and finding["fix"] == "kiripix describe prop"
    assert "owner_action" not in finding or finding["owner_action"] is None
    assert not (project.cwd / "assets" / "prop" / "bench" / "decisions" / "imports").exists()


def test_a_kind_whose_layers_stage_takes_no_plate_decision_refuses_too(project: Kiripix) -> None:
    project.json("new", "demo", "a")  # no `layers` Stage at all
    save_plate(project)

    result = project.json("plate-import", "demo.a", "plate.png", expect=1)

    assert [f["code"] for f in result["findings"]] == ["plate_import.no_layers_stage"]
    assert not (project.cwd / "assets" / "demo" / "a" / "decisions" / "imports").exists()


def test_the_room_takes_a_plate_import_too(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    save_plate(project)

    data = project.json("plate-import", "room.alley", "plate.png")["data"]

    assert data["stage"] == "layers"
