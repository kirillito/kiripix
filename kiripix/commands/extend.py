"""`kiripix extend <id> canvas|add <png>|undo|done` (ticket 0136): grow a room's Source one piece at a time.

The Owner makes each piece in the image model's own UI. `canvas` writes what to paste into it, `add` registers, tones
and seams the piece onto the image with the join Ops (ticket 0135), `undo` drops the last piece, and `done` imports the
joined image as a Variant, which `pick` takes as for any import. All the work is in `kiripix.core.extend`.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import extend
from kiripix.core.assets import is_asset_id, load_asset
from kiripix.core.errors import fail
from kiripix.core.project import find_project


class ExtendInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    action: Literal["canvas", "add", "undo", "done"] = Field(
        description="canvas: write the canvas for the next piece. add: join a piece onto the image. undo: drop the "
                    "last piece. done: import the joined image as a Variant.")
    piece: Path | None = Field(None, description="With add: the piece's PNG, made from the canvas.")
    side: str | None = Field(
        None, description="With canvas: the side to extend, east, south, west or north, or a corner of two such as "
                          "east,south. With add: the same, if given it must be the canvas' side.")
    keep: int | None = Field(None, ge=1, description="With canvas: px of the image kept in the canvas along the join "
                                                     "(a third of the canvas by default).")
    offset: int = Field(0, description="With canvas: where along the edge the canvas starts, px from the image's top "
                                       "(east, west) or left (north, south).")


class ExtendData(BaseModel):
    asset: str
    action: str
    canvas: str | None = Field(None, description="With canvas: the path of the canvas PNG to paste into the image model.")
    canvas_size: tuple[int, int] | None = None
    sides: list[str] = []
    keep: tuple[int, int] | None = None
    piece: str | None = Field(None, description="With add or undo: the piece's name, the start of its hash.")
    width: int | None = Field(None, description="With add or done: the joined image's size.")
    height: int | None = None
    residual: float | None = Field(None, description="With add: root-mean-square px of the registration.")
    scale: tuple[float, float] | None = None
    gain: tuple[float, float] | None = Field(None, description="With add: the lowest and highest tone gain.")
    seam_length: float | None = None
    seam_difference: float | None = Field(None, description="With add: mean absolute RGB difference along the seam.")
    pieces: int = Field(0, description="The live pieces after the Command.")
    variant: str | None = Field(None, description="With done: the Variant the joined image became.")
    created: bool | None = None
    transparent_pixels: int | None = Field(None, description="With done: pixels still without picture (an unfilled corner).")

    def text(self) -> str:
        if self.action == "canvas":
            w, h = self.canvas_size or (0, 0)
            return (f"{self.asset}: wrote {self.canvas} ({w}x{h}, strip kept {self.keep[0] if self.keep else 0} x "
                    f"{self.keep[1] if self.keep else 0} px, {'+'.join(self.sides)}); paste it into the image model, then "
                    f"kiripix extend {self.asset} add <png>")
        if self.action == "add":
            return (f"{self.asset}: joined {self.piece} ({'+'.join(self.sides)}): {self.width}x{self.height}, residual "
                    f"{self.residual:.2f} px, gain {self.gain[0]:.3f} to {self.gain[1]:.3f}, seam "  # type: ignore[index]
                    f"{self.seam_length:.0f} px (difference {self.seam_difference:.1f}); {self.pieces} pieces")
        if self.action == "undo":
            return f"{self.asset}: dropped the piece {self.piece}; {self.pieces} pieces"
        added = "added" if self.created else "already had"
        return (f"{self.asset}: {added} the Variant {self.variant} ({self.width}x{self.height}); pick it with "
                f"kiripix pick {self.asset} {self.variant}")


def _asset_lock(arguments: ExtendInput) -> str | None:
    return arguments.asset if is_asset_id(arguments.asset) else None


@command(
    "extend",
    summary="Grow a room's Source past its edge, one piece at a time: canvas (write the canvas for the next piece), "
            "add <png> (join a piece onto the image), undo (drop the last piece), done (import the joined image as "
            "a Variant).",
    input=ExtendInput,
    output=ExtendData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "action", "piece")),
    locks=LockNeeds(asset=_asset_lock),
    files=("piece",),
)
def extend_command(arguments: ExtendInput, context: Context) -> Outcome[ExtendData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    example = f"kiripix extend {asset.id} {arguments.action}"
    sides = extend.parse_sides(asset, arguments.side, example) if arguments.side else None
    data = ExtendData(asset=asset.id, action=arguments.action)
    if arguments.action == "canvas":
        if sides is None:
            raise fail("extend.side_needed", "canvas needs the side to extend", fix=f"{example} --side east")
        path, size, keep, _ = extend.write_canvas(project, asset, sides, project.settings.extend.canvas,
                                                  arguments.keep, arguments.offset, example)
        data.canvas, data.canvas_size, data.keep, data.sides = project.relative(path), size, keep, sides
        data.pieces = len(extend.live_pieces(extend.read_journal(asset)))
        return Outcome(data)
    if arguments.action == "add":
        if arguments.piece is None:
            raise fail("extend.piece_needed", "add needs the piece's PNG", fix=f"{example} <png>")
        joined, findings = extend.add_piece(project, asset, context.cwd / arguments.piece, str(arguments.piece),
                                            sides, example)
        data.piece, data.sides, data.width, data.height = joined.piece, joined.sides, joined.width, joined.height
        data.residual, data.scale, data.gain = joined.residual, joined.scale, joined.gain
        data.seam_length, data.seam_difference, data.pieces = joined.seam_length, joined.seam_difference, joined.pieces
        return Outcome(data, findings)
    if arguments.action == "undo":
        data.piece, data.pieces = extend.undo(project, asset)
        return Outcome(data)
    variant, created, size, holes, live = extend.done(project, asset)
    data.variant, data.created, data.pieces = variant, created, len(live)
    data.width, data.height, data.transparent_pixels = size[0], size[1], holes
    return Outcome(data, extend.hole_findings(asset, holes))
