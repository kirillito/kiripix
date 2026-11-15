"""The cast sheet (ticket 0226, spec §10): several characters side by side, each at its pivot on one ground line.

One character is built through the fake Blender; the others get a hand-written `sheet` output, a different cell and
pivot, so that the ground line has something to line up."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_character_model import HERO
from test_character_sheet import sheet_of
from test_sprite import SPRITE, WORDS, import_sheet, make_zip, new_sprite, pixellab_zip

ELDER = "character.elder"


def hand_sheet(project: Kiripix, name: str, *, cell: tuple[int, int] = (40, 50), pivot: tuple[int, int] = (20, 44),
               colour: tuple[int, int, int] = (200, 30, 30)) -> Path:
    """A character with a `sheet` output written by hand: one clip, idle, facing s, two frames, each a filled cell."""
    project.json("new", "character", name)
    folder = project.cwd / "assets" / "character" / name / "work" / "sheet"
    folder.mkdir(parents=True)
    width, height = cell
    atlas = np.zeros((height, width * 2, 4), np.uint8)
    atlas[..., :3], atlas[..., 3] = colour, 255
    atlas[:, width:, 0] = 90  # the second frame differs
    Image.fromarray(atlas, "RGBA").save(folder / "color.png")
    rects = [{"index": i, "rect": {"x": i * width, "y": 0, "width": width, "height": height}} for i in range(2)]
    sheet = {"schema_version": 1, "files": {"color": "color.png", "normal": "normal.png"},
             "cell": {"width": width, "height": height}, "pivot": {"x": pivot[0], "y": pivot[1]}, "columns": 2,
             "atlas": {"width": width * 2, "height": height}, "directions": ["s"],
             "clips": [{"name": "idle", "fps": 8, "loop": True, "stationary": True, "directions": {"s": rects}}]}
    (folder / "sheet.json").write_text(json.dumps(sheet), encoding="utf-8")
    return folder


def built_sprite(project: Kiripix) -> None:
    """sprite.npc from a PixelLab-style ZIP, built to its `sheet`."""
    new_sprite(project)
    import_sheet(project, make_zip(project, "npc.zip", pixellab_zip(WORDS)))
    project.json("run", SPRITE)


def png(project: Kiripix, data: dict[str, Any]) -> np.ndarray:
    return np.array(Image.open(project.cwd / data["path"]).convert("RGBA"))


def test_two_characters_stand_on_one_ground_line_at_their_pivots(project: Kiripix) -> None:
    folder, sheet = sheet_of(project)
    hand_sheet(project, "elder")

    result = project.json("cast-sheet", f"{HERO},{ELDER}", "--clips", "idle", "--scale", "3")

    data = result["data"]
    image = png(project, data)
    assert data["path"].startswith(".kiripix/previews/") and data["scale"] == 3
    assert image.shape[:2] == (data["height"], data["width"])
    assert [(c["asset"], c["clip"], c["direction"], c["index"]) for c in data["cells"]] == [
        (HERO, "idle", "s", 0), (ELDER, "idle", "s", 0)]
    ground = data["ground"]
    for cell in data["cells"]:
        assert cell["y"] + cell["pivot"]["y"] == ground  # the feet on one line, in the PNG's pixels
    hero, elder = data["cells"]
    assert hero["pivot"] == {"x": 39 * 3, "y": 72 * 3} and elder["pivot"] == {"x": 20 * 3, "y": 44 * 3}
    assert elder["x"] >= hero["x"] + hero["width"]  # side by side, not over each other
    # The elder's cell holds its first frame, scaled.
    inside = image[elder["y"] + 3: elder["y"] + 6, elder["x"] + 3: elder["x"] + 6]
    assert (inside[..., :3] == (200, 30, 30)).all()
    # The hero's cell holds its idle/s/0 frame from the built atlas, scaled.
    [rect] = [f["rect"] for c in sheet["clips"] if c["name"] == "idle" for f in c["directions"]["s"] if f["index"] == 0]
    atlas = np.array(Image.open(folder / "work" / "sheet" / "color.png").convert("RGBA"))
    frame = atlas[rect["y"]: rect["y"] + rect["height"], rect["x"]: rect["x"] + rect["width"]]
    drawn = image[hero["y"]: hero["y"] + hero["height"]: 3, hero["x"]: hero["x"] + hero["width"]: 3]
    opaque = frame[..., 3] == 255
    assert opaque.any() and (drawn[opaque] == frame[opaque]).all()
    # The built hero's sheet is current; the hand-written one has never been run.
    assert [(f["code"], f["position"]["asset"]) for f in result["findings"]] == [("cast.sheet_stale", ELDER)]
    assert result["findings"][0]["severity"] == "warning"


def test_a_sprite_stands_in_the_row(project: Kiripix) -> None:
    built_sprite(project)
    hand_sheet(project, "elder")

    result = project.json("cast-sheet", f"{ELDER},{SPRITE}", "--clips", "idle")

    data = result["data"]
    assert [c["asset"] for c in data["cells"]] == [ELDER, SPRITE]
    assert all(c["y"] + c["pivot"]["y"] == data["ground"] for c in data["cells"])
    assert [f["position"]["asset"] for f in result["findings"]] == [ELDER]  # the built sprite is current


def test_frames_and_directions_pick_cells_and_a_missing_one_is_a_finding(project: Kiripix) -> None:
    hand_sheet(project, "elder")

    result = project.json("cast-sheet", ELDER, "--clips", "idle,walk", "--directions", "s,n", "--frames", "2")

    cells = [(c["clip"], c["direction"], c["index"]) for c in result["data"]["cells"]]
    assert cells == [("idle", "s", 0), ("idle", "s", 1)]
    missing = sorted(f["message"] for f in result["findings"] if f["code"] == "cast.cell_missing")
    assert len(missing) == 3 and all(ELDER in m for m in missing)  # idle/n, walk/s, walk/n
    assert any("walk" in m for m in missing) and any("idle" in m and "'n'" in m for m in missing)


def test_an_unbuilt_character_is_named_and_left_out(project: Kiripix) -> None:
    hand_sheet(project, "elder")
    project.json("new", "character", "kid")

    result = project.json("cast-sheet", f"character.kid,{ELDER}")

    assert {c["asset"] for c in result["data"]["cells"]} == {ELDER}
    [finding] = [f for f in result["findings"] if f["code"] == "cast.not_built"]
    assert finding["position"]["asset"] == "character.kid" and finding["fix"] == "kiripix run character.kid sheet"


def test_nothing_to_draw_is_an_error(project: Kiripix) -> None:
    project.json("new", "character", "kid")

    result = project.json("cast-sheet", "character.kid", expect=1)

    assert [f["code"] for f in result["findings"]] == ["cast.not_built", "cast.empty"]


def test_an_asset_without_a_sheet_stage_is_refused(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    result = project.json("cast-sheet", "room.alley", expect=1)

    assert [f["code"] for f in result["findings"]] == ["cast.not_a_figure"]


def test_it_records_nothing(project: Kiripix) -> None:
    hand_sheet(project, "elder")
    asset = project.cwd / "assets" / "character" / "elder"
    before = {p: p.stat().st_mtime_ns for p in asset.rglob("*") if p.is_file()}

    project.json("cast-sheet", ELDER)

    assert {p: p.stat().st_mtime_ns for p in asset.rglob("*") if p.is_file()} == before
