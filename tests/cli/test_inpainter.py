"""The inpainting Runner (ticket 0040, spec §6.1, §8, ADR 0002), through the test Kind `inpaint` and the fake inpainter: a
pinned RGBA crop with the hole filled; swapping the Runner behind the role makes its calls "Runner input changed" and a
`--rerun` remakes them for review; cancel pins nothing. The real Runner is listed with its licence, hash and size, and a
real-weights check runs only when the weights are on disk (the ticket's manual check is the Owner's, not CI's)."""

import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix, save_image, stage_status
from PIL import Image
from test_locks import wait_for
from test_matter import calls, pinned
from test_serve import Server, server  # noqa: F401 - the `server` fixture

ASSET = "inpaint.a"
INPAINTER = "lama"
SOURCE = (200, 100, 50, 255)
CHANGED = "Runner input changed"
RERUN = f"kiripix run {ASSET} patched --rerun"


def make_inpaint(project: Kiripix) -> Path:
    project.json("new", "inpaint", "a")
    folder = project.cwd / "assets" / "inpaint" / "a"
    save_image(folder / "src" / "input.png", (8, 6), SOURCE)
    return folder


def rerun(project: Kiripix) -> dict[str, Any]:
    return project.json("run", ASSET, "patched", "--rerun", expect=3)


def test_rerun_pins_the_crop_with_its_hole_filled_and_accept_makes_it_done(project: Kiripix) -> None:
    folder = make_inpaint(project)
    assert project.json("next", ASSET)["data"]["reason"] == "Runner not run yet"

    rerun(project)

    [call] = calls(project)
    assert call["runner"] == INPAINTER and call["params"]["crop"] == [0, 0, 4, 6]
    [path] = pinned(folder)
    with Image.open(path) as image:
        assert image.mode == "RGBA" and image.size == (6, 4), "the crop, not the whole image"
        pixels = np.asarray(image)
    assert (pixels == SOURCE).all(), "the fake fills with the mean of the rest, which is the one colour"
    assert stage_status(project, ASSET)["patched"] == "needs-review"

    project.json("accept", ASSET, "patched", owner=True)

    assert stage_status(project, ASSET)["patched"] == "done"
    project.json("run", ASSET, "patched", "--rerun")
    assert len(calls(project)) == 1


def test_swapping_the_runner_behind_the_role_is_input_changed_and_rerun_remakes_it_for_review(project: Kiripix) -> None:
    folder = make_inpaint(project)
    rerun(project)
    project.json("accept", ASSET, "patched", owner=True)
    [first] = pinned(folder)
    record = json.loads(first.with_suffix(".json").read_text("utf-8"))
    assert record["runner"] == INPAINTER

    (project.cwd / "inpainter-b").write_text("", encoding="utf-8")  # the role now has another Runner behind it

    advice = project.json("next", ASSET)["data"]
    assert (advice["status"], advice["reason"], advice["command"]) == ("needs-input", CHANGED, RERUN)
    project.json("run", ASSET, "patched", expect=3)
    assert len(calls(project)) == 1, "a plain run calls no Runner"

    rerun(project)

    assert [c["runner"] for c in calls(project)] == [INPAINTER, "fake.inpainter-b"]
    assert len(pinned(folder)) == 2 and first in pinned(folder), "the old result stays; the new one has its own key"
    assert stage_status(project, ASSET)["patched"] == "needs-review"
    project.json("accept", ASSET, "patched", owner=True)
    assert stage_status(project, ASSET)["patched"] == "done"


def test_an_inpainter_failure_fails_the_run_and_pins_nothing(project: Kiripix) -> None:
    folder = make_inpaint(project)
    (project.cwd / "runner-fails").write_text("", encoding="utf-8")

    result = project.json("run", ASSET, "patched", "--rerun", expect=1)

    assert [f["code"] for f in result["findings"]] == ["stage.failed"] and pinned(folder) == []


def test_cancel_during_a_long_inpainter_call_is_run_cancelled_and_pins_nothing(
        project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = make_inpaint(project)
    hold = project.cwd / "hold-runner"
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": ASSET, "stage": "patched", "rerun": True}
    caller = threading.Thread(target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "i"})))
    try:
        caller.start()
        wait_for(project.cwd / "runner-holding")
        server.call("/api/jobs/i/cancel")
        caller.join(timeout=30)
    finally:
        hold.unlink(missing_ok=True)

    [reply] = replies
    assert reply.status == 400 and reply.codes == ["run.cancelled"]
    assert not list(folder.glob("pinned/*"))


def _history(folder: Path) -> list[dict[str, Any]]:
    entries = [json.loads(line) for line in (folder / "history.jsonl").read_text("utf-8").splitlines()]
    return [e for e in entries if "runner" in e]


def test_serve_keeps_the_inpainter_warm_so_only_the_first_run_pays_its_load(
        project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = make_inpaint(project)
    (project.cwd / "runner-load-seconds").write_text("0.5", encoding="utf-8")
    body = {"asset": ASSET, "stage": "patched", "rerun": True}

    assert server.call("/api/run", body).status == 403  # the rerun waits for the Owner's accept
    shutil.rmtree(folder / "pinned")  # a call to make again
    assert server.call("/api/run", body).status == 403

    first, second = _history(folder)
    assert first["load_s"] >= 0.5 and "load_s" not in second, "the second run found the Runner loaded"
    assert (project.cwd / ".kiripix" / "locks" / "gpu.lock").is_file(), "serve holds the GPU lock while it is warm"


def test_cancel_during_a_long_load_is_run_cancelled_at_once_and_the_next_run_still_works(
        project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = make_inpaint(project)
    (project.cwd / "runner-load-seconds").write_text("4", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": ASSET, "stage": "patched", "rerun": True}
    caller = threading.Thread(target=lambda: replies.append(
        server.call("/api/run", body, headers={"X-Kiripix-Job": "l"})))
    caller.start()
    time.sleep(1)  # inside the load

    server.call("/api/jobs/l/cancel")
    started = time.monotonic()
    caller.join(timeout=30)

    [reply] = replies
    assert reply.codes == ["run.cancelled"] and time.monotonic() - started < 2, "it didn't wait for the load to end"
    assert not list(folder.glob("pinned/*"))
    (project.cwd / "runner-load-seconds").unlink()
    assert server.call("/api/run", body).status == 403, "the next run waits for the abandoned load, then loads its own"
    assert len(pinned(folder)) == 1


def test_the_real_inpainter_is_listed_with_its_licence_hash_and_size_without_downloading(project: Kiripix) -> None:
    rows = project.json("runners", "list", test_recipes=False)["data"]["runners"]

    [row] = [r for r in rows if r["id"] == INPAINTER]
    assert row["licence"] == "Apache-2.0" and 200_000_000 < row["size"] < 250_000_000 and not row["pulled"]
    assert len(row["weights_hash"]) == 64 and "LaMa" in row["description"]
    assert not (project.cwd / ".kiripix" / "weights").exists()


_REAL = Path(__file__).parents[2] / ".kiripix" / "weights" / "lama" / "lama_fp32.onnx"


@pytest.mark.skipif(not _REAL.is_file(), reason="the LaMa weights aren't pulled (`kiripix runners pull lama`)")
def test_real_weights_fill_only_the_hole_and_keep_the_rest_of_the_crop() -> None:
    from kiripix.runners.lama import Lama

    height, width = 300, 400  # not square, and smaller than the model's input
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[..., :3] = [60, 120, 180]
    image[..., 3] = 255
    image[:, 200:, :3] = [180, 120, 60]
    params = {"crop": [20, 30, 280, 380], "runs": [[y, 150, 40] for y in range(100, 160)]}
    runner = Lama()
    runner.load(_REAL.parent, "cpu")
    try:
        result = runner.call(image, params, lambda: None)
    finally:
        runner.unload()

    assert result.shape == (260, 350, 4) and result.dtype == np.uint8
    crop = image[20:280, 30:380]
    hole = np.zeros(result.shape[:2], dtype=np.bool_)
    for y, x, length in params["runs"]:
        hole[y, x:x + length] = True
    assert (result[~hole] == crop[~hole]).all() and (result[hole][:, 3] == 255).all()
