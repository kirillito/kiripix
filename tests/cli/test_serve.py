"""`serve` (spec §10.1, §10.3, §10.6): the real server in a temporary Project, driven over HTTP.

Each test starts `kiripix serve --port 0` as a subprocess, reads its ready line, and talks to it with the standard
library's HTTP client. Nothing here imports Kiripix: what is checked is the HTTP status and headers, the JSON bodies,
the SSE events and the files on disk.
"""

import http.client
import json
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

import psutil
import pytest

from conftest import MARK, Kiripix, in_review, kiripix_args, kiripix_env, make_demo, make_sketch, save_image, sketched
from test_contract import SAMPLES
from test_locks import start_holding, wait_for
from test_masks import ROOM, built_room, decide

TOKEN = "X-Kiripix-Token"


@dataclass
class Reply:
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def json(self) -> dict[str, Any]:
        value: dict[str, Any] = json.loads(self.body)
        return value

    @property
    def codes(self) -> list[str]:
        return [f["code"] for f in self.json["findings"]]


@dataclass
class Event:
    name: str
    data: dict[str, Any]


class EventStream:
    """`GET /api/events`, read on a thread so a test can wait for the events it expects."""

    def __init__(self, port: int, path: str = "/api/events") -> None:
        self.events: list[Event] = []
        self._changed = threading.Condition()
        self._connection = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
        self._connection.request("GET", path)
        self._response = self._connection.getresponse()
        assert self._response.status == 200
        assert self._response.getheader("Content-Type", "").startswith("text/event-stream")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        name = "message"
        try:
            while True:
                line = self._response.fp.readline().decode("utf-8")  # type: ignore[union-attr]
                if not line:
                    return
                line = line.rstrip("\r\n")
                if line.startswith("event:"):
                    name = line[6:].strip()
                elif line.startswith("data:"):
                    with self._changed:
                        self.events.append(Event(name, json.loads(line[5:])))
                        self._changed.notify_all()
        except (OSError, ValueError, AttributeError):  # the test closed the connection
            return

    def wait_for(self, matches: Callable[[Event], bool], timeout: float = 30) -> Event:
        deadline = time.monotonic() + timeout
        with self._changed:
            while True:
                for event in self.events:
                    if matches(event):
                        return event
                left = deadline - time.monotonic()
                assert left > 0, f"timed out; the events so far: {self.events}"
                self._changed.wait(left)

    def named(self, name: str) -> list[Event]:
        with self._changed:
            return [e for e in self.events if e.name == name]

    def close(self) -> None:
        self._connection.close()


class Server:
    """`kiripix serve --port 0 --print-token` in a folder."""

    def __init__(self, cwd: Path, *extra: str, temp: Path | None = None) -> None:
        """`temp` is the server's temporary folder, so a test can see what it leaves there."""
        self._errors: IO[bytes] = tempfile.TemporaryFile()
        env = kiripix_env()
        if temp is not None:
            env.update({"TMPDIR": str(temp), "TEMP": str(temp), "TMP": str(temp)})
        self.process = subprocess.Popen(
            kiripix_args("serve", "--port", "0", "--print-token", *extra),
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=self._errors,
            text=True,
            encoding="utf-8",
        )
        lines: queue.Queue[str] = queue.Queue()
        stdout = self.process.stdout
        assert stdout is not None
        threading.Thread(target=lambda: lines.put(stdout.readline()), daemon=True).start()
        try:
            self.ready: dict[str, Any] = json.loads(lines.get(timeout=60))
        except (queue.Empty, ValueError):
            self.stop()
            raise
        self.port = int(self.ready["port"])
        self.token = str(self.ready["token"])

    def call(self, path: str, body: object = None, *, token: str | None = None, method: str = "POST",
             headers: dict[str, str] | None = None, raw: bytes | None = None,
             parts: list[tuple[str, str | None, bytes]] | None = None) -> Reply:
        """`parts` sends a multipart body instead: (name, file name or None for a plain field, content)."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        sent = dict(headers or {})
        if token is not None:
            sent[TOKEN] = token
        payload = raw if raw is not None else None if body is None else json.dumps(body).encode()
        if parts is not None:
            payload, sent["Content-Type"] = _multipart(parts)
        try:
            connection.request(method, path, body=payload, headers=sent)
            response = connection.getresponse()
            return Reply(response.status, {k.lower(): v for k, v in response.getheaders()}, response.read())
        finally:
            connection.close()

    def events(self, path: str = "/api/events") -> EventStream:
        stream = EventStream(self.port, path)
        stream.wait_for(lambda e: e.name == "hello")
        return stream

    def stop(self) -> None:
        """Kill the server and everything under it (on Windows the venv's python.exe is a launcher)."""
        try:
            tree = psutil.Process(self.process.pid).children(recursive=True)
        except psutil.Error:
            tree = []
        self.process.kill()
        for child in tree:
            try:
                child.kill()
            except psutil.Error:
                pass
        self.process.wait(timeout=30)
        if self.process.stdout is not None:
            self.process.stdout.close()
        self._errors.close()


def _multipart(parts: list[tuple[str, str | None, bytes]]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = b""
    for name, filename, content in parts:
        disposition = f'form-data; name="{name}"' + ("" if filename is None else f'; filename="{filename}"')
        kind = "application/json" if filename is None else "application/octet-stream"
        body += f"--{boundary}\r\nContent-Disposition: {disposition}\r\nContent-Type: {kind}\r\n\r\n".encode()
        body += content + b"\r\n"
    return body + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


@contextmanager
def serving(cwd: Path, *extra: str, temp: Path | None = None) -> Iterator[Server]:
    server = Server(cwd, *extra, temp=temp)
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def server(project: Kiripix) -> Iterator[Server]:
    """A server with no web app, whether or not this checkout has a built `web/dist`."""
    with serving(project.cwd, "--web", str(project.cwd / "no_web_app")) as running:
        yield running


# One REST body for each Command in the contract test's samples, made from the sample's command line.
BODIES: dict[str, Callable[[list[str]], dict[str, Any]]] = {
    "init": lambda a: {"dir": a[1]},
    "new": lambda a: {"kind": a[1], "name": a[2]},
    "describe": lambda a: {"target": a[1]},
    "schema": lambda a: {"command": a[1]},
    "status": lambda a: {},
    "next": lambda a: {"asset": a[1]},
    "run": lambda a: {"asset": a[1]},
    "set": lambda a: {"asset": a[1], "stage": a[2], "assignments": a[3:]},
    "decide": lambda a: {"asset": a[1], "stage": a[2], "decision": a[4]},
    "undo": lambda a: {"asset": a[1], "stage": a[2]},
    "redo": lambda a: {"asset": a[1], "stage": a[2]},
    "override": lambda a: {"asset": a[1], "stage": a[2], "png": a[3]},
    "accept": lambda a: {"asset": a[1], "stage": a[2]},
    "import": lambda a: {"asset": a[1], "file": a[2]},
    "mask-import": lambda a: {"asset": a[1], "png": a[2]},
    "plate-import": lambda a: {"asset": a[1], "png": a[2]},
    "pick": lambda a: {"asset": a[1], "variant": a[2]},
    "check": lambda a: {"asset": a[1]},
    "show": lambda a: {"asset": a[1]},
    "preview": lambda a: {"asset": a[1], "stage": a[3], "region": a[5], "grid": int(a[7])},
    "export": lambda a: {"asset": a[1]},
    "probe": lambda a: {"name": a[1], "asset": a[2], "args": a[3:]},
    "op quantize": lambda a: {"input": a[2], "output": a[3]},
    "op conformance": lambda a: {"image": a[2]},
    "op palette-suggest": lambda a: {"image": a[2], "add": int(a[4]), "scale": float(a[6])},
    "palette-add": lambda a: {"proposal": a[1]},
    "runners list": lambda a: {},
    "runners pull": lambda a: {"runner": a[2]},
    "runners rm": lambda a: {"runner": a[2]},
    "manifest merge": lambda a: {"base": a[2], "ours": a[3], "theirs": a[4]},
    "manifest install": lambda a: {},
    "manifest repair": lambda a: {},
}

_VOLATILE = {"id", "parent", "started", "finished", "duration_s", "time", "at"}


def _normal(value: Any, roots: list[str]) -> Any:
    """The result with what legitimately differs between two runs (ids, times, the folder) replaced."""
    if isinstance(value, dict):
        return {k: "<volatile>" if k in _VOLATILE else _normal(v, roots) for k, v in value.items()}
    if isinstance(value, list):
        return [_normal(v, roots) for v in value]
    if isinstance(value, str):
        value = re.sub(r"(?<![0-9A-Z])[0-9A-HJKMNP-TV-Z]{26}(?![0-9A-Z])", "<id>", value)  # Decision ids are ULIDs
        for root in roots:
            value = value.replace(root, "<root>").replace(root.replace("\\", "/"), "<root>")
        return value
    return value


def test_every_command_has_a_rest_body() -> None:
    assert set(BODIES) == set(SAMPLES), "add the new Command's REST body to BODIES in tests/cli/test_serve.py"


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_the_rest_response_equals_the_cli_json(project: Kiripix, tmp_path_factory: pytest.TempPathFactory,
                                               name: str) -> None:
    if name not in BODIES:
        pytest.skip("no REST body yet: test_every_command_has_a_rest_body says so")
    arguments = SAMPLES[name](project)
    twin = tmp_path_factory.mktemp("twin") / "project"
    shutil.copytree(project.cwd, twin)  # the same Project, so each side starts from the same state
    owner = name in {"accept", "palette-add"}

    expected = project.json(*arguments, owner=owner)
    with serving(twin) as running:
        reply = running.call("/api/" + name.replace(" ", "/"), BODIES[name](arguments),
                             token=running.token if owner else None)

    roots = [str(project.cwd), str(twin), str(project.cwd.resolve()), str(twin.resolve())]
    assert reply.status == 200 and reply.headers["x-kiripix-exit-code"] == "0"
    assert _normal(reply.json, roots) == _normal(expected, roots)
    assert list(reply.json) == ["api_version", "ok", "data", "findings"]


# The exit code and the HTTP status


def test_schema_documents_the_status_of_each_exit_code(server: Server) -> None:
    status = server.call("/api/schema", {"command": "run"}).json["data"]["http_status"]

    assert status == {"0": 200, "1": 400, "2": 422, "3": 403, "4": 423}


def test_schema_documents_the_findings_with_their_own_status(server: Server) -> None:
    data = server.call("/api/schema", {"command": "run"}).json["data"]

    assert data["finding_status"] == {"job.not_found": 404, "file.not_found": 404, "job.duplicate": 409}


def test_a_bad_wait_is_a_400_finding_with_a_fix(server: Server) -> None:
    for wait in ("abc", "-1", "nan"):
        reply = server.call(f"/api/status?wait={wait}", {})

        assert reply.status == 400 and reply.codes == ["input.invalid"], wait
        assert reply.json["findings"][0]["fix"] == "kiripix status --wait 30"


def test_an_error_is_400_with_the_envelope(server: Server) -> None:
    reply = server.call("/api/new", {"kind": "dragon", "name": "x"})

    assert reply.status == 400 and reply.headers["x-kiripix-exit-code"] == "1"
    assert reply.json["ok"] is False and reply.json["findings"][0]["code"] == "kind.unknown"


def test_bad_input_and_bad_json_are_400_findings(server: Server) -> None:
    unknown = server.call("/api/run", {"asset": "demo.a", "bogus": 1})
    broken = server.call("/api/run", raw=b"{not json")

    assert unknown.status == 400 and unknown.codes == ["input.invalid"]
    assert broken.status == 400 and broken.codes == ["input.invalid"]
    assert set(broken.json) == {"api_version", "ok", "data", "findings"}


def test_a_failed_check_is_422(project: Kiripix, server: Server) -> None:
    folder = make_demo(project)
    (folder / "src" / "input.txt").write_text("bad", encoding="utf-8")

    reply = server.call("/api/run", {"asset": "demo.a", "stage": "copy"})

    assert reply.status == 422 and reply.headers["x-kiripix-exit-code"] == "2"
    assert reply.codes == ["demo.bad_text"]


def test_a_held_lock_is_423_with_the_holder(project: Kiripix, server: Server) -> None:
    make_demo(project)
    holder, folder = start_holding(project)
    try:
        reply = server.call("/api/run", {"asset": "demo.a"})
    finally:
        (folder / "hold").unlink(missing_ok=True)
        holder.communicate(timeout=60)

    assert reply.status == 423 and reply.json["data"]["holder"]["lock"] == "asset.demo.a"
    assert reply.codes == ["lock.busy"]


def test_wait_lets_a_request_wait_for_a_lock(project: Kiripix, server: Server) -> None:
    make_demo(project)
    holder, folder = start_holding(project)
    release = threading.Timer(1.0, lambda: (folder / "hold").unlink(missing_ok=True))
    release.start()
    try:
        reply = server.call("/api/run?wait=30", {"asset": "demo.a"})
    finally:
        release.cancel()
        (folder / "hold").unlink(missing_ok=True)
        holder.communicate(timeout=60)

    assert reply.status == 200 and reply.json["ok"] is True


# The session token


def test_accept_over_rest_needs_the_session_token(project: Kiripix, server: Server) -> None:
    in_review(project)
    body = {"asset": "sketch.a", "stage": "draw"}

    refused = server.call("/api/accept", body)
    wrong = server.call("/api/accept", body, token="not-the-token")

    for reply in (refused, wrong):
        assert reply.status == 403 and reply.headers["x-kiripix-exit-code"] == "3"
        [finding] = reply.json["findings"]
        assert finding["code"] == "owner.required" and finding["fix"] is None and finding["owner_action"]
    project.json("run", "sketch.a", expect=3)  # still waiting for the Owner

    accepted = server.call("/api/accept", body, token=server.token)

    assert accepted.status == 200 and accepted.json["ok"] is True and accepted.json["findings"] == []
    project.json("run", "sketch.a")  # nothing left to review


def test_the_token_is_not_in_the_ready_line_unless_asked_for(project: Kiripix) -> None:
    process = subprocess.Popen(kiripix_args("serve", "--port", "0"), cwd=project.cwd, env=kiripix_env(),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, encoding="utf-8")
    try:
        assert process.stdout is not None
        ready = json.loads(process.stdout.readline())
    finally:
        for child in psutil.Process(process.pid).children(recursive=True):
            child.kill()
        process.kill()
        process.wait(timeout=30)
        assert process.stdout is not None
        process.stdout.close()

    assert ready["event"] == "ready" and "token" not in ready


def test_the_token_is_new_for_each_server(project: Kiripix) -> None:
    with serving(project.cwd) as first, serving(project.cwd) as second:
        assert first.token != second.token and len(first.token) >= 20


# Progress, cancel


def test_progress_streams_over_sse(project: Kiripix, server: Server) -> None:
    make_demo(project)
    stream = server.events()
    try:
        reply = server.call("/api/run", {"asset": "demo.a"}, headers={"X-Kiripix-Job": "j1"})
        end = stream.wait_for(lambda e: e.name == "job_end")
    finally:
        stream.close()

    assert reply.status == 200 and reply.headers["x-kiripix-job"] == "j1"
    progress = [e.data["progress"] for e in stream.named("progress")]
    assert {"event": "stage_progress", "stage": "hold", "done": 1, "total": 1, "message": "held"} in progress
    assert [p["stage"] for p in progress if p["event"] == "stage_start"] == ["copy", "concat", "hold", "fail", "choose"]
    assert all(e.data["job"] == "j1" and e.data["command"] == "run" for e in stream.named("progress"))
    assert end.data == {"job": "j1", "command": "run", "exit_code": 0, "ok": True}


def test_a_stream_can_follow_one_job(project: Kiripix, server: Server) -> None:
    make_demo(project, "a")
    make_demo(project, "b")
    stream = server.events("/api/events?job=wanted")
    try:
        server.call("/api/run", {"asset": "demo.a", "stage": "copy"}, headers={"X-Kiripix-Job": "other"})
        server.call("/api/run", {"asset": "demo.b", "stage": "copy"}, headers={"X-Kiripix-Job": "wanted"})
        stream.wait_for(lambda e: e.name == "job_end")
    finally:
        stream.close()

    assert {e.data["job"] for e in stream.events if e.name != "hello"} == {"wanted"}


def test_cancel_stops_a_run_cleanly(project: Kiripix, server: Server) -> None:
    folder = make_demo(project)
    (folder / "hold").write_text("", encoding="utf-8")
    stream = server.events()
    replies: list[Reply] = []
    caller = threading.Thread(
        target=lambda: replies.append(server.call("/api/run", {"asset": "demo.a"}, headers={"X-Kiripix-Job": "j"})))
    try:
        caller.start()
        stream.wait_for(lambda e: e.name == "progress" and e.data["progress"] == {
            "event": "stage_start", "stage": "hold", "done": 2, "total": 5, "message": None})
        wait_for(folder / "holding")

        cancelled_at = time.monotonic()
        cancel = server.call("/api/jobs/j/cancel")
        caller.join(timeout=30)
        stopped_after = time.monotonic() - cancelled_at
        end = stream.wait_for(lambda e: e.name == "job_end")
    finally:
        (folder / "hold").unlink(missing_ok=True)
        stream.close()

    assert cancel.status == 200 and cancel.json["data"] == {"job": "j", "cancelled": True}
    assert stopped_after < 1.5, "the Stage stopped at its next chunk, not at the backstop"
    [reply] = replies
    assert reply.status == 400 and reply.codes == ["run.cancelled"] and reply.json["ok"] is False
    assert end.data["exit_code"] == 1
    assert not list((project.cwd / ".kiripix" / "locks").glob("*.lock"))
    entries = (folder / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(entries[-1])["outcome"] == "cancelled"
    assert not [p for p in folder.rglob(".tmp-*")]
    # Nothing is half-done, and the server carries on: the same run now finishes.
    assert server.call("/api/run", {"asset": "demo.a"}).json["ok"] is True


def test_cancel_stops_a_runner_call_and_pins_nothing(project: Kiripix, server: Server) -> None:
    folder = built_room(project)
    decide(project, "click", {"x": 30, "y": 10, "mask": "solid", "positive": True})
    hold = project.cwd / "hold-embed"
    hold.write_text("", encoding="utf-8")
    replies: list[Reply] = []
    body = {"asset": ROOM, "stage": "masks", "rerun": True}
    caller = threading.Thread(target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "r"})))
    try:
        caller.start()
        wait_for(project.cwd / "embed-holding")

        cancelled_at = time.monotonic()
        server.call("/api/jobs/r/cancel")
        caller.join(timeout=30)
        stopped_after = time.monotonic() - cancelled_at
    finally:
        hold.unlink(missing_ok=True)

    assert stopped_after < 1.5, "the Runner stopped at its next chunk, not at the backstop"
    [reply] = replies
    assert reply.status == 400 and reply.codes == ["run.cancelled"]
    assert not (folder / "pinned").exists() or not list((folder / "pinned").iterdir())
    assert not list((project.cwd / ".kiripix" / "locks").glob("asset.*.lock"))
    last = json.loads((folder / "history.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert last["outcome"] == "cancelled" and last["runner"] == "sam2.1-small"
    # Nothing is half-done, and the same call now goes through.
    assert server.call("/api/run", body).status == 403


def test_two_runner_calls_in_one_server_take_turns_even_on_the_cpu(project: Kiripix, server: Server) -> None:
    built_room(project)
    decide(project, "click", {"x": 30, "y": 10, "mask": "solid", "positive": True})
    other = "room.yard"
    project.json("new", "room", "yard", "--view", "top")
    project.json("set", other, "brief", "width=48", "height=32")
    project.json("set", other, "fit", "scale=1")
    project.json("pick", other, str(project.json("import", other, "source.png")["data"]["variant"]))
    project.json("run", other, expect=3)
    project.json("decide", other, "masks", "--decision", json.dumps(
        {"decision": "click", "data": {"x": 30, "y": 10, "mask": "solid", "positive": True}}))
    hold = project.cwd / "hold-runner"
    hold.write_text("", encoding="utf-8")
    replies: list[Reply] = []

    def rerun(asset: str) -> None:
        replies.append(server.call("/api/run", {"asset": asset, "stage": "masks", "rerun": True, "cpu": True}))

    callers = [threading.Thread(target=rerun, args=(asset,)) for asset in (ROOM, other)]
    try:
        callers[0].start()
        wait_for(project.cwd / "runner-holding")
        callers[1].start()
        time.sleep(1.5)  # long enough for the second call to start, if nothing held it back
        calls = (project.cwd / "runner-calls.jsonl").read_text(encoding="utf-8").splitlines()
    finally:
        hold.unlink(missing_ok=True)
    for caller in callers:
        caller.join(timeout=30)

    assert len(calls) == 1
    assert [reply.status for reply in replies] == [403, 403]
    assert all([c for c in r.codes if c != "masks.open_edge"] == ["stage.needs_review"] for r in replies)  # info


def test_cancel_stops_a_run_waiting_for_a_lock(project: Kiripix, server: Server) -> None:
    make_demo(project)
    holder, folder = start_holding(project)  # another process holds demo.a, and keeps holding it
    replies: list[Reply] = []
    caller = threading.Thread(target=lambda: replies.append(
        server.call("/api/run?wait=60", {"asset": "demo.a"}, headers={"X-Kiripix-Job": "w"})))
    try:
        caller.start()
        time.sleep(0.5)  # the request is now polling the held lock
        cancelled_at = time.monotonic()
        cancel = server.call("/api/jobs/w/cancel")
        caller.join(timeout=30)
        stopped_after = time.monotonic() - cancelled_at
    finally:
        (folder / "hold").unlink(missing_ok=True)
        holder.communicate(timeout=60)

    assert cancel.json["data"] == {"job": "w", "cancelled": True}
    assert stopped_after < 1.0
    [reply] = replies
    assert reply.status == 400 and reply.codes == ["run.cancelled"]
    assert not list((project.cwd / ".kiripix" / "locks").glob("*.lock"))
    assert not [p for p in folder.rglob(".tmp-*")]


def test_cancelling_an_unknown_job_is_404(server: Server) -> None:
    reply = server.call("/api/jobs/nope/cancel")

    assert reply.status == 404 and reply.codes == ["job.not_found"]


def test_a_job_id_in_use_is_refused(project: Kiripix, server: Server) -> None:
    folder = make_demo(project)
    (folder / "hold").write_text("", encoding="utf-8")
    replies: list[Reply] = []
    caller = threading.Thread(
        target=lambda: replies.append(server.call("/api/run", {"asset": "demo.a"}, headers={"X-Kiripix-Job": "j"})))
    try:
        caller.start()
        wait_for(folder / "holding")

        again = server.call("/api/status", headers={"X-Kiripix-Job": "j"})
    finally:
        (folder / "hold").unlink(missing_ok=True)
        caller.join(timeout=30)

    assert again.status == 409 and again.codes == ["job.duplicate"]
    assert replies[0].status == 200


# Probes


def test_a_probe_answers_over_rest_and_the_cli(project: Kiripix, server: Server) -> None:
    make_demo(project)

    reply = server.call("/api/probe", {"name": "echo", "asset": "demo.a", "args": ["x", "y"]})

    assert reply.status == 200
    assert reply.json["data"] == {"probe": "echo", "asset": "demo.a", "result": {"kind": "demo", "args": ["x", "y"]}}
    assert project.json("probe", "echo", "demo.a", "x", "y")["data"] == reply.json["data"]


def test_a_probe_takes_no_lock_and_records_nothing(project: Kiripix, server: Server) -> None:
    folder = make_demo(project)
    holder, held = start_holding(project)
    try:
        reply = server.call("/api/probe", {"name": "echo", "asset": "demo.a"})
    finally:
        (held / "hold").unlink(missing_ok=True)
        holder.communicate(timeout=60)

    assert reply.status == 200
    assert not (folder / "journal").exists()
    assert not any("echo" in p.read_text(encoding="utf-8", errors="ignore") for p in folder.glob("*.jsonl"))


def test_an_unknown_probe_lists_the_known_ones(project: Kiripix) -> None:
    make_demo(project)

    finding = project.json("probe", "teleport", "demo.a", expect=1)["findings"][0]

    assert finding["code"] == "probe.unknown" and "echo" in finding["message"]


# Files and uploads


def test_the_file_route_serves_a_preview(project: Kiripix, server: Server) -> None:
    make_sketch(project)
    project.json("run", "sketch.a")
    path = project.json("preview", "sketch.a", "--stage", "draw")["data"]["path"]

    reply = server.call(f"/files/{path}", method="GET")

    assert reply.status == 200 and reply.headers["content-type"] == "image/png"
    assert reply.body == (project.cwd / path).read_bytes()


def test_the_file_route_stays_inside_the_project(project: Kiripix, server: Server) -> None:
    (project.cwd.parent / "outside.txt").write_text("secret", encoding="utf-8")

    (project.cwd / ".kiripix" / "locks").mkdir(parents=True, exist_ok=True)
    (project.cwd / ".kiripix" / "locks" / "project.lock").write_text("{}", encoding="utf-8")
    (project.cwd / ".kiripix" / "uploads").mkdir(exist_ok=True)
    (project.cwd / ".kiripix" / "uploads" / "x.png").write_text("x", encoding="utf-8")

    for path in ("/files/.kiripix/locks/project.lock", "/files/.kiripix/uploads/x.png", "/files/.kiripix",
                 "/files/%2e%2e/outside.txt", "/files/..%5coutside.txt", "/files/missing.png", "/files/assets",
                 "/files/.git/config"):
        reply = server.call(path, method="GET")
        assert reply.status == 404 and reply.codes == ["file.not_found"], path


# The Commands with file inputs, and those inputs. Over REST each is a multipart part of the Command's own request.
FILE_INPUTS: dict[str, list[str]] = {"override": ["png"], "import": ["file"], "mask-import": ["png"],
                                     "plate-import": ["png"]}


def test_every_file_input_has_a_multipart_test(server: Server) -> None:
    commands = server.call("/api/schema", {}).json["data"]["commands"]

    assert {name: c["files"] for name, c in commands.items() if c["files"]} == FILE_INPUTS


def _as_parts(project: Kiripix, name: str, body: dict[str, Any]) -> list[tuple[str, str | None, bytes]]:
    """The body with each file input moved out of the JSON into a part of its own, read from the Project."""
    files = {field: body.pop(field) for field in FILE_INPUTS[name]}
    parts: list[tuple[str, str | None, bytes]] = [("input", None, json.dumps(body).encode())]
    return parts + [(field, Path(path).name, (project.cwd / path).read_bytes()) for field, path in files.items()]


@pytest.mark.parametrize("name", sorted(FILE_INPUTS))
def test_a_file_input_as_a_multipart_part_equals_the_cli_json(project: Kiripix, tmp_path_factory: pytest.TempPathFactory,
                                                              name: str) -> None:
    arguments = SAMPLES[name](project)
    twin = tmp_path_factory.mktemp("twin") / "project"
    shutil.copytree(project.cwd, twin)
    temp = tmp_path_factory.mktemp("server_temp")

    expected = project.json(*arguments)
    with serving(twin, temp=temp) as running:
        reply = running.call("/api/" + name, parts=_as_parts(project, name, BODIES[name](arguments)))
        left = list(temp.iterdir())

    roots = [str(project.cwd), str(twin), str(project.cwd.resolve()), str(twin.resolve())]
    assert reply.status == 200 and reply.headers["x-kiripix-exit-code"] == "0"
    assert _normal(reply.json, roots) == _normal(expected, roots)
    assert left == [], "the file inputs' temporary folder is deleted when the Command ends"
    assert not (twin / ".kiripix" / "uploads").exists()


def test_a_refused_file_input_leaves_nothing_behind(project: Kiripix, tmp_path_factory: pytest.TempPathFactory) -> None:
    make_sketch(project)  # never run, so there is no output to paint over
    temp = tmp_path_factory.mktemp("server_temp")
    painted = save_image(project.cwd.parent / "painted.png").read_bytes()

    with serving(project.cwd, temp=temp) as running:
        reply = running.call("/api/override", parts=[
            ("input", None, json.dumps({"asset": "sketch.a", "stage": "draw"}).encode()), ("png", "fix.png", painted)])
        left = list(temp.iterdir())

    assert reply.status == 400 and reply.codes == ["override.no_output"]
    assert left == []


def test_only_a_file_input_can_be_a_file_part(project: Kiripix, server: Server) -> None:
    sketched(project)
    painted = (project.cwd / "fix.png").read_bytes()
    body = json.dumps({"asset": "sketch.a", "stage": "draw"}).encode()

    stranger = server.call("/api/override", parts=[("input", None, body), ("stage", "x.png", painted)])
    empty = server.call("/api/override", parts=[("input", None, body), ("png", "fix.png", b"")])
    elsewhere = server.call("/api/run", parts=[("input", None, b'{"asset": "sketch.a"}'), ("png", "fix.png", painted)])

    for reply in (stranger, empty, elsewhere):
        assert reply.status == 400 and reply.codes == ["input.invalid"]
    assert "'stage' isn't a file input of 'override' (its file inputs: png)" in stranger.json["findings"][0]["message"]


def test_a_path_in_the_project_still_works_as_json(project: Kiripix, server: Server) -> None:
    sketched(project)

    reply = server.call("/api/override", {"asset": "sketch.a", "stage": "draw", "png": "fix.png"})

    assert reply.status == 200 and reply.json["ok"] is True


def test_the_upload_route_is_gone(server: Server) -> None:
    assert server.call("/api/upload?name=a.png", raw=b"x").status == 404


def test_schema_lists_the_transport_routes(server: Server) -> None:
    transport = server.call("/api/schema", {"command": "run"}).json["data"]["transport"]

    routes = {(r["method"], r["path"]): r for r in transport}
    assert set(routes) == {("GET", "/files/{path}"), ("GET", "/api/events"), ("POST", "/api/jobs/{job}/cancel")}
    assert set(routes["GET", "/files/{path}"]["statuses"]) == {"200", "404"}
    assert set(routes["POST", "/api/jobs/{job}/cancel"]["statuses"]) == {"200", "404"}
    assert all(r["purpose"] for r in transport)


# The folder watch


def test_an_agents_change_pushes_a_changed_event(project: Kiripix, server: Server) -> None:
    stream = server.events()
    try:
        project.json("new", "prop", "bench")  # an agent's CLI call, not the server's
        event = stream.wait_for(lambda e: e.name == "changed" and "assets/prop/bench/asset.toml" in e.data["paths"])
    finally:
        stream.close()

    assert event.data["count"] >= 1


def test_the_state_folder_does_not_cause_changed_events(project: Kiripix, server: Server) -> None:
    stream = server.events()
    try:
        (project.cwd / ".kiripix").mkdir(exist_ok=True)
        (project.cwd / ".kiripix" / "noise.txt").write_text("x", encoding="utf-8")
        (project.cwd / "marker.txt").write_text("x", encoding="utf-8")
        stream.wait_for(lambda e: e.name == "changed" and "marker.txt" in e.data["paths"])
    finally:
        stream.close()

    assert all(".kiripix/noise.txt" not in e.data["paths"] for e in stream.named("changed"))


# Static serving of web/


def test_the_built_web_app_is_served(project: Kiripix) -> None:
    web = project.cwd.parent / "web_dist"
    web.mkdir()
    (web / "index.html").write_text("<h1>Kiripix</h1>", encoding="utf-8")
    (web / "app.js").write_text("console.log(1)", encoding="utf-8")

    with serving(project.cwd, "--web", str(web)) as running:
        index = running.call("/", method="GET")
        script = running.call("/app.js", method="GET")
        api = running.call("/api/status", {})

    assert index.status == 200 and index.body == b"<h1>Kiripix</h1>"
    assert script.status == 200 and script.body == b"console.log(1)"
    assert api.status == 200 and api.json["ok"] is True  # the app doesn't hide the API
    assert running.ready["web"] is True


def test_a_built_app_in_the_project_is_found_without_the_option(project: Kiripix) -> None:
    web = project.cwd / "web" / "dist"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<h1>Mine</h1>", encoding="utf-8")

    with serving(project.cwd) as running:
        index = running.call("/", method="GET")

    assert running.ready["web"] is True and index.body == b"<h1>Mine</h1>"


def test_a_built_app_in_the_project_is_found_without_the_option(project: Kiripix) -> None:
    web = project.cwd / "web" / "dist"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<h1>Mine</h1>", encoding="utf-8")

    with serving(project.cwd) as running:
        index = running.call("/", method="GET")

    assert running.ready["web"] is True and index.body == b"<h1>Mine</h1>"


def test_without_a_built_web_app_the_root_is_404(server: Server) -> None:
    assert server.ready["web"] is False
    assert server.call("/", method="GET").status == 404


# Starting


def test_serve_outside_a_project_is_an_error_envelope(kpx: Kiripix) -> None:
    result = kpx("serve", "--port", "0")

    assert result.code == 1
    assert result.json["findings"][0]["code"] == "project.not_found"


def test_serve_says_when_the_port_is_taken(project: Kiripix, server: Server) -> None:
    result = project("serve", "--port", str(server.port))

    assert result.code == 1
    finding = result.json["findings"][0]
    assert finding["code"] == "serve.port_unavailable" and finding["fix"] == "kiripix serve --port 0"


def test_serve_and_ui_are_in_the_help(kpx: Kiripix) -> None:
    out = kpx("--help").stdout

    assert " serve " in out and " ui " in out and " probe " in out


def test_the_marker_decision_still_rejects_bad_data_over_rest(project: Kiripix, server: Server) -> None:
    make_demo(project)

    reply = server.call("/api/decide", {"asset": "demo.a", "stage": "choose",
                                        "decision": MARK.replace("door", "x").replace('"label"', '"lable"')})

    assert reply.status == 400 and reply.json["ok"] is False
