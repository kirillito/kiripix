"""The character's `sheet` Stage (ticket 0112, spec §6.3). The CLI tests run on the fake Blender's flat, fully opaque frames;
the ones about Checks first change what `finish` wrote (a moved pivot in its render.json, a blanked or oversized frame)."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_character_finish import finished
from test_character_model import HERO

CELL = 78


def sheet_of(project: Kiripix, *, border: int = 3) -> tuple[Path, dict[str, Any]]:
    folder = finished(project, border=border)
    project.json("run", HERO, "sheet")
    return folder, load(folder)


def load(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    return document


def edit_render(folder: Path, change: Any) -> None:
    path = folder / "work" / "finish" / "render.json"
    document = json.loads(path.read_text("utf-8"))
    change(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def findings(project: Kiripix, code: str, expect: int = 2) -> list[dict[str, Any]]:
    result = project.json("check", HERO, expect=expect)
    return [f for f in result["findings"] if f["code"] == code]


def test_the_stage_declares_its_checks(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "sheet")["data"]["kinds"]

    [stage] = kind["stages"]

    assert [c["code"] for c in stage["checks"]] == [
        "sheet.pivot_drift", "sheet.frame_overflow", "sheet.frame_count", "sheet.empty_frame"]


def test_run_writes_both_atlases_and_sheet_json_whose_rectangles_line_up(project: Kiripix) -> None:
    folder, sheet = sheet_of(project)

    out = folder / "work" / "sheet"
    assert sheet["schema_version"] == 1 and sheet["files"] == {"color": "color.png", "normal": "normal.png"}
    assert sheet["cell"] == {"width": CELL, "height": CELL} and sheet["pivot"] == {"x": 39, "y": 72}
    colour, normal = np.array(Image.open(out / "color.png")), np.array(Image.open(out / "normal.png"))
    assert colour.shape == normal.shape == (sheet["atlas"]["height"], sheet["atlas"]["width"], 4)
    assert sheet["directions"] and [c["name"] for c in sheet["clips"]] == ["hit", "idle"]
    count = 0
    for clip in sheet["clips"]:
        assert clip["fps"] > 0 and isinstance(clip["loop"], bool) and set(clip["directions"]) == set(sheet["directions"])
        for direction, listed in clip["directions"].items():
            assert [f["index"] for f in listed] == list(range(len(listed)))
            for frame in listed:
                r = frame["rect"]
                assert (r["width"], r["height"]) == (CELL, CELL) and r["x"] % CELL == 0 and r["y"] % CELL == 0
                cell = (slice(r["y"], r["y"] + r["height"]), slice(r["x"], r["x"] + r["width"]))
                name = f"{clip['name']}/{direction}/{frame['index']:03d}.png"
                source = np.array(Image.open(folder / "work" / "finish" / "color" / name))
                assert (colour[cell] == source).all()
                assert (normal[cell][..., 3] == colour[cell][..., 3]).all()  # one layout: the alpha lines up
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
    assert finding["position"]["stage"] == "sheet" and finding["fix"] and "frame 2" in finding["message"]


def test_a_moving_pivot_in_a_clip_that_is_not_stationary_is_not_drift(project: Kiripix) -> None:
    folder = finished(project, border=3)

    def move(document: dict[str, Any]) -> None:
        document["clips"][0]["directions"]["s"][2]["pivot"] = [40.0, 72.0]  # hit

    edit_render(folder, move)
    project.json("run", HERO, "sheet")

    assert findings(project, "sheet.pivot_drift", expect=0) == []


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
