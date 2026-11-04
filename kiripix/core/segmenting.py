"""The `segment-preview` Probe's work (spec §10.1): the Mask a click would make, with nothing recorded or pinned. `serve`
keeps the Runner warm for it (`kiripix.core.warm`); the CLI loads and unloads it like any other call."""

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
from kiripix.recipes.base import ClickPoint, StageFailure
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
        runner.load(directory, device)
        try:
            return runner.call(image, params, cancel.check), runner.device_used
        finally:
            runner.unload()


def segment_preview(project: Project, asset: Asset, points: list[ClickPoint], *, keep_warm: bool, cpu: bool, wait: float,
                    command_line: str, progress: ProgressSink) -> SegmentPreview:
    cache = HashCache(project.state_dir)
    graph = AssetGraph(project, asset, cache)
    spec = next((stage for stage in graph.kind.stages if stage.segment is not None), None)
    if spec is None or spec.segment is None:
        raise fail("probe.not_supported", f"a {asset.kind} has no Stage that segments", fix="kiripix describe project")
    stage_run = graph.stage_run(spec, graph.output_dir(spec))
    try:
        call = spec.segment.call(stage_run, points)
    except StageFailure as error:
        raise fail("input.invalid", str(error), position=Position(asset=asset.id, stage=spec.name),
                   fix=f"kiripix probe segment-preview {asset.id} <x,y>") from None
    if call is None:
        raise fail("probe.not_ready", f"{asset.id} has no fit and Source to segment yet", fix=f"kiripix run {asset.id}",
                   position=Position(asset=asset.id, stage=spec.name))
    device: Device = "cpu" if cpu else "auto"
    runner = all_runners()[call.runner]

    def read_image() -> np.ndarray:
        return load_rgba(call.image, project.relative(call.image))

    try:
        if keep_warm and isinstance(runner, EmbeddingRunner):
            result, computed, used = warm.warm_call(runner, project.state_dir, device, cache.file_hash(call.image),
                                                    read_image, call.params, command_line)
        else:
            computed = True
            result, used = _cold_call(project, call.runner, read_image(), call.params, device, wait, command_line,
                                      progress)
    except RunnerError as error:
        raise fail("runner.failed", str(error), fix=command_line) from None
    except KiripixError as error:
        if error.exit_code != ExitCode.BUSY:
            raise
        # A Probe has no --wait to offer, and the CPU never needs the lock.
        findings = [finding.model_copy(update={"fix": f"{command_line} --cpu"}) for finding in error.findings]
        raise KiripixError(findings, error.exit_code, error.data) from None
    cache.save()
    return SegmentPreview(spec.segment.to_target(stage_run, result), computed, used)
