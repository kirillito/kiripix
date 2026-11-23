"""A portrait's emotions (ticket 0242): `import --emotion` stores an image as a Variant of a declared emotion in
`src/emotions/<folder>/`, and `pick --emotion` records the `emotion_pick` Decision with the neutral Source's hash. The caller
holds the Asset lock. The neutral Source is the Asset's own Pick (`core.sources`), as a Prop's default state is."""

import re
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.core import atomic, editing, journal
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.images import read_as_png
from kiripix.core.project import Project
from kiripix.core.sources import IMPORTED_FILE, IMPORTED_SCHEMA_VERSION, VARIANT_NAME_LENGTH, imported_as
from kiripix.recipes import portrait
from kiripix.recipes.base import StageSpec
from kiripix.recipes.portrait import DeclaredEmotion

PORTRAIT = "portrait"


def is_portrait(asset: Asset) -> bool:
    return asset.kind == PORTRAIT


def declared_emotions(graph: AssetGraph) -> dict[str, DeclaredEmotion]:
    """A portrait's declared emotions (the `emotion` Decisions of `source`, edits replayed); none for another Kind."""
    if not is_portrait(graph.asset):
        return {}
    return portrait.declared_emotions(graph.decisions(graph.spec(portrait.SOURCE_STAGE)))


def emotion_variants(asset: Asset, emotion: DeclaredEmotion) -> dict[str, Path]:
    """An emotion's Variants by name, sorted: `src/emotions/<folder>/<hash>.png`."""
    return {path.stem: path for path in sorted((asset.dir / portrait.EMOTIONS_DIR / emotion.folder).glob("*.png"))
            if path.is_file()}


def picked_emotions(graph: AssetGraph) -> dict[str, tuple[str, str]]:
    """Each emotion's current Pick as (Variant, the neutral Source it was made on)."""
    if not is_portrait(graph.asset):
        return {}
    return portrait.emotion_picks(graph.decisions(graph.spec(portrait.SOURCE_STAGE)))


def neutral_source(graph: AssetGraph) -> str | None:
    """The Variant the neutral Pick names now; None without one, and for another Kind."""
    if not is_portrait(graph.asset):
        return None
    return portrait.neutral_source(graph.decisions(graph.spec(portrait.SOURCE_STAGE)))


def _declared(graph: AssetGraph, emotion: str, command: str, position: Position) -> DeclaredEmotion:
    """The declared emotion, or the refusal: `neutral` is no emotion, and an undeclared one has a fix that declares it."""
    asset = graph.asset
    if not is_portrait(asset):
        raise fail(f"{command}.emotion_needs_portrait", f"--emotion is for a portrait; {asset.id} is a {asset.kind}",
                   owner_action="Use --emotion on a portrait's emotions.", position=position)
    if emotion == portrait.NEUTRAL:
        raise fail("portrait.emotion_duplicate", f"{emotion} is the neutral image's ID, so it isn't an emotion: the neutral "
                   "image is the Source", fix=f"kiripix {command} {asset.id} <file>" if command == "import"
                   else f"kiripix pick {asset.id} <variant>", position=position)
    declared = declared_emotions(graph)
    if emotion not in declared:
        if re.fullmatch(portrait.EMOTION_ID, emotion) is None:
            raise fail("portrait.emotion_unknown", f"'{emotion}' is not an emotion ID: lower-case snake_case, such as happy",
                       owner_action="Choose an ID such as happy or very_sad.", position=position)
        raise fail("portrait.emotion_unknown", f"{asset.id} has no emotion {emotion}"
                   + (f"; its emotions are {', '.join(declared)}" if declared else ""), position=position,
                   fix=portrait.declare_command(asset.id, emotion))
    return declared[emotion]


def declared_emotion(graph: AssetGraph, emotion: str, command: str) -> DeclaredEmotion:
    """A portrait's declared emotion, or the refusal `import` gives (for `gen`, ticket 0379, before a call is paid)."""
    return _declared(graph, emotion, command, Position(asset=graph.asset.id))


def import_emotion(project: Project, asset: Asset, file: Path, shown: str, role: str, emotion: str) -> tuple[
        DeclaredEmotion, str, Path, bool]:
    """Add an image as a Variant of a portrait's declared emotion, in `src/emotions/<emotion>/` (a JPEG is stored as a PNG);
    the neutral Source is untouched. Returns the emotion, the Variant's name and path, and whether it is new. Records the
    name the file was imported with."""
    position = Position(asset=asset.id, file=shown)
    if role != "variant":
        raise fail("import.emotion_takes_images", f"--role {role} doesn't apply to an emotion's image",
                   fix=f"kiripix import {asset.id} {shown} --emotion {emotion}", position=position)
    declared = _declared(AssetGraph(project, asset, HashCache(project.state_dir)), emotion, "import", position)
    data, _ = read_as_png(file, shown)
    name = hash_bytes(data)[:VARIANT_NAME_LENGTH]
    path = asset.dir / portrait.EMOTIONS_DIR / declared.folder / f"{name}.png"
    created = not path.exists()
    if created:
        atomic.write_bytes(path, data)
    if imported_as(asset, path) != file.name:
        atomic.append_jsonl_many(asset.dir / IMPORTED_FILE, [
            {"schema_version": IMPORTED_SCHEMA_VERSION, "file": path.relative_to(asset.dir).as_posix(),
             "imported_as": file.name}])
    return declared, name, path, created


def pick_emotion(project: Project, asset: Asset, emotion: str, variant: str) -> tuple[StageSpec, journal.JournalEntry]:
    """Record an `emotion_pick` Decision on the `source` Stage: the Variant of a portrait's declared emotion, with the
    neutral Source's hash (Variant name) at this moment. The same entry `decide` would write."""
    position = Position(asset=asset.id, stage=portrait.SOURCE_STAGE)
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    declared = _declared(graph, emotion, "pick", position)
    source = neutral_source(graph)
    if source is None:
        raise fail("pick.emotion_needs_source", f"{asset.id} has no picked neutral Source for the edit to be made on",
                   owner_action=f"Pick the neutral Source first: kiripix pick {asset.id} <variant>.", position=position)
    known = emotion_variants(asset, declared)
    if variant not in known:
        if not known:
            raise fail("pick.unknown_variant", f"the emotion {emotion} of {asset.id} has no Variants yet", position=position,
                       fix=f"kiripix import {asset.id} <file> --emotion {emotion}")
        raise fail("pick.unknown_variant", f"the emotion {emotion} of {asset.id} has no Variant '{variant}'; its Variants are "
                   f"{', '.join(known)}", position=position,
                   owner_action=f"Pick one of them: kiripix pick {asset.id} <variant> --emotion {emotion}")
    spec = graph.spec(portrait.SOURCE_STAGE)
    document = editing.DecisionDocument(decision=portrait.EMOTION_PICK.name,
                                        data={"emotion": emotion, "variant": variant, "source": source})
    entry, _ = editing.record_decision(project, asset, spec.name, document)
    return spec, entry


def emotion_edit_findings(project: Project, asset: Asset, stage: str, documents: list[tuple[str, dict[str, Any]]]
                          ) -> list[Finding]:
    """What refuses a portrait's emotion Decision (on `decide` and on `redo`): an ID that is `neutral` or taken, and an
    emotion that isn't declared. The ID freeze after export is the exporter's (ticket 0244), which knows the Manifest."""
    names = {d.name for d in portrait.DECISIONS}
    if not is_portrait(asset) or stage != portrait.SOURCE_STAGE or not any(name in names for name, _ in documents):
        return []
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    found, _ = portrait.edit_problems(asset.id, graph.decisions(graph.spec(portrait.SOURCE_STAGE)), documents)
    return found
