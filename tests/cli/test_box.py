"""Segment with a box (ticket 0079, spec §6.1): `segment-preview` takes `x0,y0,x1,y1`, and a `box` Decision on `masks` and
`layers` is one Runner call with a pinned result, the same call as the probe's. A click keeps its call and its key. With the
fake Runner, whose Mask for a box is the box itself."""

import json
import threading
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_inpainter import CHANGED
from test_layers_stage import ROOM as LAYERS_ROOM
from test_layers_stage import accept as accept_layers
from test_layers_stage import alpha_of, calls, lift, target_image
from test_layers_stage import built_room as built_layers_room
from test_locks import wait_for
from test_masks import ROOM, built_room, decide, read_mask
from test_runner_calls import accept, box, rerun
from test_runner_calls import calls as pinned_calls
from test_runner_calls import click as masks_click
from test_runner_calls import repick
from test_serve import Server, server  # noqa: F401 - the `server` fixture

BOX = {"x0": 24, "y0": 4, "x1": 36, "y1": 16}  # both ends included: 13 x 13


def probe(project: Kiripix, *args: str, expect: int = 0) -> dict[str, Any]:
    return project.json("probe", "segment-preview", ROOM, *args, expect=expect)


def as_mask(answer: dict[str, Any]) -> np.ndarray:
    mask = np.zeros((answer["height"], answer["width"]), dtype=np.bool_)
    for y, x, length in answer["runs"]:
        mask[y, x:x + length] = True
    return mask


def box_decision(project: Kiripix, mask: str, positive: bool = True, expect: int = 0, **corners: int) -> None:
    decide(project, "box", {**(corners or BOX), "mask": mask, "positive": positive}, expect=expect)


def runner_lines(project: Kiripix, name: str) -> list[dict[str, Any]]:
    path: Path = project.cwd / name
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


# the probe


def test_segment_preview_takes_a_box_in_target_pixels(project: Kiripix) -> None:
    built_room(project)

    result = probe(project, "24,4,36,16")["data"]["result"]

    assert (as_mask(result) == box(4, 16, 24, 36)).all()
    assert result["pixels"] == 169 and result["box"] == {"x": 24, "y": 4, "width": 13, "height": 13}


def test_a_one_pixel_box_is_allowed(project: Kiripix) -> None:
    built_room(project)

    result = probe(project, "5,6,5,6", "--summary")["data"]["result"]

    assert result["pixels"] == 1 and result["box"] == {"x": 5, "y": 6, "width": 1, "height": 1}


def test_a_bad_box_is_refused_and_no_runner_is_loaded(project: Kiripix) -> None:
    built_room(project)

    for args in (["24,4,36"], ["24,4,36,16,5"], ["36,4,24,16"], ["24,16,36,4"], ["0,0,99,5"], ["0,0,5,99"], ["a,4,36,16"],
                 ["24,4,36,16", "10,10"], ["24,4,36,16,neg"]):
        [finding] = probe(project, *args, expect=1)["findings"]
        assert finding["code"] == "input.invalid", args
    assert runner_lines(project, "runner-embeds.jsonl") == []


def test_a_box_probe_is_nothing_recorded_or_pinned(project: Kiripix) -> None:
    folder = built_room(project)
    status = stage_status(project, ROOM)

    probe(project, "24,4,36,16")

    assert stage_status(project, ROOM) == status and not (folder / "pinned").exists()


def test_the_probe_and_the_decision_make_the_same_runner_call(project: Kiripix) -> None:
    built_room(project)
    probe(project, "24,4,36,16")
    box_decision(project, "solid")
    rerun(project)

    previewed, lifted = pinned_calls(project)  # the Runner's own log: the probe's call, then the Decision's
    assert previewed["params"] == lifted["params"]
    assert lifted["params"] == {"box": [24, 4, 37, 17], "max_size": 1536}, "the box's outer edges, in Source pixels"


# masks


def test_a_box_decision_makes_the_mask_the_probe_shows_in_one_pinned_call(project: Kiripix) -> None:
    folder = built_room(project)
    box_decision(project, "solid")

    assert project.json("next", ROOM)["data"]["reason"] == "Runner not run yet"
    rerun(project)

    assert len(pinned_calls(project)) == 1 and len(list((folder / "pinned").glob("*.png"))) == 1
    shown = as_mask(probe(project, "24,4,36,16")["data"]["result"])
    assert stage_status(project, ROOM)["masks"] == "needs-review"
    assert (read_mask(folder) == shown).all() and (shown == box(4, 16, 24, 36)).all()


def test_a_rebuild_of_a_box_makes_no_runner_call_and_a_changed_source_needs_a_rerun(project: Kiripix) -> None:
    folder = built_room(project)
    box_decision(project, "solid")
    rerun(project)
    accept(project)

    project.json("run", ROOM, expect=3)
    assert len(pinned_calls(project)) == 1 and stage_status(project, ROOM)["masks"] == "done"
    assert (read_mask(folder) == box(4, 16, 24, 36)).all()

    repick(project)
    result = project.json("run", ROOM, expect=3)

    assert stage_status(project, ROOM)["masks"] == "needs-input"
    assert result["data"]["results"][-1]["message"] == CHANGED
    assert len(pinned_calls(project)) == 1, "`run` never re-runs a stale pinned call"
    rerun(project)
    assert stage_status(project, ROOM)["masks"] == "needs-review" and len(pinned_calls(project)) == 2


def test_a_negative_box_takes_its_segment_away_and_a_later_positive_box_adds_it_back(project: Kiripix) -> None:
    folder = built_room(project)
    box_decision(project, "solid")
    box_decision(project, "solid", positive=False, x0=28, y0=6, x1=32, y1=10)
    rerun(project)

    expected = box(4, 16, 24, 36)
    expected[6:11, 28:33] = False
    assert (read_mask(folder) == expected).all()
    assert len(pinned_calls(project)) == 2
    accept(project)

    box_decision(project, "solid", x0=28, y0=6, x1=32, y1=10)
    project.json("run", ROOM, "masks")  # the same call as the negative box's: pinned already
    assert (read_mask(folder) == box(4, 16, 24, 36)).all() and len(pinned_calls(project)) == 2


def test_a_box_and_a_click_replay_in_order_and_a_click_keeps_its_call(project: Kiripix) -> None:
    folder = built_room(project)
    masks_click(project, 10, 20)
    box_decision(project, "solid")
    rerun(project)

    first, second = pinned_calls(project)
    assert set(first["params"]) == {"points", "max_size"}, "a click's call carries no box"
    assert set(second["params"]) == {"box", "max_size"}
    assert read_mask(folder)[4:17, 24:37].all() and read_mask(folder)[20, 10]


def test_a_box_that_is_outside_the_plate_or_reversed_needs_the_owner(project: Kiripix) -> None:
    built_room(project)
    for corners in ({"x0": 40, "y0": 4, "x1": 60, "y1": 16}, {"x0": 24, "y0": 4, "x1": 30, "y1": 40},
                    {"x0": 36, "y0": 4, "x1": 24, "y1": 16}):
        box_decision(project, "solid", **corners)
        result = project.json("run", ROOM, expect=3)
        [finding] = [f for f in result["findings"] if f["code"] == "stage.needs_input"]
        assert finding["owner_action"] and "undo" in finding["owner_action"].lower(), corners
        project.json("undo", ROOM, "masks")
    assert pinned_calls(project) == []


def test_a_box_names_a_painted_mask(project: Kiripix) -> None:
    built_room(project)
    box_decision(project, "walkable")  # derived, never painted

    result = project.json("run", ROOM, "masks", "--rerun", expect=1)

    assert "derived" in json.dumps(result["findings"])


def test_cancel_during_a_box_call_is_run_cancelled_and_pins_nothing(project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = built_room(project)
    box_decision(project, "solid")
    hold = project.cwd / "hold-embed"  # `serve` keeps the segmenter warm: its embed is where the fake waits
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": ROOM, "stage": "masks", "rerun": True}
    caller = threading.Thread(target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "b"})))
    try:
        caller.start()
        wait_for(project.cwd / "embed-holding")
        server.call("/api/jobs/b/cancel")
        caller.join(timeout=30)
    finally:
        hold.unlink(missing_ok=True)

    [reply] = replies
    assert reply.codes == ["run.cancelled"] and not list(folder.glob("pinned/*"))


# layers


def layer_box(project: Kiripix, layer: str, positive: bool = True, expect: int = 0, **corners: int) -> dict[str, Any]:
    data = {**corners, "layer": layer, "positive": positive}
    return project.json("decide", LAYERS_ROOM, "layers", "--decision", json.dumps({"decision": "box", "data": data}),
                        expect=expect)


LAMP = {"x0": 6, "y0": 5, "x1": 10, "y1": 11}  # the lamp's pixels in the layers fixture, both ends included


def test_a_box_lifts_a_layer_the_probe_shows_with_one_segmentation_and_one_fill(project: Kiripix) -> None:
    folder = built_layers_room(project)
    project.json("set", LAYERS_ROOM, "layers", "grow=0")
    layer_box(project, "lamp", **LAMP)

    assert project.json("next", LAYERS_ROOM)["data"]["reason"] == "Runner not run yet"
    lift(project)

    assert calls(project) == (1, 1)
    shown = as_mask(project.json("probe", "segment-preview", LAYERS_ROOM, "6,5,10,11")["data"]["result"])
    assert (alpha_of(folder, "lamp") == shown).all() and shown.sum() == 35
    assert stage_status(project, LAYERS_ROOM)["layers"] == "needs-review"


def test_a_layer_box_rebuild_calls_no_runner_and_a_changed_source_needs_a_rerun(project: Kiripix) -> None:
    built_layers_room(project)
    layer_box(project, "lamp", **LAMP)
    lift(project)
    accept_layers(project)

    project.json("run", LAYERS_ROOM, "layers")
    assert calls(project) == (1, 1) and stage_status(project, LAYERS_ROOM)["layers"] == "done"

    changed = np.repeat(np.repeat(target_image(), 2, axis=0), 2, axis=1)
    changed[0:4, 40:48] = (120, 80, 60, 255)
    Image.fromarray(changed, "RGBA").save(project.cwd / "source2.png")
    project.json("pick", LAYERS_ROOM, str(project.json("import", LAYERS_ROOM, "source2.png")["data"]["variant"]))
    result = json.loads(project("run", LAYERS_ROOM, "--json").stdout)  # whole room: `fit` is stale too

    assert stage_status(project, LAYERS_ROOM)["layers"] == "needs-input"
    layers = next(r for r in result["data"]["results"] if r["stage"] == "layers")
    assert layers["message"] == CHANGED and calls(project) == (1, 1)


def test_a_negative_layer_box_takes_its_segment_away_and_a_click_keeps_its_call(project: Kiripix) -> None:
    folder = built_layers_room(project)
    project.json("set", LAYERS_ROOM, "layers", "grow=0")
    layer_box(project, "lamp", **LAMP)
    layer_box(project, "lamp", positive=False, x0=6, y0=5, x1=10, y1=7)
    project.json("decide", LAYERS_ROOM, "layers", "--decision", json.dumps(
        {"decision": "click", "data": {"layer": "crate", "x": 40, "y": 24, "positive": True}}))
    lift(project)

    lamp = alpha_of(folder, "lamp")
    assert lamp[8:12, 6:11].all() and not lamp[5:8].any(), "rows 5 to 7 were taken away"
    assert alpha_of(folder, "crate")[24, 40]
    segmentations = [c["params"] for c in (json.loads(line) for line in
                                           (project.cwd / "runner-calls.jsonl").read_text("utf-8").splitlines())
                     if "crop" not in c["params"]]
    assert [set(p) for p in segmentations] == [{"box", "max_size"}, {"box", "max_size"}, {"points", "max_size"}]
