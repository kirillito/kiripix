"""Growing the Project's palette from an image: `op palette-suggest` (an agent may run it, it only writes a proposal) and
`palette-add` (owner-only, it appends the proposal's colours to the palette)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
from pydantic import BaseModel, ConfigDict, Field

from kiripix.checks import check_palette
from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.image_ops import OP_GROUP, resolve_palette
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import atomic
from kiripix.core.assets import list_assets
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.images import load_rgba, png_bytes
from kiripix.core.project import Project, find_project
from kiripix.ops import Grid, downscale, parse_gpl, quantize, suggest_palette

PROPOSAL_SCHEMA_VERSION = 1
PROPOSALS_DIR = "palette-proposals"
DEFAULT_SCALE = 2.15
DEFAULT_MIN_DISTANCE = 0.03  # OKLab; the closest pair in the art repo's 64 colours is 0.032 (see backlog/0077)
DEFAULT_PREFIX = "added"
_SWATCH = 16


def _hex(rgb: Any) -> str:
    return f"#{int(rgb[0]):02X}{int(rgb[1]):02X}{int(rgb[2]):02X}"


class PaletteProposal(BaseModel):
    """`proposal.json`: what `palette-suggest` found, and what it was made from, so `palette-add` can tell it's current."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    image: str
    image_hash: str
    palette: str = Field(description="The palette it was made for, as given; the Project's palette's path by default.")
    palette_hash: str
    scale: float
    min_distance: float
    add: int
    colours: list[str] = Field(min_length=1)

    def again(self) -> str:
        """The `palette-suggest` that makes this proposal afresh, for the Project's palette."""
        return f"kiripix op palette-suggest {self.image} --add {self.add} --scale {self.scale} " \
               f"--min-distance {self.min_distance}"


# op palette-suggest


class PaletteSuggestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: Path = Field(description="The image to take colours from.")
    add: int = Field(ge=0, description="The most colours to suggest; fewer come back when the palette already fits.")
    scale: float = Field(
        DEFAULT_SCALE,
        ge=1,
        description="Source pixels per target pixel: the image is downscaled as `fit` does first, because the game "
        "never sees noise at full size. The default is the scale the Project's rooms use so far.",
    )
    min_distance: float = Field(
        DEFAULT_MIN_DISTANCE,
        ge=0,
        description="The least OKLab distance between a suggested colour and any other colour in the palette or the "
        f"suggestion; the default is {DEFAULT_MIN_DISTANCE}, a little under the closest pair in the Owner's 64-colour "
        "palette (0.032), so new colours are no closer together than the old ones.",
    )
    palette: Path | None = Field(None, description="A .gpl or .hex palette; the Project's palette by default.")


class PaletteSuggestData(BaseModel):
    image: str
    palette: str
    scale: float
    min_distance: float
    width: int = Field(description="Width of the downscaled image, in target pixels.")
    height: int
    colours: list[str] = Field(description="The suggested colours as #RRGGBB, most used first.")
    error_before: float = Field(description="Mean OKLab distance from the image's pixels to their nearest palette colour.")
    error_after: float = Field(description="The same, with the suggested colours added.")
    proposal: str | None = Field(description="The proposal file for `kiripix palette-add`; null when nothing is suggested.")
    swatch: str | None
    mapped_before: str = Field(description="The downscaled image mapped through today's palette.")
    mapped_after: str = Field(description="The downscaled image mapped through the palette with the new colours.")
    note: str | None = None

    def text(self) -> str:
        if not self.colours:
            return f"{self.palette} already fits {self.image}: nothing to add (error {self.error_before:.4f})"
        return (
            f"{len(self.colours)} colours suggested for {self.palette}: error {self.error_before:.4f} -> "
            f"{self.error_after:.4f}; proposal {self.proposal}"
        )


def _swatch(colours: np.ndarray) -> np.ndarray:
    strip = np.repeat(np.repeat(colours.reshape(1, -1, 3), _SWATCH, axis=0), _SWATCH, axis=1)
    return np.dstack([strip, np.full(strip.shape[:2], 255, dtype=np.uint8)])


@command(
    "op palette-suggest",
    summary="Suggest up to N colours the palette lacks for an image; changes nothing in the palette.",
    input=PaletteSuggestInput,
    output=PaletteSuggestData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("image",)),
    group_summary=OP_GROUP,
)
def op_palette_suggest(arguments: PaletteSuggestInput, context: Context) -> Outcome[PaletteSuggestData]:
    shown = str(arguments.image)
    project = find_project(context.cwd)
    example = f"kiripix op palette-suggest {shown} --add {arguments.add}"
    palette, palette_name = resolve_palette(arguments.palette, context, example)
    image_path = context.cwd / arguments.image
    rgba = load_rgba(image_path, shown)
    height, width = rgba.shape[:2]
    target_w, target_h = max(1, round(width / arguments.scale)), max(1, round(height / arguments.scale))
    small = downscale(rgba, Grid.to_size(width, height, target_w, target_h))
    palette_rgb = palette.rgb()
    suggestion = suggest_palette(small, palette_rgb, arguments.add, arguments.min_distance)
    both = np.concatenate([palette_rgb, suggestion.colours])

    image_hash = hash_bytes(image_path.read_bytes())
    palette_file = context.cwd / arguments.palette if arguments.palette else project.root / palette_name
    palette_hash = hash_bytes(palette_file.read_bytes())
    made_from = hash_bytes(f"{image_hash} {palette_hash} {arguments.add} {arguments.scale} {arguments.min_distance}"
                           .encode())
    folder = project.state_dir / PROPOSALS_DIR / f"{arguments.image.stem}-{made_from[:8]}"  # one per set of arguments
    before_path, after_path = folder / "mapped-before.png", folder / "mapped-after.png"
    atomic.write_bytes(before_path, png_bytes(quantize(small, palette_rgb)))
    atomic.write_bytes(after_path, png_bytes(quantize(small, both)))
    swatch_path = folder / "swatch.png"
    proposal_path = folder / "proposal.json"
    colours = [_hex(c) for c in suggestion.colours]
    if colours:
        atomic.write_bytes(swatch_path, png_bytes(_swatch(suggestion.colours)))
        proposal = PaletteProposal(
            schema_version=PROPOSAL_SCHEMA_VERSION, image=shown, image_hash=image_hash, palette=palette_name,
            palette_hash=palette_hash, scale=arguments.scale, min_distance=arguments.min_distance, add=arguments.add,
            colours=colours,
        )
        atomic.write_json(proposal_path, proposal.model_dump())
    else:
        swatch_path.unlink(missing_ok=True)
        proposal_path.unlink(missing_ok=True)
    data = PaletteSuggestData(
        image=shown,
        palette=palette_name,
        scale=arguments.scale,
        min_distance=arguments.min_distance,
        width=target_w,
        height=target_h,
        colours=colours,
        error_before=suggestion.error_before,
        error_after=suggestion.error_after,
        proposal=project.relative(proposal_path) if colours else None,
        swatch=project.relative(swatch_path) if colours else None,
        mapped_before=project.relative(before_path),
        mapped_after=project.relative(after_path),
        note=None if colours else f"{palette_name} already fits {shown}: no colour is farther than "
        f"{arguments.min_distance} from it",
    )
    return Outcome(data)


# palette-add


class PaletteAddInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: Path = Field(description="A proposal file written by `kiripix op palette-suggest`.")
    name: str = Field(DEFAULT_PREFIX, min_length=1, pattern=r"^[A-Za-z0-9_]+$",
                      description="The prefix of the new colours' names: <prefix>-01, <prefix>-02 and so on.")


class PaletteAddData(BaseModel):
    palette: str
    added: list[str] = Field(description="The new lines' colours and names, as '#RRGGBB name'.")
    colours_total: int
    assets_made_stale: list[str] = Field(
        description="Assets (rooms and props) with a Stage that was up to date and now isn't; nothing is rebuilt, "
                    "`run` does that."
    )

    def text(self) -> str:
        stale = f"; {len(self.assets_made_stale)} assets are now stale (run them)" if self.assets_made_stale else ""
        return f"Added {len(self.added)} colours to {self.palette} ({self.colours_total} in all){stale}"


_WHERE = f"Name a proposal.json that `kiripix op palette-suggest` wrote under .kiripix/{PROPOSALS_DIR}/."


def _read_proposal(path: Path, shown: str) -> PaletteProposal:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise fail("palette.proposal_missing", f"no proposal at {shown}", owner_action=_WHERE) from None
    except (OSError, ValueError):
        raise fail("palette.proposal_invalid", f"{shown} is not a palette proposal", owner_action=_WHERE) from None
    image = loaded.get("image") if isinstance(loaded, dict) else None
    if not isinstance(loaded, dict) or loaded.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        message = f"{shown} is not a palette proposal this Kiripix reads"
        if isinstance(image, str):
            raise fail("palette.proposal_invalid", message, fix=f"kiripix op palette-suggest {image} --add 16")
        raise fail("palette.proposal_invalid", message, owner_action=_WHERE)
    try:
        return PaletteProposal.model_validate(loaded)
    except ValueError as error:
        raise fail("palette.proposal_invalid", f"{shown} is not a palette proposal: {error}",
                   owner_action=_WHERE) from None


def _stale_assets(project: Project) -> set[str]:
    assets, _ = list_assets(project)
    cache = HashCache(project.state_dir)
    found: set[str] = set()
    for asset in assets:
        try:
            states = AssetGraph(project, asset, cache).states()
        except KiripixError:
            continue
        if any(s.status == "stale" for s in states):
            found.add(asset.id)
    return found


@command(
    "palette-add",
    summary="Append a proposal's colours to the Project's palette (owner-only); nothing is rebuilt.",
    input=PaletteAddInput,
    output=PaletteAddData,
    kind="owner-only",
    mcp="owner-only",
    locks=LockNeeds(project=True),
    cli=CliMeta(positional=("proposal",)),
)
def palette_add(arguments: PaletteAddInput, context: Context) -> Outcome[PaletteAddData]:
    shown = str(arguments.proposal)
    project = find_project(context.cwd)
    proposal = _read_proposal(context.cwd / arguments.proposal, shown)
    relative = project.settings.project.palette
    path = project.root / relative
    if path.suffix.lower() != ".gpl":
        raise fail("palette.unknown_format", f"{relative} is not a .gpl palette, so colours can't be appended",
                   owner_action=f"Keep the Project's palette as a GIMP .gpl file.")
    if Path(proposal.palette) != Path(relative):
        raise fail(
            "palette.proposal_other_palette",
            f"{shown} was made for {proposal.palette}, not the Project's palette {relative}",
            fix=proposal.again(),
        )
    original = path.read_bytes()
    if hash_bytes(original) != proposal.palette_hash:
        raise fail(
            "palette.proposal_stale",
            f"{shown} was made for another version of {relative}: the palette has changed since",
            fix=proposal.again(),
        )
    existing = parse_gpl(original.decode("utf-8"))
    prefix = arguments.name
    taken = [int(m.group(1)) for e in existing.entries if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", e.name))]
    number = max(taken, default=0)
    lines: list[str] = []
    added: list[str] = []
    for hex_colour in proposal.colours:
        number += 1
        r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
        name = f"{prefix}-{number:02d}"
        lines.append(f"{r:3d} {g:3d} {b:3d}\t{name}")
        added.append(f"{hex_colour} {name}")
    updated = original + (b"" if original.endswith(b"\n") else b"\n") + ("\n".join(lines) + "\n").encode("utf-8")
    problems = check_palette(parse_gpl(updated.decode("utf-8")), relative)
    if problems:
        raise KiripixError(problems, ExitCode.CHECK_FAILED)
    before = _stale_assets(project)
    atomic.write_bytes(path, updated)
    stale = sorted(_stale_assets(project) - before)
    return Outcome(
        PaletteAddData(palette=relative, added=added, colours_total=len(existing.entries) + len(lines),
                       assets_made_stale=stale)
    )
