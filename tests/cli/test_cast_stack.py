"""The cast sheet's stacks and colour swaps (ticket 0337, spec §10.5): a body with Wearables over it, and Parts' ramps swapped.

Every figure is a hand-written `sheet` output (and `palette.json` for its Parts), as in test_cast_sheet: 8 x 8 cells, one frame."""

import json
from pathlib import Path

import numpy as np
from conftest import Kiripix
from PIL import Image

ELDER, KID, HAIR, COAT = "character.elder", "character.kid", "wearable.hair", "wearable.coat"
SKIN = [(100, 50, 40), (200, 120, 100)]
HAIR_RAMP = [(60, 40, 20), (120, 80, 40)]
COAT_COLOUR = (30, 30, 150)
NEW_SKIN = [(1, 2, 3), (4, 5, 6)]


def paint(rows: slice, columns: slice, colour: tuple[int, int, int]) -> np.ndarray:
    frame = np.zeros((8, 8, 4), np.uint8)
    frame[rows, columns] = (*colour, 255)
    return frame


def put(frame: np.ndarray, rows: slice, columns: slice, colour: tuple[int, int, int]) -> np.ndarray:
    frame[rows, columns] = (*colour, 255)
    return frame


def body_frame() -> np.ndarray:
    return put(paint(slice(0, 8), slice(0, 4), SKIN[0]), slice(0, 8), slice(4, 8), SKIN[1])


def hair_frame() -> np.ndarray:
    return paint(slice(0, 3), slice(2, 6), HAIR_RAMP[1])


def coat_frame() -> np.ndarray:
    return paint(slice(2, 8), slice(0, 8), COAT_COLOUR)


def folder(project: Kiripix, asset: str, stage: str) -> Path:
    kind, name = asset.split(".")
    return project.cwd / "assets" / kind / name / "work" / stage


def make(project: Kiripix, asset: str, frame: np.ndarray, depth: int | None, order: int | None, parts: dict[str, list[tuple[int, int, int]]],
         *, body: str | None = None) -> None:
    kind, name = asset.split(".")
    project.json("new", kind, name, *(["--body", body] if body else []))
    out = folder(project, asset, "sheet")
    out.mkdir(parents=True)
    Image.fromarray(frame, "RGBA").save(out / "color.png")
    files = {"color": "color.png", "normal": "normal.png"}
    if depth is not None:
        z = np.full((8, 8), 65535, np.uint16)
        z[frame[..., 3] > 0] = depth
        Image.fromarray(z).save(out / "depth.png")
        files["depth"] = "depth.png"
    rect = {"x": 0, "y": 0, "width": 8, "height": 8}
    sheet: dict[str, object] = {
        "schema_version": 2, "files": files, "cell": {"width": 8, "height": 8}, "pivot": {"x": 4, "y": 7},
        "atlas": {"width": 8, "height": 8}, "directions": ["s"],
        "clips": [{"name": "idle", "fps": 8, "loop": True, "stationary": True,
                   "directions": {"s": [{"index": 0, "rect": rect, "offset": {"x": 0, "y": 0}}]}}]}
    if order is not None:
        sheet["order"] = order
    (out / "sheet.json").write_text(json.dumps(sheet), encoding="utf-8")
    palette = folder(project, asset, "palette")
    palette.mkdir(parents=True)
    record = {"parts": [{"name": part, "rgb": [list(c) for c in ramp]} for part, ramp in parts.items()]}
    (palette / "palette.json").write_text(json.dumps(record), encoding="utf-8")


def cast(project: Kiripix) -> None:
    """character.elder, with wearable.hair (order 30, in front of the body by depth) and wearable.coat (order 20, behind
    the body by depth), and character.kid, which is the elder as built."""
    make(project, ELDER, body_frame(), 100, None, {"skin": SKIN})
    make(project, HAIR, hair_frame(), 50, 30, {"hair": HAIR_RAMP}, body=ELDER)
    make(project, COAT, coat_frame(), 200, 20, {}, body=ELDER)
    make(project, KID, body_frame(), 100, None, {"skin": SKIN})


def figure(project: Kiripix, data: dict[str, object], index: int = 0) -> np.ndarray:
    """The cell `index` of the sheet, at scale 1."""
    image = np.array(Image.open(project.cwd / str(data["path"])).convert("RGBA"))
    cell = data["cells"][index]  # type: ignore[index]
    return image[cell["y"]: cell["y"] + cell["height"], cell["x"]: cell["x"] + cell["width"]]


def codes(result: dict[str, object]) -> list[str]:
    return sorted(f["code"] for f in result["findings"] if f["code"] != "cast.sheet_stale")  # type: ignore[attr-defined, union-attr]


def test_a_stack_draws_the_wearables_over_the_body_by_their_order(project: Kiripix) -> None:
    cast(project)

    result = project.json("cast-sheet", f"{ELDER}+{HAIR}+{COAT}")

    data = result["data"]
    expected = body_frame()
    for layer in (coat_frame(), hair_frame()):  # the coat is order 20, the hair 30: the hair is last
        expected[layer[..., 3] > 0] = layer[layer[..., 3] > 0]
    assert [(c["asset"], c["clip"]) for c in data["cells"]] == [(f"{ELDER}+{HAIR}+{COAT}", "idle")]
    assert (figure(project, data) == expected).all()
    assert codes(result) == []


def test_by_depth_the_nearer_frame_wins(project: Kiripix) -> None:
    cast(project)

    data = project.json("cast-sheet", f"{ELDER}+{HAIR}+{COAT}", "--stack", "depth")["data"]

    drawn = figure(project, data)
    assert (drawn[5, 1, :3] == SKIN[0]).all(), "the coat is behind the body (depth 200 against 100)"
    assert (drawn[1, 3, :3] == HAIR_RAMP[1]).all(), "the hair is in front of it (depth 50)"
    assert (drawn[7, 7, :3] == SKIN[1]).all()


def test_a_wearable_of_another_body_is_refused_naming_both(project: Kiripix) -> None:
    cast(project)

    result = project.json("cast-sheet", f"{KID}+{HAIR}", expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "cast.wearable_body"
    assert HAIR in finding["message"] and ELDER in finding["message"] and KID in finding["message"]


def test_a_stack_starts_with_its_body_and_holds_only_wearables(project: Kiripix) -> None:
    cast(project)

    first = project.json("cast-sheet", f"{HAIR}+{ELDER}", expect=1)
    second = project.json("cast-sheet", f"{ELDER}+{KID}", expect=1)

    assert [f["code"] for f in first["findings"]] == ["cast.stack_body"]
    assert [f["code"] for f in second["findings"]] == ["cast.stack_wearable"]


def test_a_colour_file_swaps_one_part_on_one_figure_and_leaves_the_next_as_built(project: Kiripix) -> None:
    cast(project)
    (project.cwd / "colours.json").write_text(json.dumps([{"skin": [list(c) for c in NEW_SKIN]}]), encoding="utf-8")

    result = project.json("cast-sheet", f"{ELDER}+{HAIR},{KID}", "--colours", "colours.json")

    data = result["data"]
    swapped, built = figure(project, data, 0), figure(project, data, 1)
    expected = body_frame()
    expected[:, :4, :3], expected[:, 4:, :3] = NEW_SKIN[0], NEW_SKIN[1]
    hair = hair_frame()
    expected[hair[..., 3] > 0] = hair[hair[..., 3] > 0]  # the hair is a Part of its own, not swapped
    assert (swapped == expected).all()
    assert (built == body_frame()).all()
    assert [c["swapped"] for c in data["cells"]] == [["skin"], []]
    assert codes(result) == ["cast.colour_off_palette"]  # (1, 2, 3) isn't in the Project palette


def test_a_part_the_figure_lacks_is_a_warning_and_a_ramp_of_another_length_is_an_error(project: Kiripix) -> None:
    cast(project)
    colours = project.cwd / "colours.json"
    colours.write_text(json.dumps([{"cape": [[1, 2, 3]]}]), encoding="utf-8")

    lacking = project.json("cast-sheet", ELDER, "--colours", "colours.json")
    colours.write_text(json.dumps([{"skin": [[1, 2, 3]]}]), encoding="utf-8")
    short = project.json("cast-sheet", ELDER, "--colours", "colours.json", expect=1)

    assert "cast.part_missing" in codes(lacking) and (figure(project, lacking["data"]) == body_frame()).all()
    assert [f["code"] for f in short["findings"]] == ["cast.colours_length"]


def test_a_toml_colour_file_and_a_bad_one(project: Kiripix) -> None:
    cast(project)
    (project.cwd / "colours.toml").write_text("[[figure]]\nskin = [[1, 2, 3], [4, 5, 6]]\n", encoding="utf-8")
    (project.cwd / "bad.json").write_text(json.dumps([{"skin": "red"}]), encoding="utf-8")

    good = project.json("cast-sheet", ELDER, "--colours", "colours.toml")
    bad = project.json("cast-sheet", ELDER, "--colours", "bad.json", expect=1)

    assert figure(project, good["data"])[0, 0, :3].tolist() == list(NEW_SKIN[0])
    assert [f["code"] for f in bad["findings"]] == ["cast.colours_invalid"]


def test_snapshots_draw_stacks_by_order_and_refuse_depth(project: Kiripix) -> None:
    cast(project)
    project.json("snapshot", f"{ELDER},{HAIR}", "--label", "first")

    result = project.json("cast-sheet", f"{ELDER}+{HAIR}", "--snapshots", "first")
    refused = project.json("cast-sheet", f"{ELDER}+{HAIR}", "--snapshots", "first", "--stack", "depth", expect=1)

    [cell] = result["data"]["cells"]
    assert cell["asset"] == f"{ELDER}+{HAIR}" and cell["row"] == "first"
    assert [f["code"] for f in refused["findings"]] == ["cast.snapshot_depth"]
