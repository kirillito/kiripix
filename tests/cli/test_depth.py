"""The depth Runner (ticket 0340, spec §8, ADR 0002, ADR 0014), through the test Kind `depth` and the fake depth Runner: one
pinned 16-bit greyscale result at the model's input size, whose `size` parameter is part of the key; a pinned call replays
without the Runner; other weights make it "Runner input changed"; cancel pins nothing. The real Runner is listed with its
licence, hash and size, and a real-weights check runs only with CUDA, the weights and the trial's room on disk."""

import json
import os
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

ASSET = "depth.a"
DEPTH = "depth-anything-v2-small"
CHANGED = "Runner input changed"
RERUN = f"kiripix run {ASSET} relief --rerun"


def make_depth(project: Kiripix, size: tuple[int, int] = (40, 20)) -> Path:
    project.json("new", "depth", "a")
    folder = project.cwd / "assets" / "depth" / "a"
    save_image(folder / "src" / "input.png", size, (200, 100, 50, 255))
    return folder


def test_rerun_pins_one_16_bit_depth_at_the_input_size_and_a_pinned_call_replays_without_the_runner(project: Kiripix) -> None:
    folder = make_depth(project)
    assert project.json("next", ASSET)["data"]["reason"] == "Runner not run yet"

    project.json("run", ASSET, "relief", "--rerun", expect=3)

    [call] = calls(project)
    assert call["runner"] == DEPTH and call["params"] == {"size": 1036}
    [path] = pinned(folder)
    with Image.open(path) as image:
        assert image.mode == "I;16" and image.size == (1036, 518), "the long side at `size`, both sides a multiple of 14"
        pixels = np.asarray(image)
    assert pixels[0, 0] == 0 and pixels[0, -1] == 65535 and (np.diff(pixels[0].astype(int)) >= 0).all()
    assert stage_status(project, ASSET)["relief"] == "needs-review"

    project.json("accept", ASSET, "relief", owner=True)
    project.json("run", ASSET, "relief")
    project.json("run", ASSET, "relief", "--rerun")

    assert stage_status(project, ASSET)["relief"] == "done" and len(calls(project)) == 1, "nothing stale, so no second call"


def test_other_weights_make_the_pinned_depth_needs_input_with_runner_input_changed(project: Kiripix) -> None:
    folder = make_depth(project)
    project.json("run", ASSET, "relief", "--rerun", expect=3)
    project.json("accept", ASSET, "relief", owner=True)

    (project.cwd / "fake-weights-v2").write_text("", encoding="utf-8")

    advice = project.json("next", ASSET)["data"]
    assert (advice["status"], advice["reason"], advice["command"]) == ("needs-input", CHANGED, RERUN)
    project.json("run", ASSET, "relief", expect=3)
    assert len(calls(project)) == 1, "`run` never makes a stale pinned call again"
    project.json("run", ASSET, "relief", "--rerun", expect=3)
    assert stage_status(project, ASSET)["relief"] == "needs-review" and len(pinned(folder)) == 2


def test_the_pin_record_names_the_runner_its_weights_licence_and_size_and_not_the_device(project: Kiripix) -> None:
    folder = make_depth(project)
    project.json("run", ASSET, "relief", "--rerun", "--cpu", expect=3)
    [path] = pinned(folder)
    record = json.loads(path.with_suffix(".json").read_text("utf-8"))

    assert record["runner"] == DEPTH and record["params"] == {"size": 1036} and record["decisions"] == []
    assert record["device"] == "cpu" and len(record["weights_hash"]) == len(record["image_hash"]) == 64

    path.unlink()
    path.with_suffix(".json").unlink()
    project.json("run", ASSET, "relief", "--rerun", expect=3)
    assert pinned(folder) == [path], "the same inputs on another device give the same key"


def test_a_depth_failure_fails_the_run_and_pins_nothing(project: Kiripix) -> None:
    folder = make_depth(project)
    (project.cwd / "runner-fails").write_text("", encoding="utf-8")

    result = project.json("run", ASSET, "relief", "--rerun", expect=1)

    assert [f["code"] for f in result["findings"]] == ["stage.failed"]
    assert pinned(folder) == []


def test_cancel_during_a_long_depth_call_is_run_cancelled_and_pins_nothing(project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = make_depth(project)
    hold = project.cwd / "hold-runner"
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": ASSET, "stage": "relief", "rerun": True}
    caller = threading.Thread(target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "d"})))
    try:
        caller.start()
        wait_for(project.cwd / "runner-holding")
        cancelled_at = time.monotonic()
        server.call("/api/jobs/d/cancel")
        caller.join(timeout=30)
        stopped_after = time.monotonic() - cancelled_at
    finally:
        hold.unlink(missing_ok=True)

    [reply] = replies
    assert stopped_after < 1.5 and reply.status == 400 and reply.codes == ["run.cancelled"]
    assert not list(folder.glob("pinned/*"))


def test_the_real_depth_runner_is_listed_with_its_licence_hash_and_size_without_downloading(project: Kiripix) -> None:
    rows = project.json("runners", "list", test_recipes=False)["data"]["runners"]

    [row] = [r for r in rows if r["id"] == DEPTH]
    assert row["licence"] == "Apache-2.0" and row["size"] == 99_060_839 and not row["pulled"]
    assert len(row["weights_hash"]) == 64 and "Depth Anything V2 Small" in row["description"]
    assert not (project.cwd / ".kiripix" / "weights").exists()


_REAL = Path(__file__).parents[2] / ".kiripix" / "weights" / DEPTH / "model.onnx"
_ROOM = Path(os.environ.get("KIRIPIX_TEST_ART", r"C:\Homespace\urban-mystery-club-art")) / "assets" / "room" / "ch01_dungeon_r01"
_TRIAL_SECONDS = 3.0  # trial 0252: about 3 s a room on the GPU, with the load


def _cuda() -> bool:
    try:
        import onnxruntime

        return "CUDAExecutionProvider" in onnxruntime.get_available_providers()
    except ImportError:
        return False


@pytest.mark.skipif(not _REAL.is_file() or not _cuda() or not _ROOM.is_dir(),
                    reason="needs CUDA, the depth weights (`kiripix runners pull depth-anything-v2-small`) and the trial's room")
def test_real_weights_depth_the_trials_room_on_the_gpu_within_twice_the_trials_time() -> None:
    from kiripix.runners.depth import DepthAnythingV2Small, decode, encode

    [source] = (_ROOM / "src").glob("*.png")
    with Image.open(source) as opened:
        image = np.asarray(opened.convert("RGBA"))
    runner = DepthAnythingV2Small()
    started = time.monotonic()
    runner.load(_REAL.parent, "auto")
    try:
        if runner.device_used != "cuda":
            pytest.skip("ONNX Runtime can't use a GPU on this machine")
        depth = runner.call(image, {"size": 1036}, lambda: None)
        took = time.monotonic() - started
        small = runner.call(image, {"size": 518}, lambda: None)
    finally:
        runner.unload()

    assert depth.dtype == np.float32 and depth.shape == (1036, 742), "864 x 1216 at the long side 1036: 742 x 1036"
    assert depth.min() == 0 and depth.max() == 1 and small.shape == (518, 364)
    assert took < 2 * _TRIAL_SECONDS
    assert np.abs(decode(encode(depth)) - depth).max() < 1 / 65535
    assert depth[:, :].std() > 0.05, "relief, not a flat image"


@pytest.mark.skipif(not _REAL.is_file(), reason="the depth weights aren't pulled (`kiripix runners pull depth-anything-v2-small`)")
def test_real_weights_run_on_the_cpu_too_and_refuse_a_size_that_is_not_recorded() -> None:
    from kiripix.runners import RunnerError
    from kiripix.runners.depth import DepthAnythingV2Small

    image = np.zeros((60, 80, 4), dtype=np.uint8)
    image[..., :3] = np.linspace(0, 255, 80, dtype=np.uint8)[None, :, None]
    image[..., 3] = 255
    runner = DepthAnythingV2Small()
    runner.load(_REAL.parent, "cpu")
    try:
        depth = runner.call(image, {"size": 518}, lambda: None)
        with pytest.raises(RunnerError, match="`size`"):
            runner.call(image, {"size": 777}, lambda: None)
    finally:
        runner.unload()

    assert depth.shape == (392, 518) and depth.dtype == np.float32
