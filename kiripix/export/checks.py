"""The Exporter's Checks: the ID freeze (ADR 0003) and Exit pairing (spec §6.1).

Both read the game's Manifest or the Assets' Decisions, so they live above core. `check` calls `frozen_findings` for one
Asset, and `check --all` reaches both through the Project check registered here (core's hook, ticket 0014): this module
is imported with `kiripix.export`, which every Command that checks already imports.
"""

import json
from collections.abc import Callable
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.core import cancel
from kiripix.core.assets import Asset
from kiripix.core.emotions import is_portrait
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph, register_adviser
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.core.project_checks import register_project_check
from kiripix.export.godot import EXPORTED_MARKER_TYPES, animation_name, room_ids
from kiripix.export.manifest import ExportedIds, Manifest, read_manifest
from kiripix.export.room import EXPORT_STAGE, ROOM_FILE, ROOM_SCHEMA_VERSION
from kiripix.export.target import resolve_target
from kiripix.recipes.base import StageSpec
from kiripix.recipes.clips import CLIP, DIRECTIONS, TRANSITION
from kiripix.recipes.looks import LOOKS_STAGE, look_ids
from kiripix.recipes.loops import LOOP_EDITS, LOOPS_STAGE, declared_ids, edit_problems
from kiripix.recipes.portrait import SOURCE_STAGE as PORTRAIT_SOURCE, edit_problems as emotion_edit_problems
from kiripix.recipes.portrait import declared_emotions
from kiripix.recipes.prop_states import (
    BRIEF_STAGE,
    DECISIONS as _STATE_DECISIONS,
    SOURCE_STAGE,
    declared_states,
    edit_problems as state_edit_problems,
)
from kiripix.recipes.sprite_frames import FRAMES_FILE

STATE_NAMES = frozenset(d.name for d in _STATE_DECISIONS)

EXPORTERS = frozenset({"room", "prop", "character", "sprite", "icon", "wearable", "portrait"})  # the Kinds that have an exporter


def _current_ids(graph: AssetGraph, manifest: Manifest) -> ExportedIds:
    """The IDs the Asset would export now. Markers come from the Decisions, so a rename fails before anything is run
    again. A room's Masks and Layers come from the built export when there is one, and otherwise are taken as unchanged.
    A prop exports no Marker, Layer or Mask ID to freeze. A character's clip animations come from its `clip` Decisions."""
    markers: set[str] = set()
    links: set[str] = set()
    for spec in graph.kind.stages:
        if spec.markers is not None:
            placed = spec.markers(graph.replay(spec.name).current)
            markers.update(str(marker["id"]) for marker in placed if marker["type"] in EXPORTED_MARKER_TYPES)
            links.update(str(marker["id"]) for marker in placed if marker["type"] == "link")
    ids = manifest.ids.model_copy(update={"markers": sorted(markers), "links": sorted(links)})
    own = _IDS_OF_KIND.get(graph.asset.kind)
    return ids.model_copy(update=own(graph, ids)) if own is not None else ids


def _room_ids(graph: AssetGraph, unchanged: ExportedIds) -> dict[str, Any]:
    # a Look's ID is its `pick`'s, so one taken away fails before anything is run again
    found: dict[str, Any] = {"looks": sorted(look_ids(graph.replay(LOOKS_STAGE).current)),
                             # a Loop's ID is its `loop` Decision's once a `rename` and a `remove` are replayed, and shares
                             # the namespace with the Looks'
                             "loops": declared_ids(graph.replay(LOOPS_STAGE).current)}
    spec = graph.spec(EXPORT_STAGE)
    if graph.built_hash(spec) is not None:
        try:
            room = json.loads((graph.output_dir(spec) / ROOM_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            room = {}
        if room.get("schema_version") == ROOM_SCHEMA_VERSION:
            built = room_ids(room)
            found.update(layers=built.layers, masks=built.masks)
    return found


def _character_ids(graph: AssetGraph, unchanged: ExportedIds) -> dict[str, Any]:
    # a clip's name is its ID, and its animations are the clip in each direction: from the Decisions, so that a clip
    # taken away fails before anything is run again
    return {"clips": sorted(animation_name(str(d.data["name"]), direction) for d in graph.replay("clips").current
                            if d.name in (CLIP.name, TRANSITION.name) for direction in DIRECTIONS)}


def _sprite_ids(graph: AssetGraph, unchanged: ExportedIds) -> dict[str, Any]:
    return {"clips": _sprite_animations(graph, unchanged.clips)}


def _prop_ids(graph: AssetGraph, unchanged: ExportedIds) -> dict[str, Any]:
    # a state's ID is its `state` Decision's: one taken away fails before anything is run
    declared = declared_states(graph.decisions(graph.spec(SOURCE_STAGE)))
    # the default state's node is named by the brief's `state`, so its ID is frozen with the others (ticket 0260)
    default = [str(graph.params(graph.spec(BRIEF_STAGE))["state"])] if declared else []
    return {"states": sorted({*declared, *default})}


def _portrait_ids(graph: AssetGraph, unchanged: ExportedIds) -> dict[str, Any]:
    # an emotion's ID is its `emotion` Decision's, edits replayed (ticket 0244)
    return {"emotions": sorted(declared_emotions(graph.decisions(graph.spec(PORTRAIT_SOURCE))))}


# The IDs of a Kind that its Decisions (or built export) give, beyond the Markers' and Links': the fields of `ExportedIds`
# they replace. A Kind not listed has none, and keeps the Manifest's.
_IDS_OF_KIND: dict[str, Callable[[AssetGraph, ExportedIds], dict[str, Any]]] = {
    "room": _room_ids, "character": _character_ids, "sprite": _sprite_ids, "prop": _prop_ids, "portrait": _portrait_ids}


def _sprite_animations(graph: AssetGraph, unchanged: list[str]) -> list[str]:
    """A sprite's animation names, from the clips `frames` last cut (its clips come from the sheets, not from Decisions, so
    a clip taken away is seen once `frames` has run again). With `frames` not built, they are taken as unchanged."""
    spec = graph.spec("frames")
    if graph.built_hash(spec) is None:
        return unchanged
    try:
        document = json.loads((graph.output_dir(spec) / FRAMES_FILE).read_text(encoding="utf-8"))
        return sorted(animation_name(str(clip["name"]), direction) for clip in document["clips"]
                      for direction in clip["directions"])
    except (OSError, ValueError, KeyError, TypeError):
        return unchanged


def frozen_findings(project: Project, asset: Asset, cache: HashCache) -> list[Finding]:
    """An error for every ID the game's Manifest lists that the Asset no longer has. Nothing is frozen with no game
    configured or no Manifest yet. With a game configured but not at its path, the freeze refuses rather than guesses
    (ADR 0003), and that refusal is the finding."""
    exported = _exported(project, asset)
    if exported is None or isinstance(exported, list):
        return exported or []
    manifest, shown, where = exported
    now = _current_ids(AssetGraph(project, asset, cache), manifest)
    found: list[Finding] = []
    for noun, was, is_now in (("Marker", manifest.ids.markers, now.markers), ("Layer", manifest.ids.layers, now.layers),
                              ("Mask", manifest.ids.masks, now.masks), ("Look", manifest.ids.looks, now.looks), ("Loop", manifest.ids.loops, now.loops),
                              ("Link", manifest.ids.links, now.links), ("state", manifest.ids.states, now.states), ("emotion", manifest.ids.emotions, now.emotions), ("clip animation", manifest.ids.clips, now.clips)):
        for gone in sorted(set(was) - set(is_now)):
            found.append(Finding(
                code="export.id_frozen",
                message=f"{asset.id}: the {noun} ID '{gone}' was exported in {where} (Manifest {shown}, export "
                        f"{manifest.counter}), so it can't be renamed or removed",
                position=Position(asset=asset.id, file=shown),
                owner_action=f"Put '{gone}' back (undo the change, or decide the clip again under its old name): the game "
                             "refers to it. Adding new IDs is always fine." if noun == "clip animation" else
                             f"Put '{gone}' back (undo the change, or place a {noun} with that ID again): the game "
                             "refers to it. Adding new IDs is always fine."))
    return found


def _exported(project: Project, asset: Asset) -> tuple[Manifest, str, str] | list[Finding] | None:
    """The game's Manifest of an Asset that has been exported, with its path and the scenes it lists; the finding when a
    game is configured but not at its path (ADR 0003); None with no game, no Manifest or nothing exported yet."""
    if asset.kind not in EXPORTERS or project.settings.export.godot.project is None:
        return None
    try:
        target = resolve_target(project)
    except KiripixError as error:
        return list(error.findings)
    shown = target.manifest(asset.id)
    manifest = read_manifest(target.path(shown), shown)
    if manifest is None or not manifest.exported:
        return None
    return manifest, shown, ", ".join(sorted(res for res in manifest.files if res.endswith(".tscn"))) or shown


def _frozen_by_decision(project: Project, asset: Asset, noun: str, stage: str, ids: list[str], verb: str,
                        exported: Callable[[Manifest], list[str]]) -> list[Finding]:
    """An error for each of `ids` the game's Manifest lists: a Decision that takes it away is refused before it is recorded
    (spec §9)."""
    found = _exported(project, asset) if ids else None
    if found is None or isinstance(found, list):
        return found or []
    manifest, shown, where = found
    return [Finding(
        code="export.id_frozen",
        message=f"{asset.id}: the {noun} ID '{one}' was exported in {where} (Manifest {shown}, export "
                f"{manifest.counter}), so it can't be {verb}",
        position=Position(asset=asset.id, stage=stage, file=shown),
        owner_action=f"Keep the {noun} '{one}': the game refers to it. Adding new {noun}s is always fine.")
        for one in ids if one in exported(manifest)]


def frozen_layer_findings(project: Project, asset: Asset, layers: list[str]) -> list[Finding]:
    """An error for each of `layers` the game's Manifest lists: a `remove` of it is refused before it is recorded."""
    return _frozen_by_decision(project, asset, "Layer", "layers", layers, "removed", lambda m: m.ids.layers)


def frozen_loop_findings(project: Project, asset: Asset, loops: list[str]) -> list[Finding]:
    """An error for each of `loops` the game's Manifest lists: a `remove` or `rename` of it is refused before it is
    recorded."""
    return _frozen_by_decision(project, asset, "Loop", LOOPS_STAGE, loops, "renamed or removed", lambda m: m.ids.loops)


def loop_edit_findings(project: Project, asset: Asset, stage: str, documents: list[tuple[str, dict[str, Any]]]) -> list[Finding]:
    """What refuses a `remove` or `rename` of a Loop (on `decide` and on `redo`): the `loops` Stage's own rules
    (`edit_problems`), and the ID freeze, which only the Manifest knows."""
    if asset.kind != "room" or stage != LOOPS_STAGE or not any(name in LOOP_EDITS for name, _ in documents):
        return []
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    found, edited = edit_problems(asset.id, graph.replay(LOOPS_STAGE).current, documents,
                                  look_ids(graph.replay(LOOKS_STAGE).current))
    return found + frozen_loop_findings(project, asset, edited)


def state_edit_findings(project: Project, asset: Asset, stage: str, documents: list[tuple[str, dict[str, Any]]]) -> list[Finding]:
    """What refuses a Prop's state Decision (on `decide` and on `redo`): an ID that is the default's or is taken, a size over
    the project's resolution, a state that isn't declared, and, only the Manifest knowing it, a `state_remove` or
    `state_rename` of a state already exported (its ID is frozen)."""
    if asset.kind != "prop" or stage != SOURCE_STAGE or not any(name in STATE_NAMES for name, _ in documents):
        return []
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    brief = graph.params(graph.spec(BRIEF_STAGE))
    found, edited = state_edit_problems(
        asset.id, graph.decisions(graph.spec(SOURCE_STAGE)), str(brief["state"]),
        (project.settings.project.resolution[0], project.settings.project.resolution[1]), documents,
        (int(str(brief["width"])), int(str(brief["height"]))))
    return found + _frozen_by_decision(project, asset, "state", SOURCE_STAGE, edited, "renamed or removed",
                                       lambda m: m.ids.states)


def emotion_freeze_findings(project: Project, asset: Asset, stage: str, documents: list[tuple[str, dict[str, Any]]]) -> list[Finding]:
    """What the game's Manifest refuses of a portrait's emotion Decision (on `decide` and on `redo`): an `emotion_remove` or
    `emotion_rename` of an emotion already exported (its ID is frozen). Adding an emotion is fine."""
    if not is_portrait(asset) or stage != PORTRAIT_SOURCE:
        return []
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    _, edited = emotion_edit_problems(asset.id, graph.decisions(graph.spec(PORTRAIT_SOURCE)), documents)
    return _frozen_by_decision(project, asset, "emotion", PORTRAIT_SOURCE, edited, "renamed or removed",
                               lambda m: m.ids.emotions)


def _exits(project: Project, assets: list[Asset]) -> dict[str, dict[str, dict[str, str]]]:
    """Each Asset that places Markers, with its Exits by ID: `{target_room, target_exit}`."""
    cache = HashCache(project.state_dir)
    rooms: dict[str, dict[str, dict[str, str]]] = {}
    for asset in assets:
        cancel.check()
        graph = AssetGraph(project, asset, cache)
        specs = [spec for spec in graph.kind.stages if spec.markers is not None]
        if not specs:
            continue
        exits: dict[str, dict[str, str]] = {}
        for spec in specs:
            assert spec.markers is not None
            for marker in spec.markers(graph.replay(spec.name).current):
                if marker["type"] == "exit":
                    exits[str(marker["id"])] = {"target_room": str(marker.get("target_room", "")),
                                                "target_exit": str(marker.get("target_exit", ""))}
        rooms[asset.id] = exits
    return rooms


def pairing_findings(project: Project, assets: list[Asset], *, only: str | None = None,
                     severity: str = "error") -> list[Finding]:
    """Every Exit must name an existing room and an Exit of it that points back. `only` limits the Exits looked at to
    one Asset's own."""
    rooms = _exits(project, assets)
    found: list[Finding] = []
    for room in sorted(rooms):
        if only is not None and room != only:
            continue
        for exit_id, exit_ in sorted(rooms[room].items()):
            there, back = exit_["target_room"], exit_["target_exit"]
            code, why = "", ""
            if there not in rooms:
                code, why = "exit.no_room", f"there is no room '{there}'"
            elif back not in rooms[there]:
                code, why = "exit.no_exit", f"{there} has no Exit '{back}'"
            elif rooms[there][back] != {"target_room": room, "target_exit": exit_id}:
                other = rooms[there][back]
                code, why = "exit.not_paired", (f"{there} {back} leads to {other['target_room']} "
                                                f"{other['target_exit']}, not back here")
            if code:
                found.append(Finding(
                    code=code, severity=severity,
                    message=f"{room} {exit_id} leads to {there} {back}, but {why}"
                            + (" (only a warning for one room; `check --all` and `export --all` fail on it)"
                               if severity == "warning" else ""),
                    position=Position(asset=room, stage="place"),
                    owner_action=f"Place the Exit '{back}' in {there} with target_room = {room} and target_exit = "
                                 f"{exit_id}, or point {room} {exit_id} at an Exit that points back."))
    return found


def exits_naming(project: Project, assets: list[Asset], gone: set[str]) -> list[Finding]:
    """A warning for every Exit of `assets` that still leads to one of the Assets in `gone` (being pruned)."""
    rooms = _exits(project, assets)
    return [Finding(
        code="export.exit_to_pruned", severity="warning",
        message=f"{room} {exit_id} still leads to {exit_['target_room']}, which was pruned from the game",
        position=Position(asset=room, stage="place"),
        owner_action=f"Point {room} {exit_id} at another room, or remove it, so the game's door doesn't lead nowhere.")
        for room in sorted(rooms) for exit_id, exit_ in sorted(rooms[room].items()) if exit_["target_room"] in gone]


@register_adviser
def _frozen_loop_advice(graph: AssetGraph, spec: StageSpec, findings: list[Finding]) -> list[Finding]:
    """A Loop held for sharing its ID with a Look, whose ID the game's Manifest already lists: the Loop can't be renamed (the
    game refers to it), so the only way out is the Look's other ID. The finding's advice says so."""
    held = [f for f in findings if f.code == "loop.held" and f.position is not None and (f.position.field or "").startswith("loop.")]
    exported = _exported(graph.project, graph.asset) if spec.name == LOOPS_STAGE and held else None
    if exported is None or isinstance(exported, list):
        return findings
    manifest = exported[0]
    looks = look_ids(graph.replay(LOOKS_STAGE).current)
    advised: list[Finding] = []
    for finding in findings:
        name = ((finding.position.field or "")[len("loop."):]) if finding in held and finding.position else ""
        if name and name in looks and name in manifest.ids.loops:
            finding = finding.model_copy(update={"fix": None, "owner_action": (
                f"The Loop {name} was exported, so the game refers to its ID and it can't change. Give the Look {name} "
                f"another ID: undo its `pick` (kiripix undo {graph.asset.id} {LOOKS_STAGE}, as many times as it takes) and "
                "pick it again under another ID.")})
        advised.append(finding)
    return advised


@register_project_check
def _project_check(project: Project, assets: list[Asset]) -> list[Finding]:
    found: list[Finding] = []
    cache = HashCache(project.state_dir)
    for asset in assets:
        cancel.check()
        try:
            found.extend(frozen_findings(project, asset, cache))
        except KiripixError as error:
            found.extend(error.findings)
    return found + pairing_findings(project, assets)
