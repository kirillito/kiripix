"""Trimmed cells in the sheet (ticket 0308): each frame is cut to the opaque box it has over every layer, packed into the atlas, and
`sheet.json` and `character.json` give its packed `rect` and its `offset` in its clip's logical cell, so the cell can be restored
exactly. On the fake Blender, whose frames are opaque blocks with a transparent border (`border=` of `finished`)."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_character_finish import finished
from test_character_model import HERO
from test_character_sheet import findings, load, sheet_of
from test_export_wearable import WEARABLE, built_wearable, assets

BORDER = 20


def untrimmed_area(sheet: dict[str, Any]) -> int:
    """What the atlas held before: every frame's whole logical cell."""
    return sum(c["cell"]["width"] * c["cell"]["height"] for c in sheet["clips"] for fs in c["directions"].values() for _ in fs)


def restore(atlas: np.ndarray, clip: dict[str, Any], frame: dict[str, Any]) -> np.ndarray:
    """The frame's logical cell, from its `rect` in the atlas and its `offset` in the cell."""
    r, o = frame["rect"], frame["offset"]
    cell = np.zeros((clip["cell"]["height"], clip["cell"]["width"], 4), dtype=np.uint8)
    cell[o["y"]:o["y"] + r["height"], o["x"]:o["x"] + r["width"]] = atlas[r["y"]:r["y"] + r["height"], r["x"]:r["x"] + r["width"]]
    return cell


def far_depth(folder: Path, name: str, drawn: np.ndarray) -> None:
    """Redraws a frame's render depth: near (100) where `drawn`, far (65535) elsewhere, as a render's background is."""
    Image.fromarray(np.where(drawn, 100, 65535).astype(np.uint16)).save(folder / "work" / "render" / "depth" / name)


def frames_of(sheet: dict[str, Any]) -> list[tuple[dict[str, Any], str, dict[str, Any]]]:
    return [(c, d, f) for c in sheet["clips"] for d, fs in c["directions"].items() for f in fs]


def test_the_atlas_shrinks_and_every_frame_is_restored_byte_identical_from_rect_and_offset(project: Kiripix) -> None:
    folder, sheet = sheet_of(project, border=BORDER)

    out = folder / "work" / "sheet"
    colour = np.array(Image.open(out / "color.png").convert("RGBA"))
    normal = np.array(Image.open(out / "normal.png"))
    assert sheet["schema_version"] == 2
    assert colour.shape == normal.shape == (sheet["atlas"]["height"], sheet["atlas"]["width"], 4)
    assert colour.shape[0] * colour.shape[1] < untrimmed_area(sheet) // 2  # the cell is mostly empty at this border
    boxes: list[tuple[int, int, int, int]] = []
    for clip, direction, frame in frames_of(sheet):
        r, o = frame["rect"], frame["offset"]
        assert r["width"] < clip["cell"]["width"] and r["height"] < clip["cell"]["height"]
        assert o["x"] >= BORDER - 2 and o["y"] >= BORDER - 2 and o["x"] + r["width"] <= clip["cell"]["width"]
        assert r["x"] + r["width"] <= colour.shape[1] and r["y"] + r["height"] <= colour.shape[0]
        name = f"{clip['name']}/{direction}/{frame['index']:03d}.png"
        assert (restore(colour, clip, frame) == np.array(Image.open(folder / "work" / "finish" / "color" / name))).all()
        assert (restore(normal, clip, frame) == np.array(Image.open(folder / "work" / "finish" / "normal" / name))).all()
        boxes.append((r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"]))
    taken = np.zeros(colour.shape[:2], dtype=bool)
    for x0, y0, x1, y1 in boxes:
        assert not taken[y0:y1, x0:x1].any()  # no two frames overlap
        taken[y0:y1, x0:x1] = True
    assert project.json("check", HERO)["findings"] == []  # the Checks read the logical cell


def test_an_empty_frame_keeps_a_one_pixel_region_and_still_restores_to_an_empty_cell(project: Kiripix) -> None:
    folder = finished(project, border=BORDER)
    Image.new("RGBA", (78, 78), (0, 0, 0, 0)).save(folder / "work" / "finish" / "color" / "hit" / "e" / "001.png")
    Image.new("RGBA", (78, 78), (0, 0, 0, 0)).save(folder / "work" / "finish" / "normal" / "hit" / "e" / "001.png")
    far_depth(folder, "hit/e/001.png", np.zeros((78, 78), dtype=bool))  # the render drew nothing either

    project.json("run", HERO, "sheet", expect=2)

    sheet = load(folder)
    clip = next(c for c in sheet["clips"] if c["name"] == "hit")
    frame = clip["directions"]["e"][1]
    assert (frame["rect"]["width"], frame["rect"]["height"]) == (1, 1) and frame["offset"] == {"x": 0, "y": 0}
    colour = np.array(Image.open(folder / "work" / "sheet" / "color.png").convert("RGBA"))
    assert not restore(colour, clip, frame).any()
    assert [f["position"]["field"] for f in findings(project, "sheet.empty_frame")] == ["hit/e/1"]  # judged on the cell


def test_a_frame_with_one_opaque_corner_pixel_is_cut_to_that_pixel_and_restored(project: Kiripix) -> None:
    folder = finished(project, border=BORDER)
    only = np.zeros((78, 78, 4), dtype=np.uint8)
    only[30, 41] = (9, 9, 9, 255)
    for layer in ("color", "normal"):
        Image.fromarray(only, "RGBA").save(folder / "work" / "finish" / layer / "idle" / "s" / "002.png")
    far_depth(folder, "idle/s/002.png", only[..., 3] > 0)

    project.json("run", HERO, "sheet")

    sheet = load(folder)
    clip = next(c for c in sheet["clips"] if c["name"] == "idle")
    frame = clip["directions"]["s"][2]
    assert frame["offset"] == {"x": 41, "y": 30} and (frame["rect"]["width"], frame["rect"]["height"]) == (1, 1)
    normal = np.array(Image.open(folder / "work" / "sheet" / "normal.png"))
    assert (restore(normal, clip, frame) == only).all()


def test_depth_drawn_outside_the_colour_is_inside_the_box_and_restored_byte_identical(project: Kiripix) -> None:
    folder = finished(project, border=BORDER)
    render = json.loads((folder / "work" / "render" / "render.json").read_text("utf-8"))
    entry = next(c for c in render["clips"] if c["name"] == "idle")
    listed = entry["directions"]["s"][2]
    path = folder / "work" / "render" / listed["files"]["depth"]
    depth = np.array(Image.open(path), dtype=np.uint16)
    depth[1, 2] = 1234  # the render drew geometry here, which `finish` cut from the colour (an alpha-cut edge)
    Image.fromarray(depth).save(path)

    project.json("run", HERO, "sheet")

    sheet = load(folder)
    clip = next(c for c in sheet["clips"] if c["name"] == "idle")
    frame = clip["directions"]["s"][2]
    r, o = frame["rect"], frame["offset"]
    atlas = np.array(Image.open(folder / "work" / "sheet" / "depth.png"), dtype=np.uint16)
    restored = np.full((clip["cell"]["height"], clip["cell"]["width"]), 65535, dtype=np.uint16)
    restored[o["y"]:o["y"] + r["height"], o["x"]:o["x"] + r["width"]] = atlas[r["y"]:r["y"] + r["height"], r["x"]:r["x"] + r["width"]]
    pivot = (int(np.floor(listed["pivot"][0] + 0.5)), int(np.floor(listed["pivot"][1] + 0.5)))
    left, top = clip["pivot"]["x"] - pivot[0], clip["pivot"]["y"] - pivot[1]  # the render's frame placed in the cell
    expected = np.full_like(restored, 65535)
    expected[top:top + depth.shape[0], left:left + depth.shape[1]] = depth
    assert (restored == expected).all()


def test_a_wearables_sheet_is_trimmed_too_and_keeps_the_bodys_cells_frame_by_frame(project: Kiripix) -> None:
    folder = built_wearable(project)

    mine = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    theirs = json.loads((assets(project, "character", "zed") / "work" / "sheet" / "sheet.json").read_text("utf-8"))

    assert mine["schema_version"] == theirs["schema_version"] == 2
    for key in ("cell", "pivot", "directions"):
        assert mine[key] == theirs[key]

    def layout(sheet: dict[str, Any]) -> list[Any]:
        return [(c["name"], c["cell"], c["pivot"], {d: [f["index"] for f in fs] for d, fs in c["directions"].items()})
                for c in sheet["clips"]]

    assert layout(mine) == layout(theirs)  # a body and its Wearable line up frame by frame, in the logical cell
    out = folder / "work" / "sheet"
    sizes = {Image.open(out / name).size for name in ("color.png", "normal.png", "depth.png")}
    assert sizes == {(mine["atlas"]["width"], mine["atlas"]["height"])}
    colour = np.array(Image.open(out / "color.png").convert("RGBA"))
    depth = np.array(Image.open(out / "depth.png"))
    for clip, _, frame in frames_of(mine):
        r = frame["rect"]
        assert r["width"] <= clip["cell"]["width"] and r["height"] <= clip["cell"]["height"]
        assert frame["offset"]["x"] + r["width"] <= clip["cell"]["width"]
    assert depth.shape == colour.shape[:2]


def test_character_json_carries_each_frames_offset_and_an_older_one_migrates(project: Kiripix) -> None:
    from test_cell_per_clip import exported

    folder, sheet, character = exported(project, None)

    assert character["schema_version"] == 7 and character["atlas"] == sheet["atlas"]
    for clip in character["clips"]:
        for listed in clip["directions"].values():
            assert all(set(f["offset"]) == {"x", "y"} for f in listed)
    assert {c["name"]: c["directions"] for c in character["clips"]} == {c["name"]: c["directions"] for c in sheet["clips"]}
    path: Path = folder / "out" / "export" / "character.json"
    old = {**character, "schema_version": 6,
           "clips": [{**c, "directions": {d: [{k: v for k, v in f.items() if k != "offset"} for f in fs]
                                          for d, fs in c["directions"].items()}} for c in character["clips"]]}
    path.write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")

    assert project.json("export", HERO)["ok"] is True  # the version 6 file migrates: offset 0, the rect is the cell
