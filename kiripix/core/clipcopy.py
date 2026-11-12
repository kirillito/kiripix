"""Copying a character's clips to another character (ticket 0171, spec §6.3): each of the other's current clips is recorded
again as a `clip` Decision on this one, and the clip-source files they name are copied with them, byte for byte, so
they keep their hashed name. There is no link between the two: a later change on the other isn't carried over. The caller
holds the lock of the Asset copied to; the other is only read."""

from dataclasses import dataclass, field
from pathlib import Path

from kiripix.checks import Position
from kiripix.core import atomic, editing, sources
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.recipes.base import CurrentDecision
from kiripix.recipes.clips import CLIP, latest_clips

CLIPS_STAGE = "clips"


@dataclass
class ClipCopy:
    """What a copy does: the clips it adds, the ones it decides again, the ones it leaves, and the files it adds."""

    decisions: list[CurrentDecision] = field(default_factory=list)  # the other's, in its order, for the first two
    copied: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)  # the other's clip-source files to add
    stale: list[Path] = field(default_factory=list)  # this one's files of the same name and other content, to take away


def _clips(project: Project, asset: Asset) -> list[CurrentDecision]:
    return latest_clips(AssetGraph(project, asset, HashCache(project.state_dir)).replay(CLIPS_STAGE).current)


def _need_character(asset: Asset) -> None:
    if not sources.takes_models(asset):
        raise fail("clips.not_character", f"{asset.id} is a {asset.kind}, and only a character has clips",
                   fix="kiripix new character <name>", position=Position(asset=asset.id))


def plan(project: Project, asset: Asset, other: Asset, names: list[str] | None, replace: bool) -> ClipCopy:
    """What copying `other`'s clips (or only `names`) to `asset` would do. Refuses what it can't do, before any write."""
    _need_character(asset)
    _need_character(other)
    if asset.id == other.id:
        raise fail("clips.copy_itself", f"{asset.id} can't copy clips from itself", fix=f"kiripix show {asset.id}",
                   position=Position(asset=asset.id))
    theirs = _clips(project, other)
    known = {str(d.data["name"]) for d in theirs}
    if names is not None and (unknown := [n for n in names if n not in known]):
        raise fail("clips.unknown_clip", f"{other.id} has no clip {', '.join(unknown)}; its clips are "
                   f"{', '.join(sorted(known)) or 'none'}", fix=f"kiripix show {other.id}",
                   position=Position(asset=other.id, stage=CLIPS_STAGE))
    if not theirs:
        raise fail("clips.nothing_to_copy", f"{other.id} has no clips", fix=f"kiripix show {other.id}",
                   position=Position(asset=other.id, stage=CLIPS_STAGE))
    ours = {str(d.data["name"]) for d in _clips(project, asset)}
    result = ClipCopy()
    for decision in theirs:
        name = str(decision.data["name"])
        if names is not None and name not in names:
            continue
        if name in ours and not replace:
            result.skipped.append(name)
            continue
        (result.replaced if name in ours else result.copied).append(name)
        result.decisions.append(decision)
    _plan_files(asset, other, result, replace)
    return result


def _plan_files(asset: Asset, other: Asset, result: ClipCopy, replace: bool) -> None:
    theirs, ours = sources.clip_sources(other), sources.clip_sources(asset)
    for stem in dict.fromkeys(str(d.data["source"]).split("/")[0] for d in result.decisions):
        if stem not in theirs:
            continue  # an action of the rig's file: copied as it is
        mine = ours.get(stem)
        if mine is not None and mine.name == theirs[stem].name:
            continue  # the same bytes are already there
        if mine is not None:
            if not replace:
                raise fail("clips.source_differs", f"{asset.id} has its own clip source {stem}, which isn't the file "
                           f"{other.id} has; copying would replace it for the clips of {asset.id} that name it",
                           fix=f"kiripix clips copy {asset.id} --source-asset {other.id} --replace",
                           position=Position(asset=asset.id, file=f"src/clips/{mine.name}"))
            result.stale.append(mine)
        result.files.append(theirs[stem])


def apply(asset: Asset, other: Asset, project: Project, result: ClipCopy) -> list[Path]:
    """Copy the files, then record the Decisions. Returns the files added, in this Asset's folder."""
    added: list[Path] = []
    folder = asset.dir / "src" / "clips"
    names = sources.imported_names(other)
    for path in result.files:
        target = folder / path.name
        atomic.write_bytes(target, path.read_bytes())
        added.append(target)
        imported = names.get(path.relative_to(other.dir).as_posix())
        if imported is not None and sources.imported_as(asset, target) != imported:
            atomic.append_jsonl_many(asset.dir / sources.IMPORTED_FILE, [
                {"schema_version": sources.IMPORTED_SCHEMA_VERSION, "file": target.relative_to(asset.dir).as_posix(),
                 "imported_as": imported}])
    for old in result.stale:
        old.unlink(missing_ok=True)
    documents = [editing.DecisionDocument(decision=CLIP.name, data=dict(d.data)) for d in result.decisions]
    if documents:
        editing.record_decisions(project, asset, CLIPS_STAGE, documents)
    return added
