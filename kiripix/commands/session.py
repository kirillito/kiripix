"""A server session: what the REST adapter needs to decide, so the adapter itself holds no logic (spec §10.3, §10.6).

It holds the session token (the REST half of the owner-only guard), the table of running jobs with its refusals, the
parsing of a request's body (JSON, or multipart with file inputs) and `wait`, the file rules, and the ready line. The adapter only turns HTTP into
calls on a Session and its answers back into HTTP.
"""

import json
import math
import secrets
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import kiripix
from kiripix.commands.contract import ProgressEvent
from kiripix.commands.files import FileInputs, project_root, served_file
from kiripix.commands.jobs import Job
from kiripix.commands.registry import Command
from kiripix.core import warm
from kiripix.core.errors import fail

JobProgress = Callable[[str, str, ProgressEvent], None]  # (job id, Command name, event)


INPUT_PART = "input"  # the multipart part with the input's other fields, as JSON
DEFAULT_WARM_IDLE = warm.DEFAULT_IDLE_SECONDS


@dataclass(frozen=True)
class Part:
    """One part of a multipart request. `filename` is None for a plain field, and may be empty for a file."""

    name: str
    data: bytes
    filename: str | None = None


class CancelData(BaseModel):
    job: str
    cancelled: bool


def built_web(root: Path, explicit: Path | None = None) -> Path | None:
    """The built web app: `--web`, else `web/dist` in the Project, else the one that ships with Kiripix (`web/dist` next
    to a checkout's package, or `kiripix/web` inside an installed one). None when there is none."""
    if explicit is not None:
        return explicit
    package = Path(kiripix.__file__).resolve().parent
    for candidate in (root / "web" / "dist", package.parent / "web" / "dist", package / "web"):
        if candidate.is_dir():
            return candidate
    return None


class Session:
    def __init__(self, root: Path, warm_idle: float) -> None:
        self.root = root
        warm.set_idle_seconds(warm_idle)
        self._token = secrets.token_urlsafe(24)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    @classmethod
    def open(cls, cwd: Path, warm_idle: float) -> "Session":
        """The session for the Project containing `cwd`; raises `project.not_found` outside one. `warm_idle` is how long
        a warm Runner stays loaded unused, in seconds."""
        return cls(project_root(cwd), warm_idle)

    def ready(self, url: str, port: int, web: Path | None, *, with_token: bool) -> dict[str, object]:
        line: dict[str, object] = {"event": "ready", "url": url, "port": port, "root": str(self.root),
                                   "web": web is not None and web.is_dir()}
        if with_token:
            line["token"] = self._token
        return line

    def browser_url(self, url: str) -> str:
        """Where `ui` sends the browser: the fragment gives the page the token and never leaves the browser."""
        return f"{url}/#token={self._token}"

    def _is_owner(self, given: str | None) -> bool:
        return bool(given) and secrets.compare_digest((given or "").encode(), self._token.encode())

    def start(self, command: Command[Any, Any], body: bytes | list[Part], *, token: str | None, wait: str | None,
              job_id: str | None, progress: JobProgress) -> Job:
        """Start `command` on a job. `body` is the JSON input, or the parts of a multipart request.

        Raises KiripixError for a body that isn't JSON, a part that isn't a file input, a bad `wait`, or a job id in use.
        """
        seconds = self._wait(command, wait)
        files: FileInputs | None = None
        try:
            if isinstance(body, list):
                files = FileInputs()
                raw = _multipart(command, body, files)
            else:
                raw = _json(command, body)
            job = self._start(command, raw, seconds, token=token, job_id=job_id, progress=progress)
        except BaseException:
            if files is not None:
                files.remove()
            raise
        if files is not None:
            job.result.add_done_callback(lambda _: files.remove())
        job.start()
        return job

    @staticmethod
    def _wait(command: Command[Any, Any], wait: str | None) -> float:
        seconds = 0.0
        if wait is not None:
            try:
                seconds = float(wait)
            except ValueError:
                seconds = math.nan
            if not math.isfinite(seconds) or seconds < 0:
                raise fail("input.invalid", f"wait must be a number of seconds, not '{wait}'",
                           fix=f"kiripix {command.name} --wait 30")
        return seconds

    def _start(self, command: Command[Any, Any], raw: Any, seconds: float, *, token: str | None,
               job_id: str | None, progress: JobProgress) -> Job:
        name = job_id or uuid.uuid4().hex[:12]
        job = Job(command, raw, id=name, cwd=self.root, wait=seconds, owner=self._is_owner(token),
                  progress=lambda event: progress(name, command.name, event))
        with self._lock:
            if name in self._jobs:
                raise fail("job.duplicate", f"a job '{name}' is already running",
                           owner_action=f"Wait for job '{name}' to finish or cancel it, or use another job id.")
            self._jobs[name] = job
        job.result.add_done_callback(lambda _: self._forget(name))
        return job

    def _forget(self, name: str) -> None:
        with self._lock:
            self._jobs.pop(name, None)

    def cancel(self, job_id: str) -> CancelData:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise fail("job.not_found", f"no running job '{job_id}'",
                       owner_action="Check the job id; a job is forgotten as soon as it finishes.")
        return CancelData(job=job_id, cancelled=job.cancel())

    def close(self) -> None:
        """When the server stops: cancel what is running, and let go of the warm Runner and its GPU lock."""
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            job.cancel()
        warm.shut_down()

    def file(self, relative: str) -> Path:
        found = served_file(self.root, relative)
        if found is None:
            raise fail("file.not_found", f"no file '{relative}' in the Project", fix="kiripix status")
        return found


def _json(command: Command[Any, Any], body: bytes | str) -> Any:
    try:
        return json.loads(body) if body.strip() else {}
    except ValueError as error:
        raise fail("input.invalid", f"the JSON input isn't valid JSON: {error}",
                   fix=f"kiripix {command.name} --help") from None


def _multipart(command: Command[Any, Any], parts: list[Part], files: FileInputs) -> dict[str, Any]:
    """The input of a multipart request: the `input` part's JSON, with each file part stored in `files` and its field
    set to the stored path."""
    help_line = f"kiripix {command.name} --help"
    names = [part.name for part in parts]
    if repeated := sorted({name for name in names if names.count(name) > 1}):
        raise fail("input.invalid", f"the parts {', '.join(repeated)} are sent more than once", fix=help_line)
    given = next((part for part in parts if part.name == INPUT_PART), None)
    raw = _json(command, given.data) if given is not None else {}
    if not isinstance(raw, dict):
        raise fail("input.invalid", f"the '{INPUT_PART}' part must be a JSON object", fix=help_line)
    for part in parts:
        if part.name == INPUT_PART:
            continue
        if part.name not in command.files or part.filename is None:
            accepted = ", ".join(command.files) or "none"
            raise fail("input.invalid", f"'{part.name}' isn't a file input of '{command.name}' (its file inputs: "
                       f"{accepted}); send the other fields as JSON in the '{INPUT_PART}' part", fix=help_line)
        if not part.data:
            raise fail("input.invalid", f"the file '{part.name}' is empty", fix=help_line)
        raw[part.name] = str(files.store(part.name, part.filename, part.data))
    return raw


__all__ = ["CancelData", "INPUT_PART", "Part", "Session", "built_web"]
