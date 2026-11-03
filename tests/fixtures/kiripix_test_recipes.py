"""The test Kind `demo`, loaded through KIRIPIX_TEST_RECIPES. For the test harness only.

Its Stages are trivial and deterministic, so the stage graph can be tested before any image Recipe runs:
- copy: copies src/input.txt.
- concat: joins copy's output, src/extra.txt and the palette's first line, with a separator parameter.
- hold: writes a partial file; while the Asset folder has a `hold` file, it marks `holding` and waits. Takes the GPU
  lock, so two Assets holding at once collide.
- fail: fails on purpose, with the message in src/fail.txt, when that file exists.
- choose: downstream of copy only. Takes the `mark` Decision and the `level` parameter (0 to 10), and writes both to
  out.json, so tests can see exactly what the run function was handed.
"""

import json
import time

from kiripix.recipes import register_kind
from kiripix.recipes.base import (
    DecisionSpec,
    KindSpec,
    ParamSpec,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
)


def _copy(run: StageRun) -> None:
    text = run.files["src/input.txt"].read_text(encoding="utf-8")
    (run.output_dir / "out.txt").write_text(text, encoding="utf-8")


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
            time.sleep(0.05)
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
                      run=_copy),
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
