"""`kiripix op register-piece`, `op match-tone` and `op seam-join` (ticket 0135): the join Ops on any images.

An Overlap is written `side:width[:offset]`, for example `east:200` or `south:120:-3`; a corner piece has two, comma
separated (`east:200,south:120`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kiripix.checks import check_join_gain, check_join_residual, check_seam_difference
from kiripix.commands.contract import Context, Outcome
from kiripix.commands.image_ops import OP_GROUP
from kiripix.commands.registry import CliMeta, command
from kiripix.core.errors import KiripixError, fail
from kiripix.core.images import load_rgba, save_png
from kiripix.ops import JOIN_SIDES, Overlap, has_partial_alpha, match_tone, register_piece, resample_piece, seam_join

_FORMAT = "side:width[:offset], side one of " + ", ".join(JOIN_SIDES)


def parse_overlaps(text: str, example: str) -> list[Overlap]:
    overlaps = []
    for part in text.split(","):
        fields = part.strip().split(":")
        try:
            if not 2 <= len(fields) <= 3 or fields[0] not in JOIN_SIDES:
                raise ValueError(part)
            overlaps.append(Overlap(fields[0], int(fields[1]), int(fields[2]) if len(fields) == 3 else 0))  # type: ignore[arg-type]
        except ValueError:
            raise fail(
                "join.overlap_invalid",
                f"{part!r} is not an overlap; write {_FORMAT}",
                fix=_help(example),
            ) from None
    return overlaps


def _spec(overlap: Overlap) -> str:
    return f"{overlap.side}:{overlap.width}:{overlap.offset}"


def _load(path: Path, context: Context) -> tuple[str, Any]:
    shown = str(path)
    rgba = load_rgba(context.cwd / path, shown)
    if has_partial_alpha(rgba):
        raise fail(
            "image.partial_alpha",
            f"{shown} has partially transparent pixels; a join treats a pixel as present only at alpha 255",
            owner_action=f"Make every pixel of {shown} fully opaque or fully transparent.",
        )
    return shown, rgba


def _help(example: str) -> str:
    """The Command's help, for an input only the caller can correct: its overlaps, widths and parameters."""
    return " ".join(example.split()[:3]) + " --help"


def _refused(error: ValueError, example: str) -> KiripixError:
    return fail("join.failed", str(error), fix=_help(example))


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: Path = Field(description="The Source the piece joins.")
    piece: Path = Field(description="The piece an image model painted from the base's edge.")
    overlap: str = Field(description=f"Where the piece lies, as {_FORMAT}; two comma-separated for a corner piece.")
    output: Path | None = Field(None, description="Where to write the piece resampled onto the base's pixel grid.")


class RegisterData(BaseModel):
    base: str
    piece: str
    scale_x: float
    scale_y: float
    shift_x: float = Field(description="Where the piece's first pixel lands in the base's coordinates.")
    shift_y: float
    residual: float = Field(description="Root-mean-square px between the edge patches and the fit.")
    patches: int
    output: str | None
    origin: tuple[int, int] | None = Field(description="Where the resampled piece's first pixel lands, when written.")
    overlap: list[str] = Field(description="The resampled piece's Overlaps, for `op match-tone` and `op seam-join`.")

    def text(self) -> str:
        return (
            f"{self.piece}: scale {self.scale_x:.4f} x {self.scale_y:.4f}, shift ({self.shift_x:.2f}, {self.shift_y:.2f}), "
            f"residual {self.residual:.2f} px over {self.patches} patches"
        )


@command(
    "op register-piece",
    summary="Estimate the scale and shift that put a piece on a base, from patches along the overlap.",
    input=RegisterInput,
    output=RegisterData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("base", "piece")),
    group_summary=OP_GROUP,
)
def op_register_piece(arguments: RegisterInput, context: Context) -> Outcome[RegisterData]:
    example = f"kiripix op register-piece {arguments.base} {arguments.piece}"
    overlaps = parse_overlaps(arguments.overlap, example)
    base_name, base = _load(arguments.base, context)
    piece_name, piece = _load(arguments.piece, context)
    try:
        registration = register_piece(base, piece, overlaps)
    except ValueError as error:
        raise _refused(error, example) from None
    output = None
    origin = None
    placed: list[str] = []
    if arguments.output is not None:
        resampled, origin = resample_piece(piece, registration)
        save_png(context.cwd / arguments.output, resampled)
        output = str(arguments.output)
        placed = [_spec(Overlap.placed(o.side, base.shape, resampled.shape, origin)) for o in overlaps]
    return Outcome(
        RegisterData(
            base=base_name,
            piece=piece_name,
            scale_x=round(registration.scale_x, 6),
            scale_y=round(registration.scale_y, 6),
            shift_x=round(registration.shift_x, 3),
            shift_y=round(registration.shift_y, 3),
            residual=round(registration.residual, 3),
            patches=registration.patches,
            output=output,
            origin=origin,
            overlap=placed,
        ),
        check_join_residual(registration.residual, registration.patches, piece_name),
    )


class ToneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: Path = Field(description="The Source the piece joins.")
    piece: Path = Field(description="The piece, already on the base's pixel grid (`op register-piece --output`).")
    output: Path = Field(description="Where to write the toned piece.")
    overlap: str = Field(description=f"Where the piece lies on the base, as {_FORMAT}.")
    sigma: float = Field(24.0, gt=0, description="How far along the join the gain is smoothed, in px.")


class ToneData(BaseModel):
    base: str
    piece: str
    output: str
    gain_low: float
    gain_high: float

    def text(self) -> str:
        return f"Wrote {self.output}: gain {self.gain_low:.3f} to {self.gain_high:.3f}"


@command(
    "op match-tone",
    summary="Match a piece's brightness to the base with a smoothed gain per row (or column) from the overlap.",
    input=ToneInput,
    output=ToneData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("base", "piece", "output")),
    group_summary=OP_GROUP,
)
def op_match_tone(arguments: ToneInput, context: Context) -> Outcome[ToneData]:
    example = f"kiripix op match-tone {arguments.base} {arguments.piece} {arguments.output}"
    overlaps = parse_overlaps(arguments.overlap, example)
    if len(overlaps) != 1:
        raise fail("join.overlap_invalid", "match-tone takes one overlap", fix=f"{example} --overlap {_spec(overlaps[0])}")
    base_name, base = _load(arguments.base, context)
    piece_name, piece = _load(arguments.piece, context)
    try:
        toned, gain = match_tone(base, piece, overlaps[0], arguments.sigma)
    except ValueError as error:
        raise _refused(error, example) from None
    save_png(context.cwd / arguments.output, toned)
    return Outcome(
        ToneData(
            base=base_name,
            piece=piece_name,
            output=str(arguments.output),
            gain_low=round(gain.low, 4),
            gain_high=round(gain.high, 4),
        ),
        check_join_gain(gain.low, gain.high, piece_name),
    )


class SeamInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: Path = Field(description="The Source the piece joins.")
    piece: Path = Field(description="The piece, on the base's pixel grid and toned.")
    output: Path = Field(description="Where to write the joined image.")
    overlap: str = Field(description=f"Where the piece lies on the base, as {_FORMAT}.")
    blend: int = Field(6, ge=0, description="Px over which the two images are blended across the seam; 0 cuts hard.")


class SeamData(BaseModel):
    base: str
    piece: str
    output: str
    width: int
    height: int
    seam_length: float = Field(description="The seam's length in px.")
    mean_difference: float = Field(description="Mean absolute RGB difference (0..255) of the pixels the seam cuts.")
    base_origin: tuple[int, int] = Field(description="Where the base's first pixel lies in the joined image.")
    piece_origin: tuple[int, int]

    def text(self) -> str:
        return (
            f"Wrote {self.output}: {self.width}x{self.height}, seam {self.seam_length:.0f} px, "
            f"difference {self.mean_difference:.1f}"
        )


@command(
    "op seam-join",
    summary="Join a piece to a base along the least-difference path through their overlap, blended.",
    input=SeamInput,
    output=SeamData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("base", "piece", "output")),
    group_summary=OP_GROUP,
)
def op_seam_join(arguments: SeamInput, context: Context) -> Outcome[SeamData]:
    example = f"kiripix op seam-join {arguments.base} {arguments.piece} {arguments.output}"
    overlaps = parse_overlaps(arguments.overlap, example)
    if len(overlaps) != 1:
        raise fail("join.overlap_invalid", "seam-join takes one overlap", fix=f"{example} --overlap {_spec(overlaps[0])}")
    base_name, base = _load(arguments.base, context)
    piece_name, piece = _load(arguments.piece, context)
    try:
        joined, seam = seam_join(base, piece, overlaps[0], arguments.blend)
    except ValueError as error:
        raise _refused(error, example) from None
    save_png(context.cwd / arguments.output, joined)
    return Outcome(
        SeamData(
            base=base_name,
            piece=piece_name,
            output=str(arguments.output),
            width=int(joined.shape[1]),
            height=int(joined.shape[0]),
            seam_length=seam.length,
            mean_difference=seam.mean_difference,
            base_origin=seam.base_origin,
            piece_origin=seam.piece_origin,
        ),
        check_seam_difference(seam.mean_difference, seam.length, piece_name),
    )
