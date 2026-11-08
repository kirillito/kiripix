"""The matting Runner (ticket 0041, spec §6.2, §8, ADR 0002), through the test Kind `matte` and the fake matter: one pinned
RGBA result with the matte as its alpha, capped at `max_size`; cancel pins nothing; the real Runner is listed with its
licence, hash and size. A real-weights check is the Owner's (the ticket), not CI's."""

import json
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, save_image, stage_status
from PIL import Image
from test_serve import Server, server  # noqa: F401 - the `server` fixture
from test_locks import wait_for

ASSET = "matte.a"
MATTER = "birefnet"
INPUT = (200, 100, 50, 255)


def make_matte(project: Kiripix, size: tuple[int, int] = (8, 4)) -> Path:
    """A matte Asset (the test Kind that calls the MATTER Runner) with an input image. Returns its folder."""
    project.json("new", "matte", "a")
    folder = project.cwd / "assets" / "matte" / "a"
    save_image(folder / "src" / "input.png", size, INPUT)
    return folder


def pinned(folder: Path) -> list[Path]:
    return sorted((folder / "pinned").glob("*.png"))


def calls(project: Kiripix) -> list[dict[str, Any]]:
    path = project.cwd / "runner-calls.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def test_run_never_calls_the_matter_and_rerun_pins_one_rgba_result_for_review(project: Kiripix) -> None:
    folder = make_matte(project)

    project.json("run", ASSET, expect=3)
    assert calls(project) == [] and pinned(folder) == []
    assert stage_status(project, ASSET)["cutout"] == "needs-input"

    project.json("run", ASSET, "cutout", "--rerun", expect=3)

    assert len(calls(project)) == 1 and calls(project)[0]["params"] == {"max_size": 1536}
    assert stage_status(project, ASSET)["cutout"] == "needs-review"
    [path] = pinned(folder)
    with Image.open(path) as image:
        assert image.mode == "RGBA" and image.size == (8, 4)
        pixels = np.asarray(image)
    assert (pixels[..., :3] == INPUT[:3]).all()
    alpha = pixels[0, :, 3]
    assert alpha[0] == 0 and alpha[-1] == 255 and 0 < alpha[3] < 255, "the matte's partial alpha survives"

    project.json("accept", ASSET, "cutout", owner=True)

    assert stage_status(project, ASSET)["cutout"] == "done"
    project.json("run", ASSET, "cutout", "--rerun")
    assert len(calls(project)) == 1, "nothing stale, so no second call"


def test_an_accepted_result_stays_accepted_when_a_rerun_on_the_other_device_differs_a_little(project: Kiripix) -> None:
    folder = make_matte(project)
    (project.cwd / "matter-cpu-differs").write_text("", encoding="utf-8")
    project.json("run", ASSET, "cutout", "--rerun", "--cpu", expect=3)
    project.json("accept", ASSET, "cutout", owner=True)
    assert stage_status(project, ASSET)["cutout"] == "done"
    [path] = pinned(folder)
    on_cpu = path.read_bytes()

    path.unlink()  # the Owner wants the call made again, this time on the GPU
    assert stage_status(project, ASSET)["cutout"] == "needs-input"
    project.json("run", ASSET, "cutout", "--rerun")

    assert len(calls(project)) == 2 and calls(project)[0]["device"] == "cpu" and calls(project)[1]["device"] != "cpu"
    assert path.read_bytes() != on_cpu, "the two devices made different bytes"
    assert stage_status(project, ASSET)["cutout"] == "done", "the same key, made by the Runner: nothing to review again"


def test_an_accepted_key_whose_pinned_result_was_edited_is_reviewed_again(project: Kiripix) -> None:
    folder = make_matte(project)
    project.json("run", ASSET, "cutout", "--rerun", expect=3)
    project.json("accept", ASSET, "cutout", owner=True)
    [path] = pinned(folder)
    with Image.open(path) as image:
        edited = np.asarray(image).copy()
    edited[0, 1, 3] += 1
    Image.fromarray(edited, "RGBA").save(path)

    assert stage_status(project, ASSET)["cutout"] == "stale"
    project.json("run", ASSET, "cutout", expect=3)
    assert stage_status(project, ASSET)["cutout"] == "needs-review"


def test_the_matter_caps_its_result_on_the_longer_side(project: Kiripix) -> None:
    folder = make_matte(project, (3000, 8))

    project.json("run", ASSET, "cutout", "--rerun", expect=3)

    [path] = pinned(folder)
    with Image.open(path) as image:
        assert image.mode == "RGBA" and image.size == (1536, 4)


def test_the_pin_record_names_the_matter_its_weights_and_licence_and_not_the_device(project: Kiripix) -> None:
    folder = make_matte(project)
    project.json("run", ASSET, "cutout", "--rerun", "--cpu", expect=3)
    [path] = pinned(folder)
    record = json.loads(path.with_suffix(".json").read_text("utf-8"))

    assert record["runner"] == MATTER and record["stage"] == "cutout" and record["licence"] == "test"
    assert record["device"] == "cpu" and len(record["weights_hash"]) == len(record["image_hash"]) == 64

    (folder / "pinned" / f"{path.stem}.png").unlink()
    (folder / "pinned" / f"{path.stem}.json").unlink()
    project.json("run", ASSET, "cutout", "--rerun", expect=3)
    assert pinned(folder) == [path], "the same inputs on another device give the same key"


def test_a_matter_failure_fails_the_run_and_pins_nothing(project: Kiripix) -> None:
    folder = make_matte(project)
    (project.cwd / "runner-fails").write_text("", encoding="utf-8")

    result = project.json("run", ASSET, "cutout", "--rerun", expect=1)

    assert [f["code"] for f in result["findings"]] == ["stage.failed"]
    assert pinned(folder) == []


def test_cancel_during_a_long_matter_call_is_run_cancelled_and_pins_nothing(project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = make_matte(project)
    hold = project.cwd / "hold-runner"
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": ASSET, "stage": "cutout", "rerun": True}
    caller = threading.Thread(target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "m"})))
    try:
        caller.start()
        wait_for(project.cwd / "runner-holding")
        cancelled_at = time.monotonic()
        server.call("/api/jobs/m/cancel")
        caller.join(timeout=30)
        stopped_after = time.monotonic() - cancelled_at
    finally:
        hold.unlink(missing_ok=True)

    [reply] = replies
    assert stopped_after < 1.5 and reply.status == 400 and reply.codes == ["run.cancelled"]
    assert not list(folder.glob("pinned/*"))


def test_the_real_matter_is_listed_with_its_licence_hash_and_size_without_downloading(project: Kiripix) -> None:
    rows = project.json("runners", "list", test_recipes=False)["data"]["runners"]

    [row] = [r for r in rows if r["id"] == MATTER]
    assert row["licence"] == "MIT" and row["size"] > 900_000_000 and not row["pulled"]
    assert len(row["weights_hash"]) == 64 and "BiRefNet" in row["description"]
    assert not (project.cwd / ".kiripix" / "weights").exists()
