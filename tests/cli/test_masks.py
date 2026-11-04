"""The room's masks Stage (spec §6.1, ADR 0001): flood, brush and import Decisions replayed onto the Plate's size,
one 1-bit PNG per painted Mask, with `click` held back for SAM 2 (ticket 0020)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image

ROOM = "room.alley"
WALL, FLOOR, RUG = (40, 60, 200, 255), (200, 190, 170, 255), (120, 80, 60, 255)
WIDTH, HEIGHT = 48, 32


def plate() -> np.ndarray:
    """48 x 32: a wall on the left 16 columns, a floor, and a rug inside the floor."""
    image = np.full((HEIGHT, WIDTH, 4), FLOOR, dtype=np.uint8)
    image[:, :16] = WALL
    image[8:14, 24:36] = RUG
    return image


def built_room(project: Kiripix) -> Path:
    """A room run through `masks` (no Decisions yet); the Plate is `plate()`. Returns the Asset folder."""
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", f"width={WIDTH}", f"height={HEIGHT}")
    project.json("set", ROOM, "fit", "scale=1")
    Image.fromarray(plate(), "RGBA").save(project.cwd / "source.png")
    data: dict[str, Any] = project.json("import", ROOM, "source.png")["data"]
    project.json("pick", ROOM, str(data["variant"]))
    project.json("run", ROOM, expect=3)  # fit, layers and an empty masks; palette is not built yet
    return project.cwd / "assets" / "room" / "alley"


def read_mask(folder: Path, name: str = "solid") -> np.ndarray:
    with Image.open(folder / "work" / "masks" / f"{name}.png") as image:
        assert image.mode == "1"
        return np.asarray(image, dtype=np.bool_)


def decide(project: Kiripix, decision: str, data: dict[str, Any], expect: int = 0) -> dict[str, Any]:
    return project.json("decide", ROOM, "masks", "--decision", json.dumps({"decision": decision, "data": data}),
                        expect=expect)


def mask_import(project: Kiripix, image: np.ndarray, name: str = "painted.png", expect: int = 0) -> dict[str, Any]:
    """Save a painted image in the Project and import it with `mask-import`."""
    Image.fromarray(image, "RGBA").save(project.cwd / name)
    return project.json("mask-import", ROOM, name, expect=expect)


# no Decisions


def test_with_no_decisions_masks_is_done_with_an_empty_solid_and_next_says_to_paint_it(project: Kiripix) -> None:
    folder = built_room(project)

    result = project.json("run", ROOM, "masks", "--force")

    assert stage_status(project, ROOM)["masks"] == "done"
    solid = read_mask(folder)
    assert solid.shape == (HEIGHT, WIDTH) and not solid.any()
    assert sorted(p.name for p in (folder / "work" / "masks").glob("*.png")) == ["solid.png"]  # derived are not painted
    assert "mask.none_painted" in [f["code"] for f in result["findings"]]
    advice = project.json("next", ROOM)
    assert advice["data"]["stage"] == "place"  # an unpainted solid is advice, never a block
    [finding] = [f for f in advice["findings"] if f["code"] == "mask.none_painted"]
    assert finding["severity"] == "info" and finding["fix"] is None
    assert "solid" in finding["owner_action"] and "Paint" in finding["owner_action"]


def test_a_painted_mask_leaves_next_without_the_advice(project: Kiripix) -> None:
    built_room(project)
    decide(project, "flood", {"x": 0, "y": 0, "mask": "solid"})

    result = project.json("run", ROOM, "masks")

    assert "mask.none_painted" not in [f["code"] for f in result["findings"]]
    advice = project.json("next", ROOM)
    assert advice["data"]["stage"] == "place" and advice["findings"] == []


# flood


def test_a_flood_fills_the_region_under_the_point_and_undo_empties_the_mask_again(project: Kiripix) -> None:
    folder = built_room(project)
    project.json("run", ROOM, "masks")

    decide(project, "flood", {"x": 30, "y": 10, "mask": "solid"})
    assert stage_status(project, ROOM)["masks"] == "stale"
    project.json("run", ROOM, "masks")

    expected = np.zeros((HEIGHT, WIDTH), dtype=np.bool_)
    expected[8:14, 24:36] = True  # the rug, not the floor around it
    assert (read_mask(folder) == expected).all()

    project.json("undo", ROOM, "masks")
    project.json("run", ROOM, "masks")

    assert stage_status(project, ROOM)["masks"] == "done"
    assert not read_mask(folder).any()


def test_a_flood_records_the_plate_it_was_made_on_and_a_changed_plate_needs_review(project: Kiripix) -> None:
    folder = built_room(project)
    entry = decide(project, "flood", {"x": 30, "y": 10, "mask": "solid"})["data"]
    project.json("run", ROOM, "masks")
    assert stage_status(project, ROOM)["masks"] == "done"
    assert entry["current"][0]["image_hash"] is not None

    repainted = plate()
    repainted[0:4, 40:48] = RUG
    Image.fromarray(repainted, "RGBA").save(project.cwd / "source2.png")
    data: dict[str, Any] = project.json("import", ROOM, "source2.png")["data"]
    project.json("pick", ROOM, str(data["variant"]))
    result = project.json("run", ROOM, expect=3)

    assert stage_status(project, ROOM)["masks"] == "needs-review"
    assert "stage.needs_review" in [f["code"] for f in result["findings"]]
    assert (folder / "decisions" / "masks.jsonl").is_file()


def test_a_flood_naming_a_derived_or_unknown_mask_fails_the_stage_with_the_undo(project: Kiripix) -> None:
    built_room(project)
    decide(project, "flood", {"x": 0, "y": 0, "mask": "walkable"})

    result = project.json("run", ROOM, "masks", expect=1)

    assert result["findings"][-1]["code"] == "stage.failed"
    assert "derived" in result["findings"][-1]["message"] and "never painted" in result["findings"][-1]["message"]
    project.json("undo", ROOM, "masks")
    decide(project, "flood", {"x": 0, "y": 0, "mask": "oneway"})
    result = project.json("run", ROOM, "masks", expect=1)
    assert "not a painted Mask" in result["findings"][-1]["message"]


def test_a_flood_outside_the_plate_fails_the_stage(project: Kiripix) -> None:
    built_room(project)
    decide(project, "flood", {"x": 99, "y": 0, "mask": "solid"})

    result = project.json("run", ROOM, "masks", expect=1)

    assert "outside" in result["findings"][-1]["message"]


def test_the_flood_decision_is_validated_by_its_schema(project: Kiripix) -> None:
    built_room(project)

    result = decide(project, "flood", {"x": 1, "mask": "solid"}, expect=1)

    assert result["findings"][0]["code"] == "decision.invalid"


# brush


def test_brush_strokes_and_erases_replay_in_order(project: Kiripix) -> None:
    folder = built_room(project)
    decide(project, "brush", {"mask": "solid", "erase": False, "radius": 1, "points": [[4, 4], [20, 4]]})
    decide(project, "brush", {"mask": "solid", "erase": True, "radius": 0, "points": [[10, 3], [10, 5]]})

    project.json("run", ROOM, "masks")

    solid = read_mask(folder)
    assert solid[4, 4] and solid[3, 20] and solid[5, 12] and not solid[6, 12]
    assert not solid[3, 10] and not solid[4, 10] and not solid[5, 10] and solid[4, 11]
    project.json("undo", ROOM, "masks")  # undo the erase
    project.json("run", ROOM, "masks")
    assert read_mask(folder)[4, 10]


def test_snap_cell_applies_the_cell_grid_to_every_mask(project: Kiripix) -> None:
    folder = built_room(project)
    decide(project, "brush", {"mask": "solid", "erase": False, "radius": 1, "points": [[5, 5]]})
    project.json("set", ROOM, "masks", "snap_cell=8")

    project.json("run", ROOM, "masks")

    expected = np.zeros((HEIGHT, WIDTH), dtype=np.bool_)  # 9 of 64 pixels: under half, so the cell clears
    assert (read_mask(folder) == expected).all()
    decide(project, "brush", {"mask": "solid", "erase": False, "radius": 4, "points": [[4, 4]]})
    project.json("run", ROOM, "masks")
    expected[0:8, 0:8] = True  # a disc of radius 4 is 45 of the cell's 64 pixels: the whole cell is set
    assert (read_mask(folder) == expected).all()


# import


def painted_image() -> np.ndarray:
    image = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    image[4:10, 2:12] = (255, 0, 0, 255)  # solid
    image[20:26, 20:40] = (255, 255, 0, 255)  # the import colour: solid
    image[6, 5] = (240, 15, 10, 255)  # stray, off-colour, inside the red
    image[22, 30] = (250, 245, 50, 255)  # stray, off-colour, inside the yellow
    return image


def test_an_imported_painted_image_snaps_a_stray_pixel_to_the_nearest_defined_colour(project: Kiripix) -> None:
    folder = built_room(project)
    mask_import(project, painted_image())

    project.json("run", ROOM, "masks")

    expected = np.zeros((HEIGHT, WIDTH), dtype=np.bool_)
    expected[4:10, 2:12] = True
    expected[20:26, 20:40] = True
    assert (read_mask(folder) == expected).all()  # both strays are set: snapped, not dropped or left as holes


def test_mask_import_stores_the_image_by_its_hash_and_records_the_import_decision(project: Kiripix) -> None:
    folder = built_room(project)

    data = mask_import(project, painted_image())["data"]

    digest = hashlib.sha256((project.cwd / "painted.png").read_bytes()).hexdigest()
    assert data["file"] == f"assets/room/alley/decisions/imports/{digest}.png"
    assert (project.cwd / data["file"]).read_bytes() == (project.cwd / "painted.png").read_bytes()
    assert data["stage"] == "masks" and {s["stage"]: s["status"] for s in data["stages"]}["masks"] == "stale"
    entries = (folder / "decisions" / "masks.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(entries[-1])["decision"] == "import" and json.loads(entries[-1])["data"] == {"png": digest}


def test_undo_of_a_mask_import_empties_the_masks_again(project: Kiripix) -> None:
    folder = built_room(project)
    mask_import(project, painted_image())
    project.json("run", ROOM, "masks")
    assert read_mask(folder).any()

    project.json("undo", ROOM, "masks")
    project.json("run", ROOM, "masks")

    assert not read_mask(folder).any()


def test_importing_the_same_image_twice_stores_one_png(project: Kiripix) -> None:
    folder = built_room(project)

    first = mask_import(project, painted_image(), "one.png")["data"]
    second = mask_import(project, painted_image(), "two.png")["data"]

    assert first["file"] == second["file"] and first["id"] != second["id"]
    assert len(list((folder / "decisions" / "imports").iterdir())) == 1
    assert len((folder / "decisions" / "masks.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_mask_import_refuses_a_file_that_is_not_a_png(project: Kiripix) -> None:
    folder = built_room(project)
    (project.cwd / "painted.png").write_text("not an image", encoding="utf-8")

    result = project.json("mask-import", ROOM, "painted.png", expect=1)

    assert [f["code"] for f in result["findings"]] == ["image.not_png"]
    assert not (folder / "decisions" / "imports").exists() and not (folder / "decisions" / "masks.jsonl").exists()


def test_mask_import_refuses_an_asset_without_a_masks_stage(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    Image.fromarray(painted_image(), "RGBA").save(project.cwd / "painted.png")

    result = project.json("mask-import", "prop.bench", "painted.png", expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "mask_import.no_masks_stage" and finding["fix"] == "kiripix describe prop"
    assert not (project.cwd / "assets" / "prop" / "bench" / "decisions" / "imports").exists()


def test_an_import_of_the_wrong_size_or_missing_file_fails_the_stage(project: Kiripix) -> None:
    built_room(project)
    mask_import(project, np.zeros((8, 8, 4), dtype=np.uint8))

    result = project.json("run", ROOM, "masks", expect=1)

    assert "8x8" in result["findings"][-1]["message"] and f"{WIDTH}x{HEIGHT}" in result["findings"][-1]["message"]
    project.json("undo", ROOM, "masks")
    decide(project, "import", {"png": "0" * 64})
    result = project.json("run", ROOM, "masks", expect=1)
    assert "missing" in result["findings"][-1]["message"]


def test_an_import_with_partial_alpha_fails_the_stage(project: Kiripix) -> None:
    built_room(project)
    image = painted_image()
    image[0, 0] = (255, 0, 0, 128)
    mask_import(project, image)

    result = project.json("run", ROOM, "masks", expect=1)

    assert "partial alpha" in result["findings"][-1]["message"]


def test_a_brush_after_an_import_edits_the_imported_mask(project: Kiripix) -> None:
    folder = built_room(project)
    mask_import(project, painted_image())
    decide(project, "brush", {"mask": "solid", "erase": True, "radius": 0, "points": [[5, 5], [6, 5]]})

    project.json("run", ROOM, "masks")

    solid = read_mask(folder)
    assert not solid[5, 5] and not solid[5, 6] and solid[4, 5] and solid[6, 5]


# click


def test_a_click_makes_masks_needs_input_until_ticket_0020(project: Kiripix) -> None:
    built_room(project)
    decide(project, "click", {"x": 30, "y": 10, "mask": "solid", "positive": True})

    result = project.json("run", ROOM, "masks", expect=3)

    assert result["data"]["results"][-1]["outcome"] == "needs-input"
    assert "not implemented until 0020" in result["data"]["results"][-1]["message"]
    assert stage_status(project, ROOM)["masks"] == "needs-input"
    advice = project.json("next", ROOM)["data"]
    assert advice["stage"] == "masks" and "not implemented until 0020" in advice["reason"]
    assert f"kiripix undo {ROOM} masks" in advice["owner_action"]
    project.json("undo", ROOM, "masks")
    project.json("run", ROOM, "masks")
    assert stage_status(project, ROOM)["masks"] == "done"


# checks and preview


def test_a_mask_that_is_not_1_bit_is_reported_with_a_fix_that_works(project: Kiripix) -> None:
    folder = built_room(project)
    project.json("run", ROOM, "masks")
    Image.fromarray(np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8) + 255, "RGBA").save(
        folder / "work" / "masks" / "solid.png")

    result = project.json("check", ROOM, expect=2)

    finding = next(f for f in result["findings"] if f["code"] == "mask.not_binary")
    assert finding["position"] == {**finding["position"], "asset": ROOM, "stage": "masks", "file": "solid.png"}
    assert finding["fix"] == f"kiripix run {ROOM} masks --force" and "RGBA" in finding["message"]
    project.json("run", ROOM, "masks", "--force")
    assert "mask.not_binary" not in [f["code"] for f in project.json("check", ROOM)["findings"]]


def test_check_reports_only_the_info_finding_on_an_unpainted_room(project: Kiripix) -> None:
    built_room(project)
    project.json("run", ROOM, "masks")

    result = project.json("check", ROOM)

    assert [(f["code"], f["severity"]) for f in result["findings"] if f["position"]["stage"] == "masks"] == [
        ("mask.none_painted", "info")]


def test_preview_overlay_masks_tints_the_built_masks_over_the_plate(project: Kiripix) -> None:
    built_room(project)
    decide(project, "flood", {"x": 30, "y": 10, "mask": "solid"})
    project.json("run", ROOM, "masks")

    data = project.json("preview", ROOM, "--stage", "layers", "--overlay", "masks", "--zoom", "2")["data"]

    assert data["masks"] == ["solid"] and data["path"].endswith("room.alley.layers.masks.x2.png")
    with Image.open(project.cwd / data["path"]) as image:
        rgba = image.convert("RGBA")
        assert rgba.size == (WIDTH * 2, HEIGHT * 2)
        assert rgba.getpixel((60, 20)) == (188, 40, 30, 255)  # the rug, half way to the red tint
        assert rgba.getpixel((10, 10)) == WALL  # the wall is not in the Mask
