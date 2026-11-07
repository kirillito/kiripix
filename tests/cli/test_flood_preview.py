"""The `flood-preview` Probe, and `pixels`, the bounding box and `--summary` on the Mask Probes (spec §10.1, ticket 0074)."""

import json
from typing import Any

from conftest import Kiripix, stage_status
from test_masks import HEIGHT, ROOM, WIDTH, built_room, decide, painted_room

PROBE = ["probe", "flood-preview", ROOM]


def answers(project: Kiripix, *args: str, **more: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = project.json(*PROBE, *args, **more)["data"]["result"]["floods"]
    return result


def test_flood_preview_gives_the_pixels_a_recorded_flood_does(project: Kiripix) -> None:
    folder = painted_room(project)

    [seen] = answers(project, "30,10,0.04")
    decide(project, "flood", {"x": 30, "y": 10, "mask": "solid", "tolerance": 0.04})
    project.json("run", ROOM, "masks")

    [recorded] = json.loads((folder / "work" / "masks" / "floods.json").read_text("utf-8"))
    assert seen["pixels"] == recorded["pixels"] == 6 * 12
    assert (seen["x"], seen["y"], seen["tolerance"]) == (30, 10, 0.04)
    assert (seen["width"], seen["height"]) == (WIDTH, HEIGHT)


def test_three_tolerances_give_three_answers_and_nothing_is_recorded(project: Kiripix) -> None:
    folder = painted_room(project)
    project.json("run", ROOM, "masks")
    status = stage_status(project, ROOM)
    journal = {p: p.read_bytes() for p in folder.rglob("*.jsonl")}

    found = answers(project, "30,10,0", "30,10,0.04", "30,10,0.2")

    assert [f["tolerance"] for f in found] == [0, 0.04, 0.2]
    assert found[0]["pixels"] < found[1]["pixels"] == 72
    assert found[2]["pixels"] >= found[1]["pixels"]
    assert stage_status(project, ROOM) == status
    assert {p: p.read_bytes() for p in folder.rglob("*.jsonl")} == journal


def test_summary_leaves_out_runs_and_the_box_matches_the_runs(project: Kiripix) -> None:
    painted_room(project)

    [full] = answers(project, "30,10,0.04")
    [short] = answers(project, "30,10,0.04", "--summary")

    assert "runs" in full and "runs" not in short
    assert short["pixels"] == full["pixels"] and short["box"] == full["box"]
    assert full["box"] == {"x": 24, "y": 8, "width": 12, "height": 6}
    assert sum(length for _, _, length in full["runs"]) == full["pixels"]


def test_summary_on_segment_preview_gives_pixels_and_box_without_runs(project: Kiripix) -> None:
    built_room(project)

    full = project.json("probe", "segment-preview", ROOM, "30,10")["data"]["result"]
    short = project.json("probe", "segment-preview", ROOM, "30,10", "--summary")["data"]["result"]

    assert "runs" in full and "runs" not in short
    assert full["pixels"] == short["pixels"] == 13 * 13
    assert full["box"] == short["box"] == {"x": 24, "y": 4, "width": 13, "height": 13}


def test_a_plate_that_is_not_built_is_refused_naming_the_run(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    [finding] = project.json(*PROBE, "1,1,0", expect=1)["findings"]

    assert finding["code"] == "probe.not_ready"
    assert finding["fix"] == f"kiripix run {ROOM} layers"


def test_bad_arguments_and_other_kinds_are_refused(project: Kiripix) -> None:
    built_room(project)

    for bad in ("30,10", "a,b,0.1", "30,10,x"):
        assert project.json(*PROBE, bad, expect=1)["findings"][0]["code"] == "input.invalid"
    assert project.json(*PROBE, "99,99,0", expect=1)["findings"][0]["code"] == "input.invalid"
    too_wide = project.json(*PROBE, "30,10,0.5", expect=1)["findings"][0]  # the flood Decision refuses above 0.2
    assert too_wide["code"] == "input.invalid" and too_wide["fix"].endswith("30,10,0.2")
    assert project.json(*PROBE, expect=1)["findings"][0]["code"] == "input.invalid"
