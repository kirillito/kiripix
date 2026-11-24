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
from kiripix.core.assets import list_assets, load_asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.images import load_palette, load_rgba, png_bytes
from kiripix.core.project import Project, find_project
from kiripix.ops import Grid, downscale, parse_gpl, quantize, suggest_palette
from kiripix.recipes.common import line_thresholds

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
    asset: str | None = Field(None, description="The Asset it was made from (then `image` is its ID), or null for an image.")
    box: list[int] | None = Field(None, description="With `asset`: the box [x, y, width, height] in target px it was made "
                                                    "from; null for the whole room.")

    def again(self) -> str:
        """The `palette-suggest` that makes this proposal afresh, for the Project's palette."""
        if self.asset is not None:
            box = _box_flag(self.box)
            return f"kiripix op palette-suggest --asset {self.asset}{box} --add {self.add} " \
                   f"--min-distance {self.min_distance}"
        return f"kiripix op palette-suggest {self.image} --add {self.add} --scale {self.scale} " \
               f"--min-distance {self.min_distance}"


# op palette-suggest


def _asset_inputs(project: Project, asset_id: str) -> tuple[Grid, dict[str, float], Path, str]:
    """A room's or prop's `fit` Grid transform and line thresholds, its Source's path, and a hash of them (what a proposal was
    made from). Refused for another Kind, and while `fit` isn't built."""
    asset = load_asset(project, asset_id)
    if asset.kind not in ("room", "prop"):
        raise fail("palette.suggest_input", f"--asset takes a room or a prop; {asset_id} is a {asset.kind}, which has "
                   f"no fit Grid transform to take a Source through",
                   fix="kiripix op palette-suggest <image> --add 16 --scale 1")
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    fit_spec = graph.spec("fit")
    if graph.state("fit").status not in ("done", "needs-review"):
        raise fail("palette.suggest_needs_fit", f"{asset_id}'s fit Stage isn't built, so there is no Grid transform to "
                   f"take the Source through", fix=f"kiripix run {asset_id} fit")
    grid_bytes = (graph.output_dir(fit_spec) / "grid.json").read_bytes()
    source_path = graph.output_dir(graph.spec("source")) / "source.png"
    record = json.loads(grid_bytes.decode("utf-8"))
    made_from = hash_bytes(hash_bytes(source_path.read_bytes()).encode() + grid_bytes)
    return Grid.from_json(record), line_thresholds(record), source_path, made_from


def _parse_box(given: str) -> tuple[int, int, int, int] | None:
    parts = given.split(",")
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (int(part) for part in parts)
    except ValueError:
        return None
    return x, y, w, h


def _asset_source(project: Project, asset_id: str, given: str | None, add: int) -> tuple[Any, list[int], float, str]:
    """The Asset's Source cut to `given` (x,y,w,h in target px, the whole room by default) and downscaled by the `fit`
    Grid transform: the image, the box, the scale and the hash of what it was made from."""
    grid, thresholds, source_path, made_from = _asset_inputs(project, asset_id)
    source = load_rgba(source_path, str(source_path))
    cells_x, cells_y = grid.cells_x, grid.cells_y
    if given is None:
        x, y, w, h = 0, 0, cells_x, cells_y
    else:
        parsed = _parse_box(given)
        if parsed is None or parsed[0] < 0 or parsed[1] < 0 or parsed[2] < 1 or parsed[3] < 1                 or parsed[0] + parsed[2] > cells_x or parsed[1] + parsed[3] > cells_y:
            raise fail("palette.box_invalid", f"--box {given!r} isn't x,y,w,h inside the room's {cells_x}x{cells_y} "
                       f"target pixels", fix=f"kiripix op palette-suggest --asset {asset_id} --box 0,0,{cells_x},"
                       f"{cells_y} --add {add}")
        x, y, w, h = parsed
    edges_x, edges_y = grid.edges_x(), grid.edges_y()
    left, right, top, bottom = int(edges_x[x]), int(edges_x[x + w]), int(edges_y[y]), int(edges_y[y + h])
    if right > source.shape[1] or bottom > source.shape[0]:  # a Grid that reaches past the Source: nothing to read there
        raise fail("palette.box_invalid", f"the box reaches past the Source, which is {source.shape[1]}x"
                   f"{source.shape[0]} px", fix=f"kiripix op palette-suggest --asset {asset_id} --box 0,0,{cells_x},"
                   f"{cells_y} --add {add}")
    crop = source[top:bottom, left:right]
    small = downscale(crop, Grid.to_size(right - left, bottom - top, w, h), **thresholds)
    return small, [x, y, w, h], float(grid.scale_x), made_from


class PaletteSuggestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: Path | None = Field(None, description="The image to take colours from; or name an Asset with --asset.")
    asset: str | None = Field(
        None,
        description="A room (or prop) whose `fit` is built: its Source is taken at its own Grid transform, so --scale "
        "isn't used (the room's is). The proposal names the Asset and the box.",
    )
    box: str | None = Field(
        None,
        description="With --asset: only this part, x,y,w,h in target pixels (mapped through the Grid transform to the "
        "Source); the whole room by default.",
    )
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
    image: str = Field(description="The image as given, or the Asset's ID with --asset.")
    palette: str
    scale: float = Field(description="Source pixels per target pixel; with --asset, the room's own.")
    min_distance: float
    box: list[int] | None = Field(None, description="With --asset: the box [x, y, width, height] in target px.")
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
    project = find_project(context.cwd)
    if (arguments.image is None) == (arguments.asset is None):
        raise fail("palette.suggest_input", "name one image or one --asset to take colours from, not both or neither",
                   fix=f"kiripix op palette-suggest --asset room.<name> --add {arguments.add}")
    if arguments.box is not None and arguments.asset is None:
        raise fail("palette.suggest_input", "--box goes with --asset: an image is taken whole",
                   fix=f"kiripix op palette-suggest {arguments.image} --add {arguments.add}")
    box: list[int] | None = None
    scale = arguments.scale
    if arguments.asset is not None:
        shown = arguments.asset
        example = f"kiripix op palette-suggest --asset {shown} --add {arguments.add}"
        small, box, scale, image_hash = _asset_source(project, shown, arguments.box, arguments.add)
        stem = shown
        made_extra = f"{shown} {box}"
    else:
        assert arguments.image is not None
        shown = str(arguments.image)
        example = f"kiripix op palette-suggest {shown} --add {arguments.add}"
        image_path = context.cwd / arguments.image
        rgba = load_rgba(image_path, shown)
        height, width = rgba.shape[:2]
        target_w, target_h = max(1, round(width / arguments.scale)), max(1, round(height / arguments.scale))
        small = downscale(rgba, Grid.to_size(width, height, target_w, target_h))
        image_hash = hash_bytes(image_path.read_bytes())
        stem = arguments.image.stem
        made_extra = ""
    palette, palette_name = resolve_palette(arguments.palette, context, example)
    target_h, target_w = small.shape[:2]
    palette_rgb = palette.rgb()
    suggestion = suggest_palette(small, palette_rgb, arguments.add, arguments.min_distance)
    both = np.concatenate([palette_rgb, suggestion.colours])

    palette_file = context.cwd / arguments.palette if arguments.palette else project.root / palette_name
    palette_hash = hash_bytes(palette_file.read_bytes())
    made_from = hash_bytes(f"{image_hash} {palette_hash} {arguments.add} {scale} {arguments.min_distance} {made_extra}"
                           .encode())
    folder = project.state_dir / PROPOSALS_DIR / f"{stem}-{made_from[:8]}"  # one per set of arguments
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
            palette_hash=palette_hash, scale=scale, min_distance=arguments.min_distance, add=arguments.add,
            colours=colours, asset=arguments.asset, box=box,
        )
        atomic.write_json(proposal_path, proposal.model_dump())
    else:
        swatch_path.unlink(missing_ok=True)
        proposal_path.unlink(missing_ok=True)
    data = PaletteSuggestData(
        image=shown,
        palette=palette_name,
        scale=scale,
        min_distance=arguments.min_distance,
        box=box,
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


def _box_flag(box: object) -> str:
    return f" --box {','.join(str(v) for v in box)}" if isinstance(box, list) and len(box) == 4 else ""


def _read_proposal(path: Path, shown: str) -> PaletteProposal:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise fail("palette.proposal_missing", f"no proposal at {shown}", owner_action=_WHERE) from None
    except (OSError, ValueError):
        raise fail("palette.proposal_invalid", f"{shown} is not a palette proposal", owner_action=_WHERE) from None
    image = loaded.get("image") if isinstance(loaded, dict) else None
    if isinstance(loaded, dict) and loaded.get("asset") is not None:
        image = None  # made from an Asset: the fix below would name an image
    if not isinstance(loaded, dict) or loaded.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        if isinstance(loaded, dict) and isinstance(loaded.get("asset"), str):
            raise fail("palette.proposal_invalid", f"{shown} is not a palette proposal this Kiripix reads",
                       fix=f"kiripix op palette-suggest --asset {loaded['asset']}{_box_flag(loaded.get('box'))} --add 16")
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
    if proposal.asset is not None:
        try:
            _, _, _, now = _asset_inputs(project, proposal.asset)
        except KiripixError as error:
            if any(f.code == "palette.suggest_needs_fit" for f in error.findings):
                raise
            raise fail("palette.proposal_stale", f"{shown} was made from {proposal.asset}, which can't be read now",
                       fix=proposal.again()) from None
        if now != proposal.image_hash:
            raise fail(
                "palette.proposal_stale",
                f"{shown} was made from another version of {proposal.asset}'s Source or fit: it has changed since",
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


# palette


class PaletteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaletteColour(BaseModel):
    index: int = Field(description="Position in the palette file, from 0.")
    hex: str = Field(description="#rrggbb, lower case.")
    name: str | None = Field(description="The colour's name in the file, or null when it has none.")


class PaletteData(BaseModel):
    palette: str = Field(description="The palette file, as the `palette` setting gives it, relative to the Project.")
    colours: list[PaletteColour] = Field(description="Every colour, in file order.")

    def text(self) -> str:
        return "\n".join(f"{c.index:3d}  {c.hex}  {c.name or ''}".rstrip() for c in self.colours)


@command(
    "palette",
    summary="The Project's palette: its file and every colour, in file order, as the Stages read it.",
    input=PaletteInput,
    output=PaletteData,
    kind="probe",
    mcp="exposed",
)
def palette_show(arguments: PaletteInput, context: Context) -> Outcome[PaletteData]:
    project = find_project(context.cwd)
    relative = project.settings.project.palette
    palette = load_palette(project.root / relative, relative)
    colours = [PaletteColour(index=i, hex=e.hex.lower(), name=e.name or None) for i, e in enumerate(palette.entries)]
    return Outcome(PaletteData(palette=relative, colours=colours))
