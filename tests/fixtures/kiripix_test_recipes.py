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

import kiripix.runners
from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.project_checks import register_project_check
from kiripix.recipes import register_kind
from kiripix.recipes.hole import hole_params
from kiripix.runners import (
    INPAINTER, MATTER, SEGMENTER, CheckCancel, Device, EmbeddingRunner, Runner, RunnerError, WeightFile, register_runner,
)
from PIL import Image
from kiripix.recipes.base import (
    PLATE,
    DecisionSpec,
    KindSpec,
    ParamSpec,
    RunnerCall,
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


# The test Kind `layered`: a `layers` Stage with the `after_overrides` hook (ticket 0038) and the `plate` Decision.
# - layers: copies src/input.png to plate.png (its image).
# - the hook, run after core paints the Overrides: writes hook.json with the pixel (0, 0) it sees in plate.png, and sets
#   the pixel (3, 3) to blue.
# - the Check: reports `layered.hooked`, with hook.json's corner in its message, when plate.png's pixel (3, 3) is blue.


def _layers(run: StageRun) -> None:
    shutil.copyfile(run.files["src/input.png"], run.output_dir / "plate.png")


def _hook_layers(run: StageRun) -> None:
    from PIL import Image

    with Image.open(run.output_dir / "plate.png") as opened:
        image = np.array(opened.convert("RGBA"))
    (run.output_dir / "hook.json").write_text(json.dumps({"corner": [int(v) for v in image[0, 0]]}), encoding="utf-8")
    image[3, 3] = (41, 173, 255, 255)
    Image.fromarray(image, "RGBA").save(run.output_dir / "plate.png")


def _check_layers(run: StageRun) -> list[Finding]:
    from PIL import Image

    with Image.open(run.output_dir / "plate.png") as opened:
        blue = tuple(opened.convert("RGBA").getpixel((3, 3))) == (41, 173, 255, 255)
    if not blue:
        return []
    corner = json.loads((run.output_dir / "hook.json").read_text(encoding="utf-8"))["corner"]
    return [Finding(code="layered.hooked", message=f"the hook saw {corner} at (0, 0)", position=Position(file="plate.png"),
                    fix="kiripix describe layered")]


register_kind(
    KindSpec(
        name="layered",
        description="A test Kind with a layers Stage: the hook after Overrides and the plate Decision.",
        stages=chain(
            StageSpec(name="layers", description="Copy the input image as the Plate.",
                      inputs=StageInputs(files=["src/input.png"]), decisions=(PLATE,), image="plate.png",
                      run=_layers, after_overrides=_hook_layers, check=_check_layers),
        ),
    )
)


# The fake Runners. Everything a test watches is in the folder the Command runs in:
# - runner-calls.jsonl: one line per call, with the device and the parameters;
# - runner-fails: while it exists, a call fails;
# - hold-runner: while it exists, a call marks `runner-holding` and waits in chunks, checking the cancel token;
# - runner-embeds.jsonl, runner-decodes.jsonl: one line per run of a warm Runner's two halves;
# - hold-embed: while it exists, an `embed` marks `embed-holding` and waits in chunks, checking the cancel token;
# - runner-no-gpu: while it exists, a Runner not asked for the CPU says it left the GPU unused;
# - matter-cpu-differs: while it exists, the fake matter's result on the CPU differs from the GPU's by one alpha level;
# - fake-weights-v2: while it exists, the Runner's weights hash is another one, as if it had been upgraded;
# - runner-load-seconds, runner-call-seconds: while they exist, a load or a call takes that many seconds (the file's text).

_WEIGHTS = Path(__file__).parent / "fake_weights.bin"


def _take_time(name: str) -> None:
    """Stand in for a slow load or call: wait the seconds that the file `name` holds, if it exists."""
    path = Path(name)
    if path.exists():
        seconds = float(path.read_text("utf-8"))
        # Until every clock Kiripix might time it with has passed it: on Windows `time.monotonic` ticks about every
        # 16 ms, so a plain sleep can measure a little short.
        start, precise = time.monotonic(), time.perf_counter()
        while min(time.monotonic() - start, time.perf_counter() - precise) < seconds:
            time.sleep(0.005)


def _fake_weight(sha256: str) -> WeightFile:
    return WeightFile("fake_weights.bin", _WEIGHTS.as_uri(), sha256, _WEIGHTS.stat().st_size)


class FakeSegmenter(EmbeddingRunner):
    """Deterministic: the Mask is capped at `max_size` as SAM 2's is. In it, a positive click sets a square reaching an
    eighth of the longer side around it, and a negative click clears one half that size. A box is the Mask itself."""

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
        _take_time("runner-load-seconds")
        self._device = device

    @property
    def device_used(self) -> str:
        return "cpu" if self._device == "cpu" else "cuda"

    @property
    def gpu_unused(self) -> str | None:
        return "the fake GPU went unused" if self._device != "cpu" and Path("runner-no-gpu").exists() else None

    def call(self, image: np.ndarray, params: dict[str, Any], check_cancel: CheckCancel) -> np.ndarray:
        assert self._device is not None, "called while not loaded"
        _take_time("runner-call-seconds")
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
        return self._mask(image.shape[:2], params)

    def embed(self, image: np.ndarray, check_cancel: CheckCancel) -> Any:
        assert self._device is not None, "called while not loaded"
        hold = Path("hold-embed")
        if hold.exists():
            Path("embed-holding").write_text("", encoding="utf-8")
            while hold.exists():
                check_cancel()
                time.sleep(0.05)  # stands in for a long encoder run
        with Path("runner-embeds.jsonl").open("a", encoding="utf-8") as calls:
            calls.write(json.dumps({"device": self._device}) + "\n")
        return "the fake embedding"

    def decode(self, embedding: Any, size: tuple[int, int], params: dict[str, Any],
               check_cancel: CheckCancel) -> np.ndarray:
        assert self._device is not None and embedding == "the fake embedding"
        _take_time("runner-call-seconds")
        with Path("runner-decodes.jsonl").open("a", encoding="utf-8") as calls:
            calls.write(json.dumps({"device": self._device, "params": params}) + "\n")
        if Path("runner-fails").exists():
            raise RunnerError("the fake Runner was told to fail")
        return self._mask(size, params)

    @staticmethod
    def _mask(size: tuple[int, int], params: dict[str, Any]) -> np.ndarray:
        height, width = size
        scale = min(1.0, int(params["max_size"]) / max(width, height))
        rows, columns = round(height * scale), round(width * scale)
        mask = np.zeros((rows, columns), dtype=np.bool_)
        reach = max(rows, columns) // 8
        if "box" in params:  # a box: the Mask is the box itself, its far edges excluded (they are Source pixel edges)
            x0, y0, x1, y1 = params["box"]
            mask[int(y0 * scale):int(y1 * scale), int(x0 * scale):int(x1 * scale)] = True
        for x, y, positive in params.get("points", []):
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


class FakeMatter(Runner):
    """Deterministic: the RGBA image back, capped at `max_size` on its longer side, with an alpha that ramps from 0 at
    the left column to 255 at the right one, so partial alpha reaches the result."""

    id = MATTER
    description = "A fake matting Runner for the tests."
    licence = "test"
    weights = (_fake_weight(hashlib.sha256(_WEIGHTS.read_bytes()).hexdigest()),)

    def __init__(self) -> None:
        self._device: Device | None = None

    def load(self, directory: Path, device: Device) -> None:
        assert (directory / "fake_weights.bin").is_file()
        _take_time("runner-load-seconds")
        self._device = device

    @property
    def device_used(self) -> str:
        return "cpu" if self._device == "cpu" else "cuda"

    def call(self, image: np.ndarray, params: dict[str, Any], check_cancel: CheckCancel) -> np.ndarray:
        assert self._device is not None, "called while not loaded"
        _take_time("runner-call-seconds")
        with Path("runner-calls.jsonl").open("a", encoding="utf-8") as calls:
            calls.write(json.dumps({"device": self._device, "params": params}) + "\n")
        # A call with a hole (the `fill` Kind) holds on its own file, so a test can stop between it and the call before.
        hold = Path("hold-hole" if "crop" in params else "hold-runner")
        if hold.exists():
            Path("runner-holding").write_text("", encoding="utf-8")
            while hold.exists():
                check_cancel()
                time.sleep(0.05)  # stands in for a long inference
        if Path("runner-fails").exists():
            raise RunnerError("the fake Runner was told to fail")
        height, width = image.shape[:2]
        scale = min(1.0, int(params["max_size"]) / max(width, height))
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        result = np.asarray(Image.fromarray(image, "RGBA").resize(size, Image.Resampling.NEAREST)).copy()
        result[..., 3] = np.round(np.linspace(0, 255, size[0]))[None, :].astype(np.uint8)
        if self._device == "cpu" and Path("matter-cpu-differs").exists():
            result[0, 1, 3] += 1  # as BiRefNet's alpha on the CPU differs by one level in a few pixels from the GPU's
        return result

    def unload(self) -> None:
        self._device = None


# The test Kind `matte`: one Stage whose only input is a Runner call on src/input.png, to the MATTER role.
_MATTE_PARAMS = {"max_size": 1536}


def _matte_calls(run: StageRun) -> list[RunnerCall]:
    return [RunnerCall(runner=MATTER, image=run.files["src/input.png"], params=dict(_MATTE_PARAMS), decisions=[])]


def _cutout(run: StageRun) -> None:
    [call] = _matte_calls(run)
    shutil.copyfile(run.pinned(call), run.output_dir / "cutout.png")


register_kind(
    KindSpec(
        name="matte",
        description="A test Kind with one matting Runner call.",
        stages=chain(
            StageSpec(name="cutout", description="The input with the matter's alpha.",
                      inputs=StageInputs(files=["src/input.png"]), image="cutout.png", run=_cutout,
                      runner_calls=_matte_calls),
        ),
    )
)

# The test Kind `fill` (ticket 0039): two chained Runner calls on src/input.png. The first, to the SEGMENTER role, finds a
# hole; the second, to the MATTER role, is made with that hole in its params (a crop and runs), so it isn't listed until the
# first is pinned. Each wraps its Decisions ([{"find": []}], [{"fill": []}]) so core can tell "not run yet" from "input
# changed". Its output is the second call's result and the hole it was made with.


def _fill_calls(run: StageRun) -> list[RunnerCall]:
    image = run.files["src/input.png"]
    find = RunnerCall(runner=SEGMENTER, image=image, params={"max_size": 1536, "points": [[2.0, 2.0, True]]},
                      decisions=[{"find": []}])
    found = run.pinned(find)
    if not found.is_file():
        return [find]
    with Image.open(found) as opened:
        hole = hole_params(np.array(opened.convert("1")), margin=1)
    return [find, RunnerCall(runner=MATTER, image=image, params={"max_size": 1536, **hole}, decisions=[{"fill": []}])]


def _fill(run: StageRun) -> None:
    _, fill = _fill_calls(run)
    shutil.copyfile(run.pinned(fill), run.output_dir / "filled.png")
    (run.output_dir / "hole.json").write_text(json.dumps(fill.params), encoding="utf-8")


register_kind(
    KindSpec(
        name="fill",
        description="A test Kind with two chained Runner calls: the second's hole is the first's pinned result.",
        stages=chain(
            StageSpec(name="filled", description="The second call's result.", inputs=StageInputs(files=["src/input.png"]),
                      run=_fill, runner_calls=_fill_calls),
        ),
    )
)

class FakeInpainter(Runner):
    """Deterministic, as the INPAINTER contract says: the crop of the image, with the hole's pixels set to the mean colour
    of the others (opaque). A subclass with another ID stands in for a swapped Runner."""

    id = INPAINTER
    description = "A fake inpainting Runner for the tests."
    licence = "test"
    can_stay_warm = True  # as the real one is: `serve` keeps it loaded
    weights = (_fake_weight(hashlib.sha256(_WEIGHTS.read_bytes()).hexdigest()),)

    def __init__(self) -> None:
        self._device: Device | None = None

    def load(self, directory: Path, device: Device) -> None:
        assert (directory / "fake_weights.bin").is_file()
        _take_time("runner-load-seconds")
        self._device = device

    def call(self, image: np.ndarray, params: dict[str, Any], check_cancel: CheckCancel) -> np.ndarray:
        assert self._device is not None, "called while not loaded"
        _take_time("runner-call-seconds")
        with Path("runner-calls.jsonl").open("a", encoding="utf-8") as calls:
            calls.write(json.dumps({"runner": self.id, "device": self._device, "params": params}) + "\n")
        hold = Path("hold-runner")
        if hold.exists():
            Path("runner-holding").write_text("", encoding="utf-8")
            while hold.exists():
                check_cancel()
                time.sleep(0.05)  # stands in for a long inference
        if Path("runner-fails").exists():
            raise RunnerError("the fake Runner was told to fail")
        top, left, bottom, right = params["crop"]
        result = image[top:bottom, left:right].copy()
        hole = np.zeros(result.shape[:2], dtype=np.bool_)
        for y, x, length in params["runs"]:
            hole[y, x:x + length] = True
        if hole.any():
            result[hole] = [*np.rint(result[~hole].mean(axis=0)[:3]).astype(np.uint8), 255] if (~hole).any() else 0
        return result

    def unload(self) -> None:
        self._device = None


class OtherInpainter(FakeInpainter):
    id = "fake.inpainter-b"


# The test Kind `inpaint`: one Stage whose only input is an INPAINTER call on src/input.png, with a fixed hole. While the
# project has an `inpainter-b` file, the call goes to OtherInpainter, as if the Runner behind the role had been replaced.
_HOLE = {"crop": [0, 0, 4, 6], "runs": [[1, 1, 3], [2, 2, 2]]}


def _inpaint_calls(run: StageRun) -> list[RunnerCall]:
    runner = OtherInpainter.id if Path("inpainter-b").exists() else INPAINTER
    return [RunnerCall(runner=runner, image=run.files["src/input.png"], params=dict(_HOLE), decisions=[])]


def _patched(run: StageRun) -> None:
    [call] = _inpaint_calls(run)
    shutil.copyfile(run.pinned(call), run.output_dir / "patched.png")


register_kind(
    KindSpec(
        name="inpaint",
        description="A test Kind with one inpainting Runner call.",
        stages=chain(
            StageSpec(name="patched", description="The crop with the hole filled.", inputs=StageInputs(files=["src/input.png"]),
                      image="patched.png", run=_patched, runner_calls=_inpaint_calls),
        ),
    )
)

register_runner(FakeSegmenter())
register_runner(FakeMatter())
register_runner(FakeInpainter())
register_runner(OtherInpainter())
register_runner(TamperedWeights())

# The room's `layers` Stage reads the INPAINTER role at call time. While the project has an `inpainter-b` file, the role
# has another Runner behind it, as if its one line had been edited (ticket 0043). Each Command is a fresh process, so the
# file is read at import.
if Path("inpainter-b").exists():
    kiripix.runners.INPAINTER = OtherInpainter.id
