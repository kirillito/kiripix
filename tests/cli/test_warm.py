"""The `segment-preview` Probe and the warm Runner (spec §10.4, §10.6): a hover runs only the decoder in `serve`, and `serve`
gives the GPU lock up when another process asks. With the fake Runner, which logs each half of a call to the Project's
folder: `runner-embeds.jsonl` and `runner-decodes.jsonl`."""

import json
import os
import shutil
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import psutil
import pytest
from conftest import Kiripix, make_demo, stage_status
from PIL import Image
from test_locks import start_holding, wait_for
from test_masks import ROOM, built_room, plate, read_mask
from test_runner_calls import box, click, pinned, repick
from test_serve import Reply, Server, serving

OTHER = "room.yard"
GPU_LOCK = Path(".kiripix") / "locks" / "gpu.lock"
PREVIEW = {"name": "segment-preview", "asset": ROOM, "args": ["30,10"]}


@pytest.fixture
def warm_server(project: Kiripix) -> Iterator[Server]:
    with serving(project.cwd, "--web", str(project.cwd / "no_web_app")) as running:
        yield running


def lines(project: Kiripix, name: str) -> int:
    path = project.cwd / name
    return len(path.read_text("utf-8").splitlines()) if path.exists() else 0


def embeds(project: Kiripix) -> int:
    return lines(project, "runner-embeds.jsonl")


def decodes(project: Kiripix) -> int:
    return lines(project, "runner-decodes.jsonl")


def preview(server: Server, *args: str, **more: Any) -> dict[str, Any]:
    reply = server.call("/api/probe", {**PREVIEW, **({"args": list(args)} if args else {}), **more})
    assert reply.status == 200, reply.body
    result: dict[str, Any] = reply.json["data"]["result"]
    return result


def as_mask(result: dict[str, Any]) -> np.ndarray:
    mask = np.zeros((result["height"], result["width"]), dtype=np.bool_)
    for y, x, length in result["runs"]:
        mask[y, x:x + length] = True
    return mask


def gpu_lock(project: Kiripix) -> dict[str, Any] | None:
    path = project.cwd / GPU_LOCK
    value: dict[str, Any] | None = json.loads(path.read_text("utf-8")) if path.exists() else None
    return value


def eventually(condition: Any, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


def second_room(project: Kiripix) -> None:
    """A second room with a click to make, on the same size as built_room's."""
    project.json("new", "room", "yard", "--view", "top")
    project.json("set", OTHER, "brief", "width=48", "height=32")
    project.json("set", OTHER, "fit", "scale=1")
    Image.fromarray(plate(), "RGBA").save(project.cwd / "yard.png")
    project.json("pick", OTHER, str(project.json("import", OTHER, "yard.png")["data"]["variant"]))
    project.json("run", OTHER, expect=3)
    project.json("decide", OTHER, "masks", "--decision", json.dumps(
        {"decision": "click", "data": {"x": 10, "y": 8, "mask": "solid", "positive": True}}))


# the Probe


def test_the_probe_returns_the_mask_the_runner_would_make_on_the_target_grid(project: Kiripix) -> None:
    built_room(project)

    data = project.json("probe", "segment-preview", ROOM, "30,10")["data"]

    assert data["probe"] == "segment-preview" and data["asset"] == ROOM
    result = data["result"]
    assert (result["width"], result["height"]) == (48, 32)
    # As for a `click` Decision at the same pixel (test_runner_calls): the fake's square reaches 6 px around it.
    assert (as_mask(result) == box(4, 16, 24, 36)).all()
    assert result["pixels"] == 13 * 13


def test_a_negative_click_takes_away_from_the_positive_before_it(project: Kiripix) -> None:
    built_room(project)

    result = project.json("probe", "segment-preview", ROOM, "30,16", "30,16,neg")["data"]["result"]

    assert (as_mask(result) == (box(10, 22, 24, 36) & ~box(13, 19, 27, 33))).all()


def test_the_probe_records_and_pins_nothing(project: Kiripix) -> None:
    folder = built_room(project)
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file() and "work" not in path.parts}
    status = stage_status(project, ROOM)

    project.json("probe", "segment-preview", ROOM, "30,10")

    assert stage_status(project, ROOM) == status
    assert not (folder / "pinned").exists()
    after = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file() and "work" not in path.parts}
    assert after == before


def test_the_cli_is_never_warm(project: Kiripix) -> None:
    built_room(project)

    project.json("probe", "segment-preview", ROOM, "30,10")
    project.json("probe", "segment-preview", ROOM, "30,10")

    assert lines(project, "runner-calls.jsonl") == 2 and gpu_lock(project) is None, "each loads and unloads its own"


@pytest.mark.parametrize("args", [[], ["nope"], ["1,2,3,4,5"], ["1,2,sideways"], ["99,0"], ["0,99"]])
def test_bad_points_are_refused(project: Kiripix, args: list[str]) -> None:
    built_room(project)

    [finding] = project.json("probe", "segment-preview", ROOM, *args, expect=1)["findings"]

    assert finding["code"] == "input.invalid" and embeds(project) == 0


def test_a_room_not_built_yet_is_refused(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    [finding] = project.json("probe", "segment-preview", ROOM, "1,1", expect=1)["findings"]

    assert finding["code"] == "probe.not_ready" and finding["fix"] == f"kiripix run {ROOM}"


def test_a_kind_with_nothing_to_segment_is_refused(project: Kiripix) -> None:
    make_demo(project)

    [finding] = project.json("probe", "segment-preview", "demo.a", "1,1", expect=1)["findings"]

    assert finding["code"] == "probe.not_supported"


# warm in serve


def test_a_second_preview_on_the_same_image_does_not_recompute_the_embedding(project: Kiripix,
                                                                             warm_server: Server) -> None:
    built_room(project)

    first = preview(warm_server)
    second = preview(warm_server)
    other_point = preview(warm_server, "10,8")

    assert first["embedding"] == "computed" and second["embedding"] == "cached" and other_point["embedding"] == "cached"
    assert embeds(project) == 1 and decodes(project) == 3
    assert (as_mask(second) == box(4, 16, 24, 36)).all()


def test_another_image_has_its_own_embedding_and_the_first_stays_cached(project: Kiripix, warm_server: Server) -> None:
    built_room(project)
    preview(warm_server)

    repick(project)
    project.json("run", ROOM, expect=3)

    assert preview(warm_server)["embedding"] == "computed"
    assert embeds(project) == 2


def test_serve_holds_the_gpu_lock_while_warm(project: Kiripix, warm_server: Server) -> None:
    built_room(project)
    assert gpu_lock(project) is None

    preview(warm_server)

    holder = gpu_lock(project)
    assert holder is not None and holder["warm"] is True and holder["lock"] == "gpu"


def test_serve_unloads_after_its_idle_timeout(project: Kiripix) -> None:
    built_room(project)
    with serving(project.cwd, "--warm-idle", "0.3", "--web", str(project.cwd / "no_web_app")) as server:
        preview(server)

        eventually(lambda: gpu_lock(project) is None)

        assert preview(server)["embedding"] == "computed"


def test_a_preview_on_the_cpu_holds_no_gpu_lock(project: Kiripix, warm_server: Server) -> None:
    built_room(project)

    assert preview(warm_server, cpu=True)["device"] == "cpu"
    assert gpu_lock(project) is None


# the GPU lock


def test_a_run_rerun_on_another_asset_gets_the_gpu_lock_after_serve_unloads(project: Kiripix,
                                                                            warm_server: Server) -> None:
    built_room(project)
    second_room(project)
    preview(warm_server)
    assert gpu_lock(project) is not None

    result = project("run", OTHER, "masks", "--rerun", "--json", "--progress", "jsonl")

    assert result.code == 3, result.stdout + result.stderr
    assert stage_status(project, OTHER)["masks"] == "needs-review"
    events = [json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")]
    assert "gpu_wait" in [event["event"] for event in events], "it waits with progress events"
    assert gpu_lock(project) is None and not (project.cwd / ".kiripix" / "locks" / "gpu.request").exists()
    assert preview(warm_server)["embedding"] == "computed", "the warm Runner was unloaded, and comes back on the next hover"


def test_a_cli_preview_while_serve_is_warm_waits_with_progress_events(project: Kiripix, warm_server: Server) -> None:
    built_room(project)
    preview(warm_server)

    result = project("probe", "segment-preview", ROOM, "30,10", "--json", "--progress", "jsonl")

    assert result.code == 0, result.stdout + result.stderr
    assert '"gpu_wait"' in result.stderr
    assert gpu_lock(project) is None


def test_a_busy_cli_preview_offers_the_cpu_since_a_probe_has_no_wait(project: Kiripix) -> None:
    built_room(project)
    make_demo(project)
    process, holder = start_holding(project)
    try:
        [finding] = project.json("probe", "segment-preview", ROOM, "30,10", expect=4)["findings"]

        assert finding["code"] == "lock.busy" and finding["fix"].endswith("--cpu")
    finally:
        (holder / "hold").unlink()
    process.communicate(timeout=60)


def test_a_run_on_the_cpu_while_serve_is_warm_leaves_its_lock_alone(project: Kiripix, warm_server: Server) -> None:
    built_room(project)
    second_room(project)
    preview(warm_server)

    project.json("run", OTHER, "masks", "--rerun", "--cpu", expect=3)

    assert gpu_lock(project) is not None and preview(warm_server)["embedding"] == "cached"


def test_a_click_through_serve_after_a_hover_runs_only_the_decoder_and_stays_warm(project: Kiripix,
                                                                                  warm_server: Server) -> None:
    folder = built_room(project)
    preview(warm_server)
    click(project)

    reply = warm_server.call("/api/run", {"asset": ROOM, "stage": "masks", "rerun": True})

    assert reply.status == 403 and stage_status(project, ROOM)["masks"] == "needs-review"
    assert embeds(project) == 1 and lines(project, "runner-calls.jsonl") == 0
    assert (read_mask(folder) == box(4, 16, 24, 36)).all()
    still_warm(project, warm_server)
    [entry] = [json.loads(line) for line in (folder / "history.jsonl").read_text("utf-8").splitlines() if '"runner"' in line]
    assert entry["device"] == "cuda" and entry["outcome"] == "done"


def test_a_click_through_serve_pins_under_the_key_the_cli_uses(project: Kiripix, warm_server: Server) -> None:
    folder = built_room(project)
    click(project)
    warm_server.call("/api/run", {"asset": ROOM, "stage": "masks", "rerun": True})
    [made_warm] = pinned(folder)
    contents = made_warm.read_bytes()
    shutil.rmtree(folder / "pinned")

    project.json("run", ROOM, "masks", "--rerun", expect=3)

    assert pinned(folder) == [made_warm] and made_warm.read_bytes() == contents


def test_a_failed_call_through_serve_fails_the_run_and_pins_nothing(project: Kiripix, warm_server: Server) -> None:
    folder = built_room(project)
    click(project)
    (project.cwd / "runner-fails").write_text("", encoding="utf-8")

    reply = warm_server.call("/api/run", {"asset": ROOM, "stage": "masks", "rerun": True})

    assert "stage.failed" in reply.codes and pinned(folder) == []
    assert stage_status(project, ROOM)["masks"] == "needs-input"


def test_a_click_through_serve_is_busy_while_another_process_holds_the_gpu(project: Kiripix, warm_server: Server) -> None:
    folder = built_room(project)
    click(project)
    make_demo(project)
    process, holder = start_holding(project)
    try:
        reply = warm_server.call("/api/run", {"asset": ROOM, "stage": "masks", "rerun": True})

        assert reply.status == 423 and reply.json["data"]["holder"]["lock"] == "gpu"
        assert pinned(folder) == []
    finally:
        (holder / "hold").unlink()
    process.communicate(timeout=60)


def test_a_cpu_run_through_serve_itself_unloads_the_warm_runner_it_shares(project: Kiripix, warm_server: Server) -> None:
    built_room(project)
    click(project)
    preview(warm_server)

    reply = warm_server.call("/api/run", {"asset": ROOM, "stage": "masks", "rerun": True, "cpu": True})

    assert reply.status == 403 and stage_status(project, ROOM)["masks"] == "needs-review"
    assert preview(warm_server)["embedding"] == "computed", "the Runner it shared with the run was unloaded after it"


def test_a_preview_while_a_real_run_holds_the_gpu_is_busy(project: Kiripix, warm_server: Server) -> None:
    built_room(project)
    make_demo(project)
    process, holder = start_holding(project)
    try:
        reply = warm_server.call("/api/probe", PREVIEW)

        assert reply.status == 423 and reply.json["data"]["holder"]["lock"] == "gpu"
        assert preview(warm_server, cpu=True)["device"] == "cpu"
    finally:
        (holder / "hold").unlink()
    process.communicate(timeout=60)


def test_a_new_preview_does_not_take_the_lock_from_a_process_that_asked_for_it(project: Kiripix,
                                                                               warm_server: Server) -> None:
    built_room(project)
    locks = project.cwd / ".kiripix" / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    # This test's process asks, so the server unloads and the ask stays until this process is gone or takes it back.
    preview(warm_server)
    (locks / "gpu.request").write_text(json.dumps({
        "lock": "gpu", "pid": os.getpid(), "host": socket.gethostname(), "started": "2026-01-01T00:00:00+00:00",
        "command": "kiripix run room.other --rerun", "process_started": psutil.Process().create_time()}), "utf-8")
    eventually(lambda: gpu_lock(project) is None)

    reply = warm_server.call("/api/probe", PREVIEW)

    assert reply.status == 423 and "room.other" in reply.json["findings"][0]["message"]
    assert gpu_lock(project) is None

    (locks / "gpu.request").unlink()
    assert preview(warm_server)["embedding"] == "computed"


# a rebuild reads pinned results and loads no Runner, so it leaves the GPU lock alone (ticket 0059)


def brush(project: Kiripix, x: int = 1) -> None:
    project.json("decide", ROOM, "masks", "--decision", json.dumps(
        {"decision": "brush", "data": {"mask": "solid", "erase": False, "radius": 0, "points": [[x, 1]]}}))


def still_warm(project: Kiripix, server: Server) -> None:
    holder = gpu_lock(project)
    assert holder is not None and holder["warm"] is True, "the warm Runner still holds the lock"
    assert not (project.cwd / ".kiripix" / "locks" / "gpu.request").exists(), "and nobody asked it to let go"
    assert preview(server)["embedding"] == "cached" and embeds(project) == 1


def test_a_rebuild_through_serve_does_not_ask_the_warm_runner_to_unload(project: Kiripix, warm_server: Server) -> None:
    built_room(project)
    preview(warm_server)
    brush(project)

    reply = warm_server.call("/api/run", {"asset": ROOM, "stage": "masks"})

    assert reply.status == 200, reply.body
    still_warm(project, warm_server)


def test_a_rebuild_from_the_cli_does_not_ask_the_warm_runner_to_unload(project: Kiripix, warm_server: Server) -> None:
    built_room(project)
    preview(warm_server)
    brush(project)

    result = project("run", ROOM, "masks", "--json", "--progress", "jsonl")

    assert result.code == 0, result.stdout + result.stderr
    assert '"gpu_wait"' not in result.stderr
    still_warm(project, warm_server)


def test_a_plain_run_needs_no_gpu_lock_but_a_run_rerun_that_calls_a_runner_does(project: Kiripix) -> None:
    built_room(project)
    click(project)
    project.json("run", ROOM, "masks", "--rerun", expect=3)
    project.json("accept", ROOM, "masks", owner=True)
    make_demo(project)
    process, holder = start_holding(project)
    try:
        brush(project)
        project.json("run", ROOM, "masks")  # replays the pinned click
        assert lines(project, "runner-calls.jsonl") == 1

        click(project, 10, 20)
        assert project.json("run", ROOM, "masks", "--rerun", expect=4)["data"]["holder"]["lock"] == "gpu"
        assert lines(project, "runner-calls.jsonl") == 1
    finally:
        (holder / "hold").unlink()
    process.communicate(timeout=60)


# cancel


def test_a_cancelled_encoder_run_leaves_nothing_cached_and_the_session_usable(project: Kiripix,
                                                                              warm_server: Server) -> None:
    built_room(project)
    hold = project.cwd / "hold-embed"
    hold.write_text("", "utf-8")
    replies: list[Reply] = []
    call = threading.Thread(target=lambda: replies.append(
        warm_server.call("/api/probe", PREVIEW, headers={"X-Kiripix-Job": "hover"})))
    call.start()
    wait_for(project.cwd / "embed-holding")

    assert warm_server.call("/api/jobs/hover/cancel").json["data"]["cancelled"] is True
    call.join(timeout=30)

    assert replies[0].codes == ["run.cancelled"]
    assert embeds(project) == 0
    hold.unlink()
    assert preview(warm_server)["embedding"] == "computed", "a cancelled run left no entry in the embedding cache"
    assert preview(warm_server)["embedding"] == "cached", "and the session still works"
