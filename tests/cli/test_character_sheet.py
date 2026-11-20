"""The character's `sheet` Stage (ticket 0112, spec §6.3). The CLI tests run on the fake Blender's flat, fully opaque frames;
the ones about Checks first change what `finish` wrote (a moved pivot in its render.json, a blanked or oversized frame)."""

import io
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, restore_template
from PIL import Image
from test_character_finish import build_finished, finished
from test_character_model import HERO

CELL = 78


def build_sheet(project: Kiripix, border: int) -> None:
    build_finished(project, border=border)
    project.json("run", HERO, "sheet")


def sheet_of(project: Kiripix, *, border: int = 3) -> tuple[Path, dict[str, Any]]:
    """The hero through `sheet`; built once per worker and copied into the test's Project (ticket 0275)."""
    restore_template(project, f"character-sheet-{border}", lambda template: build_sheet(template, border))
    folder = project.cwd / "assets" / "character" / "hero"
    return folder, load(folder)


def load(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    return document


def edit_render(folder: Path, change: Any) -> None:
    path = folder / "work" / "finish" / "render.json"
    document = json.loads(path.read_text("utf-8"))
    change(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def restored(atlas: np.ndarray, frame: dict[str, Any]) -> np.ndarray:
    """The frame's CELL x CELL cell from its rect in the atlas and its offset in the cell."""
    r, o = frame["rect"], frame["offset"]
    cell = np.zeros((CELL, CELL, 4), dtype=np.uint8)
    cell[o["y"]:o["y"] + r["height"], o["x"]:o["x"] + r["width"]] = atlas[r["y"]:r["y"] + r["height"], r["x"]:r["x"] + r["width"]]
    return cell


def findings(project: Kiripix, code: str, expect: int = 2) -> list[dict[str, Any]]:
    result = project.json("check", HERO, expect=expect)
    return [f for f in result["findings"] if f["code"] == code]


def test_the_stage_declares_its_checks(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "sheet")["data"]["kinds"]

    [stage] = kind["stages"]

    assert [c["code"] for c in stage["checks"]] == [
        "sheet.pivot_drift", "sheet.frame_overflow", "sheet.frame_count", "sheet.empty_frame", "sheet.colour_atlas_rgba"]


def test_run_writes_both_atlases_and_sheet_json_whose_rectangles_line_up(project: Kiripix) -> None:
    folder, sheet = sheet_of(project)

    out = folder / "work" / "sheet"
    assert sheet["schema_version"] == 2 and sheet["files"] == {"color": "color.png", "normal": "normal.png", "depth": "depth.png"}
    assert sheet["cell"] == {"width": CELL, "height": CELL} and sheet["pivot"] == {"x": 39, "y": 72}
    colour, normal = np.array(Image.open(out / "color.png").convert("RGBA")), np.array(Image.open(out / "normal.png"))
    assert colour.shape == normal.shape == (sheet["atlas"]["height"], sheet["atlas"]["width"], 4)
    assert sheet["directions"] and [c["name"] for c in sheet["clips"]] == ["hit", "idle"]
    count = 0
    for clip in sheet["clips"]:
        assert clip["fps"] > 0 and isinstance(clip["loop"], bool) and set(clip["directions"]) == set(sheet["directions"])
        for direction, listed in clip["directions"].items():
            assert [f["index"] for f in listed] == list(range(len(listed)))
            for frame in listed:
                r = frame["rect"]  # cut to the frame's opaque box (ticket 0308): its cell is restored from rect and offset
                assert r["width"] < CELL and r["height"] < CELL
                name = f"{clip['name']}/{direction}/{frame['index']:03d}.png"
                source = np.array(Image.open(folder / "work" / "finish" / "color" / name))
                assert (restored(colour, frame) == source).all()
                assert (restored(normal, frame)[..., 3] == restored(colour, frame)[..., 3]).all()  # one layout: the alpha lines up
                count += 1
    assert count == 8 * 14 and len({(f["rect"]["x"], f["rect"]["y"]) for c in sheet["clips"]
                                    for fs in c["directions"].values() for f in fs}) == count
    assert project.json("check", HERO)["findings"] == []


def test_an_idle_whose_pivot_moves_fails_pivot_drift_and_names_the_frame(project: Kiripix) -> None:
    folder = finished(project, border=3)

    def move(document: dict[str, Any]) -> None:
        document["clips"][1]["directions"]["s"][2]["pivot"] = [40.0, 72.0]

    edit_render(folder, move)
    project.json("run", HERO, "sheet", expect=2)

    [finding] = findings(project, "sheet.pivot_drift")
    assert finding["position"]["field"] == "idle/s/2" and finding["position"]["file"] == "color/idle/s/002.png"
    assert finding["position"]["stage"] == "sheet" and "frame 2" in finding["message"]
    assert finding["fix"] == "kiripix run character.hero render --force"  # the pivots are render's (ticket 0154)


def test_a_stationary_clip_whose_root_sways_has_no_pivot_drift(project: Kiripix) -> None:
    (project.cwd / "blender-sway").write_text("", encoding="utf-8")  # the fake root sways 0.6 px on odd frames
    finished(project, border=3)

    project.json("run", HERO, "sheet")

    assert project.json("check", HERO)["findings"] == []


def test_a_clip_that_reaches_past_the_default_cell_fits_the_grown_one(project: Kiripix) -> None:
    (project.cwd / "blender-reach").write_text(json.dumps({"hit": [-13.0, -52.0, 40.5, 10.2]}), encoding="utf-8")
    folder = finished(project, border=3)

    project.json("run", HERO, "sheet")

    assert load(folder)["cell"] == {"width": 84, "height": 84} and load(folder)["pivot"] == {"x": 42, "y": 72}
    assert project.json("check", HERO)["findings"] == []


def test_a_moving_pivot_in_a_clip_that_is_not_stationary_is_not_drift(project: Kiripix) -> None:
    folder = finished(project, border=3)

    def move(document: dict[str, Any]) -> None:
        document["clips"][0]["directions"]["s"][2]["pivot"] = [40.0, 72.0]  # hit

    edit_render(folder, move)
    project.json("run", HERO, "sheet")

    assert findings(project, "sheet.pivot_drift", expect=0) == []


def test_the_colour_atlas_is_an_indexed_png_that_decodes_to_the_rgba_it_replaces_and_is_smaller(project: Kiripix) -> None:
    folder, sheet = sheet_of(project)

    path = folder / "work" / "sheet" / "color.png"
    with Image.open(path) as indexed:
        assert indexed.mode == "P" and indexed.size == (sheet["atlas"]["width"], sheet["atlas"]["height"])
        rgba = indexed.convert("RGBA")
        assert indexed.info["transparency"] is not None
        palette = indexed.getpalette() or []
    # index 0 is transparent: the empty cells of the grid are index 0, and the palette entry decodes to alpha 0
    pixels = np.array(Image.open(path))
    colour = np.array(rgba)
    assert (pixels == 0).any() and (colour[pixels == 0][..., 3] == 0).all() and len(palette) <= 768
    assert (colour[pixels != 0][..., 3] == 255).all()
    # exactly the frames: every cell equals the finished frame it came from
    for clip in sheet["clips"]:
        for direction, listed in clip["directions"].items():
            for frame in listed:
                source = np.array(Image.open(folder / "work" / "finish" / "color" / f"{clip['name']}/{direction}/{frame['index']:03d}.png"))
                assert (restored(colour, frame) == source).all()
    plain = io.BytesIO()
    rgba.save(plain, format="PNG")
    assert path.stat().st_size < plain.getbuffer().nbytes
    assert project.json("check", HERO)["findings"] == []


def test_more_than_256_colours_keep_an_rgba_atlas_and_an_info_finding_names_the_count(project: Kiripix) -> None:
    folder = finished(project, border=3)
    noise = np.random.default_rng(7).integers(0, 256, (CELL, CELL, 4), dtype=np.uint8)
    noise[..., 3] = 255
    Image.fromarray(noise, "RGBA").save(folder / "work" / "finish" / "color" / "hit" / "s" / "000.png")

    project.json("run", HERO, "sheet")

    out = folder / "work" / "sheet" / "color.png"
    with Image.open(out) as atlas:
        assert atlas.mode == "RGBA"
        assert len(np.unique(np.array(atlas).reshape(-1, 4), axis=0)) > 256
    [finding] = findings(project, "sheet.colour_atlas_rgba")  # the off-palette noise is an error too, so exit 2
    assert finding["severity"] == "info" and finding["fix"] and re.search(r"[0-9]{3,} colours", finding["message"])


def test_an_empty_frame_is_reported_on_its_frame(project: Kiripix) -> None:
    folder = finished(project, border=3)
    Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0)).save(folder / "work" / "finish" / "color" / "hit" / "e" / "001.png")
    project.json("run", HERO, "sheet", expect=2)

    [finding] = findings(project, "sheet.empty_frame")
    assert finding["position"]["field"] == "hit/e/1" and finding["fix"]


def test_a_frame_too_large_for_the_cell_is_reported_with_its_box(project: Kiripix) -> None:
    folder = finished(project, border=3)
    Image.new("RGBA", (CELL + 10, CELL), (9, 9, 9, 255)).save(folder / "work" / "finish" / "color" / "hit" / "n" / "000.png")
    project.json("run", HERO, "sheet", expect=2)

    [finding] = findings(project, "sheet.frame_overflow")
    assert finding["position"]["field"] == "hit/n/0" and finding["position"]["width"] == CELL + 10
    assert finding["fix"] == "kiripix run character.hero render --force"  # render sizes the cell (ticket 0155)


def test_a_missing_frame_gives_a_frame_count_finding(project: Kiripix) -> None:
    folder = finished(project, border=3)
    (folder / "work" / "finish" / "color" / "idle" / "e" / "003.png").unlink()
    project.json("run", HERO, "sheet", expect=2)

    [finding] = findings(project, "sheet.frame_count")
    assert finding["position"]["field"] == "idle/e" and "frames" in finding["message"]


def test_the_sheet_follows_finish(project: Kiripix) -> None:
    sheet_of(project)
    assert project.json("run", HERO, "sheet")["data"]["results"][0]["outcome"] == "skipped"

    project.json("set", HERO, "finish", "outline_colour=2")

    project.json("run", HERO, "finish")
    result = project.json("run", HERO, "sheet")
    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("sheet", "done")]
