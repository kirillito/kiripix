"""What the UI had to compute itself (ticket 0296): the tile and a body's Wearables in `show`, `depth.png` on a character's
`sheet`, and the data of `wearable.stack_differs`. On the fake Blender."""

import json
from pathlib import Path

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_export_wearable import build_body
from test_wearable import BODY, WEARABLE, hair
from test_wearable_stack import COAT, FAR, HAIR as STACK_HAIR, build, paint


def test_show_carries_the_tile(project: Kiripix) -> None:
    project.json("new", "character", "zed")

    assert project.json("show", BODY)["data"]["tile"] == 16


def test_a_bodys_show_lists_its_wearables_by_order_then_id(project: Kiripix) -> None:
    hair(project)
    project.json("new", "wearable", "coat", "--body", BODY)
    assert project.json("show", BODY)["data"]["wearables"] == [
        {"asset": "wearable.coat", "order": 10}, {"asset": WEARABLE, "order": 10}]

    project.json("set", "wearable.coat", "sheet", "order=30")
    project.json("set", WEARABLE, "sheet", "order=20")

    assert project.json("show", BODY)["data"]["wearables"] == [
        {"asset": WEARABLE, "order": 20}, {"asset": "wearable.coat", "order": 30}]
    assert project.json("show", WEARABLE)["data"]["wearables"] == []


def test_a_characters_sheet_writes_depth_in_the_layout_of_its_atlases(project: Kiripix) -> None:
    hair(project)
    build_body(project)
    folder = project.cwd / "assets" / "character" / "zed" / "work" / "sheet"

    sheet = json.loads((folder / "sheet.json").read_text("utf-8"))
    depth = np.asarray(Image.open(folder / "depth.png"))

    assert sheet["files"] == {"color": "color.png", "normal": "normal.png", "depth": "depth.png"}
    assert "order" not in sheet
    assert depth.dtype == np.uint16 and depth.shape == (sheet["atlas"]["height"], sheet["atlas"]["width"])
    rect = sheet["clips"][0]["directions"]["s"][0]["rect"]
    cell = depth[rect["y"]:rect["y"] + rect["height"], rect["x"]:rect["x"] + rect["width"]]
    colour = np.asarray(Image.open(folder / "color.png"))[rect["y"]:rect["y"] + rect["height"],
                                                          rect["x"]:rect["x"] + rect["width"]]
    assert (cell[colour[..., 3] > 0] < FAR).all()  # the body's pixels have a depth
    assert (depth[np.asarray(Image.open(folder / "color.png"))[..., 3] == 0] == FAR).all()


def test_stack_differs_lists_the_worst_frames_with_their_boxes(project: Kiripix) -> None:
    build(project)
    paint(project, BODY, 10, 30, 10, 30, (200, 160, 120), 100)
    paint(project, STACK_HAIR, 5, 20, 5, 20, (40, 90, 200), 150, front_rows=15)
    paint(project, COAT, 25, 35, 25, 35, (180, 30, 60), 200)

    found = [f for f in project.json("check", BODY)["findings"] if f["code"] == "wearable.stack_differs"]

    assert [f["data"]["clip"] for f in found] == ["idle", "walk"]
    for finding in found:
        data = finding["data"]
        assert len(data["worst"]) == 3 and data["differing"] > 0 and data["shown"] >= data["differing"]
        first = data["worst"][0]
        assert first["differing"] == 75 and first["box"] == {"x": 10, "y": 15, "width": 20, "height": 15}
        assert set(first) == {"direction", "frame", "differing", "box"}
        position = finding["position"]
        assert position["field"] == f"{data['clip']}/{first['direction']}/{first['frame']}"
