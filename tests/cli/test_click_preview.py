"""The `click-preview` Probe (ticket 0085, spec §10.1): the answer a lift of the same clicks would give, one Runner call per
click, with one load and one embedding for all of them in the CLI. With the fake Runners, which log to the Project's folder."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, make_demo, stage_status
from test_layers_stage import ROOM, alpha_of, built_room, calls
from test_locks import start_holding
from test_masks import read_mask

CLICKS = ["4,8", "10,8", "7,8,neg"]


def preview(project: Kiripix, *args: str, expect: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = project.json("probe", "click-preview", ROOM, *args, expect=expect)["data"]["result"]
    return result


def as_mask(answer: dict[str, Any]) -> np.ndarray:
    mask = np.zeros((answer["height"], answer["width"]), dtype=np.bool_)
    for y, x, length in answer["runs"]:
        mask[y, x:x + length] = True
    return mask


def lines(project: Kiripix, name: str) -> int:
    path: Path = project.cwd / name
    return len(path.read_text("utf-8").splitlines()) if path.exists() else 0


def decide_all(project: Kiripix, stage: str, clicks: list[str]) -> None:
    for text in clicks:
        x, y, *sign = text.split(",")
        data: dict[str, Any] = {"x": int(x), "y": int(y), "positive": not sign}
        data["layer" if stage == "layers" else "mask"] = "lamp" if stage == "layers" else "solid"
        project.json("decide", ROOM, stage, "--decision", json.dumps({"decision": "click", "data": data}))


def test_the_union_equals_the_layer_a_lift_makes_with_grow_0(project: Kiripix) -> None:
    folder = built_room(project)
    project.json("set", ROOM, "layers", "grow=0")
    decide_all(project, "layers", CLICKS)
    project.json("run", ROOM, "layers", "--rerun", expect=3)

    union = as_mask(preview(project, *CLICKS)["union"])

    assert (union == alpha_of(folder, "lamp")).all() and union.any()


def test_the_union_equals_the_mask_a_masks_lift_makes(project: Kiripix) -> None:
    folder = built_room(project)
    decide_all(project, "masks", CLICKS)
    project.json("run", ROOM, "masks", "--rerun", expect=3)

    union = as_mask(preview(project, *CLICKS)["union"])

    assert (union == read_mask(folder)).all() and union.any()


def test_a_negative_click_takes_its_segment_away_at_its_place_in_the_order(project: Kiripix) -> None:
    built_room(project)

    after = as_mask(preview(project, "4,8", "10,8", "7,8,neg")["union"])
    before = as_mask(preview(project, "4,8", "7,8,neg", "10,8")["union"])

    assert not after[8, 7] and before[8, 7], "a positive click after the negative one puts it back"


def test_each_click_equals_segment_preview_with_that_click_alone(project: Kiripix) -> None:
    built_room(project)

    answer = preview(project, *CLICKS)

    assert len(answer["clicks"]) == 3
    for text, entry in zip(["4,8", "10,8", "7,8"], answer["clicks"]):
        alone = project.json("probe", "segment-preview", ROOM, text)["data"]["result"]
        assert as_mask(entry).tolist() == as_mask(alone).tolist()
        assert (entry["pixels"], entry["box"]) == (alone["pixels"], alone["box"])
    assert [(c["x"], c["y"], c["positive"]) for c in answer["clicks"]] == [(4, 8, True), (10, 8, True), (7, 8, False)]


def test_twenty_clicks_load_the_runner_once_and_embed_once(project: Kiripix) -> None:
    built_room(project)

    answer = preview(project, *[f"{x},8" for x in range(4, 24)])

    assert len(answer["clicks"]) == 20 and answer["embedding"] == "computed"
    assert lines(project, "runner-embeds.jsonl") == 1 and lines(project, "runner-decodes.jsonl") == 20
    assert lines(project, "runner-calls.jsonl") == 0


def test_summary_leaves_out_runs_and_the_union_has_pieces(project: Kiripix) -> None:
    built_room(project)

    answer = preview(project, "4,8", "40,24", "--summary")

    assert "runs" not in answer["union"] and all("runs" not in c for c in answer["clicks"])
    assert answer["union"]["pieces"]["count"] == 2 and answer["union"]["pixels"] > 0
    assert answer["union"]["box"]["width"] > 0


def test_nothing_is_recorded_or_pinned(project: Kiripix) -> None:
    folder = built_room(project)
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file() and "work" not in path.parts}
    status = stage_status(project, ROOM)

    preview(project, *CLICKS)

    assert stage_status(project, ROOM) == status and calls(project) == (0, 0)
    assert not (folder / "pinned").exists()
    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file() and "work" not in path.parts} == before


def test_a_room_not_built_yet_is_refused(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    [finding] = project.json("probe", "click-preview", ROOM, "1,1", expect=1)["findings"]

    assert finding["code"] == "probe.not_ready"


def test_a_busy_gpu_exits_4_and_offers_the_cpu(project: Kiripix) -> None:
    built_room(project)
    make_demo(project)
    process, holder = start_holding(project)
    try:
        [finding] = project.json("probe", "click-preview", ROOM, "4,8", expect=4)["findings"]

        assert finding["code"] == "lock.busy" and finding["fix"].endswith("--cpu")
        assert preview(project, "4,8", "--cpu")["device"] == "cpu"
    finally:
        (holder / "hold").unlink()
    process.communicate(timeout=60)


def test_bad_points_are_refused(project: Kiripix) -> None:
    built_room(project)
    for args in ([], ["nope"], ["1,2,sideways"], ["99,0"], ["4,8", "0,99"]):
        [finding] = project.json("probe", "click-preview", ROOM, *args, expect=1)["findings"]
        assert finding["code"] == "input.invalid"
    assert lines(project, "runner-embeds.jsonl") == 0
