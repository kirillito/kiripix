"""A Look's (or a Loop's) edit made on a piece or a crop of a room's Source (ticket 0232, ADR 0009).

The image model resizes what it is given to its own size (1376 x 768), so an edit of an extended room's whole Source
(2407 x 1343) comes back smaller and has to be scaled up again, which blurs it. An edit made on one piece of the room
(`extend/pieces/<hash>.png`, or a Variant such as the first screen) or on a crop of the Source at the model's size
(`extend crop`) keeps its pixels. `import --look <look> --of <piece|crop>` finds where that piece or crop lies in the
Source, registers the edit to that place (scale and shift, as the `looks` Stage registers an edit, `kiripix.ops.looks`),
and stores an edit of the whole Source: the Source's own pixels everywhere the edit doesn't reach, the edit's where it
does. So `looks`, its region and its drift are unchanged. The caller holds the Asset lock.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
from pydantic import BaseModel, ConfigDict, ValidationError

from kiripix.checks import Finding, Position
from kiripix.core import atomic, cancel, changes, extend, sources
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.images import load_rgba, png_bytes, read_as_png
from kiripix.core.project import Project
from kiripix.core.settings import CROP_SCHEMA_VERSION, migrate_crop_record
from kiripix.ops import register, resample_piece
from kiripix.ops.colour import U8
from kiripix.ops.join import Registration
from kiripix.ops.looks import Alignment

CROP = "crop"
CROP_PNG = "crop.png"
CROP_JSON = "crop.json"
CROPS = "crops"
COARSE = 4  # the factor the piece is first looked for at
TRIM = 8  # px of the piece's border left out of the coarse match: the join may have cut it
MIN_MATCH = 0.5  # the coarse match's normalised correlation below which the piece isn't in the Source
MAX_RESIDUAL = 1.0  # Source px: a registration that misses by more is reported
PASSES = 3


class CropRecord(BaseModel):
    """`extend/crops/<name>.json`: where the crop lies in the Source, for `import --of <crop>` to place the edit."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    source: str  # the Source Variant it was cut from
    origin: tuple[int, int]  # the crop's first pixel in the Source
    size: tuple[int, int]
    png: str  # the hash of the crop's PNG: two files can't be swapped in together, so a crop and a record that don't match are refused
    number: int  # the order the crops were written (a rewritten crop takes the next): `--of crop` is the highest


@dataclass
class Placed:
    pixels: U8  # the edit of the whole Source
    scale: tuple[float, float]  # the edit's px per Source px, as the placement found it
    origin: tuple[int, int]  # where the edit's top-left lies in the Source
    residual: float  # Source px, the median miss of the registration's tiles
    tiles: int
    findings: list[Finding]


# the crop


def parse_box(text: str, example: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4 or not all(p.lstrip("-").isdigit() for p in parts):
        raise fail("extend.box_invalid", f"--box {text!r} is not a box: use x0,y0,x1,y1 in the Source's px",
                   fix=f"{example} --box 100,100,500,400")
    x0, y0, x1, y1 = (int(p) for p in parts)
    if x1 <= x0 or y1 <= y0:
        raise fail("extend.box_invalid", f"--box {text}: the box has no area (x1 and y1 must be past x0 and y0)",
                   fix=f"{example} --box 100,100,500,400")
    return x0, y0, x1, y1


def parse_size(text: str | None, default: tuple[int, int], example: str) -> tuple[int, int]:
    if text is None:
        return default
    parts = text.lower().replace("x", ",").split(",")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts) or min(int(p) for p in parts) < 16:
        raise fail("extend.size_invalid", f"--size {text!r} is not a size: use WIDTHxHEIGHT, at least 16 px each",
                   fix=f"{example} --size 1376x768")
    return int(parts[0]), int(parts[1])


def _crops_folder(asset: Asset) -> Path:
    return extend.folder(asset) / CROPS


def _read_record(asset: Asset, path: Path) -> CropRecord:
    shown = f"{asset.id}/extend/{path.parent.name}/{path.name}" if path.parent.name == CROPS else f"{asset.id}/extend/{path.name}"
    try:
        document = migrate_crop_record(json.loads(path.read_text(encoding="utf-8")), shown)
        return CropRecord.model_validate(document)
    except (ValidationError, ValueError, AttributeError) as error:
        detail = error.errors()[0]["msg"] if isinstance(error, ValidationError) else "not JSON"
        raise fail("extend.record_invalid", f"{shown} is not valid: {detail}",
                   owner_action=f"Remove {shown} and its PNG, and write the crop again.") from None


def _legacy(asset: Asset) -> tuple[Path, Path] | None:
    """The pre-0287 single crop, `extend/crop.png` and `crop.json`, if there is one."""
    png, record = extend.folder(asset) / CROP_PNG, extend.folder(asset) / CROP_JSON
    return (png, record) if record.is_file() else None


def _crops(asset: Asset) -> list[tuple[str, Path, Path]]:
    """Every crop of the room, oldest first: its name, PNG and record. The pre-0287 single crop counts, named by its
    PNG's hash."""
    found: list[tuple[int, str, Path, Path]] = []
    for record_path in sorted(_crops_folder(asset).glob("*.json")):
        found.append((_read_record(asset, record_path).number, record_path.stem, record_path.with_suffix(".png"), record_path))
    legacy = _legacy(asset)
    if legacy is not None:
        record = _read_record(asset, legacy[1])
        found.append((record.number, record.png[:extend.HASH_LENGTH], legacy[0], legacy[1]))
    found.sort(key=lambda item: (item[0], item[1]))
    return [(name, png, record) for _, name, png, record in found]


def crop_names(asset: Asset) -> list[str]:
    """The names of the room's crops, oldest first."""
    return [name for name, _, _ in _crops(asset)]


def _move_legacy(asset: Asset) -> None:
    """The writing side of the migration: the pre-0287 single crop moves into `crops/` (the PNG first, then the record;
    a stop between them leaves the old crop readable)."""
    legacy = _legacy(asset)
    if legacy is None:
        return
    png, record_path = legacy
    record = _read_record(asset, record_path)
    name = record.png[:extend.HASH_LENGTH]
    if png.is_file():
        target = _crops_folder(asset) / f"{name}.png"
        if not target.exists():
            atomic.write_bytes(target, png.read_bytes())
        atomic.write_json(target.with_suffix(".json"), record.model_dump(mode="json"))
        changes.remove(png)
    changes.remove(record_path)


def write_crop(project: Project, asset: Asset, box: tuple[int, int, int, int], size: tuple[int, int],
               example: str) -> tuple[Path, tuple[int, int]]:
    """Write the Source's crop of `size` around `box` (the window moved in, if it would leave the Source) as
    `extend/crops/<hash>.png` with its record. Returns its path and where it starts in the Source. The same crop again
    is the same file, and the latest."""
    name, source = extend.picked_source(project, asset)
    height, width = (int(v) for v in source.shape[:2])
    cw, ch = size
    if cw > width or ch > height:
        raise fail("extend.crop_too_big", f"the crop, {cw}x{ch}, is bigger than the Source, {width}x{height}",
                   fix=f"{example} --size {min(cw, width)}x{min(ch, height)}")
    x0, y0, x1, y1 = box
    if x1 - x0 > cw or y1 - y0 > ch:
        raise fail("extend.crop_too_small", f"the box, {x1 - x0}x{y1 - y0}, doesn't fit the crop, {cw}x{ch}",
                   fix=f"{example} --size {max(cw, x1 - x0)}x{max(ch, y1 - y0)}")
    ox = min(max((x0 + x1 - cw) // 2, 0), width - cw)
    oy = min(max((y0 + y1 - ch) // 2, 0), height - ch)
    _move_legacy(asset)
    data = png_bytes(np.ascontiguousarray(source[oy:oy + ch, ox:ox + cw]))
    digest = hash_bytes(data)
    path = _crops_folder(asset) / f"{digest[:extend.HASH_LENGTH]}.png"
    number = max((_read_record(asset, r).number for _, _, r in _crops(asset)), default=0) + 1
    atomic.write_bytes(path, data)
    record = CropRecord(schema_version=CROP_SCHEMA_VERSION, source=name, origin=(ox, oy), size=(cw, ch), png=digest, number=number)
    atomic.write_json(path.with_suffix(".json"), record.model_dump(mode="json"))
    return path, (ox, oy)


def _crop_record(asset: Asset, source: str, of: str) -> CropRecord:
    """The record of the crop `of` names (`crop`: the latest), refused if the Source or the PNG isn't the one it records."""
    crops = _crops(asset)
    if not crops:
        raise fail("import.crop_needed", f"{asset.id} has no crop written", fix=f"kiripix extend {asset.id} crop --box 0,0,400,300")
    _, png, record_path = crops[-1] if of == CROP else next(c for c in crops if c[0].startswith(of))
    record = _read_record(asset, record_path)
    if record.source != source:
        raise fail("import.crop_stale", "the Source has changed since the crop was written",
                   fix=f"kiripix extend {asset.id} crop --box 0,0,400,300")
    if not png.is_file() or hash_bytes(png.read_bytes()) != record.png:
        raise fail("import.crop_stale", f"{asset.id}/extend/{png.name} isn't the crop its record names (a crop was "
                   "stopped half-written)", fix=f"kiripix extend {asset.id} crop --box 0,0,400,300")
    return record


# the piece


def find_reference(asset: Asset, name: str, shown: str) -> Path:
    """The piece or Variant `name` names (the start of its hash): in `extend/pieces/` or `src/`."""
    found: dict[str, Path] = {}
    for folder in (extend.folder(asset) / "pieces", asset.dir / "src"):
        for path in sorted(folder.glob("*.png")):
            if path.stem.startswith(name):
                found.setdefault(path.stem, path)
    if len(found) == 1:
        return next(iter(found.values()))
    known = sorted({p.stem for folder in (extend.folder(asset) / "pieces", asset.dir / "src") for p in folder.glob("*.png")})
    if found:
        raise fail("import.of_ambiguous", f"'{name}' names more than one piece or Variant: {', '.join(found)}",
                   owner_action="Give more of the hash.", position=Position(asset=asset.id, file=shown))
    raise fail("import.of_unknown", f"{asset.id} has no piece or Variant '{name}'; "
               + (f"its pieces and Variants are {', '.join(known)}" if known else "it has none"),
               owner_action=f"Name a piece of `extend/pieces/`, a Variant or a crop (kiripix extend {asset.id} crop --box ...), or `crop` for the latest.",
               position=Position(asset=asset.id, file=shown))


def _luma(rgba: U8) -> np.ndarray:
    rgb = rgba[..., :3].astype(np.float64)
    result: np.ndarray = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    return result


def _blocks(image: np.ndarray, factor: int) -> np.ndarray:
    height, width = (image.shape[0] // factor) * factor, (image.shape[1] // factor) * factor
    cut = image[:height, :width]
    result: np.ndarray = cut.reshape(height // factor, factor, width // factor, factor).mean(axis=(1, 3))
    return result


def locate(source: U8, piece: U8) -> tuple[tuple[int, int], float]:
    """Where `piece` lies in `source`, at scale 1, to a few px: the top-left of the best match of its luma (normalised
    cross-correlation at a quarter of the size), and the match's score. A piece sticking out of the Source by up to
    `TRIM` px still matches, for its border is left out."""
    ph, pw = (int(v) for v in piece.shape[:2])
    inner = piece[TRIM:ph - TRIM, TRIM:pw - TRIM] if min(ph, pw) > 4 * TRIM else piece
    trim = (ph - inner.shape[0]) // 2
    template = _blocks(_luma(inner), COARSE)
    base = _blocks(_luma(source), COARSE)
    th, tw = template.shape
    bh, bw = base.shape
    if th > bh or tw > bw or template.std() < 1.0:
        raise ValueError("the piece is larger than the Source, or flat")
    tz = template - template.mean()
    shape = (bh, bw)
    correlation = np.fft.irfft2(np.fft.rfft2(base) * np.conj(np.fft.rfft2(tz, s=shape)), s=shape)[:bh - th + 1, :bw - tw + 1]

    def window_sums(values: np.ndarray) -> np.ndarray:
        total = np.pad(values.cumsum(axis=0).cumsum(axis=1), ((1, 0), (1, 0)))
        rows, columns = bh - th + 1, bw - tw + 1
        result: np.ndarray = (total[th:th + rows, tw:tw + columns] - total[:rows, tw:tw + columns]
                              - total[th:th + rows, :columns] + total[:rows, :columns])
        return result

    count = th * tw
    sums = window_sums(base)
    variance = np.maximum(window_sums(base * base) - sums * sums / count, 0.0)
    score = correlation / np.sqrt(np.maximum(variance * float((tz * tz).sum()), 1e-9))
    iy, ix = (int(v) for v in np.unravel_index(int(np.argmax(score)), score.shape))
    return (ix * COARSE - trim, iy * COARSE - trim), float(score[iy, ix])


# placing


def _snap(r: Registration) -> Registration:
    def axis(scale: float, shift: float) -> tuple[float, float]:
        if abs(scale - 1) < 5e-4 and abs(shift - round(shift)) < 0.02:
            return 1.0, float(round(shift))
        return scale, shift

    sx, tx = axis(r.scale_x, r.shift_x)
    sy, ty = axis(r.scale_y, r.shift_y)
    return Registration(sx, sy, tx, ty, r.residual, r.patches)


def _lay(source: U8, edit: U8, r: Registration) -> tuple[U8, np.ndarray]:
    """The Source with `edit` laid on it by `r`, and the Mask of the pixels the edit covers."""
    placed, (x, y) = resample_piece(edit, _snap(r))
    height, width = (int(v) for v in source.shape[:2])
    ph, pw = (int(v) for v in placed.shape[:2])
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + pw, width), min(y + ph, height)
    covered = np.zeros((height, width), dtype=np.bool_)
    out = source.copy()
    if x1 > x0 and y1 > y0:
        patch = placed[y0 - y:y1 - y, x0 - x:x1 - x]
        mask = patch[..., 3] == 255
        covered[y0:y1, x0:x1] = mask
        out[y0:y1, x0:x1][mask] = patch[mask]
    return out, covered


def place(source: U8, edit: U8, scale: tuple[float, float], origin: tuple[int, int], shown: str, asset: Asset,
          exact: bool) -> Placed:
    """Lay `edit` on `source`: first at `origin` with `scale` source px per edit px, then refined by registering the
    laid edit against the Source on the tiles it covers (`PASSES` times at most). An image of the Source's size.
    `exact`: the place is known (a crop), so too few textured tiles to refine it leave it as it is, with a finding."""
    sx, sy = scale
    tx, ty = float(origin[0]), float(origin[1])
    position = Position(asset=asset.id, file=shown)
    alignment = Alignment()
    for _ in range(PASSES):
        cancel.check()
        laid, covered = _lay(source, edit, Registration(sx, sy, tx, ty, 0.0, 0))
        if not covered.any():
            raise fail("import.of_not_found", f"{shown} doesn't lie on the Source", position=position,
                       owner_action="Check the edit is of the piece or crop `--of` names.")
        alignment = register(source, laid, ~covered)
        if alignment.tiles == 0 and exact:
            return Placed(laid, (round(sx, 4), round(sy, 4)), (round(tx), round(ty)), 0.0, 0, [Finding(
                code="import.of_unregistered", severity="info",
                message=f"{shown} has too little texture on the Source to register: it is placed where the crop was cut",
                position=position, owner_action="Nothing to do unless the edit comes back shifted or rescaled; then make "
                                                 "the crop larger or with more of the picture in it.")])
        if alignment.tiles == 0:
            raise fail("import.of_not_found", f"{shown} has too little texture on the Source to register it", position=position,
                       owner_action="Make the edit from a piece or crop with more of the picture in it.")
        if alignment.displacement(*(int(v) for v in source.shape[1::-1])) < 0.05:
            break
        # The edit's content at room position q lies in `laid` at a * q + s; move it back by that.
        sx, sy = sx / alignment.scale_x, sy / alignment.scale_y
        tx, ty = (tx - alignment.shift_x) / alignment.scale_x, (ty - alignment.shift_y) / alignment.scale_y
    else:
        laid, covered = _lay(source, edit, Registration(sx, sy, tx, ty, 0.0, 0))
        alignment = register(source, laid, ~covered)
    findings: list[Finding] = []
    if alignment.residual > MAX_RESIDUAL:
        findings.append(Finding(
            code="import.of_misregistered", severity="warning",
            message=f"{shown} still misses the Source by {alignment.residual:.2f} px (median) after registration, over "
                    f"{MAX_RESIDUAL:g}: it may not be an edit of what `--of` names",
            position=position, owner_action="Check the edit is of that piece or crop, made from it without cropping or rotating."))
    return Placed(laid, (round(sx, 4), round(sy, 4)), (round(tx), round(ty)), round(alignment.residual, 3), alignment.tiles, findings)


def placed_edit(project: Project, asset: Asset, file: Path, shown: str, of: str) -> Placed:
    """The edit in `file`, made on `of` (`crop`, or a piece or Variant's hash), as an edit of the whole Source."""
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    if sources.picked(graph) is None:
        raise fail("import.look_needs_source", f"{asset.id} has no picked Source for the edit to be made on",
                   owner_action=f"Pick the room's Source first: kiripix pick {asset.id} <variant>.",
                   position=Position(asset=asset.id, file=shown))
    name, source = extend.picked_source(project, asset)
    _, edit = read_as_png(file, shown)
    eh, ew = (int(v) for v in edit.shape[:2])
    named = [n for n in crop_names(asset) if n.startswith(of)] if of != CROP else []
    if of == CROP or named:
        if len(named) > 1:
            raise fail("import.of_ambiguous", f"'{of}' names more than one crop: {', '.join(named)}",
                       owner_action="Give more of the hash.", position=Position(asset=asset.id, file=shown))
        record = _crop_record(asset, name, CROP if of == CROP else named[0])
        cw, ch = record.size
        return place(source, edit, (cw / ew, ch / eh), record.origin, shown, asset, True)
    reference = find_reference(asset, of, shown)
    piece = load_rgba(reference, project.relative(reference))
    try:
        origin, score = locate(source, piece)
    except ValueError as error:
        raise fail("import.of_not_found", f"{reference.stem} can't be placed on the Source: {error}",
                   owner_action="Name a piece that is part of the picked Source.",
                   position=Position(asset=asset.id, file=shown)) from None
    if score < MIN_MATCH:
        raise fail("import.of_not_found", f"{reference.stem} isn't found in the Source (best match {score:.2f}, under {MIN_MATCH})",
                   owner_action="Name a piece that is part of the picked Source: pieces from before its last `extend done` are.",
                   position=Position(asset=asset.id, file=shown))
    ph, pw = (int(v) for v in piece.shape[:2])
    return place(source, edit, (pw / ew, ph / eh), origin, shown, asset, False)


@contextmanager
def placed_file(project: Project, asset: Asset, file: Path, shown: str, of: str) -> Iterator[tuple[Path, Placed]]:
    """The edit placed (`placed_edit`) as a PNG that lives for the `with`, under the file's own name so the import
    records that name."""
    placed = placed_edit(project, asset, file, shown, of)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / (Path(shown).stem + ".png")
        path.write_bytes(png_bytes(placed.pixels))
        yield path, placed


__all__ = ["CROP", "crop_names", "Placed", "parse_box", "parse_size", "placed_edit", "placed_file", "write_crop"]
