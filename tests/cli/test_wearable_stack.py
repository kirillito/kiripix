"""The Check `wearable.stack_differs` (ticket 0294): a body with two Wearables, their built render frames stacked by order and
by depth. On the fake Blender, whose frames are flat, so each test writes the frames it needs over the built ones."""

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image

FIXTURES = Path(__file__).parent.parent / "fixtures" / "characters"
BODY = "character.zed"
HAIR, COAT = "wearable.hair", "wearable.coat"
IDLE = {"name": "idle", "source": "idle", "start": 0, "end": 24, "fps": 12, "loop": True, "stationary": True}
WALK = {"name": "walk", "source": "walk", "start": 0, "end": 30, "fps": 10, "loop": True}
FAR = 65535


def work(project: Kiripix, asset: str) -> Path:
    kind, name = asset.split(".")
    return project.cwd / "assets" / kind / name / "work" / "render"


def build(project: Kiripix, wearables: tuple[str, ...] = (HAIR, COAT)) -> None:
    """character.zed with idle and walk and its render built, and each Wearable's render built."""
    project.json("new", "character", "zed")
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "zed.glb")
    project.json("pick", BODY, project.json("import", BODY, "zed.glb")["data"]["variant"])
    for data in (IDLE, WALK):
        project.json("decide", BODY, "clips", "--decision", json.dumps({"decision": "clip", "data": data}))
    for stage in ("model", "rig", "clips", "render"):
        project.json("run", BODY, stage)
    for wearable in wearables:
        project.json("new", "wearable", wearable.split(".")[1], "--body", BODY)
        shutil.copy(FIXTURES / "rigged.glb", project.cwd / "part.glb")
        project.json("pick", wearable, project.json("import", wearable, "part.glb")["data"]["variant"])
        for stage in ("model", "rig", "render"):
            project.json("run", wearable, stage)


def paint(project: Kiripix, asset: str, x0: int, x1: int, y0: int, y1: int, colour: tuple[int, int, int], depth: int,
          front_rows: int | None = None) -> None:
    """Every frame of the asset's render: one block at depth `depth` (nearer, depth 50, above row `front_rows`), nothing else."""
    folder = work(project, asset)
    document = json.loads((folder / "render.json").read_text("utf-8"))
    width, height = document["frame"]["width"], document["frame"]["height"]
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[y0:y1, x0:x1] = (*colour, 255)
    z = np.full((height, width), FAR, dtype=np.uint16)
    z[y0:y1, x0:x1] = depth
    if front_rows is not None:
        z[y0:front_rows, x0:x1] = 50
    for clip in document["clips"]:
        for frames in clip["directions"].values():
            for frame in frames:
                Image.fromarray(rgba, "RGBA").save(folder / frame["files"]["color"])
                Image.fromarray(z).save(folder / frame["files"]["depth"])


def stack_findings(project: Kiripix) -> list[dict[str, Any]]:
    return [f for f in project.json("check", BODY)["findings"] if f["code"] == "wearable.stack_differs"]


def test_no_finding_until_a_wearable_is_built(project: Kiripix) -> None:
    build(project, wearables=())

    assert stack_findings(project) == []


def test_the_finding_counts_the_pixels_and_boxes_the_worst_frames_per_clip(project: Kiripix) -> None:
    build(project)
    width = json.loads((work(project, BODY) / "render.json").read_text("utf-8"))["frame"]["width"]
    assert width >= 40
    paint(project, BODY, 10, 30, 10, 30, (200, 160, 120), 100)
    # the hair is in front of the body above row 15 and behind it below: stacked by order it covers the body there too
    paint(project, HAIR, 5, 20, 5, 20, (40, 90, 200), 150, front_rows=15)
    # the coat is behind the body where they overlap
    paint(project, COAT, 25, 35, 25, 35, (180, 30, 60), 200)

    found = stack_findings(project)

    assert [f["position"]["field"].split("/")[0] for f in found] == ["idle", "walk"]
    idle, walk = found
    assert all(f["severity"] == "info" and f["fix"] and f["owner_action"] is None for f in found)
    assert f"stacked by order (the body, then {COAT}, {HAIR})" in idle["message"]
    # per frame: hair rows 15 to 20 over the body's columns 10 to 20 (50 px), coat 5 x 5 over the body (25 px)
    frames = {c["name"]: 8 * len(c["directions"]["s"]) for c in
              json.loads((work(project, BODY) / "render.json").read_text("utf-8"))["clips"]}
    for finding, clip in ((idle, "idle"), (walk, "walk")):
        assert f"{clip}: stacked by order" in finding["message"] and f"{75 * frames[clip]} px differ" in finding["message"]
        assert "75 px in x 10 y 15 w 20 h 15" in finding["message"]
        position = finding["position"]
        assert (position["x"], position["y"], position["width"], position["height"]) == (10, 15, 20, 15)
        assert position["asset"] == BODY and position["stage"] == "render"


def test_wearables_that_agree_in_both_stackings_give_no_finding(project: Kiripix) -> None:
    build(project)
    paint(project, BODY, 10, 30, 10, 30, (200, 160, 120), 100)
    paint(project, HAIR, 12, 20, 2, 12, (40, 90, 200), 50)  # in front of the body, and above it
    paint(project, COAT, 12, 20, 20, 28, (180, 30, 60), 40)

    assert stack_findings(project) == []


def test_the_check_reads_the_built_wearables_only(project: Kiripix) -> None:
    build(project, wearables=(HAIR,))
    paint(project, BODY, 10, 30, 10, 30, (200, 160, 120), 100)
    paint(project, HAIR, 5, 20, 5, 20, (40, 90, 200), 150)
    project.json("new", "wearable", "coat", "--body", BODY)  # a second Wearable, not built

    found = stack_findings(project)

    assert len(found) == 2 and f"then {HAIR})" in found[0]["message"] and COAT not in found[0]["message"]


def test_the_order_parameter_of_sheet_sets_the_stacking_order_not_the_id(project: Kiripix) -> None:
    build(project)
    paint(project, BODY, 10, 30, 10, 30, (200, 160, 120), 100)
    paint(project, HAIR, 5, 20, 5, 20, (40, 90, 200), 150)
    paint(project, COAT, 25, 35, 25, 35, (180, 30, 60), 200)
    assert f"(the body, then {COAT}, {HAIR})" in stack_findings(project)[0]["message"]  # equal orders: by ID

    project.json("set", COAT, "sheet", "order=30")
    project.json("set", HAIR, "sheet", "order=20")

    assert f"(the body, then {HAIR}, {COAT})" in stack_findings(project)[0]["message"]
