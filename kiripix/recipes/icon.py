"""The icon Recipe (spec §6.6): brief, source, cutout, fit, palette, finish, export.

The front half of a Prop (ticket 0262): the Prop's Stages for the Source, cutout, palette and outline, and a `fit` that lands
the cutout on a fixed square, centred in its padding. An icon has no footprint and no origin."""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, Position, check_alpha
from kiripix.ops import conformance
from kiripix.recipes.base import (
    FIT_PARAMS,
    PALETTE_PARAMS,
    PICK,
    CheckSpec,
    KindSpec,
    NeedsInput,
    ParamSpec,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
)
from kiripix.recipes.common import (
    check_fit,
    check_palette,
    read_rgba,
    run_fit,
    run_palette,
    run_source,
    source_needs_input,
    write_rgba,
)
from kiripix.recipes.prop import (
    _check_cutout,
    _check_finish,
    _check_export,
    _cutout,
    _cutout_calls,
    _export_needs_input,
    _finish,
)
from kiripix.recipes.prop import PROP

ICON_SIZES = (16, 24, 32)
DEFAULT_PADDING = 1  # px: room for the outline


# brief


def _brief(run: StageRun) -> None:
    size = int(run.params["size"]) or int(run.settings["icon.size"])
    brief = {"width": size, "height": size, "size": size, "padding": int(run.params["padding"]),
             "notes": str(run.params["notes"])}
    (run.output_dir / "brief.json").write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")


def _check_brief(run: StageRun) -> list[Finding]:
    brief = json.loads((run.output_dir / "brief.json").read_text(encoding="utf-8"))
    size, padding = int(brief["size"]), int(brief["padding"])
    position = Position(asset=run.asset_id, stage="brief", field="stages.brief.size")
    findings: list[Finding] = []
    if size not in ICON_SIZES:
        findings.append(Finding(
            code="brief.size_invalid", message=f"the icon's size {size} isn't 16, 24 or 32",
            position=position, fix=f"kiripix set {run.asset_id} brief size={min(ICON_SIZES, key=lambda s: abs(s - size))}"))
    if padding * 2 >= size:
        findings.append(Finding(
            code="brief.padding_too_large", message=f"a padding of {padding} px leaves nothing of the {size} px square",
            position=Position(asset=run.asset_id, stage="brief", field="stages.brief.padding"),
            fix=f"kiripix set {run.asset_id} brief padding={DEFAULT_PADDING}"))
    return findings


# source


def _source(run: StageRun) -> None:
    run_source(run)


# fit: the Prop's `grid` or `downscale` onto the square less the padding, then centred in the square. `grid.json` is of the
# inner square; its `inset` is the padding, which a target pixel of the icon is that far from the inner square's.


def _read_brief(run: StageRun) -> tuple[int, int]:
    brief = json.loads((run.upstream["brief"] / "brief.json").read_text(encoding="utf-8"))
    return int(brief["size"]), int(brief["padding"])


def _fit(run: StageRun) -> None:
    size, padding = _read_brief(run)
    inner = size - 2 * padding
    if inner < 1:
        raise StageFailure(f"a padding of {padding} px leaves nothing of the {size} px square; "
                           f"kiripix set {run.asset_id} brief padding={DEFAULT_PADDING}")
    run_fit(run, run.upstream["cutout"] / "cutout.png", vote_alpha=True, size=(inner, inner))
    fitted = read_rgba(run.output_dir / "fit.png")
    if fitted.shape[:2] == (inner, inner):  # a grid larger than the square stays as it is: `icon.size` reports it
        canvas = np.zeros((size, size, 4), dtype=np.uint8)
        canvas[padding:padding + inner, padding:padding + inner] = fitted
        write_rgba(run.output_dir / "fit.png", canvas)
    path = run.output_dir / "grid.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["inset"] = padding
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _check_fit(run: StageRun) -> list[Finding]:
    size, padding = _read_brief(run)
    inner = size - 2 * padding
    image = read_rgba(run.output_dir / "fit.png")
    findings = check_alpha(conformance(image, np.zeros((0, 3), dtype=np.uint8)), "fit.png")
    height, width = image.shape[:2]
    if (width, height) != (size, size):
        mode = json.loads((run.output_dir / "grid.json").read_text(encoding="utf-8"))["mode"]
        findings.append(Finding(
            code="icon.size", message=f"the icon is {width}x{height}, not the {size}x{size} square",
            position=Position(asset=run.asset_id, stage="fit", field="stages.fit.mode"),
            fix=f"kiripix set {run.asset_id} fit mode=downscale" if mode == "grid" else None,
            owner_action=None if mode == "grid" else "Import a larger Source, or set the brief's size to match."))
    elif inner >= 1:
        findings += check_fit(run, None, (inner, inner))
    for finding in findings:
        if finding.position is not None:
            finding.position.asset, finding.position.stage = run.asset_id, "fit"
    return findings


ICON_SCHEMA_VERSION = 1  # 1: `asset` and `size` (ticket 0263)
ICON_FILE, ICON_RECORD = "icon.png", "icon.json"


def _export(run: StageRun) -> None:
    """What the game gets: the finished icon and its record. No scene: the game's inventory UI loads the texture."""
    shutil.copyfile(run.upstream["finish"] / "finish.png", run.output_dir / ICON_FILE)
    size, _ = _read_brief(run)
    record = {"schema_version": ICON_SCHEMA_VERSION, "asset": run.asset_id, "size": size}
    (run.output_dir / ICON_RECORD).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


ICON = KindSpec(
    name="icon",
    description="An item or skill icon at a fixed square size (16, 24 or 32 px): a Prop without footprint or origin.",
    stages=chain(
        StageSpec(
            name="brief",
            description="The icon's size (the Project's `[icon] size` unless set), the padding round it and notes.",
            params=(
                ParamSpec(name="size", type="int", default=0, minimum=0,
                          description="The square's side in px: 16, 24 or 32. 0 takes the Project's `[icon] size`."),
                ParamSpec(name="padding", type="int", default=DEFAULT_PADDING, minimum=0,
                          description="Transparent px kept round the subject: room for the outline."),
                ParamSpec(name="notes", type="str", default="", description="What the icon shows."),
            ),
            inputs=StageInputs(settings=["icon.size"]),
            checks=(CheckSpec(code="brief.size_invalid", description="The size is 16, 24 or 32."),
                    CheckSpec(code="brief.padding_too_large", description="The padding leaves room for the icon.")),
            owner_input="Writes the brief.",
            available_from="M5",
            run=_brief,
            check=_check_brief,
        ),
        StageSpec(
            name="source",
            description="Generated on a flat chroma background, or imported.",
            inputs=StageInputs(files=["src/*.png"]),
            decisions=(PICK,),
            checks=(CheckSpec(code="source.not_picked", description="A Source has been picked."),),
            owner_input="Picks one Variant.",
            available_from="M5",
            image="source.png",
            run=_source,
            needs_input=source_needs_input,
        ),
        StageSpec(
            name="cutout",
            description="Chroma key or matting on the full-size Source.",
            params=next(s for s in PROP.stages if s.name == "cutout").params,
            checks=next(s for s in PROP.stages if s.name == "cutout").checks,
            available_from="M5",
            image="cutout.png",
            run=_cutout,
            check=_check_cutout,
            runner_calls=_cutout_calls,
        ),
        StageSpec(
            name="fit",
            description="Grid snap or downscale onto the square less the padding, centred; alpha goes to the target grid "
                        "by majority vote.",
            inputs=StageInputs(upstream=["cutout", "brief"]),
            params=FIT_PARAMS,
            checks=(
                CheckSpec(code="icon.size", description="The output is exactly the brief's square."),
                CheckSpec(code="fit.padded", description="The grid output was padded up to the square (info)."),
                CheckSpec(code="fit.cropped", description="Downscale cropped part of the Source (info)."),
                CheckSpec(code="image.partial_alpha", description="Alpha is binary."),
            ),
            available_from="M5",
            image="fit.png",
            run=_fit,
            check=_check_fit,
        ),
        StageSpec(
            name="palette",
            description="Palette mapping and orphan cleanup.",
            inputs=StageInputs(settings=["palette"]),
            params=PALETTE_PARAMS,
            checks=(
                CheckSpec(code="palette.off_palette", description="Every opaque pixel is a palette colour."),
                CheckSpec(code="palette.mapping_error", description="The palette maps the image without a high error."),
            ),
            available_from="M5",
            image="palette.png",
            run=lambda run: run_palette(run, run.upstream["fit"] / "fit.png", "fit image"),
            check=check_palette,
        ),
        StageSpec(
            name="finish",
            description="Optional 1 px outline in a palette colour.",
            inputs=StageInputs(settings=["palette"]),
            params=next(s for s in PROP.stages if s.name == "finish").params,
            checks=(CheckSpec(code="palette.off_palette", description="Every opaque pixel is a palette colour."),),
            available_from="M5",
            image="finish.png",
            run=_finish,
            check=_check_finish,
        ),
        StageSpec(
            name="export",
            description="Builds what the game gets: `icon.png` and `icon.json`. `kiripix export` then writes them under "
                        "the export root's `icons/`.",
            version=2,  # 2: the Stage writes `icon.png` and `icon.json` (ticket 0263); it was a stub
            inputs=StageInputs(upstream=["finish", "brief"], settings=["export.godot"]),
            checks=(CheckSpec(code="export.no_target", description="The export target is set."),),
            output_root="out",
            available_from="M5",
            run=_export,
            needs_input=_export_needs_input,
            check=_check_export,
        ),
    ),
)
