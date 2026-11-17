"""The Project clip table against what the characters and sprites built (ticket 0239, spec §6.3).

`kiripix.toml`'s `[[character.clips]]` fixes a clip's rendered frame count, fps and loop (and, with `foot`, its foot frames) for every
body that has a clip of that name. This module reads a character's built `clips.json` and a sprite's built `render.json` as files
(core sits above `recipes` but never runs its Stages) and registers the Project check `clips.timing_differs`, run by `check --all`
and `export --all`. A character that lacks a clip of the table raises nothing: an NPC needn't have `phone`. Nothing here writes.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.core.project_checks import register_project_check
from kiripix.core.settings import ClipSpec

CLIPS_STAGE = "clips"
CLIPS_FILE = "clips.json"
FIT_STAGE = "fit"
RENDER_FILE = "render.json"
FRAMES_STAGE = "frames"
CHARACTER_KIND = "character"
SPRITE_KIND = "sprite"


@dataclass(frozen=True)
class BuiltClip:
    """A clip as built: its frame count (in one direction), fps, loop, whether it has foot frames and, for a character, the
    `clip` Decision's data it was built from (None for a transition)."""

    name: str
    frames: int
    fps: int
    loop: bool
    foot: bool
    stationary: bool = False
    decision: dict[str, Any] | None = None


def _read(path: Path) -> dict[str, Any] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _built_file(graph: AssetGraph, stage: str, file: str) -> dict[str, Any] | None:
    specs = [s for s in graph.kind.stages if s.name == stage]
    if not specs or graph.built_hash(specs[0]) is None:
        return None
    return _read(graph.output_dir(specs[0]) / file)


def built_clips(graph: AssetGraph) -> dict[str, BuiltClip] | None:
    """The clips the Asset built, by name, or None when it has no built `clips` Stage (a character) or `fit` Stage (a sprite)."""
    if graph.asset.kind == CHARACTER_KIND:
        document = _built_file(graph, CLIPS_STAGE, CLIPS_FILE)
        if document is None:
            return None
        decided = {str(d.data.get("name")): dict(d.data) for d in graph.decisions(graph.spec(CLIPS_STAGE)) if d.name == "clip"}
        found: dict[str, BuiltClip] = {}
        for entry in document.get("clips", []):
            if not isinstance(entry, dict) or "name" not in entry:
                continue
            name = str(entry["name"])
            events = entry.get("events") or {}
            found[name] = BuiltClip(name, len(entry.get("frames", [])), int(entry.get("fps", 0)), bool(entry.get("loop", False)),
                                    bool(events.get("foot")), bool(entry.get("stationary", False)), decided.get(name))
        return found
    if graph.asset.kind == SPRITE_KIND:
        document = _built_file(graph, FIT_STAGE, RENDER_FILE)
        if document is None:
            return None
        found = {}
        for entry in document.get("clips", []):
            if not isinstance(entry, dict) or "name" not in entry:
                continue
            counts = [len(frames) for frames in (entry.get("directions") or {}).values()]
            name = str(entry["name"])
            found[name] = BuiltClip(name, max(counts, default=0), int(entry.get("fps", 0)), bool(entry.get("loop", False)),
                                    False, bool(entry.get("stationary", False)))
        return found
    return None


def _decide(asset: str, stage: str, data: dict[str, Any]) -> str:
    return f"kiripix decide {asset} {stage} --decision '{json.dumps({'decision': 'clip', 'data': data})}'"


def differences(row: ClipSpec, built: BuiltClip, *, foot: bool = True) -> dict[str, str]:
    """What differs between a built clip and its row, by field (`frames`, `fps`, `loop`, `foot`), each with its message. With
    `foot` False (a sprite, which has no foot events), foot frames aren't asked for."""
    differs: dict[str, str] = {}
    if built.frames != row.frames:
        differs["frames"] = f"frames are {built.frames}, the table's are {row.frames}"
    if built.fps != row.fps:
        differs["fps"] = f"fps is {built.fps}, the table's is {row.fps}"
    if built.loop != row.loop:
        differs["loop"] = f"loop is {str(built.loop).lower()}, the table's is {str(row.loop).lower()}"
    if foot and row.foot and not built.foot:
        differs["foot"] = "it has no foot frames, and the table asks for them"
    return differs


def timing_findings(row: ClipSpec, built: BuiltClip, asset: Asset) -> list[Finding]:
    """The `clips.timing_differs` of one clip of one Asset against its row (none when it matches)."""
    sprite = asset.kind == SPRITE_KIND
    differs = differences(row, built, foot=not sprite)
    if not differs:
        return []
    stage = FIT_STAGE if sprite else CLIPS_STAGE
    where = Position(asset=asset.id, stage=stage, file=RENDER_FILE if sprite else CLIPS_FILE,
                     field=f"clips.{row.name}.{','.join(differs)}")
    message = f"{asset.id}'s clip '{row.name}' differs from the Project's clip table: {'; '.join(differs.values())}"
    kind: dict[str, Any] = {}
    timing = built.fps != row.fps or built.loop != row.loop
    if sprite:
        message += ". A sprite's clip is warned about, not failed: a one-frame PixelLab idle will differ"
        kind["severity"] = "warning"
        if timing:
            data = {"name": row.name, "fps": row.fps, "loop": row.loop, "stationary": built.stationary}
            return [Finding(code="clips.timing_differs", message=message, position=where, fix=_decide(asset.id, FRAMES_STAGE, data),
                            **kind)]
        return [Finding(code="clips.timing_differs", message=message, position=where, **kind,
                        owner_action=f"The sprite's sheets decide the frame count of '{row.name}': cut it to {row.frames} frames, "
                                     "or change the table's row if this sprite is the exception.")]
    if built.decision is not None and timing and "still" not in built.decision:
        data = {**built.decision, "fps": row.fps, "loop": row.loop}
        note = ""
        if built.frames != row.frames:
            note = " (the frame count follows the fps; if it still differs, only the Owner can choose the range or speed)"
        return [Finding(code="clips.timing_differs", message=message + note, position=where,
                        fix=_decide(asset.id, CLIPS_STAGE, data))]
    if built.decision is not None and built.frames != row.frames and not timing and "still" in built.decision:
        advice = (f"Hold the still for {row.frames} frames: decide '{row.name}' again with still={row.frames} "
                  f"(kiripix decide {asset.id} {CLIPS_STAGE}), or change the table's row.")
    elif built.decision is not None and built.frames != row.frames and not timing:
        advice = (f"Only the Owner can choose how '{row.name}' gets {row.frames} frames: its start and end, or its speed "
                  f"(kiripix decide {asset.id} {CLIPS_STAGE}), or change the table's row.")
    elif not built.foot and row.foot:
        advice = (f"Foot frames come from the clip's source: choose a range of '{row.name}' where a foot plants "
                  f"(kiripix decide {asset.id} {CLIPS_STAGE}), or take `foot` out of the table's row.")
    else:
        advice = f"Decide '{row.name}' again to match the table (kiripix decide {asset.id} {CLIPS_STAGE}), or change the table's row."
    return [Finding(code="clips.timing_differs", message=message, position=where, owner_action=advice)]


def clip_timing_findings(project: Project, assets: list[Asset], cache: HashCache | None = None) -> list[Finding]:
    """`clips.timing_differs` for every character and sprite that has a clip named in the table. An Asset without that clip, or
    without a built `clips` (a sprite: `fit`) Stage, raises nothing."""
    table = project.settings.character.clips
    if not table:
        return []
    cache = cache or HashCache(project.state_dir)
    found: list[Finding] = []
    for asset in assets:
        if asset.kind not in (CHARACTER_KIND, SPRITE_KIND):
            continue
        try:
            built = built_clips(AssetGraph(project, asset, cache))
        except KiripixError:
            continue
        if built is None:
            continue
        for row in table:
            if row.name in built:
                found.extend(timing_findings(row, built[row.name], asset))
    return found


@register_project_check
def _check_timing_differs(project: Project, assets: list[Asset]) -> list[Finding]:
    return clip_timing_findings(project, assets)
