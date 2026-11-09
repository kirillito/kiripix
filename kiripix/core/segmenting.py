"""The mask Probes' work (spec §10.1): `segment-preview`, the Mask a click would make, and `flood-preview`, the region
a flood would fill, with nothing recorded or pinned. `serve` keeps segment-preview's Runner warm (`kiripix.core.warm`);
the CLI loads and unloads it like any other call. flood-preview needs no Runner."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from kiripix.checks import Position
from kiripix.core import cancel, warm
from kiripix.core.assets import Asset
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.core.graph import AssetGraph, ProgressSink, gpu_wait_notice
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba
from kiripix.core.kinds import all_runners
from kiripix.core.locks import GPU_LOCK, hold
from kiripix.core.project import Project
from kiripix.ops import flood_region
from kiripix.recipes.base import (BoxCorners, ClickPoint, RunnerCall, SegmentHooks, StageFailure, StageRun,
                                  StageSpec)
from kiripix.runners import Device, EmbeddingRunner, RunnerError, pull, weights_dir


@dataclass(frozen=True)
class SegmentPreview:
    mask: np.ndarray  # on the target grid
    computed: bool  # whether the image's embedding was computed for this call, or found cached
    device: str


def _cold_call(project: Project, runner_id: str, image: np.ndarray, params: dict[str, Any], device: Device, wait: float,
               command_line: str, progress: ProgressSink) -> tuple[np.ndarray, str]:
    runner = all_runners()[runner_id]
    directory = weights_dir(project.state_dir, runner)
    pull(directory, runner, cancel.check)
    locks = [] if device == "cpu" else [GPU_LOCK]
    with hold(project.state_dir, locks, wait, command_line, on_wait=gpu_wait_notice(progress)), warm.one_runner_loaded():
        warm.load_runner(runner, directory, device)
        try:
            return runner.call(image, params, cancel.check), runner.device_used
        finally:
            runner.unload()


def _cold_calls(project: Project, runner_id: str, image: np.ndarray, params: list[dict[str, Any]], device: Device,
                wait: float, command_line: str, progress: ProgressSink) -> tuple[list[np.ndarray], str]:
    """Several calls on one image in one load: an embedding Runner embeds once and decodes each."""
    runner = all_runners()[runner_id]
    directory = weights_dir(project.state_dir, runner)
    pull(directory, runner, cancel.check)
    locks = [] if device == "cpu" else [GPU_LOCK]
    with hold(project.state_dir, locks, wait, command_line, on_wait=gpu_wait_notice(progress)), warm.one_runner_loaded():
        warm.load_runner(runner, directory, device)
        try:
            results = []
            if isinstance(runner, EmbeddingRunner):
                embedding = runner.embed(image, cancel.check)
                for each in params:
                    results.append(runner.decode(embedding, image.shape[:2], each, cancel.check))
            else:
                for each in params:
                    cancel.check()
                    results.append(runner.call(image, each, cancel.check))
            return results, runner.device_used
        finally:
            runner.unload()


@dataclass(frozen=True)
class ClickPreview:
    masks: list[np.ndarray]  # each click's Mask on the target grid, in order, as that click alone would make
    union: np.ndarray  # the clicks replayed in order: a positive one adds its Mask, a negative one takes it away
    computed: bool
    device: str


def _segmenting(graph: AssetGraph) -> tuple[StageSpec, SegmentHooks, StageRun]:
    """The Stage that segments, its hooks, and a run of it to build calls from."""
    spec, hooks = graph.stage_with(lambda s: s.segment, "segments")
    return spec, hooks, graph.stage_run(spec, graph.output_dir(spec))


def _not_ready(asset: Asset, spec: StageSpec) -> KiripixError:
    return fail("probe.not_ready", f"{asset.id} has no fit and Source to segment yet", fix=f"kiripix run {asset.id}",
                position=Position(asset=asset.id, stage=spec.name))


def _segment(project: Project, cache: HashCache, calls: list[RunnerCall], *, batched: bool, keep_warm: bool, cpu: bool,
             wait: float, command_line: str, progress: ProgressSink) -> tuple[list[np.ndarray], bool, str]:
    """The results of calls on one image, and whether its embedding was computed, and the device. In `serve` each goes
    to the warm Runner. In the CLI, `batched` loads the Runner once and embeds once for all of them; otherwise there is
    one call. A busy GPU is refused with `--cpu` as the fix, since a Probe has no --wait to offer and the CPU never
    needs the lock."""
    first = calls[0]
    device: Device = "cpu" if cpu else "auto"
    runner = all_runners()[first.runner]

    def read_image() -> np.ndarray:
        return load_rgba(first.image, project.relative(first.image))

    try:
        if keep_warm and isinstance(runner, EmbeddingRunner):
            results, computed, used = [], False, runner.device_used
            image_hash = cache.file_hash(first.image)
            for call in calls:
                cancel.check()
                result, was_computed, used = warm.warm_call(runner, project.state_dir, device, image_hash, read_image,
                                                            call.params, command_line)
                results.append(result)
                computed = computed or was_computed
        elif batched:
            computed = True
            results, used = _cold_calls(project, first.runner, read_image(), [call.params for call in calls], device,
                                        wait, command_line, progress)
        else:
            computed = True
            result, used = _cold_call(project, first.runner, read_image(), first.params, device, wait, command_line,
                                      progress)
            results = [result]
    except RunnerError as error:
        raise fail("runner.failed", str(error), fix=command_line) from None
    except KiripixError as error:
        if error.exit_code != ExitCode.BUSY:
            raise
        findings = [finding.model_copy(update={"fix": f"{command_line} --cpu"}) for finding in error.findings]
        raise KiripixError(findings, error.exit_code, error.data) from None
    cache.save()
    return results, computed, used


def click_preview(project: Project, asset: Asset, points: list[ClickPoint], *, keep_warm: bool, cpu: bool, wait: float,
                  command_line: str, progress: ProgressSink) -> ClickPreview:
    """What a lift of these clicks would make: one Runner call per click, each the call `click_call` makes (a negative
    click is segmented as a positive one at its point), replayed in order. One load and one embedding for all of them."""
    cache = HashCache(project.state_dir)
    spec, hooks, stage_run = _segmenting(AssetGraph(project, asset, cache))
    try:
        built = [hooks.call(stage_run, [(x, y, True)]) for x, y, _ in points]
    except StageFailure as error:
        raise fail("input.invalid", str(error), position=Position(asset=asset.id, stage=spec.name),
                   fix=f"kiripix probe click-preview {asset.id} <x,y>") from None
    calls = [call for call in built if call is not None]
    if len(calls) < len(built):
        raise _not_ready(asset, spec)
    results, computed, used = _segment(project, cache, calls, batched=True, keep_warm=keep_warm, cpu=cpu, wait=wait,
                                       command_line=command_line, progress=progress)
    masks = [hooks.to_target(stage_run, result) for result in results]
    union = np.zeros_like(masks[0])
    for (_, _, positive), mask in zip(points, masks):
        union = union | mask if positive else union & ~mask
    return ClickPreview(masks, union, computed, used)


def flood_preview(project: Project, asset: Asset, floods: list[tuple[int, int, float]]) -> list[np.ndarray]:
    """The region each flood would fill on the built Plate, by the Op the `flood` Decision replays. Nothing is recorded;
    no Runner is loaded, so there is no lock."""
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    spec = next((stage for stage in graph.kind.stages if any(d.name == "flood" for d in stage.decisions)), None)
    source = graph.input_image(spec) if spec is not None else None
    if spec is None or source is None:
        raise fail("probe.not_supported", f"a {asset.kind} has no Stage that floods", fix="kiripix describe project")
    upstream, path = source
    if graph.built_hash(upstream) is None or not path.is_file():
        raise fail("probe.not_ready", f"{asset.id} has no built {upstream.name} image to flood yet",
                   fix=f"kiripix run {asset.id} {upstream.name}", position=Position(asset=asset.id, stage=spec.name))
    decision = next(d for d in spec.decisions if d.name == "flood")
    bounds = decision.entry_schema["properties"]["tolerance"]  # the Decision's own limits, so `decide` takes what this did
    low, high = bounds.get("minimum", 0.0), bounds.get("maximum", float("inf"))
    for x, y, tolerance in floods:
        if not low <= tolerance <= high:
            raise fail("input.invalid", f"tolerance {tolerance:g} is outside {low:g} to {high:g}, which the flood "
                       "Decision takes", position=Position(asset=asset.id, stage=spec.name, x=x, y=y),
                       fix=f"kiripix probe flood-preview {asset.id} {x},{y},{min(max(tolerance, low), high):g}")
    plate = load_rgba(path, project.relative(path))
    regions = []
    for x, y, tolerance in floods:
        try:
            regions.append(flood_region(plate, x, y, tolerance))
        except ValueError as error:
            raise fail("input.invalid", str(error), position=Position(asset=asset.id, stage=spec.name, x=x, y=y),
                       fix=f"kiripix probe flood-preview {asset.id} 10,12,0.04") from None
    return regions


def segment_preview(project: Project, asset: Asset, points: list[ClickPoint], *, keep_warm: bool, cpu: bool, wait: float,
                    command_line: str, progress: ProgressSink, box: BoxCorners | None = None) -> SegmentPreview:
    """The Mask the clicks `points` would make as one prompt, or, with `box`, the Mask that box would make (ticket 0079)."""
    cache = HashCache(project.state_dir)
    spec, hooks, stage_run = _segmenting(AssetGraph(project, asset, cache))
    try:
        if box is not None:
            if hooks.box_call is None:
                raise fail("probe.not_supported", f"a {asset.kind} has no Stage that segments with a box",
                           fix="kiripix describe project")
            call = hooks.box_call(stage_run, box)
        else:
            call = hooks.call(stage_run, points)
    except StageFailure as error:
        raise fail("input.invalid", str(error), position=Position(asset=asset.id, stage=spec.name),
                   fix=f"kiripix probe segment-preview {asset.id} {'<x0,y0,x1,y1>' if box is not None else '<x,y>'}") from None
    if call is None:
        raise _not_ready(asset, spec)
    results, computed, used = _segment(project, cache, [call], batched=False, keep_warm=keep_warm, cpu=cpu, wait=wait,
                                       command_line=command_line, progress=progress)
    return SegmentPreview(hooks.to_target(stage_run, results[0]), computed, used)
