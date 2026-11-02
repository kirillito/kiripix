"""Locks with real concurrent processes, killed runs, stale-lock takeover and cancellation (spec §10.4)."""

import json
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import Kiripix, Result, make_demo, stage_status


def wait_for(path: Path, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        assert time.monotonic() < deadline, f"timed out waiting for {path}"
        time.sleep(0.05)


def start_holding(project: Kiripix, name: str = "a") -> tuple[subprocess.Popen[str], Path]:
    """Start `run demo.<name>` and wait until it holds the Asset and GPU locks inside the hold Stage."""
    folder = project.cwd / "assets" / "demo" / name
    (folder / "hold").write_text("", encoding="utf-8")
    process = project.popen("run", f"demo.{name}")
    wait_for(folder / "holding")
    return process, folder


def finish(process: subprocess.Popen[str]) -> Result:
    stdout, stderr = process.communicate(timeout=60)
    return Result(process.returncode, stdout, stderr)


def dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def write_lock(project: Kiripix, lock: str, pid: int, host: str) -> None:
    folder = project.cwd / ".kiripix" / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    holder = {"lock": lock, "pid": pid, "host": host, "started": "2026-01-01T00:00:00+00:00",
              "command": "kiripix run demo.a", "process_started": 0.0}
    (folder / f"{lock}.lock").write_text(json.dumps(holder), encoding="utf-8")


def test_a_second_writer_is_busy_with_exit_4(project: Kiripix) -> None:
    make_demo(project)
    process, folder = start_holding(project)
    try:
        result = project.json("run", "demo.a", expect=4)

        holder = result["data"]["holder"]
        # On Windows the venv's python.exe is a launcher, so the holder is its child process.
        assert holder["pid"] > 0 and holder["host"] == socket.gethostname()
        assert holder["lock"] == "asset.demo.a"
        assert holder["command"].startswith("kiripix run demo.a")
        finding = result["findings"][0]
        assert finding["code"] == "lock.busy"
        assert finding["fix"].endswith("--wait 60")
    finally:
        (folder / "hold").unlink()
    assert finish(process).code == 0


def test_a_writer_with_wait_succeeds_once_the_lock_is_released(project: Kiripix) -> None:
    make_demo(project)
    process, folder = start_holding(project)
    waiter = project.popen("run", "demo.a", "--wait", "30")
    time.sleep(1.0)
    (folder / "hold").unlink()

    assert finish(process).code == 0
    waited = finish(waiter)
    assert waited.code == 0, waited.stdout + waited.stderr
    assert {r["outcome"] for r in waited.json["data"]["results"]} == {"skipped"}


def test_wait_gives_up_after_its_timeout(project: Kiripix) -> None:
    make_demo(project)
    process, folder = start_holding(project)
    try:
        started = time.monotonic()
        result = project.json("run", "demo.a", "--wait", "1", expect=4)
        assert time.monotonic() - started >= 1
        assert result["findings"][0]["code"] == "lock.busy"
    finally:
        (folder / "hold").unlink()
    finish(process)


def test_the_gpu_lock_is_shared_across_assets(project: Kiripix) -> None:
    make_demo(project, "a")
    make_demo(project, "b")
    process, folder = start_holding(project, "a")
    try:
        result = project.json("run", "demo.b", expect=4)
        assert result["data"]["holder"]["lock"] == "gpu"
    finally:
        (folder / "hold").unlink()
    finish(process)


def test_read_only_commands_never_wait_for_a_lock(project: Kiripix) -> None:
    make_demo(project)
    process, folder = start_holding(project)
    try:
        assert project.json("status")["ok"]
        assert project.json("next", "demo.a")["ok"]
        assert project.json("describe", "demo")["ok"]
    finally:
        (folder / "hold").unlink()
    finish(process)


def test_run_all_keeps_going_past_a_locked_asset(project: Kiripix) -> None:
    make_demo(project, "a")
    make_demo(project, "c")
    (project.cwd / "assets" / "demo" / "c" / "src" / "input.txt").write_text("c", encoding="utf-8")
    process, folder = start_holding(project, "a")
    try:
        result = project.json("run", "--all", expect=4)
        assert "lock.busy" in [f["code"] for f in result["findings"]]
        # demo.c got as far as the GPU-locked Stage
        assert stage_status(project, "demo.c")["concat"] == "done"
    finally:
        (folder / "hold").unlink()
    finish(process)


def test_a_killed_run_leaves_no_completed_output_and_its_lock_is_taken_over(project: Kiripix) -> None:
    folder = make_demo(project)
    process, _ = start_holding(project)

    process.kill()
    process.wait()

    assert (project.cwd / ".kiripix" / "locks" / "asset.demo.a.lock").exists()
    assert not (folder / "work" / "hold").exists()
    assert stage_status(project, "demo.a")["hold"] == "todo"
    (folder / "hold").unlink()
    project.json("run", "demo.a")
    assert stage_status(project, "demo.a")["hold"] == "done"
    assert not [p for p in (folder / "work").iterdir() if p.name.startswith(".")]


def test_a_lock_from_a_dead_process_is_taken_over(project: Kiripix) -> None:
    make_demo(project)
    write_lock(project, "asset.demo.a", dead_pid(), socket.gethostname())

    project.json("run", "demo.a")

    assert not (project.cwd / ".kiripix" / "locks" / "asset.demo.a.lock").exists()


def test_a_lock_from_another_host_is_never_taken_over(project: Kiripix) -> None:
    make_demo(project)
    write_lock(project, "asset.demo.a", dead_pid(), "another-machine")

    result = project.json("run", "demo.a", expect=4)

    assert "another-machine" in result["findings"][0]["message"]


@pytest.mark.skipif(sys.platform == "win32", reason="Ctrl+C can't be sent to one console process on Windows")
def test_ctrl_c_stops_cleanly(project: Kiripix) -> None:
    folder = make_demo(project)
    process, _ = start_holding(project)

    process.send_signal(signal.SIGINT)
    result = finish(process)

    assert result.code == 1
    assert result.json["findings"][0]["code"] == "run.cancelled"
    assert not list((project.cwd / ".kiripix" / "locks").glob("*.lock"))
    entries = (folder / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(entries[-1])["outcome"] == "cancelled"
    assert stage_status(project, "demo.a")["hold"] == "todo"
