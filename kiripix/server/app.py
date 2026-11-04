"""The REST adapter (spec §10.6): one route per Command, generated from the registry. It holds no logic:
every decision (the token, jobs, parsing, files) is made by `kiripix.commands.Session`.

Every Command is `POST /api/<command path>` (`/api/run`, `/api/op/quantize`) with its input as the JSON body, and answers
with the result envelope, the same bytes `--json` prints. A Command with file inputs also takes a multipart body: an
`input` part with the JSON, and one part per file input, named after its field (ADR 0007). The HTTP status comes from the exit code and the finding
(`http_status`; `schema` documents it).
Around the Commands, the transport routes `schema` lists: progress and "changed" events over SSE, a cancel route and a
route that serves Project files; and the built `web/` app when there is one. Uses only `kiripix.commands`.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from kiripix.commands import (
    API_VERSION,
    REGISTRY,
    Command,
    CancelData,
    Envelope,
    ExitCode,
    Finding,
    KiripixError,
    ProgressEvent,
    Part,
    ProjectWatch,
    error_envelope,
    Session,
    http_status,
)

TOKEN_HEADER = "X-Kiripix-Token"
JOB_HEADER = "X-Kiripix-Job"
EXIT_HEADER = "X-Kiripix-Exit-Code"
_HEARTBEAT_SECONDS = 15


def _sse(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


class Hub:
    """Fans events out to the SSE subscribers. `publish` is safe to call from any thread."""

    def __init__(self) -> None:
        self._closed = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[tuple[str, dict[str, Any]]]] = set()

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[tuple[str, dict[str, Any]]]:
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[tuple[str, dict[str, Any]]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, name: str, data: dict[str, Any]) -> None:
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._deliver, name, data)

    def _deliver(self, name: str, data: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait((name, data))


def _respond(envelope: Envelope[Any], exit_code: int, headers: dict[str, str] | None = None) -> Response:
    return Response(
        content=envelope.model_dump_json(),
        media_type="application/json",
        status_code=http_status(exit_code, envelope.findings),
        headers={EXIT_HEADER: str(int(exit_code)), **(headers or {})},
    )


def _refused(error: KiripixError) -> Response:
    return _respond(error_envelope(error.findings), error.exit_code)


async def _body(request: Request) -> bytes | list[Part]:
    """The request's JSON body, or the parts of a multipart one."""
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        return await request.body()
    parts = []
    try:
        async with request.form() as form:
            for name, value in form.multi_items():
                if isinstance(value, UploadFile):
                    parts.append(Part(name, await value.read(), value.filename or ""))
                else:
                    parts.append(Part(name, value.encode("utf-8")))
    except HTTPException as error:  # Starlette's answer to a malformed multipart body
        finding = Finding(code="input.invalid", message=f"the multipart body can't be read: {error.detail}",
                          fix="kiripix schema")
        raise KiripixError([finding], ExitCode.ERROR) from None
    return parts


def create_app(session: Session, web: Path | None = None) -> FastAPI:
    hub = Hub()
    watch = ProjectWatch(session.root, lambda paths: hub.publish("changed", {"count": len(paths), "paths": paths[:200]}))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        hub.attach(asyncio.get_running_loop())
        watch.start()
        try:
            yield
        finally:
            hub.close()
            watch.stop()
            session.close()

    app = FastAPI(title="Kiripix", version=str(API_VERSION), lifespan=lifespan, docs_url=None, redoc_url=None,
                  openapi_url=None)

    def progress(job: str, command: str, event: ProgressEvent) -> None:
        hub.publish("progress", {"job": job, "command": command, "progress": event.model_dump()})

    def command_route(command: Command[Any, Any]) -> Callable[[Request], Awaitable[Response]]:
        async def call(request: Request) -> Response:
            try:
                job = session.start(command, await _body(request), token=request.headers.get(TOKEN_HEADER),
                                    wait=request.query_params.get("wait"), job_id=request.headers.get(JOB_HEADER),
                                    progress=progress)
            except KiripixError as error:
                return _refused(error)
            try:
                envelope, exit_code = await asyncio.wrap_future(job.result)
            except asyncio.CancelledError:  # the client went away: stop the work it asked for
                job.cancel()
                raise
            hub.publish("job_end", {"job": job.id, "command": command.name, "exit_code": int(exit_code),
                                    "ok": envelope.ok})
            return _respond(envelope, exit_code, headers={JOB_HEADER: job.id})

        return call

    for command in REGISTRY.values():
        app.add_api_route("/api/" + "/".join(command.path), command_route(command), methods=["POST"],
                          name=command.name, summary=command.summary)

    @app.get("/api/events")
    async def events(job: str | None = None) -> StreamingResponse:
        queue = hub.subscribe()

        async def stream() -> AsyncIterator[str]:
            idle = 0
            try:
                yield _sse("hello", {"api_version": API_VERSION})
                while not hub.closed:
                    try:
                        name, data = await asyncio.wait_for(queue.get(), 1.0)
                    except TimeoutError:
                        idle += 1
                        if idle >= _HEARTBEAT_SECONDS:
                            idle = 0
                            yield ": keep-alive\n\n"
                        continue
                    idle = 0
                    if job is None or data.get("job") == job:
                        yield _sse(name, data)
            finally:
                hub.unsubscribe(queue)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel(job_id: str) -> Response:
        try:
            return _respond(Envelope[CancelData](ok=True, data=session.cancel(job_id)), ExitCode.OK)
        except KiripixError as error:
            return _refused(error)

    @app.get("/files/{relative:path}")
    async def files(relative: str) -> Response:
        try:
            return FileResponse(session.file(relative), headers={"Cache-Control": "no-cache"})
        except KiripixError as error:
            return _refused(error)

    if web is not None and web.is_dir():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app


__all__ = ["EXIT_HEADER", "JOB_HEADER", "TOKEN_HEADER", "create_app"]
