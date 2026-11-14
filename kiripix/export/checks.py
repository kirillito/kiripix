"""The Exporter's Checks: the ID freeze (ADR 0003) and Exit pairing (spec §6.1).

Both read the game's Manifest or the Assets' Decisions, so they live above core. `check` calls `frozen_findings` for one
Asset, and `check --all` reaches both through the Project check registered here (core's hook, ticket 0014): this module
is imported with `kiripix.export`, which every Command that checks already imports.
"""

import json

from kiripix.checks import Finding, Position
from kiripix.core import cancel
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.core.project_checks import register_project_check
from kiripix.export.godot import EXPORTED_MARKER_TYPES, animation_name, room_ids
from kiripix.export.manifest import ExportedIds, Manifest, read_manifest
from kiripix.export.room import EXPORT_STAGE, ROOM_FILE, ROOM_SCHEMA_VERSION
from kiripix.export.target import resolve_target
from kiripix.recipes.clips import CLIP, DIRECTIONS
from kiripix.recipes.looks import LOOKS_STAGE
from kiripix.recipes.loops import LOOPS_STAGE
from kiripix.recipes.sprite_frames import FRAMES_FILE

EXPORTERS = frozenset({"room", "prop", "character", "sprite"})  # the Kinds that have an exporter


def _current_ids(graph: AssetGraph, manifest: Manifest) -> ExportedIds:
    """The IDs the Asset would export now. Markers come from the Decisions, so a rename fails before anything is run
    again. A room's Masks and Layers come from the built export when there is one, and otherwise are taken as unchanged.
    A prop exports no Marker, Layer or Mask ID to freeze. A character's clip animations come from its `clip` Decisions."""
    markers: set[str] = set()
    for spec in graph.kind.stages:
        if spec.markers is not None:
            markers.update(str(marker["id"]) for marker in spec.markers(graph.replay(spec.name).current)
                           if marker["type"] in EXPORTED_MARKER_TYPES)
    layers, masks, looks, loops = manifest.ids.layers, manifest.ids.masks, manifest.ids.looks, manifest.ids.loops
    if graph.asset.kind == "room":
        # a Look's ID is its `pick`'s, so one taken away fails before anything is run again
        looks = sorted({str(d.data["look"]) for d in graph.replay(LOOKS_STAGE).current if d.name == "pick"})
        # a Loop's ID is its `loop` Decision's, and shares the namespace with the Looks'
        loops = sorted({str(d.data["loop"]) for d in graph.replay(LOOPS_STAGE).current if d.name == "loop"})
    spec = graph.spec(EXPORT_STAGE)
    if graph.asset.kind == "room" and graph.built_hash(spec) is not None:
        try:
            room = json.loads((graph.output_dir(spec) / ROOM_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            room = {}
        if room.get("schema_version") == ROOM_SCHEMA_VERSION:
            built = room_ids(room)
            layers, masks = built.layers, built.masks
    clips = manifest.ids.clips
    if graph.asset.kind == "character":
        # a clip's name is its ID, and its animations are the clip in each direction: from the Decisions, so that a clip
        # taken away fails before anything is run again
        clips = sorted(animation_name(str(d.data["name"]), direction)
                       for d in graph.replay("clips").current if d.name == CLIP.name for direction in DIRECTIONS)
    if graph.asset.kind == "sprite":
        clips = _sprite_animations(graph, clips)
    return ExportedIds(markers=sorted(markers), layers=layers, masks=masks, clips=clips, looks=looks, loops=loops)


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
    if asset.kind not in EXPORTERS or project.settings.export.godot.project is None:
        return []
    try:
        target = resolve_target(project)
    except KiripixError as error:
        return list(error.findings)
    shown = target.manifest(asset.id)
    manifest = read_manifest(target.path(shown), shown)
    if manifest is None or not manifest.exported:
        return []
    now = _current_ids(AssetGraph(project, asset, cache), manifest)
    where = ", ".join(sorted(res for res in manifest.files if res.endswith(".tscn"))) or shown
    found: list[Finding] = []
    for noun, was, is_now in (("Marker", manifest.ids.markers, now.markers), ("Layer", manifest.ids.layers, now.layers),
                              ("Mask", manifest.ids.masks, now.masks), ("Look", manifest.ids.looks, now.looks), ("Loop", manifest.ids.loops, now.loops),
                              ("clip animation", manifest.ids.clips, now.clips)):
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


def frozen_layer_findings(project: Project, asset: Asset, layers: list[str]) -> list[Finding]:
    """An error for each of `layers` that the game's Manifest lists as exported: a `remove` Decision on it is refused
    before it is recorded, as a rename would fail the freeze (spec §9). Nothing is frozen with no game or no Manifest."""
    if asset.kind not in EXPORTERS or project.settings.export.godot.project is None:
        return []
    try:
        target = resolve_target(project)
    except KiripixError as error:
        return list(error.findings)
    shown = target.manifest(asset.id)
    manifest = read_manifest(target.path(shown), shown)
    if manifest is None or not manifest.exported:
        return []
    where = ", ".join(sorted(res for res in manifest.files if res.endswith(".tscn"))) or shown
    return [Finding(
        code="export.id_frozen",
        message=f"{asset.id}: the Layer ID '{layer}' was exported in {where} (Manifest {shown}, export "
                f"{manifest.counter}), so it can't be removed",
        position=Position(asset=asset.id, stage="layers", file=shown),
        owner_action=f"Keep the Layer '{layer}': the game refers to it. Adding new Layers is always fine.")
        for layer in layers if layer in manifest.ids.layers]


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
                    message=f"{room} {exit_id} leads to {there} {back}, but {why}",
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
