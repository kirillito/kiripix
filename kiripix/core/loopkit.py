"""A frame Loop's kit (ticket 0193): `kiripix loop kit` writes a folder to paint in, `import --loop` takes the frames back.

The kit's frame 0 is the room, from the `palette` Stage, inside the Loop's region, cropped to the region's box and
transparent outside it. Frames 1 to N-1 start as copies of it. The Owner (or an agent) paints them at target size, only
with the palette's colours, and imports them in name order. Frame 0 is always the room's, so it is never imported.

An import stores each frame as `src/loops/<loop>/<hash>.png` and records a `kit` Decision in the `loops` journal (see
`kiripix.recipes.kit_record`): the frames' names, the box, and the hashes of the fit and the palette they were painted on.
Those come from the kit's `kit.json` when the frames sit beside one, so a refit between writing the kit and importing the
frames is noticed; without it, from the room as it is. The caller holds the Asset lock.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, Position
from kiripix.core import atomic, editing, sources
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import png_bytes, read_as_png
from kiripix.core.project import Project
from kiripix.ops.palette import Palette, PaletteEntry, format_gpl
from kiripix.recipes.base import StageRun
from kiripix.recipes.common import palette_rgb
from kiripix.recipes.kit_record import (
    KIT_DIR,
    fit_hash,
    frame_name,
    frame_path,
    kit_region,
    palette_hash,
)
from kiripix.recipes.loops import LOOPS_STAGE, PLATE, declared
from kiripix.recipes.regions import EditRoom

KIT_FILE = "kit.json"
KIT_SCHEMA_VERSION = 1
FRAME_ZERO = "frame_000"
MAX_FRAMES = 64
SWATCH = 8  # px: one colour of `palette.png`
README = (
    "Paint on copies: keep frame_000.png as it is (the room's own frame) and paint frame_001.png onward.\n"
    "Stay in the box: every frame is exactly {width}x{height} px; import them with kiripix import <asset> <png...> "
    "--loop {loop}.\n"
    "Use only the palette: palette.gpl and palette.png hold the colours; any other colour is refused when the room "
    "builds.\n"
)
# the stages a kit is cut from: `EditRoom` reads them
READS = ("layers", "palette", "source", "fit", "masks")


@dataclass
class _Prepared:
    graph: AssetGraph
    run: StageRun
    layer: str
    region: Any
    box: tuple[int, int, int, int]
    room: EditRoom
    fit: str
    palette: Any
    palette_id: str


def _prepare(project: Project, asset: Asset, loop: str, prefix: str) -> _Prepared:
    """The Loop's region and what a kit is painted on, from the built room. Refused unless the Loop is a declared frame
    Loop and the room is built. `prefix` is the start of the finding codes (`loop.kit` or `import.loop`)."""
    position = Position(asset=asset.id, stage=LOOPS_STAGE)
    if asset.kind != "room":
        raise fail(f"{prefix}_needs_room", f"a Loop's kit is for a room; {asset.id} is a {asset.kind}",
                   owner_action="Use a room Asset.", position=position)
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    spec = graph.spec(LOOPS_STAGE)
    run = graph.stage_run(spec, graph.output_dir(spec))
    loops = declared(run)
    if loop not in loops:
        declare = json.dumps({"decision": "loop", "data": {"loop": loop, "form": "frames"}})
        raise fail(f"{prefix}_unknown", f"{asset.id} has no Loop {loop}"
                   + (f"; its Loops are {', '.join(sorted(loops))}" if loops else ""),
                   fix=f"kiripix decide {asset.id} {LOOPS_STAGE} --decision '{declare}'", position=position)
    if loops[loop].get("form", "cycle") != "frames":
        raise fail(f"{prefix}_not_frames", f"the Loop {loop} is a cycle, and a kit holds the frames of a frame Loop",
                   owner_action=f"Declare it again with form frames (kiripix decide {asset.id} {LOOPS_STAGE} --help).",
                   position=position)
    for stage in READS:
        if graph.state(stage).status not in ("done", "needs-review"):
            raise fail(f"{prefix}_needs_build", f"the room's {stage} Stage isn't built, and the kit is cut from it",
                       fix=f"kiripix run {asset.id} {stage}", position=position)
    room = EditRoom(run)
    layer = str(loops[loop].get("layer", PLATE))
    region, box = kit_region(run, room, loop, None if layer == PLATE else layer)
    if box is None:
        raise fail(f"{prefix}_no_region", f"the Loop {loop} has no region, so its kit has no box",
                   owner_action=f"Mark where {loop} plays: a flood, a polygon or a brush "
                                f"(kiripix decide {asset.id} {LOOPS_STAGE} --help).", position=position)
    rgb = palette_rgb(run)
    return _Prepared(graph, run, layer, region, box, room, fit_hash(run.upstream["fit"] / "fit.png"), rgb,
                     palette_hash(rgb))


# loop kit


@dataclass
class KitWritten:
    box: tuple[int, int, int, int]
    frames: int
    colours: int
    files: list[str]


def _existing(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("frame_*.png") if re.fullmatch(r"frame_\d{3}\.png", p.name))


def write_kit(project: Project, asset: Asset, loop: str, folder: Path, shown: str, frames: int,
              force: bool) -> KitWritten:
    """Write the kit of a frame Loop into `folder`. Refused when the folder has frames, unless `force` (then the frames
    in it are replaced, painted ones too)."""
    if not 2 <= frames <= MAX_FRAMES:
        raise fail("loop.kit_frames", f"--frames {frames} is outside 2 to {MAX_FRAMES}",
                   fix=f"kiripix loop kit {asset.id} {loop} {shown} --frames 4",
                   position=Position(asset=asset.id, stage=LOOPS_STAGE))
    found = _existing(folder) if folder.is_dir() else []
    if found and not force:
        raise fail("loop.kit_exists", f"{shown} already has {len(found)} frames ({found[0].name} ...); a new kit would "
                   "replace them, painted ones too",
                   owner_action=f"Use another folder, or write over these: kiripix loop kit {asset.id} {loop} {shown} "
                                f"--frames {frames} --force",
                   position=Position(asset=asset.id, stage=LOOPS_STAGE, file=shown))
    kit = _prepare(project, asset, loop, "loop.kit")
    x, y, width, height = kit.box
    crop = (slice(y, y + height), slice(x, x + width))
    area = kit.region[crop]
    frame0 = np.where(area[..., None], kit.room.composite[crop], 0).astype(np.uint8)
    data = png_bytes(frame0)
    names = [f"frame_{n:03d}.png" for n in range(frames)]
    palette = Palette("kiripix", tuple(PaletteEntry(int(r), int(g), int(b)) for r, g, b in kit.palette))
    swatches = np.zeros((SWATCH, SWATCH * len(palette.entries), 4), dtype=np.uint8)
    for n, (r, g, b) in enumerate(kit.palette):
        swatches[:, n * SWATCH:(n + 1) * SWATCH] = (int(r), int(g), int(b), 255)
    for stale in found:  # a larger kit before: its extra frames would be imported with the rest
        if stale.name not in names:
            stale.unlink()
    for name in names:
        atomic.write_bytes(folder / name, data)
    atomic.write_bytes(folder / "palette.png", png_bytes(swatches))
    atomic.write_text(folder / "palette.gpl", format_gpl(palette))
    atomic.write_text(folder / "README.txt", README.format(width=width, height=height, loop=loop))
    atomic.write_json(folder / KIT_FILE, {
        "schema_version": KIT_SCHEMA_VERSION, "asset": asset.id, "loop": loop, "box": [x, y, width, height],
        "frames": frames, "fit": kit.fit, "palette": kit.palette_id})
    files = [*names, "palette.gpl", "palette.png", "README.txt", KIT_FILE]
    return KitWritten((x, y, width, height), frames, len(palette.entries), files)


# import --loop


@dataclass
class FramesImported:
    names: list[str]  # the stored frames' names, for frames 1 to N-1, in order
    paths: list[Path]  # the distinct stored files
    created: bool
    skipped: list[str]
    box: tuple[int, int, int, int]
    findings: list[Finding]


def _kit_file(first: Path, asset: Asset, loop: str) -> dict[str, Any] | None:
    """The `kit.json` beside the frames, when it is this Asset's and Loop's."""
    path = first.parent / KIT_FILE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (isinstance(document, dict) and document.get("schema_version") == KIT_SCHEMA_VERSION
            and document.get("asset") == asset.id and document.get("loop") == loop):
        return document
    return None


def import_frames(project: Project, asset: Asset, files: list[Path], shown: list[str], loop: str) -> FramesImported:
    """Store painted frames as frames 1 to N-1 of a frame Loop and record them (a `kit` Decision). Every frame must be
    the region's box in size; nothing is stored unless all are."""
    position = Position(asset=asset.id, stage=LOOPS_STAGE)
    kit = _prepare(project, asset, loop, "import.loop")
    x, y, width, height = kit.box
    named = sorted(zip(files, shown, strict=True), key=lambda pair: pair[0].name)
    findings: list[Finding] = []
    skipped: list[str] = []
    frames: list[tuple[bytes, str]] = []
    for file, name in named:
        if file.stem == FRAME_ZERO:
            skipped.append(name)
            findings.append(Finding(
                code="import.frame_zero_skipped", severity="info", message=f"{name} is frame 0, which is always the "
                "room's own, so it isn't imported", position=Position(asset=asset.id, stage=LOOPS_STAGE, file=name),
                owner_action="Nothing to do."))
            continue
        data, pixels = read_as_png(file, name)
        if pixels.shape[1] != width or pixels.shape[0] != height:
            raise fail("import.size_mismatch",
                       f"{name} is {pixels.shape[1]}x{pixels.shape[0]} px; the box of {loop} is {width}x{height}",
                       owner_action=f"Paint every frame at {width}x{height} px (kiripix loop kit {asset.id} {loop} "
                                    f"<folder> writes a kit of that size).",
                       position=Position(asset=asset.id, stage=LOOPS_STAGE, file=name))
        frames.append((data, name))
    if not frames:
        raise fail("import.loop_no_frames", "there are no frames to import: frame 0 is the room's, and only frames 1 "
                   "and up are imported",
                   owner_action=f"Paint frame_001.png and the frames after it, then import them with --loop {loop}.",
                   position=position)
    fit, palette = kit.fit, kit.palette_id
    made = _kit_file(named[0][0], asset, loop)
    if made is not None:
        if [int(v) for v in made["box"]] != [x, y, width, height]:
            raise fail("import.loop_region_changed",
                       f"the region of {loop} moved or changed size since the kit was written (its box was "
                       f"{made['box']}, now [{x}, {y}, {width}, {height}])",
                       owner_action=f"Write a new kit (kiripix loop kit {asset.id} {loop} <folder> --force) and paint "
                                    "on it.", position=position)
        fit, palette = str(made["fit"]), str(made["palette"])
    stored: list[str] = []
    paths: dict[str, Path] = {}
    created = False
    log = sources.imported_names(asset)
    records: list[dict[str, Any]] = []
    for data, name in frames:
        stem = frame_name(data)
        path = asset.dir / frame_path(loop, stem)
        if not path.exists():
            atomic.write_bytes(path, data)
            created = True
        stored.append(stem)
        paths[stem] = path
        relative = path.relative_to(asset.dir).as_posix()
        original = Path(name).name
        if log.get(relative) != original and not any(r["file"] == relative for r in records):
            records.append({"schema_version": sources.IMPORTED_SCHEMA_VERSION, "file": relative, "imported_as": original})
    if records:
        atomic.append_jsonl_many(asset.dir / sources.IMPORTED_FILE, records)
    editing.record_decision(project, asset, LOOPS_STAGE, editing.DecisionDocument(decision="kit", data={
        "loop": loop, "box": [x, y, width, height], "frames": stored, "fit": fit, "palette": palette}))
    return FramesImported(stored, list(paths.values()), created, skipped, (x, y, width, height), findings)


__all__ = ["KIT_DIR", "KitWritten", "FramesImported", "import_frames", "write_kit"]
