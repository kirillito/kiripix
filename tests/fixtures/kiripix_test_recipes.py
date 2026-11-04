"""The test Kinds `demo` and `sketch` (at the end), loaded through KIRIPIX_TEST_RECIPES. For the test harness only.

Its Stages are trivial and deterministic, so the stage graph can be tested before any image Recipe runs:
- copy: copies src/input.txt. Its Check reports `demo.bad_text` at x=1, y=2 when the text contains "bad".
- concat: joins copy's output, src/extra.txt and the palette's first line, with a separator parameter.
- hold: writes a partial file; while the Asset folder has a `hold` file, it marks `holding` and waits in chunks,
  checking the cancel token between them. Takes the GPU lock, so two Assets holding at once collide.
- fail: fails on purpose, with the message in src/fail.txt, when that file exists.
- choose: downstream of copy only. Takes the `mark` Decision and the `level` parameter (0 to 10), and writes both to
  out.json, so tests can see exactly what the run function was handed.

It also replaces SAM 2 with a fake Runner (at the end), so that no test ever downloads weights.
"""

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.project_checks import register_project_check
from kiripix.recipes import register_kind
from kiripix.runners import SEGMENTER, CheckCancel, Device, Runner, RunnerError, WeightFile, register_runner
from kiripix.recipes.base import (
    DecisionSpec,
    KindSpec,
    ParamSpec,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
    point_decision,
)


def _copy(run: StageRun) -> None:
    text = run.files["src/input.txt"].read_text(encoding="utf-8")
    (run.output_dir / "out.txt").write_text(text, encoding="utf-8")


def _check_copy(run: StageRun) -> list[Finding]:
    if "bad" not in (run.output_dir / "out.txt").read_text(encoding="utf-8"):
        return []
    return [Finding(code="demo.bad_text", message="the text says bad", position=Position(file="out.txt", x=1, y=2),
                    fix=f"kiripix set {run.asset_id} concat sep=-")]


@register_project_check
def _check_demo_count(project: object, assets: list[Asset]) -> list[Finding]:
    """The test Project check: at most one demo Asset."""
    demos = [a.id for a in assets if a.kind == "demo"]
    if len(demos) < 2:
        return []
    return [Finding(code="demo.too_many", message=f"{len(demos)} demo Assets: {', '.join(demos)}",
                    owner_action="Remove all but one demo Asset.")]


def _concat(run: StageRun) -> None:
    upstream = (run.upstream["copy"] / "out.txt").read_text(encoding="utf-8")
    extra = run.files["src/extra.txt"].read_text(encoding="utf-8")
    palette_line = run.settings["palette"].read_text(encoding="utf-8").splitlines()[0]
    separator = str(run.params["sep"])
    (run.output_dir / "out.txt").write_text(separator.join([upstream, extra, palette_line]), encoding="utf-8")


def _hold(run: StageRun) -> None:
    (run.output_dir / "partial.txt").write_text("half", encoding="utf-8")
    hold = run.asset_dir / "hold"
    if hold.exists():
        (run.asset_dir / "holding").write_text("", encoding="utf-8")
        while hold.exists():
            run.check_cancel()
            time.sleep(0.05)  # stands in for one chunk of work
        (run.asset_dir / "holding").unlink()
    run.progress(1, 1, "held")
    (run.output_dir / "out.txt").write_text("held", encoding="utf-8")


def _fail(run: StageRun) -> None:
    reason = run.files.get("src/fail.txt")
    if reason is not None:
        raise StageFailure(reason.read_text(encoding="utf-8"))
    (run.output_dir / "out.txt").write_text("ok", encoding="utf-8")


def _choose(run: StageRun) -> None:
    current = [{"decision": d.name, "data": d.data} for d in run.decisions]
    document = {"level": run.params["level"], "decisions": current}
    (run.output_dir / "out.json").write_text(json.dumps(document), encoding="utf-8")


MARK = DecisionSpec(
    name="mark",
    description="Mark a place by name, with a count.",
    entry_schema={
        "type": "object",
        "properties": {"label": {"type": "string"}, "count": {"type": "integer", "minimum": 0}},
        "required": ["label"],
        "additionalProperties": False,
    },
)

register_kind(
    KindSpec(
        name="demo",
        description="A test Kind with trivial Stages.",
        stages=chain(
            StageSpec(name="copy", description="Copy the input.", inputs=StageInputs(files=["src/input.txt"]),
                      run=_copy, check=_check_copy),
            StageSpec(
                name="concat",
                description="Join the copy, the extra file and the palette's first line.",
                inputs=StageInputs(files=["src/extra.txt"], settings=["palette"]),
                params=(ParamSpec(name="sep", type="str", description="Separator.", default="+"),),
                run=_concat,
            ),
            StageSpec(name="hold", description="Wait while a hold file exists.", gpu=True, run=_hold),
            StageSpec(name="fail", description="Fail when src/fail.txt exists.",
                      inputs=StageInputs(files=["src/fail.txt"]), run=_fail),
            StageSpec(
                name="choose",
                description="Write the current Decisions and the level to the output.",
                inputs=StageInputs(upstream=["copy"]),
                params=(ParamSpec(name="level", type="int", description="A level.", default=1, minimum=0,
                                  maximum=10),),
                decisions=(MARK,),
                run=_choose,
            ),
        ),
    )
)


# The test Kind `sketch`: two image Stages, for Overrides and replay onto changed input.
# - draw: copies src/input.png; its image is draw.png.
# - trace: takes `click` Decisions on draw's image (with any Overrides of draw applied), copies the image it was
#   handed to trace.png and writes its current Decisions to out.json.


def _draw(run: StageRun) -> None:
    shutil.copyfile(run.files["src/input.png"], run.output_dir / "draw.png")


def _trace(run: StageRun) -> None:
    shutil.copyfile(run.upstream["draw"] / "draw.png", run.output_dir / "trace.png")
    current = [{"decision": d.name, "data": d.data} for d in run.decisions]
    (run.output_dir / "out.json").write_text(json.dumps({"decisions": current}), encoding="utf-8")


register_kind(
    KindSpec(
        name="sketch",
        description="A test Kind with two image Stages.",
        stages=chain(
            StageSpec(name="draw", description="Copy the input image.", inputs=StageInputs(files=["src/input.png"]),
                      image="draw.png", run=_draw),
            StageSpec(name="trace", description="Copy the image it is handed and write its Decisions.",
                      decisions=(point_decision("click", "A click on the image.", on_image=True),),
                      image="trace.png", run=_trace),
        ),
    )
)


# The fake Runners. Everything a test watches is in the folder the Command runs in:
# - runner-calls.jsonl: one line per call, with the device and the parameters;
# - runner-fails: while it exists, a call fails;
# - hold-runner: while it exists, a call marks `runner-holding` and waits in chunks, checking the cancel token;
# - fake-weights-v2: while it exists, the Runner's weights hash is another one, as if it had been upgraded.

_WEIGHTS = Path(__file__).parent / "fake_weights.bin"


def _fake_weight(sha256: str) -> WeightFile:
    return WeightFile("fake_weights.bin", _WEIGHTS.as_uri(), sha256, _WEIGHTS.stat().st_size)


class FakeSegmenter(Runner):
    """Deterministic: the Mask is capped at `max_size` as SAM 2's is. In it, a positive click sets a square reaching an
    eighth of the longer side around it, and a negative click clears one half that size."""

    id = SEGMENTER
    description = "A fake SAM 2 for the tests."
    licence = "test"
    weights = (_fake_weight(hashlib.sha256(_WEIGHTS.read_bytes()).hexdigest()),)

    def __init__(self) -> None:
        self._device: Device | None = None

    @property
    def weights_hash(self) -> str:
        version = "v2" if Path("fake-weights-v2").exists() else "v1"
        return hashlib.sha256(f"{version} {super().weights_hash}".encode()).hexdigest()

    def load(self, directory: Path, device: Device) -> None:
        assert (directory / "fake_weights.bin").is_file()
        self._device = device

    @property
    def device_used(self) -> str:
        return "cpu" if self._device == "cpu" else "cuda"

    def call(self, image: np.ndarray, params: dict[str, Any], check_cancel: CheckCancel) -> np.ndarray:
        assert self._device is not None, "called while not loaded"
        with Path("runner-calls.jsonl").open("a", encoding="utf-8") as calls:
            calls.write(json.dumps({"device": self._device, "params": params}) + "\n")
        hold = Path("hold-runner")
        if hold.exists():
            Path("runner-holding").write_text("", encoding="utf-8")
            while hold.exists():
                check_cancel()
                time.sleep(0.05)  # stands in for a long inference
        if Path("runner-fails").exists():
            raise RunnerError("the fake Runner was told to fail")
        height, width = image.shape[:2]
        scale = min(1.0, int(params["max_size"]) / max(width, height))
        rows, columns = round(height * scale), round(width * scale)
        mask = np.zeros((rows, columns), dtype=np.bool_)
        reach = max(rows, columns) // 8
        for x, y, positive in params["points"]:
            cx, cy = int(x * scale), int(y * scale)
            size = reach if positive else reach // 2
            mask[max(cy - size, 0):cy + size + 1, max(cx - size, 0):cx + size + 1] = positive
        return mask

    def unload(self) -> None:
        self._device = None


class TamperedWeights(FakeSegmenter):
    """A Runner whose download doesn't match its declared hash."""

    id = "fake.tampered"
    weights = (_fake_weight("0" * 64),)


register_runner(FakeSegmenter())
register_runner(TamperedWeights())
