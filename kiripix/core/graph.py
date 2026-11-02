"""The stage graph (ADR 0005, spec §5): input hashes, derived status, and running Stages.

A Stage's input hash covers its declared files, project settings, parameters and its upstream Stages' input hashes,
so a change anywhere above it makes it stale. The hash an output was built from is stored beside the output, in
`work/<stage>/` or `out/<stage>/`, never in a committed data file. `failed` lives only in the git-ignored
`.kiripix/failures/`.
"""

import json
import shutil
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from kiripix.checks import Finding, Position
from kiripix.core import atomic
from kiripix.core.assets import HISTORY_FILE, Asset, list_assets
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.core.hashing import HashCache, hash_json
from kiripix.core.kinds import get_kind
from kiripix.core.locks import GPU_LOCK, asset_lock, hold
from kiripix.core.project import Project
from kiripix.core.settings import settings_document
from kiripix.recipes.base import Scalar, StageFailure, StageRun, StageSpec

Status = Literal["todo", "stale", "done", "needs-input", "needs-review", "failed"]
Outcome = Literal["done", "skipped", "failed", "needs-input", "cancelled"]

STAMP_FILE = ".stage.json"


class StageState(BaseModel):
    stage: str
    status: Status
    reason: str | None = None


class StageRunResult(BaseModel):
    asset: str
    stage: str
    outcome: Outcome
    input_hash: str
    duration_s: float | None = None
    message: str | None = None


class ProgressEvent(BaseModel):
    """One progress event, streamed on stderr with `--progress=jsonl`."""

    event: str
    stage: str | None = None
    done: int | None = None
    total: int | None = None
    message: str | None = None


ProgressSink = Callable[[ProgressEvent], None]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Failures:
    """The last failure of each Stage of one Asset, with the input hash it failed on. Cache only."""

    def __init__(self, state_dir: Path, asset_id: str) -> None:
        self._path = state_dir / "failures" / f"{asset_id}.json"
        try:
            self._entries: dict[str, dict[str, str]] = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._entries = {}

    def get(self, stage: str, input_hash: str) -> str | None:
        entry = self._entries.get(stage)
        return entry["message"] if entry and entry["input_hash"] == input_hash else None

    def record(self, stage: str, input_hash: str, message: str) -> None:
        self._entries[stage] = {"input_hash": input_hash, "message": message, "time": _now()}
        atomic.write_json(self._path, self._entries)

    def clear(self, stage: str) -> None:
        if self._entries.pop(stage, None) is not None:
            atomic.write_json(self._path, self._entries)


def _lookup(document: dict[str, Any], dotted: str) -> Any:
    value: Any = document
    for part in dotted.split("."):
        value = value[part]
    return value


class AssetGraph:
    """The Stages of one Asset, with their input hashes and derived status."""

    def __init__(self, project: Project, asset: Asset, cache: HashCache) -> None:
        self.project = project
        self.asset = asset
        self.kind = get_kind(asset.kind)
        self.cache = cache
        self.failures = Failures(project.state_dir, asset.id)
        self._hashes: dict[str, str] = {}
        self._settings = settings_document(project.settings)
        unknown = sorted(set(asset.settings.stages) - {s.name for s in self.kind.stages})
        if unknown:
            file = project.relative(asset.dir / "asset.toml")
            raise fail(
                "config.unknown_key",
                f"{file}: unknown Stage '{unknown[0]}' under [stages]",
                owner_action=f"Remove [stages.{unknown[0]}] from {file}, or correct its spelling.",
                position=Position(asset=asset.id, file=file, field=f"stages.{unknown[0]}"),
            )

    def spec(self, stage: str) -> StageSpec:
        spec = self.kind.stage(stage)
        if spec is None:
            names = ", ".join(s.name for s in self.kind.stages)
            raise fail(
                "stage.unknown",
                f"a {self.kind.name} has no Stage '{stage}'; its Stages are {names}",
                fix=f"kiripix describe {self.kind.name}",
            )
        return spec

    def params(self, spec: StageSpec) -> dict[str, Scalar]:
        """The Stage's parameters: declared defaults, overridden by `[stages.<stage>]` in `asset.toml`."""
        overrides = self.asset.settings.stages.get(spec.name, {})
        declared = {p.name: p for p in spec.params}
        file = self.project.relative(self.asset.dir / "asset.toml")
        findings = []
        for name, value in overrides.items():
            problem = f"unknown parameter '{name}'" if name not in declared else declared[name].problem(value)
            if problem:
                findings.append(
                    Finding(
                        code="config.invalid",
                        message=f"{file}: stages.{spec.name}.{name}: {problem}",
                        position=Position(asset=self.asset.id, stage=spec.name, file=file,
                                          field=f"stages.{spec.name}.{name}"),
                        owner_action=f"Fix stages.{spec.name}.{name} in {file}: {problem}.",
                    )
                )
        if findings:
            raise KiripixError(findings)
        result: dict[str, Scalar] = {p.name: p.default for p in spec.params if p.default is not None}
        result.update(overrides)
        return result

    def files(self, spec: StageSpec) -> dict[str, Path]:
        found: dict[str, Path] = {}
        for pattern in spec.inputs.files:
            for path in sorted(self.asset.dir.glob(pattern)):
                if path.is_file():
                    found[path.relative_to(self.asset.dir).as_posix()] = path
        return found

    def palette_path(self) -> Path:
        return self.project.root / self.project.settings.project.palette

    def _setting_for_hash(self, name: str) -> Any:
        if name == "palette":
            path = self.palette_path()
            return {"file": self.project.settings.project.palette,
                    "hash": self.cache.file_hash(path) if path.is_file() else None}
        return _lookup(self._settings, name)

    def settings(self, spec: StageSpec) -> dict[str, Any]:
        return {name: self.palette_path() if name == "palette" else _lookup(self._settings, name)
                for name in spec.inputs.settings}

    def input_hash(self, stage: str) -> str:
        if stage not in self._hashes:
            spec = self.spec(stage)
            self._hashes[stage] = hash_json(
                {
                    "kind": self.kind.name,
                    "stage": spec.name,
                    "asset_params": self.asset.settings.params,
                    "params": self.params(spec),
                    "files": {name: self.cache.file_hash(path) for name, path in self.files(spec).items()},
                    "settings": {name: self._setting_for_hash(name) for name in spec.inputs.settings},
                    "upstream": {name: self.input_hash(name) for name in spec.inputs.upstream},
                }
            )
        return self._hashes[stage]

    def output_dir(self, spec: StageSpec) -> Path:
        return self.asset.dir / spec.output_root / spec.name

    def built_hash(self, spec: StageSpec) -> str | None:
        """The input hash the current output was built from, or None if there is no complete output."""
        try:
            stamp = json.loads((self.output_dir(spec) / STAMP_FILE).read_text(encoding="utf-8"))
            return str(stamp["input_hash"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def state(self, stage: str) -> StageState:
        spec = self.spec(stage)
        if spec.run is None:
            when = f"until {spec.available_from}" if spec.available_from else "yet"
            return StageState(stage=stage, status="needs-input",
                              reason=f"the {self.kind.name} Stage '{stage}' is not implemented {when}")
        current = self.input_hash(stage)
        failure = self.failures.get(stage, current)
        if failure is not None:
            return StageState(stage=stage, status="failed", reason=failure)
        built = self.built_hash(spec)
        if built is None:
            return StageState(stage=stage, status="todo")
        if built != current:
            return StageState(stage=stage, status="stale", reason="an input changed since the output was built")
        return StageState(stage=stage, status="done")

    def states(self) -> list[StageState]:
        return [self.state(s.name) for s in self.kind.stages]


def _rename(source: Path, target: Path) -> None:
    for attempt in range(20):
        try:
            source.rename(target)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def _swap_into_place(built: Path, final: Path) -> None:
    """Replace `final` with `built`. If interrupted, the Stage has no stamped output: it shows todo, never done."""
    old = None
    if final.exists():
        old = final.with_name(f".old-{final.name}-{uuid.uuid4().hex[:8]}")
        _rename(final, old)
    _rename(built, final)
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)


def _remove_leftovers(asset: Asset) -> None:
    """Delete half-built outputs left by a killed run. Called with the Asset lock held."""
    for root in (asset.dir / "work", asset.dir / "out"):
        if root.is_dir():
            for path in root.iterdir():
                if path.is_dir() and path.name.startswith((".tmp-", ".old-")):
                    shutil.rmtree(path, ignore_errors=True)


class _Runner:
    def __init__(self, graph: AssetGraph, progress: ProgressSink, wait: float, command_line: str) -> None:
        self.graph = graph
        self.progress = progress
        self.wait = wait
        self.command_line = command_line

    def _history(self, spec: StageSpec, params: dict[str, Scalar], result: StageRunResult) -> None:
        entry: dict[str, Any] = {
            "time": _now(),
            "stage": spec.name,
            "params": params,
            "input_hash": result.input_hash,
            "duration_s": result.duration_s,
            "outcome": result.outcome,
        }
        if result.message:
            entry["message"] = result.message
        atomic.append_jsonl(self.graph.asset.dir / HISTORY_FILE, entry)

    def execute(self, spec: StageSpec) -> StageRunResult:
        assert spec.run is not None
        graph = self.graph
        input_hash = graph.input_hash(spec.name)
        params = graph.params(spec)
        final = graph.output_dir(spec)
        building = final.with_name(f".tmp-{spec.name}-{uuid.uuid4().hex[:8]}")
        building.mkdir(parents=True)

        def report(done: int, total: int, message: str) -> None:
            self.progress(ProgressEvent(event="stage_progress", stage=spec.name, done=done, total=total,
                                        message=message))

        context = StageRun(
            asset_id=graph.asset.id,
            asset_dir=graph.asset.dir,
            output_dir=building,
            files=graph.files(spec),
            upstream={name: graph.output_dir(graph.spec(name)) for name in spec.inputs.upstream},
            params=params,
            settings=graph.settings(spec),
            progress=report,
        )
        started = time.monotonic()

        def result(outcome: Outcome, message: str | None = None) -> StageRunResult:
            return StageRunResult(asset=graph.asset.id, stage=spec.name, outcome=outcome, input_hash=input_hash,
                                  duration_s=round(time.monotonic() - started, 3), message=message)

        try:
            with hold(graph.project.state_dir, [GPU_LOCK] if spec.gpu else [], self.wait, self.command_line):
                spec.run(context)
            atomic.write_json(building / STAMP_FILE, {"stage": spec.name, "input_hash": input_hash,
                                                      "finished": _now()})
            _swap_into_place(building, final)
            graph.failures.clear(spec.name)
            outcome = result("done")
        except KeyboardInterrupt:
            self._history(spec, params, result("cancelled", "cancelled by the user"))
            raise
        except KiripixError:
            raise  # busy GPU: not a Stage failure
        except StageFailure as error:
            outcome = result("failed", str(error))
        except Exception as error:  # noqa: BLE001 - a Stage's own bug is that Stage's failure
            outcome = result("failed", f"{type(error).__name__}: {error}")
        finally:
            shutil.rmtree(building, ignore_errors=True)
        if outcome.outcome == "failed":
            graph.failures.record(spec.name, input_hash, outcome.message or "failed")
        self._history(spec, params, outcome)
        return outcome


class AssetRun(BaseModel):
    results: list[StageRunResult]
    findings: list[Finding]
    exit_code: ExitCode


def run_asset(
    project: Project,
    asset: Asset,
    cache: HashCache,
    *,
    stage: str | None,
    force: bool,
    progress: ProgressSink,
    wait: float,
    command_line: str,
) -> AssetRun:
    """Run the Asset's stale and todo Stages in order, or one Stage; stop at the first that can't finish.

    The caller holds the Asset lock.
    """
    graph = AssetGraph(project, asset, cache)
    _remove_leftovers(asset)
    if stage is not None:
        spec = graph.spec(stage)
        for name in spec.inputs.upstream:
            upstream = graph.state(name)
            if upstream.status != "done":
                raise fail(
                    "stage.upstream_not_done",
                    f"'{stage}' needs '{name}', which is {upstream.status}",
                    fix=f"kiripix run {asset.id}",
                    position=Position(asset=asset.id, stage=stage),
                )
        specs = [spec]
    else:
        specs = list(graph.kind.stages)
    runner = _Runner(graph, progress, wait, command_line)
    results: list[StageRunResult] = []
    findings: list[Finding] = []
    exit_code = ExitCode.OK
    for index, spec in enumerate(specs):
        state = graph.state(spec.name)
        if state.status == "needs-input":
            results.append(StageRunResult(asset=asset.id, stage=spec.name, outcome="needs-input",
                                          input_hash=graph.input_hash(spec.name), message=state.reason))
            findings.append(
                Finding(
                    code="stage.needs_input",
                    message=f"{asset.id} {spec.name}: needs-input: {state.reason}",
                    position=Position(asset=asset.id, stage=spec.name),
                    owner_action=f"{asset.id} waits on the Owner: {state.reason}.",
                )
            )
            exit_code = ExitCode.NEEDS_OWNER
            break
        if state.status == "done" and not force:
            results.append(StageRunResult(asset=asset.id, stage=spec.name, outcome="skipped",
                                          input_hash=graph.input_hash(spec.name)))
            continue
        progress(ProgressEvent(event="stage_start", stage=spec.name, done=index, total=len(specs)))
        outcome = runner.execute(spec)
        progress(ProgressEvent(event="stage_end", stage=spec.name, done=index + 1, total=len(specs),
                               message=outcome.outcome))
        results.append(outcome)
        if outcome.outcome == "failed":
            findings.append(
                Finding(
                    code="stage.failed",
                    message=f"{asset.id} {spec.name} failed: {outcome.message}",
                    position=Position(asset=asset.id, stage=spec.name),
                    fix=f"kiripix run {asset.id} {spec.name}",
                )
            )
            exit_code = ExitCode.ERROR
            break
    cache.save()
    return AssetRun(results=results, findings=findings, exit_code=exit_code)


_SEVERITY = {ExitCode.OK: 0, ExitCode.NEEDS_OWNER: 1, ExitCode.BUSY: 2, ExitCode.CHECK_FAILED: 3, ExitCode.ERROR: 4}


def run_all(
    project: Project,
    cache: HashCache,
    *,
    kind: str | None,
    force: bool,
    progress: ProgressSink,
    wait: float,
    command_line: str,
) -> AssetRun:
    """Run every Asset (of one Kind, if given), locking one Asset at a time. One Asset stopping doesn't stop the rest.

    The exit code is the most serious one: error, then busy, then needs the owner.
    """
    assets, findings = list_assets(project)
    exit_code = ExitCode.ERROR if findings else ExitCode.OK
    results: list[StageRunResult] = []
    for asset in assets:
        if kind is not None and asset.kind != kind:
            continue
        progress(ProgressEvent(event="asset_start", stage=None, message=asset.id))
        try:
            with hold(project.state_dir, [asset_lock(asset.id)], wait, command_line):
                run = run_asset(project, asset, cache, stage=None, force=force, progress=progress, wait=wait,
                                command_line=command_line)
        except KiripixError as error:
            findings.extend(error.findings)
            code = error.exit_code
        else:
            results.extend(run.results)
            findings.extend(run.findings)
            code = run.exit_code
        if _SEVERITY[code] > _SEVERITY[exit_code]:
            exit_code = code
    return AssetRun(results=results, findings=findings, exit_code=exit_code)
