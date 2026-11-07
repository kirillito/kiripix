"""`kiripix op`: Ops run directly on any image, outside Recipes."""

from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from kiripix.checks import check_alpha, check_conformance
from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.registry import CliMeta, command
from kiripix.core.errors import KiripixError, fail
from kiripix.core.images import load_palette, load_rgba, save_png
from kiripix.core.project import find_root
from kiripix.core.settings import load_project_settings
from kiripix.ops import BayerSize, ConformanceReport, Palette, conformance, quantize

OP_GROUP = "Run one Op directly on an image."
Dither = Literal["none", "bayer2", "bayer4", "bayer8"]
_BAYER: dict[str, BayerSize] = {"none": 0, "bayer2": 2, "bayer4": 4, "bayer8": 8}


class ConformanceData(BaseModel):
    """How an image keeps to the palette. Positions are [x, y], the first few in row-major order."""

    image: str
    palette: str
    width: int
    height: int
    opaque: int
    transparent: int
    partial_alpha: int
    off_palette: int
    first_off_palette: list[tuple[int, int]]
    first_partial_alpha: list[tuple[int, int]]

    @classmethod
    def from_report(cls, report: ConformanceReport, image: str, palette: str) -> "ConformanceData":
        return cls(image=image, palette=palette, **report.__dict__)

    def text(self) -> str:
        return (
            f"{self.image}: {self.width}x{self.height}, {self.off_palette} pixels off {self.palette}, "
            f"{self.partial_alpha} partially transparent"
        )


def resolve_palette(given: Path | None, context: Context, example: str) -> tuple[Palette, str]:
    """The palette named on the command line, or else the Project's."""
    if given is not None:
        return load_palette(context.cwd / given, str(given)), str(given)
    root = find_root(context.cwd)
    if root is None:
        raise fail(
            "palette.not_set",
            "no --palette given, and not inside a Project",
            fix=f"{example} --palette style/palette.gpl",
        )
    relative = load_project_settings(root / "kiripix.toml").project.palette
    return load_palette(root / relative, relative), relative


class QuantizeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: Path = Field(description="The image to map.")
    output: Path = Field(description="Where to write the mapped PNG.")
    palette: Path | None = Field(None, description="A .gpl or .hex palette; the Project's palette by default.")
    dither: Dither = Field("none", description="Ordered Bayer dithering in OKLab, or none for strict mapping.")
    strength: float = Field(1.0, ge=0, le=1, description="Dither strength, from 0 to 1.")


class QuantizeData(BaseModel):
    input: str
    output: str
    palette: str
    width: int
    height: int
    dither: Dither
    strength: float
    colours_used: int
    input_conformance: ConformanceData

    def text(self) -> str:
        return (
            f"Wrote {self.output}: {self.width}x{self.height}, {self.colours_used} colours of {self.palette}; "
            f"the input had {self.input_conformance.off_palette} pixels off the palette"
        )


@command(
    "op quantize",
    summary="Map an image to the palette in OKLab, strictly or with ordered dithering.",
    input=QuantizeInput,
    output=QuantizeData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("input", "output")),
    group_summary=OP_GROUP,
)
def op_quantize(arguments: QuantizeInput, context: Context) -> Outcome[QuantizeData]:
    example = f"kiripix op quantize {arguments.input} {arguments.output}"
    palette, palette_name = resolve_palette(arguments.palette, context, example)
    shown = str(arguments.input)
    rgba = load_rgba(context.cwd / arguments.input, shown)
    palette_rgb = palette.rgb()
    report = conformance(rgba, palette_rgb)
    alpha = check_alpha(report, shown)
    if alpha:
        raise KiripixError(alpha, ExitCode.CHECK_FAILED)
    mapped = quantize(rgba, palette_rgb, _BAYER[arguments.dither], arguments.strength)
    save_png(context.cwd / arguments.output, mapped)
    opaque = mapped[mapped[..., 3] == 255][:, :3]
    return Outcome(
        QuantizeData(
            input=shown,
            output=str(arguments.output),
            palette=palette_name,
            width=int(rgba.shape[1]),
            height=int(rgba.shape[0]),
            dither=arguments.dither,
            strength=arguments.strength,
            colours_used=int(len(np.unique(opaque, axis=0))),
            input_conformance=ConformanceData.from_report(report, shown, palette_name),
        )
    )


class ConformanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: Path = Field(description="The image to check.")
    palette: Path | None = Field(None, description="A .gpl or .hex palette; the Project's palette by default.")


@command(
    "op conformance",
    summary="Check an image against the palette: pixels off the palette and partially transparent pixels.",
    input=ConformanceInput,
    output=ConformanceData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("image",)),
    group_summary=OP_GROUP,
)
def op_conformance(arguments: ConformanceInput, context: Context) -> Outcome[ConformanceData]:
    shown = str(arguments.image)
    stem = arguments.image.with_name(f"{arguments.image.stem}.quantized.png").as_posix()
    palette, palette_name = resolve_palette(arguments.palette, context, f"kiripix op conformance {shown}")
    report = conformance(load_rgba(context.cwd / arguments.image, shown), palette.rgb())
    palette_flag = f" --palette {arguments.palette}" if arguments.palette else ""
    findings = check_alpha(report, shown) + check_conformance(
        report, shown, fix=f"kiripix op quantize {shown} {stem}{palette_flag}"
    )
    return Outcome(
        ConformanceData.from_report(report, shown, palette_name),
        findings,
        ExitCode.CHECK_FAILED if findings else ExitCode.OK,
    )
