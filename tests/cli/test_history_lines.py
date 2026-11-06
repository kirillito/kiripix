"""A Runner call's `history.jsonl` line (ticket 0069, spec §5, ADR 0002): a pinned result is named by its `key`, and its
`params` are only in `pinned/<key>.json`; a call with no pinned result (failed, cancelled) keeps its `params`."""

import json
import threading
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_inpainter import ASSET, make_inpaint
from test_locks import wait_for
from test_matter import pinned
from test_serve import Server, server  # noqa: F401 - the `server` fixture


def runner_lines(folder: Path) -> list[dict[str, Any]]:
    lines = (folder / "history.jsonl").read_text("utf-8").splitlines()
    return [entry for entry in map(json.loads, lines) if "runner" in entry]


def test_a_pinned_call_has_its_key_and_no_params_and_the_pin_record_has_them(project: Kiripix) -> None:
    folder = make_inpaint(project)

    project.json("run", ASSET, "patched", "--rerun", expect=3)

    [entry] = runner_lines(folder)
    [path] = pinned(folder)
    assert entry["outcome"] == "done" and entry["key"] == path.stem and "params" not in entry
    record = json.loads(path.with_suffix(".json").read_text("utf-8"))
    assert record["params"]["crop"] == [0, 0, 4, 6]


def test_a_failed_call_keeps_its_params(project: Kiripix) -> None:
    folder = make_inpaint(project)
    (project.cwd / "runner-fails").write_text("", encoding="utf-8")

    project.json("run", ASSET, "patched", "--rerun", expect=1)

    [entry] = runner_lines(folder)
    assert entry["outcome"] == "failed" and "key" not in entry and entry["params"]["crop"] == [0, 0, 4, 6]


def test_a_cancelled_call_keeps_its_params(project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = make_inpaint(project)
    hold = project.cwd / "hold-runner"
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": ASSET, "stage": "patched", "rerun": True}
    caller = threading.Thread(
        target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "h"})))
    try:
        caller.start()
        wait_for(project.cwd / "runner-holding")
        server.call("/api/jobs/h/cancel")
        caller.join(timeout=30)
    finally:
        hold.unlink(missing_ok=True)

    [entry] = runner_lines(folder)
    assert entry["outcome"] == "cancelled" and "key" not in entry and entry["params"]["crop"] == [0, 0, 4, 6]
