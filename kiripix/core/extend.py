"""`extend` (ticket 0136, spec §14 M4): grow a room's Source past its edge, one piece at a time, before `source`.

The pieces live in a journal of their own, `extend/journal.jsonl` in the Asset folder (append-only, one object per
line, LF), not as Decisions of a Stage: a piece is made outside Kiripix and joined here, and `undo` drops the last
one. Beside it, content-addressed so nothing is ever rewritten: `extend/pieces/<hash>.png` (the piece as the Owner
made it), `extend/joined/<hash>.png` (the joined image after it), and the latest canvas, `extend/canvas.png` with its
geometry in `extend/canvas.json` (what `add` needs to place the piece; it is rewritten whole, atomically).

The journal's live pieces are the `add` entries not dropped by an `undo` and not closed by a `done`. The current image
is the joined image of the newest live piece, or, with none, the room's picked Source. The caller holds the Asset lock.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kiripix.checks import Finding, check_join_gain, check_join_residual, check_seam_difference
from kiripix.checks.join import MAX_RESIDUAL
from kiripix.core import atomic, cancel, journal, sources
from kiripix.core.assets import Asset
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.images import load_rgba, png_bytes, read_as_png, save_png
from kiripix.core.project import Project
from kiripix.ops import (
    Overlap, has_partial_alpha, match_tone, register_piece, resample_piece, seam_join, srgb_to_oklab,
)
from kiripix.ops.join import Registration
from kiripix.ops.colour import U8

FOLDER = "extend"
JOURNAL = "journal.jsonl"
CANVAS_PNG = "canvas.png"
CANVAS_JSON = "canvas.json"
SCHEMA_VERSION = 1
# The canvas' flat fill, what the image model paints over: the first of these loud colours far enough from the kept
# strip's colours, so the model can't mistake the fill for picture (a grey fill matched the asphalt). Red first: the
# Owner's own canvases used it.
FILLS = ((237, 28, 36), (255, 0, 255), (0, 255, 0), (0, 0, 255), (0, 255, 255), (255, 255, 0))
FILL_DISTANCE = 0.15  # OKLab: far enough (red is 0.23 from grey asphalt)
FILL_SAMPLE = 20000  # strip pixels sampled to choose the fill
HASH_LENGTH = 16
HORIZONTAL = ("east", "west")
VERTICAL = ("north", "south")
BLEND = 6

Action = Literal["add", "undo", "done"]


class ExtendEntry(BaseModel):
    """One line of `extend/journal.jsonl`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    id: str
    action: Action
    sides: list[str] = Field(default_factory=list)  # add: the piece's sides, one, or two for a corner
    piece: str | None = None  # add: the piece's name (the start of its hash)
    base: str | None = None  # add: the image it was joined onto
    joined: str | None = None  # add: the image after it
    residual: float | None = None
    gain: tuple[float, float] | None = None
    seam_length: float | None = None
    seam_difference: float | None = None
    variant: str | None = None  # done: the Variant the joined image was imported as


class CanvasRecord(BaseModel):
    """`extend/canvas.json`: where the canvas lies on the current image, for `add` to place the piece."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    sides: list[str]
    keep: tuple[int, int]  # the strip kept along x and along y, px
    origin: tuple[int, int]  # where the canvas' first pixel lies in the current image's coordinates (may be negative)
    canvas: tuple[int, int]
    base: str  # the current image's name


def folder(asset: Asset) -> Path:
    return asset.dir / FOLDER


def _journal_path(asset: Asset) -> Path:
    return folder(asset) / JOURNAL


def _invalid(asset: Asset, path: Path, detail: str) -> KiripixError:
    name = f"{asset.id}/{FOLDER}/{path.name}"
    return fail("extend.record_invalid", f"{name} is not valid: {detail}",
                owner_action=f"Fix or remove {name}; `kiripix extend {asset.id} undo` drops the last piece.")


def read_journal(asset: Asset) -> list[ExtendEntry]:
    path = _journal_path(asset)
    if not path.is_file():
        return []
    entries = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = ExtendEntry.model_validate_json(line)
        except ValidationError as error:
            raise _invalid(asset, path, f"line {number}: {error.errors()[0]['msg']}") from None
        if entry.schema_version != SCHEMA_VERSION:
            raise fail("extend.record_invalid", f"{asset.id}/{FOLDER}/{JOURNAL} line {number} has schema_version "
                       f"{entry.schema_version}; this Kiripix reads {SCHEMA_VERSION}", owner_action="Update Kiripix.")
        entries.append(entry)
    return entries


def live_pieces(entries: list[ExtendEntry]) -> list[ExtendEntry]:
    """The `add` entries that count: `undo` drops the newest, `done` closes them all."""
    live: list[ExtendEntry] = []
    for entry in entries:
        if entry.action == "add":
            live.append(entry)
        elif entry.action == "undo" and live:
            live.pop()
        elif entry.action == "done":
            live.clear()
    return live


def _append(asset: Asset, entries: list[ExtendEntry]) -> None:
    atomic.append_jsonl_many(_journal_path(asset), [e.model_dump(mode="json", exclude_none=True) for e in entries])


def _new_entry(asset: Asset, action: Action, **fields: object) -> ExtendEntry:
    entries = read_journal(asset)
    ulid = journal.new_ulid(entries[-1].id if entries else None)
    return ExtendEntry.model_validate({"schema_version": SCHEMA_VERSION, "id": ulid, "action": action, **fields})


# the current image


def _name(data: bytes) -> str:
    return hash_bytes(data)[:HASH_LENGTH]


def _source(project: Project, asset: Asset) -> tuple[str, U8]:
    """The room's picked Source, the first piece's base."""
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    if not sources.takes_pick(graph):
        raise fail("extend.not_extendable", f"a {asset.kind} has no Source to extend",
                   owner_action="Extend a room or a Prop.")
    variants = sources.variants(asset)
    name = sources.picked(graph)
    if name is None or name not in variants:
        if variants:
            raise fail("extend.no_source", f"{asset.id} has no picked Source to extend from",
                       fix=f"kiripix pick {asset.id} {next(iter(variants))}")
        raise fail("extend.no_source", f"{asset.id} has no Source to extend from",
                   owner_action=f"Import the first screen: kiripix import {asset.id} <png>, then pick it.")
    path = variants[name]
    return name, load_rgba(path, project.relative(path))


def current_image(project: Project, asset: Asset) -> tuple[str, U8, list[ExtendEntry]]:
    """The image the next piece joins: its name, its pixels, and the live pieces."""
    live = live_pieces(read_journal(asset))
    if not live:
        name, rgba = _source(project, asset)
        return name, rgba, live
    name = str(live[-1].joined)
    path = folder(asset) / "joined" / f"{name}.png"
    if not path.is_file():
        raise _invalid(asset, path, "the joined image of the newest piece is missing")
    return name, load_rgba(path, project.relative(path)), live


def _partial(rgba: U8, shown: str) -> None:
    if has_partial_alpha(rgba):
        raise fail("image.partial_alpha", f"{shown} has partially transparent pixels; a join treats a pixel as present "
                   "only at alpha 255", owner_action=f"Make every pixel of {shown} fully opaque or fully transparent.")


# sides


def parse_sides(asset: Asset, text: str, example: str) -> list[str]:
    """`east`, or a corner such as `east,south`: one of east and west and one of north and south."""
    sides = [part.strip() for part in text.split(",")]
    valid = (len(sides) == 1 and sides[0] in HORIZONTAL + VERTICAL) or (
        len(sides) == 2 and sum(s in HORIZONTAL for s in sides) == 1 and sum(s in VERTICAL for s in sides) == 1)
    if not valid:
        raise fail("extend.side_invalid", f"{text!r} is not a side; use east, south, west or north, or a corner of "
                   "two such as east,south", fix=f"{example} --side east")
    return sorted(sides, key=lambda s: (s in VERTICAL, s))  # the horizontal side first


# canvas


def _corner(rgba: U8, sides: list[str]) -> tuple[int, int]:
    """Where the transparent corner of an L-shaped image starts, in its coordinates (the corner `sides` names).

    The notch's inner edges are read across the whole notch (the median depth of its columns and of its rows), not
    from the image's outermost row and column alone: a rescaled piece can leave its last pixel short there, and the
    edge is where the picture stops as it is (ticket 0230)."""
    opaque = rgba[..., 3] == 255
    height, width = opaque.shape
    flip_x, flip_y = "west" in sides, "north" in sides
    mask = opaque[::-1 if flip_y else 1, ::-1 if flip_x else 1]  # the corner turned to the south-east
    if not mask[height - 1].any() or not mask[:, width - 1].any():
        raise fail("extend.no_corner", f"the {'+'.join(sides)} corner has no picture along its edges to continue",
                   owner_action="Add a piece on one of those sides first.")
    x = int(np.flatnonzero(mask[height - 1]).max()) + 1  # first guesses, from the outer row and column
    y = int(np.flatnonzero(mask[:, width - 1]).max()) + 1
    if x < width and y < height:
        y = height - int(np.median(_open_run(mask[:, x:].T)))  # each notch column's transparent run from the bottom
        x = width - int(np.median(_open_run(mask[y:])))  # each notch row's run from the east
    return (width - x if flip_x else x), (height - y if flip_y else y)


def _open_run(lines: U8) -> np.ndarray:
    """For each line (a row of `lines`), how many transparent pixels it ends with."""
    reversed_ = lines[:, ::-1]
    return np.where(reversed_.any(axis=1), reversed_.argmax(axis=1), lines.shape[1])


def contrasting_fill(pixels: U8) -> tuple[int, int, int]:
    """The fill for a canvas whose kept strip has these RGB pixels (n x 3): the first of `FILLS` whose nearest strip
    colours are at least `FILL_DISTANCE` away in OKLab (the 1st percentile of the distances, so a few stray pixels, such
    as a red leaf, don't count); if none is, the farthest."""
    if not len(pixels):
        return FILLS[0]
    step = max(1, len(pixels) // FILL_SAMPLE)
    lab = srgb_to_oklab(np.ascontiguousarray(pixels[::step, :3]))
    fills = srgb_to_oklab(np.array(FILLS, dtype=np.uint8))
    near = [float(np.percentile(np.linalg.norm(lab - fill, axis=1), 1)) for fill in fills]
    far_enough = [i for i, distance in enumerate(near) if distance >= FILL_DISTANCE]
    return FILLS[far_enough[0] if far_enough else int(np.argmax(near))]


def make_canvas(
    rgba: U8, sides: list[str], canvas: tuple[int, int], keep: tuple[int, int], offset: int
) -> tuple[U8, tuple[int, int], tuple[int, int, int]]:
    """The canvas for the next piece: the kept strip(s) of `rgba` and a flat fill that contrasts with them. Returns it,
    where its first pixel lies in `rgba`'s coordinates, and the fill."""
    cw, ch = canvas
    kx, ky = keep
    height, width = rgba.shape[:2]
    if len(sides) == 2:
        px, py = _corner(rgba, sides)
        ox = px - kx if "east" in sides else px + kx - cw
        oy = py - ky if "south" in sides else py + ky - ch
    else:
        side = sides[0]
        ox = {"east": width - kx, "west": kx - cw}.get(side, offset)
        oy = {"south": height - ky, "north": ky - ch}.get(side, offset)
    x0, y0 = max(ox, 0), max(oy, 0)
    x1, y1 = min(ox + cw, width), min(oy + ch, height)
    window = rgba[y0:y1, x0:x1] if x1 > x0 and y1 > y0 else rgba[:0, :0]
    kept = window[..., 3] == 255
    fill = contrasting_fill(window[kept])
    out = np.empty((ch, cw, 4), dtype=np.uint8)
    out[:] = (*fill, 255)
    if kept.any():
        out[y0 - oy : y1 - oy, x0 - ox : x1 - ox][kept] = window[kept]
    return out, (ox, oy), fill


def parse_keep(text: str | None, sides: list[str], canvas: tuple[int, int], example: str) -> tuple[int, int]:
    """`--keep`: px of the image kept in the canvas, one number for both axes or two, `across,down` (ticket 0231). A
    one-sided canvas uses the axis across its join, so only the axes the canvas uses must fit. A third by default."""
    if text is None:
        return canvas[0] // 3, canvas[1] // 3
    again = f"{example} --side {','.join(sides)}"
    parts = [part.strip() for part in text.split(",")]
    if len(parts) not in (1, 2) or not all(part.isdigit() for part in parts):
        raise fail("extend.keep_invalid", f"--keep {text} is not px kept: use one number for both axes, or two, "
                   "across,down (such as 344,192)", fix=again)
    kept = (int(parts[0]), int(parts[-1]))
    used = [axis for axis, names in ((0, HORIZONTAL), (1, VERTICAL)) if any(side in names for side in sides)]
    for axis in used:
        limit = canvas[axis] - 1
        if not 1 <= kept[axis] <= limit:
            name, extent = ("across", "wide") if axis == 0 else ("down", "tall")
            raise fail("extend.keep_invalid", f"--keep {text}: {kept[axis]} px {name} doesn't fit the canvas, "
                       f"{canvas[axis]} px {extent}: use 1 to {limit}", fix=again)
    return kept


def write_canvas(
    project: Project, asset: Asset, sides: list[str], canvas: tuple[int, int], keep: str | None, offset: int,
    example: str,
) -> tuple[Path, tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int, int]]:
    """Write the canvas for the next piece. Returns its path, its size, the strip kept (x, y), its origin and its
    fill."""
    kept = parse_keep(keep, sides, canvas, example)
    name, rgba, _ = current_image(project, asset)
    _partial(rgba, name)
    image, origin, fill = make_canvas(rgba, sides, canvas, kept, offset)
    cancel.check()
    path = folder(asset) / CANVAS_PNG
    save_png(path, image)
    record = CanvasRecord(schema_version=SCHEMA_VERSION, sides=sides, keep=kept, origin=origin, canvas=canvas, base=name)
    atomic.write_json(folder(asset) / CANVAS_JSON, record.model_dump(mode="json"))
    return path, canvas, kept, origin, fill


# add


class Joined(BaseModel):
    piece: str
    sides: list[str]
    width: int
    height: int
    residual: float
    patches: int
    scale: tuple[float, float]
    gain: tuple[float, float]
    seam_length: float
    seam_difference: float
    pieces: int


def _canvas_record(asset: Asset, name: str, sides: list[str] | None, example: str) -> CanvasRecord:
    path = folder(asset) / CANVAS_JSON
    again = f"{example} --side {','.join(sides)}" if sides else f"kiripix extend {asset.id} canvas --side east"
    if not path.is_file():
        raise fail("extend.canvas_needed", "no canvas has been written for this piece", fix=again)
    try:
        record = CanvasRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise _invalid(asset, path, error.errors()[0]["msg"]) from None
    wanted = ",".join(record.sides)
    if record.base != name:
        raise fail("extend.canvas_stale", "the image has changed since the canvas was written (a piece was added, "
                   "dropped or imported)", fix=f"kiripix extend {asset.id} canvas --side {wanted}")
    if sides is not None and sides != record.sides:
        raise fail("extend.canvas_mismatch", f"the canvas was written for {wanted}, not {','.join(sides)}",
                   fix=f"kiripix extend {asset.id} canvas --side {','.join(sides)}")
    return record


def _missed(piece_name: str, detail: str, asset: Asset) -> KiripixError:
    return fail(
        "extend.registration_missed", f"{piece_name} doesn't register onto the image: {detail}",
        owner_action=f"Make the piece again from the canvas, or write the canvas with a wider strip "
                     f"(`kiripix extend {asset.id} canvas --keep N`): a piece fails when too little of a subject is in "
                     "the strip.",
        exit_code=ExitCode.CHECK_FAILED)


def add_piece(
    project: Project, asset: Asset, piece_file: Path, shown: str, sides: list[str] | None, example: str,
) -> tuple[Joined, list[Finding]]:
    """Register, tone and seam the piece onto the current image and record it. Records nothing if the registration
    misses its limit (`MAX_RESIDUAL`) or the piece can't be joined."""
    name, base, live = current_image(project, asset)
    _partial(base, name)
    record = _canvas_record(asset, name, sides, example)
    data, piece = read_as_png(piece_file, shown)
    _partial(piece, shown)
    piece_name = _name(data)
    cancel.check()
    sides = record.sides
    try:
        box = _within(sides, base.shape, piece.shape, record.origin)
        registration = register_piece(_crop(base, box), piece, _overlaps(sides, box, piece.shape, record.origin))
        if registration.residual > MAX_RESIDUAL:
            raise ValueError(f"the edge patches are {registration.residual:.2f} px from the fit, over the "
                             f"{MAX_RESIDUAL} px limit")
        registration = _snap(_shifted(registration, box))
        cancel.check()
        resampled, placed_at = _trim(*resample_piece(piece, registration))
        if len(sides) == 2:  # a corner lies inside the L's bounds; the joined image keeps the base's size
            resampled, placed_at = _trim(*_clip(resampled, placed_at, base.shape))
        box = _within(sides, base.shape, resampled.shape, placed_at)
        region = _crop(base, box)
        placed = _overlaps(sides, box, resampled.shape, placed_at)
        cancel.check()
        toned, gain = match_tone(region, resampled, placed[0])
        cancel.check()
        joined, seam = seam_join(region, toned, placed[0], BLEND)
        lengths, differences = [seam.length], [seam.mean_difference]
        if len(placed) == 2:  # a corner joins one neighbour at a time, the second on the first's result
            cancel.check()
            second = Overlap.placed(sides[1], joined.shape, toned.shape, seam.piece_origin)  # type: ignore[arg-type]
            joined, seam = seam_join(joined, toned, second, BLEND)
            lengths.append(seam.length)
            differences.append(seam.mean_difference)
            whole = base.copy()  # any pixel only the base has, outside the piece's extent, stays the base's
            whole[box[1]:box[3], box[0]:box[2]] = joined
            joined = whole
    except ValueError as error:
        raise _missed(shown, str(error), asset) from None
    cancel.check()
    joined_data = png_bytes(joined)
    joined_name = _name(joined_data)
    length = round(sum(lengths), 3)
    difference = round(max(differences), 3)
    # Nothing is recorded before here; the files first (content-addressed, harmless alone), the journal line last.
    atomic.write_bytes(folder(asset) / "pieces" / f"{piece_name}.png", data)
    atomic.write_bytes(folder(asset) / "joined" / f"{joined_name}.png", joined_data)
    entry = _new_entry(
        asset, "add", sides=record.sides, piece=piece_name, base=name, joined=joined_name,
        residual=round(registration.residual, 3), gain=(round(gain.low, 4), round(gain.high, 4)),
        seam_length=length, seam_difference=difference)
    _append(asset, [entry])
    findings = (check_join_residual(registration.residual, registration.patches, shown)
                + check_join_gain(gain.low, gain.high, shown) + check_seam_difference(difference, length, shown))
    result = Joined(
        piece=piece_name, sides=record.sides, width=int(joined.shape[1]), height=int(joined.shape[0]),
        residual=round(registration.residual, 3), patches=registration.patches,
        scale=_scale(registration), gain=(round(gain.low, 4), round(gain.high, 4)), seam_length=length,
        seam_difference=difference, pieces=len(live) + 1)
    return result, findings


Box = tuple[int, int, int, int]  # x0, y0, x1, y1 in the base's coordinates


def _within(sides: list[str], base_shape: tuple[int, ...], piece_shape: tuple[int, ...], origin: tuple[int, int]) -> Box:
    """The part of the base a corner piece joins: the base cut at the piece's far edge on each side, so each overlap
    ends where the piece does, not where the base does (ticket 0230). A one-sided piece joins the whole base."""
    bh, bw = int(base_shape[0]), int(base_shape[1])
    if len(sides) == 1:
        return 0, 0, bw, bh
    ph, pw = int(piece_shape[0]), int(piece_shape[1])
    x, y = origin
    x0, x1 = (0, min(bw, x + pw)) if "east" in sides else (max(0, x), bw)
    y0, y1 = (0, min(bh, y + ph)) if "south" in sides else (max(0, y), bh)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("the piece doesn't overlap the image")
    return x0, y0, x1, y1


def _crop(rgba: U8, box: Box) -> U8:
    return np.ascontiguousarray(rgba[box[1]:box[3], box[0]:box[2]])


def _overlaps(sides: list[str], box: Box, piece_shape: tuple[int, ...], origin: tuple[int, int]) -> list[Overlap]:
    """The Overlaps that put a piece at `origin` (the base's coordinates) on the base cropped to `box`."""
    shape = (box[3] - box[1], box[2] - box[0])
    at = (origin[0] - box[0], origin[1] - box[1])
    return [Overlap.placed(side, shape, piece_shape, at) for side in sides]  # type: ignore[arg-type]


def _shifted(r: Registration, box: Box) -> Registration:
    """A registration on the base cropped to `box`, in the whole base's coordinates."""
    return Registration(r.scale_x, r.scale_y, r.shift_x + box[0], r.shift_y + box[1], r.residual, r.patches)


def _clip(rgba: U8, origin: tuple[int, int], base_shape: tuple[int, ...]) -> tuple[U8, tuple[int, int]]:
    """Cut what of a placed piece lies past the base's bounds (a corner piece rescaled a px beyond them)."""
    x, y = origin
    h, w = rgba.shape[:2]
    x0, y0 = max(0, -x), max(0, -y)
    x1, y1 = min(w, int(base_shape[1]) - x), min(h, int(base_shape[0]) - y)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("the piece lies outside the image after registration")
    return np.ascontiguousarray(rgba[y0:y1, x0:x1]), (x + x0, y + y0)


def _snap(r: Registration) -> Registration:
    """A piece that lands on the grid unscaled (a scale within 0.05 % of 1 and a shift within 0.02 px of a whole px, on
    an axis) is put there exactly, so the resampling doesn't drop its last row or column to rounding noise."""
    def axis(scale: float, shift: float) -> tuple[float, float]:
        if abs(scale - 1) < 5e-4 and abs(shift - round(shift)) < 0.02:
            return 1.0, float(round(shift))
        return scale, shift

    scale_x, shift_x = axis(r.scale_x, r.shift_x)
    scale_y, shift_y = axis(r.scale_y, r.shift_y)
    return Registration(scale_x, scale_y, shift_x, shift_y, r.residual, r.patches)


def _trim(rgba: U8, origin: tuple[int, int]) -> tuple[U8, tuple[int, int]]:
    """Cut the transparent margin the resampling leaves (a sub-pixel scale rounds the footprint up), and move the
    origin with it, so the joined image isn't a row or a column wider than the picture."""
    present = rgba[..., 3] == 255
    rows, columns = np.flatnonzero(present.any(axis=1)), np.flatnonzero(present.any(axis=0))
    if not len(rows):
        raise ValueError("the piece has no picture after registration")
    y0, y1, x0, x1 = int(rows[0]), int(rows[-1]) + 1, int(columns[0]), int(columns[-1]) + 1
    return np.ascontiguousarray(rgba[y0:y1, x0:x1]), (origin[0] + x0, origin[1] + y0)


def _scale(registration: Registration) -> tuple[float, float]:
    return round(registration.scale_x, 6), round(registration.scale_y, 6)


# undo and done


def undo(project: Project, asset: Asset) -> tuple[str, int]:
    """Drop the newest live piece. Returns its name and how many remain."""
    live = live_pieces(read_journal(asset))
    if not live:
        raise fail("extend.nothing_to_undo", f"{asset.id} has no piece to drop (none added since the last `done`)",
                   owner_action=f"Add a piece first: kiripix extend {asset.id} add <png>.")
    _append(asset, [_new_entry(asset, "undo")])
    return str(live[-1].piece), len(live) - 1


class Done(BaseModel):
    variant: str
    created: bool
    width: int
    height: int
    holes: int  # transparent pixels left (a corner not yet filled)
    cropped: dict[str, int]  # px cut from each side with an open margin
    pieces: int


MAX_MARGIN = 2  # the deepest open margin `done` crops: a piece registered a px or two inside the image's edge


def _open_margins(rgba: U8) -> tuple[U8, dict[str, int]]:
    """Cut an open margin on each side: the outer rows (or columns) with transparent pixels, at most `MAX_MARGIN`
    deep, when the next one inward is whole but for its ends. A piece that registers at 1 px, or ends 1 px inside the image, leaves
    one (ticket 0230). An unfilled corner is deeper, so it stays, and `hole_findings` reports it."""
    cropped: dict[str, int] = {}
    changed = True
    while changed:
        changed = False
        for side in ("north", "south", "west", "east"):
            opaque = rgba[..., 3] == 255
            lines = {"north": opaque, "south": opaque[::-1], "west": opaque.T, "east": opaque.T[::-1]}[side]
            inner = lines[:, MAX_MARGIN:-MAX_MARGIN] if lines.shape[1] > 2 * MAX_MARGIN else lines
            whole = inner.all(axis=1)  # the line's ends belong to the margins across it, which crop on their own turn
            depth = int(np.argmax(whole)) if whole.any() else len(whole)
            if not 1 <= depth <= MAX_MARGIN - cropped.get(side, 0):
                continue
            height, width = rgba.shape[:2]
            rgba = {"north": rgba[depth:], "south": rgba[:height - depth],
                    "west": rgba[:, depth:], "east": rgba[:, :width - depth]}[side]
            cropped[side] = cropped.get(side, 0) + depth
            changed = True
    return np.ascontiguousarray(rgba), cropped


def done(project: Project, asset: Asset) -> Done:
    """Import the joined image as a Variant, its open margins cropped (`_open_margins`)."""
    name, rgba, live = current_image(project, asset)
    if not live:
        raise fail("extend.nothing_to_join", f"{asset.id} has no piece to join into a Variant",
                   fix=f"kiripix extend {asset.id} canvas --side east")
    path = folder(asset) / "joined" / f"{name}.png"
    rgba, cropped = _open_margins(rgba)
    if cropped:
        data = png_bytes(rgba)
        path = folder(asset) / "joined" / f"{_name(data)}.png"  # content-addressed, like every joined image
        atomic.write_bytes(path, data)
    cancel.check()
    variant, _, created = sources.import_file(asset, path, project.relative(path), "variant")
    _append(asset, [_new_entry(asset, "done", variant=variant)])
    return Done(variant=variant, created=created, width=int(rgba.shape[1]), height=int(rgba.shape[0]),
                holes=int((rgba[..., 3] != 255).sum()), cropped=cropped, pieces=len(live))


def hole_findings(asset: Asset, holes: int) -> list[Finding]:
    """A joined image with transparent pixels, such as an L whose corner piece is missing, is a poor Source."""
    if not holes:
        return []
    return [Finding(
        code="extend.holes_remain", severity="warning",
        message=f"the joined image still has {holes} transparent pixels, where no piece reaches",
        owner_action=f"Pick it only if you will paint or crop the gap; or `kiripix extend {asset.id} undo` and add "
                     "the corner piece first.")]
