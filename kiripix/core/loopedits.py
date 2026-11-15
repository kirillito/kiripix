"""A frame Loop's edit frames (ticket 0219, route (c) of 0183): each frame is an edit of the room's Source.

`import --loop <loop> --frame <n>` stores an image as `src/loops/<loop>/edits/<n>/<hash>.png`, a Variant of frame n (frame 0
is the room and is never imported), as `import --look` stores a Look's. `pick --loop <loop> --frame <n>` records a `pick`
Decision in the `loops` journal: the frame, the Variant and the room's Source it was made on. A new Source puts the edit
frames in needs-input (`kiripix.recipes.loops`, `_held_edits`).

A renamed Loop keeps its files where they are: a Variant is looked for under every ID the Loop has had, and a `pick`
records the ID of the folder it was found in as `was` when that isn't the Loop's current ID (the same as a kit's `was`).

An edit made from another edit drifts further from the Source each time (trial 0184: the median ΔE outside the screen
1.65, 2.61, 3.65, 4.67), so an import measures the edit against the Source outside the Loop's region, and when it is
over twice the first imported frame's and over 2.5, says so (`import.edit_of_an_edit`). The caller holds the Asset lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, Position
from kiripix.core import atomic, editing, journal, loopkit, sources
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba, read_as_png
from kiripix.core.project import Project
from kiripix.ops import difference_map, resize_nearest
from kiripix.recipes.base import StageSpec
from kiripix.recipes.kit_record import KIT_DIR, frame_name
from kiripix.recipes.loops import LOOPS_STAGE, declared, edit_path, former_ids, frames_source
from kiripix.recipes.regions import EditRoom
from kiripix.recipes.regions import fitted as fitted_edit

OF_AN_EDIT_RATIO = 2.0  # an edit this many times the first one's ΔE outside the region (and over the floor) is of an edit
OF_AN_EDIT_FLOOR = 2.5  # ΔE: the median outside the region must be over this (trial 0184: 1.65 for an edit of the Source)


@dataclass
class EditImported:
    name: str
    path: Path
    created: bool
    variants: list[str]  # this frame's Variants
    findings: list[Finding]


def _folder(asset: Asset, folder: str, frame: int) -> Path:
    return asset.dir / KIT_DIR / folder / "edits" / str(frame)


def frame_variants(asset: Asset, folders: list[str], frame: int) -> dict[str, str]:
    """Frame `frame`'s edit Variants by name, sorted, each with the folder ID it is stored under."""
    found: dict[str, str] = {}
    for folder in folders:
        for path in sorted(_folder(asset, folder, frame).glob("*.png")):
            found.setdefault(path.stem, folder)
    return dict(sorted(found.items()))


def _check_frame(asset: Asset, frame: int, prefix: str, loop: str, shown: str) -> None:
    if frame < 1:
        raise fail(f"{prefix}.frame_zero", f"frame {frame} of a Loop is the room's own, so it is never imported or picked; "
                   "edit frames count from 1",
                   fix=f"kiripix {prefix} {asset.id} {shown} --loop {loop} --frame 1",
                   position=Position(asset=asset.id, stage=LOOPS_STAGE))


def _edit_loop(graph: AssetGraph, asset: Asset, loop: str, prefix: str) -> None:
    """Refused unless `loop` is a declared frame Loop whose frames aren't a kit's or an Op's."""
    position = Position(asset=asset.id, stage=LOOPS_STAGE)
    spec = graph.spec(LOOPS_STAGE)
    run = graph.stage_run(spec, graph.output_dir(spec))
    loops = declared(run)
    if loop not in loops:
        raise fail(f"{prefix}.loop_unknown", f"{asset.id} has no Loop {loop}"
                   + (f"; its Loops are {', '.join(sorted(loops))}" if loops else ""),
                   fix=f"kiripix decide {asset.id} {LOOPS_STAGE} --decision "
                       f"'{{\"decision\": \"loop\", \"data\": {{\"loop\": \"{loop}\", \"form\": \"frames\"}}}}'",
                   position=position)
    if loops[loop].get("form", "cycle") != "frames":
        raise fail(f"{prefix}.loop_not_frames", f"the Loop {loop} is a cycle, and edit frames are the frames of a frame Loop",
                   owner_action=f"Declare it again with form frames (kiripix decide {asset.id} {LOOPS_STAGE} --help).",
                   position=position)
    chosen = frames_source(run, loop)
    if chosen in ("kit", "op"):
        what = "a kit's frames" if chosen == "kit" else "an Op"
        raise fail(f"{prefix}.loop_source_mixed",
                   f"the Loop {loop} takes its frames from {what}, and a frame Loop's frames come from one source only",
                   owner_action=f"Undo what chose them (kiripix undo {asset.id} {LOOPS_STAGE}), or set `source` `edits` "
                                f"in its `frames` Decision (kiripix decide {asset.id} {LOOPS_STAGE} --help).",
                   position=position)


def _median_outside(room: EditRoom, region: Any, edit: Any) -> float:
    """The median ΔE between the fitted edit and the fitted room, outside the Loop's region (the 3x3 mean, as a Look's
    `difference` measures it). The edit is resized to the Source's size first, as the `looks` Stage does."""
    height, width = room.source.shape[:2]
    fitted = fitted_edit(room.record, room.grid, resize_nearest(edit, width, height))
    seen = ~region & (room.fit[..., 3] > 0) & (fitted[..., 3] > 0)
    if not seen.any():
        return 0.0
    return float(np.median(difference_map(room.fit, fitted)[seen]))


def import_edit(project: Project, asset: Asset, file: Path, shown: str, loop: str, frame: int) -> EditImported:
    """Store an image as a Variant of frame `frame` of a frame Loop. Frame 0 is the room's and is refused."""
    _check_frame(asset, frame, "import", loop, shown)
    prepared = loopkit.prepare(project, asset, loop, "import.loop", need_region=False)
    graph = prepared.graph
    _edit_loop(graph, asset, loop, "import")
    folders = former_ids(graph.replay(LOOPS_STAGE).current, loop)
    data, pixels = read_as_png(file, shown)
    name = frame_name(data)
    folder = _folder(asset, loop, frame)
    path = folder / f"{name}.png"
    findings: list[Finding] = []
    first = _first_stored(asset, folders, exclude=path)
    if first is not None:
        before = _median_outside(prepared.room, prepared.region, load_rgba(first, first.name))
        now = _median_outside(prepared.room, prepared.region, pixels)
        if now > OF_AN_EDIT_FLOOR and now > OF_AN_EDIT_RATIO * before:
            findings.append(Finding(
                code="import.edit_of_an_edit", severity="info",
                message=f"{shown} differs from the Source outside the Loop's region by a median ΔE of {now:.2f}, over "
                        f"{OF_AN_EDIT_RATIO:g} times the first imported frame's {before:.2f}: it looks made from another "
                        "edit, which drifts further from the Source each time",
                position=Position(asset=asset.id, stage=LOOPS_STAGE, file=shown),
                owner_action="Make each edit from the Source, not from another edit."))
    created = not path.exists()
    if created:
        atomic.write_bytes(path, data)
    relative = path.relative_to(asset.dir).as_posix()
    if sources.imported_names(asset).get(relative) != Path(shown).name:
        atomic.append_jsonl_many(asset.dir / sources.IMPORTED_FILE, [
            {"schema_version": sources.IMPORTED_SCHEMA_VERSION, "file": relative, "imported_as": Path(shown).name}])
    return EditImported(name, path, created, list(frame_variants(asset, folders, frame)), findings)


def _first_stored(asset: Asset, folders: list[str], exclude: Path) -> Path | None:
    """The edit imported first, of any frame of the Loop (by file time, then name), other than `exclude`."""
    stored = [p for folder in folders for p in (asset.dir / KIT_DIR / folder / "edits").glob("*/*.png") if p != exclude]
    return min(stored, key=lambda p: (p.stat().st_mtime_ns, p.parent.name, p.name), default=None)


def pick_edit(project: Project, asset: Asset, loop: str, frame: int, variant: str) -> tuple[StageSpec, journal.JournalEntry]:
    """Record a `pick` Decision on the `loops` Stage: frame `frame`'s edit Variant, with the room's Source at this moment."""
    position = Position(asset=asset.id, stage=LOOPS_STAGE)
    _check_frame(asset, frame, "pick", loop, variant)
    if asset.kind != "room":
        raise fail("pick.loop_needs_room", f"--loop is for a room; {asset.id} is a {asset.kind}",
                   owner_action="Pick a Loop's edit on a room Asset.", position=position)
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    source = sources.picked(graph)
    if source is None:
        raise fail("pick.loop_needs_source", f"{asset.id} has no picked Source for the edit to be made on",
                   owner_action=f"Pick the room's Source first: kiripix pick {asset.id} <variant>.", position=position)
    _edit_loop(graph, asset, loop, "pick")
    folders = former_ids(graph.replay(LOOPS_STAGE).current, loop)
    known = frame_variants(asset, folders, frame)
    if variant not in known:
        if not known:
            raise fail("pick.unknown_variant", f"frame {frame} of {loop} has no edits yet", position=position,
                       fix=f"kiripix import {asset.id} <file> --loop {loop} --frame {frame}")
        raise fail("pick.unknown_variant", f"frame {frame} of {loop} has no edit '{variant}'; its edits are "
                   f"{', '.join(known)}", position=position,
                   owner_action=f"Pick one of them: kiripix pick {asset.id} <variant> --loop {loop} --frame {frame}")
    data: dict[str, Any] = {"loop": loop, "frame": frame, "variant": variant, "source": source}
    if known[variant] != loop:
        data["was"] = known[variant]
    entry, _ = editing.record_decision(project, asset, LOOPS_STAGE, editing.DecisionDocument(decision="pick", data=data))
    return graph.spec(LOOPS_STAGE), entry


__all__ = ["EditImported", "edit_path", "former_ids", "frame_variants", "import_edit", "pick_edit"]
