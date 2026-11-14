"""The stage graph (ADR 0005, spec §5): input hashes, derived status, and running Stages.

A Stage's input hash covers its declared files, project settings, parameters and its upstream Stages' input hashes,
so a change anywhere above it makes it stale. The hash an output was built from is stored beside the output, in
`work/<stage>/` or `out/<stage>/`, never in a committed data file. `failed` lives only in the git-ignored
`.kiripix/failures/`.

A Stage's input image is the image of its first upstream Stage that declares one, and its clicks record that image's
hash. An Override is a Decision of the Stage whose image it paints: core paints it over the image after the run
function, so every Stage reading the image sees it, and records the unpainted image's hash in the stamp. A built Stage
with any current click or Override recorded on another image than that is needs-review.

A Runner call is pinned per call (ADR 0002, `kiripix.core.pinning`). `run` never makes one: a Stage whose call has no
pinned result is needs-input, and `run --rerun` makes it. A pinned result no `accept` has listed puts the built Stage in
needs-review. The pinned results of a Stage's current calls are part of its input hash.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ContextManager, Literal, TypeVar

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
from pydantic import BaseModel

from kiripix.checks import Finding, Position
from kiripix.core import atomic, cancel, journal, pinning, warm
from kiripix.core.assets import HISTORY_FILE, Asset, list_assets
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.core.hashing import HashCache, hash_bytes, hash_json
from kiripix.core.images import load_rgba, save_png
from kiripix.core.kinds import get_kind
from kiripix.core.locks import GPU_LOCK, asset_lock, hold
from kiripix.core.project import Project
from kiripix.core.settings import settings_document
from kiripix.ops import overlay
from kiripix.recipes.base import COMPUTED_SETTINGS, CurrentDecision, LazyMap, NeedsInput, RunnerCall, Scalar, StageFailure, StageRun, StageSpec
import kiripix.ops as ops_package
import kiripix.recipes as recipes_package
import kiripix.runners as runners_package
from kiripix.runners import Device, RunnerError, pull, runners, weights_dir

Hook = TypeVar("Hook")

Status = Literal["todo", "stale", "done", "needs-input", "needs-review", "failed"]
Outcome = Literal["done", "skipped", "failed", "needs-input", "needs-review", "cancelled"]

STAMP_FILE = ".stage.json"
REPLAYED_ON_CHANGED_IMAGE = "clicks or Overrides were replayed onto a changed image"
RUNNER_NOT_RUN = "Runner not run yet"
RUNNER_INPUT_CHANGED = "Runner input changed"
RUNNER_RESULT_NEW = "a Runner's new result waits for the Owner"
RUNNER_SAME_RESULT = "the Runner ran and made the same result the Owner already accepted, so there is nothing to rebuild"


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


def gpu_wait_notice(progress: ProgressSink, stage: str | None = None) -> Callable[[str], None]:
    """What `hold` tells when it waits for a warm Runner to unload, as a progress event."""
    return lambda message: progress(ProgressEvent(event="gpu_wait", stage=stage, message=message))


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


def _lookup(document: dict[str, Any], known: Callable[[], dict[str, Any]], dotted: str) -> Any:
    """A setting by dotted path. `document` leaves out optional settings that aren't set; `known()` holds every setting
    (asked only then, as it costs a dump), so an unset one is None and a name that isn't a setting at all (a typo in a
    StageSpec) is an error, not a silent None."""
    value: Any = document
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            break
        value = value[part]
    else:
        return value
    schema: Any = known()
    for part in dotted.split("."):
        if not isinstance(schema, dict) or part not in schema:
            raise KeyError(f"'{dotted}' is not a setting in kiripix.toml (a Stage's inputs name it)")
        schema = schema[part]
    return None


def _recipes_code() -> list[list[Any]]:
    """The recipes' and Ops' source files by name, size and time, so a changed Stage function or an Op it replays
    never reads an old answer."""
    folders = [Path(recipes_package.__file__).parent, Path(ops_package.__file__).parent]
    return [[f"{p.parent.name}/{p.name}", p.stat().st_size, p.stat().st_mtime_ns]
            for folder in folders for p in sorted(folder.glob("*.py"))]


def _runner_roles() -> dict[str, str]:
    """Which Runner is behind each role (`runners.INPAINTER`...): a Stage reads it when it lists its calls."""
    return {name: value for name, value in vars(runners_package).items() if name.isupper() and isinstance(value, str)}


class AssetGraph:
    """The Stages of one Asset, with their input hashes and derived status."""

    def __init__(self, project: Project, asset: Asset, cache: HashCache) -> None:
        self.project = project
        self.asset = asset
        self.kind = get_kind(asset.kind)
        self.cache = cache
        self.failures = Failures(project.state_dir, asset.id)
        self._hashes: dict[str, str] = {}
        self._image_hashes: dict[Path, str] = {}  # for `pin_key`, which a pass over a room's Stages asks hundreds of times
        self._replays: dict[str, journal.Replay] = {}
        self._calls: dict[str, list[RunnerCall]] = {}
        self._files: dict[str, dict[str, Path]] = {}
        self._settings = settings_document(project.settings)
        self._known_settings: dict[str, Any] | None = None
        unknown = sorted(set(asset.settings.stages) - {s.name for s in self.kind.stages})
        if unknown:
            file = project.relative(asset.dir / "asset.toml")
            raise fail(
                "config.unknown_key",
                f"{file}: unknown Stage '{unknown[0]}' under [stages]",
                owner_action=f"Remove [stages.{unknown[0]}] from {file}, or correct its spelling.",
                position=Position(asset=asset.id, file=file, field=f"stages.{unknown[0]}"),
            )

    def stage_with(self, hook: Callable[[StageSpec], Hook | None], does: str, code: str = "probe.not_supported",
                   position: Position | None = None) -> tuple[StageSpec, Hook]:
        """The first Stage of the Kind that has `hook` (such as `lambda s: s.layer_stats`), and that hook. A Kind with no
        such Stage is refused with `code`, saying it has no Stage that `does`, as a Probe or a preview asks for one."""
        for spec in self.kind.stages:
            found = hook(spec)
            if found is not None:
                return spec, found
        raise fail(code, f"a {self.asset.kind} has no Stage that {does}", fix="kiripix describe project",
                   position=position)

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

    def replay(self, stage: str) -> journal.Replay:
        """The Stage's Decision journal, replayed: its current Decisions and whether the journal diverged."""
        if stage not in self._replays:
            path = journal.journal_path(self.asset.dir, stage)
            self._replays[stage] = journal.replay(journal.read_entries(path, self.project.relative(path)))
        return self._replays[stage]

    def files(self, spec: StageSpec) -> dict[str, Path]:
        if spec.name not in self._files:
            found: dict[str, Path] = {}
            for pattern in spec.inputs.files:
                literal = not any(c in pattern for c in "*?[")  # a plain path needs no directory walk
                for path in ([self.asset.dir / pattern] if literal else sorted(self.asset.dir.glob(pattern))):
                    if path.is_file():
                        found[path.relative_to(self.asset.dir).as_posix()] = path
            self._files[spec.name] = found
        return dict(self._files[spec.name])

    def palette_path(self) -> Path:
        return self.project.root / self.project.settings.project.palette

    def _known(self) -> dict[str, Any]:
        """Every setting, unset ones as None: asked only when a setting is missing from the document."""
        if self._known_settings is None:
            self._known_settings = self.project.settings.model_dump(mode="json", by_alias=True)
        return self._known_settings

    def _setting_for_hash(self, name: str) -> Any:
        if name in COMPUTED_SETTINGS:  # not in kiripix.toml: worked out when asked, such as a tool's version (ADR 0010)
            return COMPUTED_SETTINGS[name]()
        if name == "palette":
            path = self.palette_path()
            return {"file": self.project.settings.project.palette,
                    "hash": self.cache.file_hash(path) if path.is_file() else None}
        return _lookup(self._settings, self._known, name)

    def settings(self, spec: StageSpec) -> dict[str, Any]:
        """What a Stage is given (`StageRun.settings`): its hashed `settings`, plus its `given` ones, which aren't inputs."""
        hashed = {name: self.palette_path() if name == "palette" else self._setting_for_hash(name)
                  for name in spec.inputs.settings}
        return {**hashed, **{name: _lookup(self._settings, self._known, name) for name in spec.inputs.given}}

    def input_hash(self, stage: str) -> str:
        if stage not in self._hashes:
            spec = self.spec(stage)
            self._hashes[stage] = hash_json(
                {
                    "kind": self.kind.name,
                    "stage": spec.name,
                    "asset_params": self.asset.settings.params,
                    "params": self.params(spec),
                    "decisions": journal.hashable(self.replay(stage)),
                    "files": {name: self.cache.file_hash(path) for name, path in self.files(spec).items()},
                    "settings": {name: self._setting_for_hash(name) for name in spec.inputs.settings},
                    "upstream": {name: self.input_hash(name) for name in spec.inputs.upstream},
                    **self._pinned_for_hash(spec),
                }
            )
        return self._hashes[stage]

    def _pinned_for_hash(self, spec: StageSpec) -> dict[str, Any]:
        calls = self.runner_calls(spec)
        if not calls:
            return {}
        paths = {self.pin_key(call): self.pinned_path(call) for call in calls}
        return {"pinned": {key: self.cache.file_hash(path) if path.is_file() else None for key, path in paths.items()}}

    def forget_hashes(self) -> None:
        """Forget the hashes worked out so far, after a Runner call added a pinned result or a Stage rebuilt its image."""
        self._hashes.clear()
        self._image_hashes.clear()
        self._calls.clear()
        self._files.clear()

    def _calls_key(self, spec: StageSpec) -> str:
        """What a Stage's Runner calls derive from: its own inputs, every file of its upstream outputs, and which
        results are pinned (a call list can depend on whether an earlier call is pinned)."""
        upstream: dict[str, str] = {}
        for name in spec.inputs.upstream:
            folder = self.output_dir(self.spec(name))
            if folder.is_dir():
                for path in sorted(folder.rglob("*")):
                    if path.is_file():
                        upstream[path.relative_to(self.asset.dir).as_posix()] = self.cache.file_hash(path)
        pins = self.asset.dir / pinning.PINNED_DIR
        pinned = sorted(p.name for p in pins.glob("*.png")) if pins.is_dir() else []
        return hash_json({
            "code": _recipes_code(), "roles": _runner_roles(),
            "kind": self.kind.name, "stage": spec.name, "asset_params": self.asset.settings.params,
            "params": self.params(spec), "decisions": journal.hashable(self.replay(spec.name)),
            "files": {name: self.cache.file_hash(path) for name, path in self.files(spec).items()},
            "settings": {name: self._setting_for_hash(name) for name in spec.inputs.settings},
            "upstream": upstream, "pinned": pinned,
        })

    def runner_calls(self, spec: StageSpec) -> list[RunnerCall]:
        """The Runner calls the Stage's current Decisions need, as far as its upstream outputs are built. Working them
        out can replay a whole lift, so the answer is kept by what it derives from (a computation, not a status)."""
        if spec.runner_calls is None:
            return []
        if spec.name in self._calls:
            return self._calls[spec.name]
        if not self.replay(spec.name).current:  # nothing decided: the cheap answer needs no cache
            calls = spec.runner_calls(self.stage_run(spec, self.output_dir(spec)))
        else:
            name = f"runner-calls:{self.asset.id}:{spec.name}"
            key = self._calls_key(spec)
            stored = self.cache.derived(name, key)
            if stored is not None:
                # Images are kept relative to the Project, so a moved or re-cloned Project reads its own files.
                calls = [RunnerCall(runner=c["runner"], image=self.project.root / c["image"], params=c["params"],
                                    decisions=c["decisions"]) for c in stored]
            else:
                calls = spec.runner_calls(self.stage_run(spec, self.output_dir(spec)))
                if all(c.image.is_relative_to(self.project.root) for c in calls):
                    self.cache.remember(name, key, [
                        {"runner": c.runner, "image": c.image.relative_to(self.project.root).as_posix(),
                         "params": c.params, "decisions": c.decisions} for c in calls])
        self._calls[spec.name] = calls
        return calls

    def pin_key(self, call: RunnerCall) -> str:
        if call.image not in self._image_hashes:
            self._image_hashes[call.image] = self.cache.file_hash(call.image)
        return pinning.key(call, self._image_hashes[call.image])

    def pinned_path(self, call: RunnerCall) -> Path:
        return pinning.result_path(self.asset.dir, self.pin_key(call))

    def missing_calls(self, spec: StageSpec) -> list[RunnerCall]:
        """The Stage's Runner calls with no pinned result."""
        return [call for call in self.runner_calls(spec) if not self.pinned_path(call).is_file()]

    def unreviewed_pins(self, spec: StageSpec) -> list[str]:
        """The Stage's pinned results that no `accept` has listed, each as `<key>:<hash of the result>`: so a call made
        with other inputs, or a result that changed, is reviewed again, and one not made yet can't be accepted ahead of
        time."""
        accepted = self.replay(spec.name).accepted
        accepted_keys = {entry.split(":", 1)[0] for entry in accepted}
        paths = {self.pin_key(call): self.pinned_path(call) for call in self.runner_calls(spec)}
        results = []
        for key, path in paths.items():
            if not path.is_file():
                continue
            # The key doesn't hold the device (ADR 0002), and a Runner's bytes differ a little between the CPU and the
            # GPU (BiRefNet: 1 level of alpha in about 14 of a million pixels). So a key the Owner accepted stays
            # accepted when it is pinned again, as long as the PNG is still the bytes the Runner made for it.
            png_hash = self.cache.file_hash(path)
            if key in accepted_keys and pinning.is_as_made(self.asset.dir, key, png_hash):
                continue
            results.append(f"{key}:{png_hash}")
        return [result for result in results if result not in accepted]

    def output_dir(self, spec: StageSpec) -> Path:
        return self.asset.dir / spec.output_root / spec.name

    def input_image(self, spec: StageSpec) -> tuple[StageSpec, Path] | None:
        """The upstream Stage whose image this Stage's clicks and Overrides are made on, and that image's path."""
        for name in spec.inputs.upstream:
            upstream = self.spec(name)
            if upstream.image is not None:
                return upstream, self.output_dir(upstream) / upstream.image
        return None

    def image_hash(self, spec: StageSpec) -> str | None:
        """The hash of the Stage's input image as built, without Overrides; None if there is none yet."""
        source = self.input_image(spec)
        if source is None or not source[1].is_file():
            return None
        return self.cache.file_hash(source[1])

    def unpainted_hash(self, spec: StageSpec) -> str | None:
        """The hash of the Stage's image as its run function made it, before its Overrides; None if not built."""
        value = self._stamp(spec).get("unpainted_hash")
        return str(value) if value is not None else None

    def replayed_on_other_images(self, spec: StageSpec) -> list[tuple[CurrentDecision, str]]:
        """The current Decisions recorded on an image other than the one they apply to now, each with that image's
        hash: a click's is the Stage's input image, an Override's is the Stage's own image before its Overrides."""
        clicked_on, painted_on = self.image_hash(spec), self.unpainted_hash(spec)
        moved = []
        for decision in self.replay(spec.name).current:
            current = painted_on if decision.name == journal.OVERRIDE else clicked_on
            if decision.image_hash is not None and current is not None and decision.image_hash != current:
                moved.append((decision, current))
        return moved

    def moved_inputs(self, spec: StageSpec) -> list[tuple[CurrentDecision, dict[str, Any]]]:
        """The Decisions a Stage's own `review` function says were made on inputs that have moved (none without one)."""
        if spec.review is None:
            return []
        return spec.review(self.stage_run(spec, self.output_dir(spec)))

    def stage_run(self, spec: StageSpec, output_dir: Path,
                  progress: Callable[[int, int, str], None] | None = None) -> StageRun:
        """What the Stage's run, `needs_input` and `check` functions are handed."""
        return StageRun(
            asset_id=self.asset.id,
            asset_dir=self.asset.dir,
            output_dir=output_dir,
            files=self.files(spec),
            upstream={name: self.output_dir(self.spec(name)) for name in spec.inputs.upstream},
            params=self.params(spec),
            settings=self.settings(spec),
            progress=progress or (lambda done, total, message: None),
            check_cancel=cancel.check,
            pinned=self.pinned_path,
            decisions=self.replay(spec.name).current,
            asset_params=dict(self.asset.settings.params),
            upstream_decisions=LazyMap(spec.inputs.upstream, lambda name: self.replay(name).current),
            upstream_params=LazyMap(spec.inputs.upstream, lambda name: self.params(self.spec(name))),
        )

    def needs_input(self, spec: StageSpec) -> NeedsInput | None:
        """Why the Stage can't run until the Owner acts, from its inputs alone, or until its Runner calls are made."""
        if spec.needs_input is not None:
            waiting = spec.needs_input(self.stage_run(spec, self.output_dir(spec)))
            if waiting is not None:
                return waiting
        missing = self.missing_calls(spec)
        if not missing:
            return None
        changed = any(pinning.was_made_before(self.asset.dir, spec.name, call) for call in missing)
        return NeedsInput(RUNNER_INPUT_CHANGED if changed else RUNNER_NOT_RUN,
                          command=f"kiripix run {self.asset.id} {spec.name} --rerun")

    def check(self, spec: StageSpec) -> list[Finding]:
        """The Stage's Checks on its built output; nothing when it has no output."""
        if spec.check is None or self.built_hash(spec) is None:
            return []
        return spec.check(self.stage_run(spec, self.output_dir(spec)))

    def _stamp(self, spec: StageSpec) -> dict[str, Any]:
        """The stamp beside a complete output; empty when there is none."""
        try:
            stamp = json.loads((self.output_dir(spec) / STAMP_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return stamp if isinstance(stamp, dict) else {}

    def built_hash(self, spec: StageSpec) -> str | None:
        """The input hash the current output was built from, or None if there is no complete output."""
        value = self._stamp(spec).get("input_hash")
        return str(value) if value is not None else None

    def state(self, stage: str) -> StageState:
        spec = self.spec(stage)
        if spec.run is None:
            when = f"until {spec.available_from}" if spec.available_from else "yet"
            return StageState(stage=stage, status="needs-input",
                              reason=f"the {self.kind.name} Stage '{stage}' is not implemented {when}")
        if self.replay(stage).divergent:
            return StageState(stage=stage, status="needs-review", reason=journal.DIVERGENT)
        waiting = self.needs_input(spec)
        if waiting is not None:
            return StageState(stage=stage, status="needs-input", reason=waiting.reason)
        current = self.input_hash(stage)
        failure = self.failures.get(stage, current)
        if failure is not None:
            return StageState(stage=stage, status="failed", reason=failure)
        built = self.built_hash(spec)
        if built is None:
            return StageState(stage=stage, status="todo")
        if built != current:
            return StageState(stage=stage, status="stale", reason="an input changed since the output was built")
        if self.replayed_on_other_images(spec):
            return StageState(stage=stage, status="needs-review", reason=REPLAYED_ON_CHANGED_IMAGE)
        if self.unreviewed_pins(spec):
            return StageState(stage=stage, status="needs-review", reason=RUNNER_RESULT_NEW)
        if self.moved_inputs(spec):
            return StageState(stage=stage, status="needs-review", reason=spec.review_reason)
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
            cancel.sleep(0.05)


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
    def __init__(self, graph: AssetGraph, progress: ProgressSink, wait: float, command_line: str,
                 cpu: bool = False, keep_warm: bool = False, force: bool = False) -> None:
        self.force = force
        self.graph = graph
        self.progress = progress
        self.wait = wait
        self.command_line = command_line
        self.cpu = cpu
        self.keep_warm = keep_warm
        self.gpu_unused: str | None = None  # a call just made left the GPU unused, and why
        self.runner_seconds: dict[str, float] = {}  # per Stage: what its Runner calls took, less any wait for a lock
        self.failure_findings: dict[str, tuple[str | None, str | None, str | None]] = {}  # per Stage: a failure's code, owner_action, fix
        self._lock_wait = 0.0
        self._loaded_seconds: dict[str, float] = {}  # per Runner: its load, until its first call's history entry

    def _gpu_lock(self) -> list[str]:
        return [] if self.cpu else [GPU_LOCK]

    def _hold_gpu(self, stage: str, needed: bool = True) -> ContextManager[None]:
        return hold(self.graph.project.state_dir, self._gpu_lock() if needed else [], self.wait, self.command_line,
                    on_wait=gpu_wait_notice(self.progress, stage))

    def make_runner_calls(self, spec: StageSpec) -> str | None:
        """Make the Stage's Runner calls that have no pinned result, and pin each as it finishes, so a cancel loses only
        the call it stopped. One Runner is loaded at a time, under the GPU lock, and unloaded after use, except that
        `serve` makes them on its warm Runner while it can have the lock. A call that depends on an earlier one's pinned
        result (ticket 0039) isn't listed until that is pinned, so it goes on in rounds until the Stage lists none
        missing; a call is never made twice in one run. Returns why they failed, or None."""
        graph = self.graph
        device: Device = "cpu" if self.cpu else "auto"
        attempted: set[str] = set()
        started = time.monotonic()
        self._lock_wait = 0.0
        try:
            while True:
                missing = [c for c in graph.missing_calls(spec) if graph.pin_key(c) not in attempted]
                if not missing:
                    break
                attempted.update(graph.pin_key(c) for c in missing)
                self._make_round(spec, missing, device)
                graph.forget_hashes()  # the pinned results just made can add calls and change keys
        except RunnerError as error:
            return str(error)
        finally:
            graph.forget_hashes()
            # The Stage's `duration_s` covers all of it: pulling, loading, the calls and unloading.
            took = time.monotonic() - started - self._lock_wait
            self.runner_seconds[spec.name] = self.runner_seconds.get(spec.name, 0.0) + max(took, 0.0)
        return None

    def took(self, stage: str, forget: bool = False) -> float | None:
        """The seconds the Stage's Runner calls took in this run, or None when it made none."""
        seconds = self.runner_seconds.pop(stage, None) if forget else self.runner_seconds.get(stage)
        return None if seconds is None else round(seconds, 3)

    def _make_round(self, spec: StageSpec, missing: list[RunnerCall], device: Device) -> None:
        graph = self.graph
        for runner_id in dict.fromkeys(call.runner for call in missing):
            runner = runners()[runner_id]
            directory = weights_dir(graph.project.state_dir, runner)
            self.progress(ProgressEvent(event="runner_start", stage=spec.name, message=runner_id))
            pull(directory, runner, cancel.check)
            calls = [c for c in missing if c.runner == runner_id]
            if self.keep_warm and not self.cpu and runner.can_stay_warm:
                calls = self._warm_calls(spec, calls)
            if not calls:
                continue
            with ExitStack() as stack:
                waited = time.monotonic()
                stack.enter_context(self._hold_gpu(spec.name))
                self._lock_wait += time.monotonic() - waited
                stack.enter_context(warm.one_runner_loaded())
                loading = time.monotonic()
                warm.load_runner(runner, directory, device)
                self._loaded_seconds[runner_id] = round(time.monotonic() - loading, 3)
                try:
                    for call in calls:
                        self._call(spec, call)
                finally:
                    runner.unload()

    def _warm_calls(self, spec: StageSpec, calls: list[RunnerCall]) -> list[RunnerCall]:
        """Make the calls on the warm Runner. Returns those it couldn't because the GPU lock is busy: the cold path waits
        for it as `--wait` says, and asks another process's warm Runner to let go."""
        for index, call in enumerate(calls):
            try:
                self._call(spec, call, on_warm=True)
            except KiripixError as error:
                if error.exit_code != ExitCode.BUSY:
                    raise
                return calls[index:]
        return []

    def _call(self, spec: StageSpec, call: RunnerCall, on_warm: bool = False) -> None:
        graph = self.graph
        runner = runners()[call.runner]
        started = time.monotonic()
        device_used = runner.device_used
        loaded: list[float] = []  # the warm path's load, if this call made it

        def history(outcome: str, **extra: Any) -> None:
            # A pinned result's `params` are in `pinned/<key>.json`; only a call with no pinned result keeps them here.
            params = {} if "key" in extra else {"params": call.params}
            load_s = self._loaded_seconds.pop(call.runner, None)
            if load_s is None and loaded:
                load_s = loaded[0]
            if load_s is not None:
                extra = {"load_s": load_s, **extra}
            atomic.append_jsonl(graph.asset.dir / HISTORY_FILE, {
                "time": _now(), "stage": spec.name, "runner": call.runner, "weights_hash": runner.weights_hash,
                **params, "device": device_used,
                "duration_s": round(time.monotonic() - started, 3), "outcome": outcome, **extra})

        def read_image() -> np.ndarray:
            return load_rgba(call.image, graph.project.relative(call.image))

        cancel.check()
        try:
            if on_warm:
                result, _, device_used = warm.warm_call(runner, graph.project.state_dir, "auto",
                                                        graph.cache.file_hash(call.image), read_image, call.params,
                                                        self.command_line, loaded)
            else:
                result = runner.call(read_image(), call.params, cancel.check)
                device_used = runner.device_used
            self.gpu_unused = runner.gpu_unused or self.gpu_unused
            pinning.store(graph.asset.dir, spec.name, call, graph.pin_key(call), graph.cache.file_hash(call.image),
                          result, device=device_used, licence=runner.licence, time=_now())
        except (KeyboardInterrupt, cancel.Cancelled):
            history("cancelled")
            raise
        except RunnerError as error:
            history("failed", message=str(error))
            raise
        history("done", key=graph.pin_key(call))

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

    def _paint_overrides(self, spec: StageSpec, building: Path) -> str | None:
        """Paint the Stage's current Overrides over the image it just built, in order. Returns the hash of the image
        as the run function made it, which the Overrides are checked against; None for a Stage without an image."""
        graph = self.graph
        if spec.image is None:
            return None
        image_path = building / spec.image
        unpainted = hash_bytes(image_path.read_bytes())
        overrides = [d for d in graph.replay(spec.name).current if d.name == journal.OVERRIDE]
        if not overrides:
            return unpainted
        try:
            image = load_rgba(image_path, spec.image)
            for override in overrides:
                path = journal.override_path(graph.asset.dir, str(override.data["png"]))
                painted = load_rgba(path, graph.project.relative(path))
                if painted.shape != image.shape:
                    raise StageFailure(
                        f"the Override {path.name} is {painted.shape[1]}x{painted.shape[0]} but the {spec.name} "
                        f"image is now {image.shape[1]}x{image.shape[0]}; undo it with "
                        f"kiripix undo {graph.asset.id} {spec.name}")
                image = overlay(image, painted)
        except KiripixError as error:
            raise StageFailure(error.findings[0].message) from None
        save_png(image_path, image)
        return unpainted

    def execute(self, spec: StageSpec) -> tuple[StageRunResult, list[Finding]]:
        """Run the Stage, paint its Overrides over its image, run its `after_overrides` hook, then run its Checks on
        the result; their findings come back beside the result."""
        assert spec.run is not None
        graph = self.graph
        input_hash = graph.input_hash(spec.name)
        params = graph.params(spec)
        final = graph.output_dir(spec)
        building = final.with_name(f".tmp-{spec.name}-{uuid.uuid4().hex[:8]}")
        building.mkdir(parents=True)
        checked: list[Finding] = []

        def report(done: int, total: int, message: str) -> None:
            self.progress(ProgressEvent(event="stage_progress", stage=spec.name, done=done, total=total,
                                        message=message))
            cancel.check()

        started = time.monotonic()

        def result(outcome: Outcome, message: str | None = None) -> StageRunResult:
            own = time.monotonic() - started
            return StageRunResult(asset=graph.asset.id, stage=spec.name, outcome=outcome, input_hash=input_hash,
                                  duration_s=round(own + self.runner_seconds.get(spec.name, 0.0), 3), message=message)

        try:
            context = graph.stage_run(spec, building, progress=report)
            old = final if (final / STAMP_FILE).is_file() else None
            context = replace(context, cpu=self.cpu, previous=old, forced=self.force, notes=[])
            with self._hold_gpu(spec.name, spec.gpu):
                spec.run(context)
            cancel.check()
            unpainted = self._paint_overrides(spec, building)
            if spec.after_overrides is not None:
                spec.after_overrides(context)
                cancel.check()
            if spec.check is not None:
                checked = spec.check(context)
            stamp = {"stage": spec.name, "input_hash": input_hash, "finished": _now()}
            if unpainted is not None:
                stamp["unpainted_hash"] = unpainted
            atomic.write_json(building / STAMP_FILE, stamp)
            _swap_into_place(building, final)
            graph.forget_hashes()
            graph.failures.clear(spec.name)
            outcome = result("done", "; ".join(context.notes) or None)
        except (KeyboardInterrupt, cancel.Cancelled):
            self._history(spec, params, result("cancelled", "cancelled by the user"))
            raise
        except KiripixError:
            raise  # busy GPU: not a Stage failure
        except StageFailure as error:
            self.failure_findings[spec.name] = (error.code, error.owner_action, error.fix)
            outcome = result("failed", str(error))
        except Exception as error:  # noqa: BLE001 - a Stage's own bug is that Stage's failure
            outcome = result("failed", f"{type(error).__name__}: {error}")
        finally:
            shutil.rmtree(building, ignore_errors=True)
            self.runner_seconds.pop(spec.name, None)
        if outcome.outcome == "failed":
            graph.failures.record(spec.name, input_hash, outcome.message or "failed")
        self._history(spec, params, outcome)
        return outcome, checked


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
    rerun: bool = False,
    cpu: bool = False,
    keep_warm: bool = False,
) -> AssetRun:
    """Run the Asset's stale and todo Stages in order, or one Stage; stop at the first that can't finish.

    With `rerun`, a Stage's Runner calls with no pinned result are made first, so it lands in needs-review. With `cpu`,
    Runners run on the CPU and no GPU lock is taken. With `keep_warm`, in `serve`, those calls use its warm Runner.

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
    runner = _Runner(graph, progress, wait, command_line, cpu, keep_warm, force)
    results: list[StageRunResult] = []
    findings: list[Finding] = []
    exit_code = ExitCode.OK
    for index, spec in enumerate(specs):
        cancel.check()
        state = graph.state(spec.name)
        called = rerun and state.status == "needs-input" and state.reason in (RUNNER_NOT_RUN, RUNNER_INPUT_CHANGED)
        if called:
            problem = runner.make_runner_calls(spec)
            if runner.gpu_unused is not None:
                findings.append(Finding(code="runner.gpu_unused", severity="warning", message=runner.gpu_unused,
                                        position=Position(asset=asset.id, stage=spec.name), fix="uv sync"))
                runner.gpu_unused = None
            if problem is not None:
                results.append(StageRunResult(asset=asset.id, stage=spec.name, outcome="failed",
                                              input_hash=graph.input_hash(spec.name), message=problem,
                                              duration_s=runner.took(spec.name, forget=True)))
                findings.append(
                    Finding(
                        code="stage.failed",
                        message=f"{asset.id} {spec.name} failed: {problem}",
                        position=Position(asset=asset.id, stage=spec.name),
                        fix=f"kiripix run {asset.id} {spec.name} --rerun",
                    )
                )
                exit_code = _worse(exit_code, ExitCode.ERROR)
                break
            state = graph.state(spec.name)
        if state.status == "needs-input":
            results.append(StageRunResult(asset=asset.id, stage=spec.name, outcome="needs-input",
                                          input_hash=graph.input_hash(spec.name), message=state.reason))
            waiting = graph.needs_input(spec) if spec.run is not None else None
            fix = waiting.command if waiting else None
            owner_action = None
            if fix is None:
                owner_action = waiting.owner_action if waiting and waiting.owner_action else \
                    f"{asset.id} waits on the Owner: {state.reason}."
            findings.append(
                Finding(
                    code="stage.needs_input",
                    message=f"{asset.id} {spec.name}: needs-input: {state.reason}",
                    position=Position(asset=asset.id, stage=spec.name),
                    fix=fix,
                    owner_action=owner_action,
                )
            )
            exit_code = _worse(exit_code, ExitCode.NEEDS_OWNER)
            break
        if state.status == "needs-review":
            results.append(StageRunResult(asset=asset.id, stage=spec.name, outcome="needs-review",
                                          input_hash=graph.input_hash(spec.name), message=state.reason,
                                          duration_s=runner.took(spec.name, forget=True)))
            findings.append(_needs_review(asset, spec.name, state.reason))
            exit_code = _worse(exit_code, ExitCode.NEEDS_OWNER)
            break
        if state.status == "done" and not force:
            results.append(StageRunResult(asset=asset.id, stage=spec.name, outcome="skipped",
                                          input_hash=graph.input_hash(spec.name),
                                          message=RUNNER_SAME_RESULT if called else None,
                                          duration_s=runner.took(spec.name, forget=True)))
            continue
        progress(ProgressEvent(event="stage_start", stage=spec.name, done=index, total=len(specs)))
        outcome, checked = runner.execute(spec)
        progress(ProgressEvent(event="stage_end", stage=spec.name, done=index + 1, total=len(specs),
                               message=outcome.outcome))
        findings.extend(checked)
        if any(f.severity == "error" for f in checked):
            exit_code = _worse(exit_code, ExitCode.CHECK_FAILED)
        if outcome.outcome == "failed":
            results.append(outcome)
            code, owner_action, own_fix = runner.failure_findings.pop(spec.name, (None, None, None))
            findings.append(
                Finding(
                    code=code or "stage.failed",
                    message=f"{asset.id} {spec.name} failed: {outcome.message}",
                    position=Position(asset=asset.id, stage=spec.name),
                    # A finding carries exactly one of fix and owner_action; the owner's action wins.
                    fix=None if owner_action else (own_fix or f"kiripix run {asset.id} {spec.name}"),
                    owner_action=owner_action,
                )
            )
            # A failure only the Owner can clear (Blender missing, a rig to make) needs the Owner, not another run.
            exit_code = _worse(exit_code, ExitCode.NEEDS_OWNER if owner_action else ExitCode.ERROR)
            break
        after = graph.state(spec.name)
        if after.status == "needs-review":  # replayed clicks or Overrides onto a changed image
            results.append(outcome.model_copy(update={"outcome": "needs-review", "message": after.reason}))
            findings.append(_needs_review(asset, spec.name, after.reason))
            exit_code = _worse(exit_code, ExitCode.NEEDS_OWNER)
            break
        results.append(outcome)
    cache.save()
    return AssetRun(results=results, findings=findings, exit_code=exit_code)


def _needs_review(asset: Asset, stage: str, reason: str | None) -> Finding:
    return Finding(
        code="stage.needs_review",
        message=f"{asset.id} {stage}: needs-review: {reason}",
        position=Position(asset=asset.id, stage=stage),
        owner_action=f"Review {asset.id} {stage} ({reason}), then accept it: kiripix accept {asset.id} {stage}",
    )


_SEVERITY = {ExitCode.OK: 0, ExitCode.NEEDS_OWNER: 1, ExitCode.BUSY: 2, ExitCode.CHECK_FAILED: 3, ExitCode.ERROR: 4}


def _worse(a: ExitCode, b: ExitCode) -> ExitCode:
    """The more serious exit code: error, then check failed, then busy, then needs the owner."""
    return a if _SEVERITY[a] >= _SEVERITY[b] else b


def run_all(
    project: Project,
    cache: HashCache,
    *,
    kind: str | None,
    force: bool,
    progress: ProgressSink,
    wait: float,
    command_line: str,
    rerun: bool = False,
    cpu: bool = False,
    keep_warm: bool = False,
) -> AssetRun:
    """Run every Asset (of one Kind, if given), locking one Asset at a time. One Asset stopping doesn't stop the rest.

    The exit code is the most serious one (see `_worse`).
    """
    assets, findings = list_assets(project)
    exit_code = ExitCode.ERROR if findings else ExitCode.OK
    results: list[StageRunResult] = []
    for asset in assets:
        if kind is not None and asset.kind != kind:
            continue
        cancel.check()
        progress(ProgressEvent(event="asset_start", stage=None, message=asset.id))
        try:
            with hold(project.state_dir, [asset_lock(asset.id)], wait, command_line):
                run = run_asset(project, asset, cache, stage=None, force=force, progress=progress, wait=wait,
                                command_line=command_line, rerun=rerun, cpu=cpu, keep_warm=keep_warm)
        except KiripixError as error:
            findings.extend(error.findings)
            code = error.exit_code
        else:
            results.extend(run.results)
            findings.extend(run.findings)
            code = run.exit_code
        exit_code = _worse(exit_code, code)
    return AssetRun(results=results, findings=findings, exit_code=exit_code)
