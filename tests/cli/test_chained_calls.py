"""Pinned Runner calls that depend on earlier ones (ticket 0039, spec §5, ADR 0002), through the test Kind `fill`: a call
to the segmenter whose pinned Mask is the hole in the next call's params, to the matter."""

import json
import shutil
import threading
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, save_image, stage_status
from PIL import Image
from test_locks import wait_for
from test_serve import Server, server  # noqa: F401 - the `server` fixture

ASSET = "fill.a"
NOT_RUN = "Runner not run yet"
CHANGED = "Runner input changed"
RERUN = f"kiripix run {ASSET} filled --rerun"


def make_fill(project: Kiripix) -> Path:
    project.json("new", "fill", "a")
    folder = project.cwd / "assets" / "fill" / "a"
    save_image(folder / "src" / "input.png", (16, 8), (200, 100, 50, 255))
    return folder


def calls(project: Kiripix) -> list[dict[str, Any]]:
    path = project.cwd / "runner-calls.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def records(folder: Path) -> dict[str, dict[str, Any]]:
    """The pin records by the Runner that made them."""
    found = [json.loads(p.read_text("utf-8")) for p in (folder / "pinned").glob("*.json")]
    return {record["runner"]: record for record in found}


def rerun(project: Kiripix, expect: int = 3) -> dict[str, Any]:
    return project.json("run", ASSET, "filled", "--rerun", expect=expect)


def test_one_rerun_makes_both_calls_and_accept_makes_the_stage_done(project: Kiripix) -> None:
    folder = make_fill(project)
    assert project.json("next", ASSET)["data"]["reason"] == NOT_RUN

    rerun(project)

    log = calls(project)
    assert len(log) == 2 and "points" in log[0]["params"] and "crop" in log[1]["params"]
    assert len(list((folder / "pinned").glob("*.png"))) == 2
    assert stage_status(project, ASSET)["filled"] == "needs-review"

    project.json("accept", ASSET, "filled", owner=True)

    assert stage_status(project, ASSET)["filled"] == "done"
    project.json("run", ASSET, "filled", "--rerun")
    assert len(calls(project)) == 2, "nothing stale, so no more calls"


def test_the_hole_reaches_the_runner_as_a_crop_and_runs_in_the_pinned_record(project: Kiripix) -> None:
    folder = make_fill(project)

    rerun(project)

    # The fake segmenter's square reaches 2 px (16 // 8) around (2, 2): rows and columns 0 to 4. A margin of 1 on a crop
    # that stops at the image's edge makes the crop rows and columns 0 to 6.
    hole = calls(project)[1]["params"]
    assert hole["crop"] == [0, 0, 6, 6] and hole["runs"] == [[y, 0, 5] for y in range(5)]
    record = records(folder)["birefnet"]
    assert record["params"] == hole, "the pinned record covers the hole with no new field"
    assert json.loads((folder / "work" / "filled" / "hole.json").read_text("utf-8")) == hole


def test_each_runner_is_unloaded_before_the_next_and_the_first_is_pinned_before_the_second_starts(
        project: Kiripix) -> None:
    folder = make_fill(project)
    hold = project.cwd / "hold-hole"
    hold.write_text("", encoding="utf-8")
    process = project.popen("run", ASSET, "filled", "--rerun")
    try:
        wait_for(project.cwd / "runner-holding")
        assert len(list((folder / "pinned").glob("*.png"))) == 1, "the first call is pinned while the second is loaded"
    finally:
        hold.unlink()
    process.communicate(timeout=30)

    assert process.returncode == 3 and len(list((folder / "pinned").glob("*.png"))) == 2


def test_a_cancel_between_the_calls_keeps_the_first_and_the_next_rerun_makes_only_the_second(
        project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = make_fill(project)
    hold = project.cwd / "hold-hole"
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": ASSET, "stage": "filled", "rerun": True}
    caller = threading.Thread(target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "c"})))
    try:
        caller.start()
        wait_for(project.cwd / "runner-holding")
        server.call("/api/jobs/c/cancel")
        caller.join(timeout=30)
    finally:
        hold.unlink(missing_ok=True)

    assert replies[0].codes == ["run.cancelled"]
    assert list(records(folder)) == ["sam2.1-small"] and len(list((folder / "pinned").glob("*.png"))) == 1
    assert project.json("next", ASSET)["data"]["reason"] == NOT_RUN, "the call before it has the same clicks, still not run"

    rerun(project)

    log = calls(project)
    decodes = (project.cwd / "runner-decodes.jsonl").read_text("utf-8").splitlines()  # `serve`'s warm segmenter
    assert len(decodes) == 1 and not any("points" in c["params"] for c in log), "the first call is not made again"
    assert sum("crop" in c["params"] for c in log) == 2
    assert stage_status(project, ASSET)["filled"] == "needs-review"


def test_changing_what_the_first_call_returns_changes_the_second_key_and_is_input_changed(project: Kiripix) -> None:
    folder = make_fill(project)
    rerun(project)
    project.json("accept", ASSET, "filled", owner=True)
    first = records(folder)["sam2.1-small"]
    before = records(folder)["birefnet"]["key"]

    other = np.zeros((8, 16), dtype=np.bool_)
    other[6:8, 10:16] = True
    Image.fromarray(other).save(folder / "pinned" / f"{first['key']}.png")  # a 1-bit PNG, as it was

    advice = project.json("next", ASSET)["data"]
    assert (advice["status"], advice["reason"], advice["command"]) == ("needs-input", CHANGED, RERUN)

    rerun(project)

    log = calls(project)
    assert sum("points" in c["params"] for c in log) == 1 and sum("crop" in c["params"] for c in log) == 2
    assert records(folder)["birefnet"]["key"] != before
    assert stage_status(project, ASSET)["filled"] == "needs-review"


def test_a_new_input_image_or_other_weights_is_input_changed_for_the_chain(project: Kiripix) -> None:
    folder = make_fill(project)
    rerun(project)
    project.json("accept", ASSET, "filled", owner=True)

    save_image(folder / "src" / "input.png", (16, 8), (10, 20, 30, 255))
    assert project.json("next", ASSET)["data"]["reason"] == CHANGED

    rerun(project)
    assert len(calls(project)) == 4
    project.json("accept", ASSET, "filled", owner=True)
    assert stage_status(project, ASSET)["filled"] == "done"

    (project.cwd / "fake-weights-v2").write_text("", encoding="utf-8")
    assert project.json("next", ASSET)["data"]["reason"] == CHANGED


def test_a_plain_run_after_deleting_work_calls_no_runner(project: Kiripix) -> None:
    folder = make_fill(project)
    rerun(project)
    project.json("accept", ASSET, "filled", owner=True)
    before = (folder / "work" / "filled" / "filled.png").read_bytes()
    shutil.rmtree(folder / "work")

    project.json("run", ASSET)

    assert len(calls(project)) == 2, "a rebuild never calls a Runner"
    assert (folder / "work" / "filled" / "filled.png").read_bytes() == before
    assert stage_status(project, ASSET)["filled"] == "done"
